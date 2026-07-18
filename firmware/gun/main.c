#include <math.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "bsp/board_api.h"
#include "hardware/adc.h"
#include "hardware/flash.h"
#include "hardware/gpio.h"
#include "hardware/sync.h"
#include "pico/bootrom.h"
#include "pico/stdlib.h"
#include "tusb.h"
#include "usb_descriptors.h"

#ifndef TG_PLAYER_ID
#error "TG_PLAYER_ID must be 1 or 2"
#endif

#if (TG_PLAYER_ID != 1) && (TG_PLAYER_ID != 2)
#error "TG_PLAYER_ID must be 1 or 2"
#endif

#define X_ADC_GPIO 26u
#define Y_ADC_GPIO 27u
#define X_ADC_INPUT 0u
#define Y_ADC_INPUT 1u
#define GP19_ENABLE_PIN 19u

#define STATUS_PERIOD_MS 50u
#define HID_PERIOD_MS 4u
#define SOFTWARE_OFF_LEASE_MS 5000u
#define CALIBRATION_TIMEOUT_MS 120000u
#define CALIBRATION_SAMPLES 32u
#define CALIBRATION_MAX_SPREAD 120u
#define RX_LINE_MAX 128u

#define SETTINGS_MAGIC 0x54474734u
#define SETTINGS_VERSION 4u
#define SETTINGS_SECTOR_A (PICO_FLASH_SIZE_BYTES - (2u * FLASH_SECTOR_SIZE))
#define SETTINGS_SECTOR_B (PICO_FLASH_SIZE_BYTES - FLASH_SECTOR_SIZE)

typedef struct {
    float x;
    float y;
} point_f_t;

typedef struct {
    uint32_t magic;
    uint16_t version;
    uint16_t size;
    uint32_t sequence;
    uint16_t corner_x[4];
    uint16_t corner_y[4];
    uint8_t smoothing;
    uint8_t calibrated;
    uint8_t quality;
    uint8_t reserved0;
    uint32_t checksum;
} gun_settings_t;

typedef struct __attribute__((packed)) {
    uint8_t buttons;
    int16_t x;
    int16_t y;
} absolute_mouse_report_t;

static gun_settings_t settings;
static uint16_t pending_x[4];
static uint16_t pending_y[4];
static uint8_t pending_index = 0u;
static bool calibrating = false;
static uint32_t calibration_deadline_ms = 0u;

static float filtered_x = 2048.0f;
static float filtered_y = 2048.0f;
static bool filter_initialized = false;

static uint32_t software_off_until_ms = 0u;
static uint32_t next_status_ms = 0u;
static uint32_t next_hid_ms = 0u;
static char rx_line[RX_LINE_MAX];
static size_t rx_len = 0u;

static inline bool deadline_reached(uint32_t now, uint32_t deadline) {
    return (int32_t)(now - deadline) >= 0;
}

static float clamp_float(float value, float minimum, float maximum) {
    if (value < minimum) {
        return minimum;
    }
    if (value > maximum) {
        return maximum;
    }
    return value;
}

static float point_distance(point_f_t a, point_f_t b) {
    const float dx = b.x - a.x;
    const float dy = b.y - a.y;
    return sqrtf(dx * dx + dy * dy);
}

static float cross(point_f_t a, point_f_t b, point_f_t c) {
    return (b.x - a.x) * (c.y - a.y) -
           (b.y - a.y) * (c.x - a.x);
}

static bool segments_intersect(point_f_t a, point_f_t b, point_f_t c, point_f_t d) {
    const float ab_c = cross(a, b, c);
    const float ab_d = cross(a, b, d);
    const float cd_a = cross(c, d, a);
    const float cd_b = cross(c, d, b);
    return (ab_c * ab_d < 0.0f) && (cd_a * cd_b < 0.0f);
}

static uint32_t checksum_bytes(const void *data, size_t size) {
    const uint8_t *bytes = (const uint8_t *)data;
    uint32_t value = 2166136261u;
    for (size_t index = 0u; index < size; ++index) {
        value ^= bytes[index];
        value *= 16777619u;
    }
    return value;
}

static uint32_t settings_checksum(const gun_settings_t *value) {
    return checksum_bytes(value, offsetof(gun_settings_t, checksum));
}

static bool settings_valid(const gun_settings_t *value) {
    return value->magic == SETTINGS_MAGIC &&
           value->version == SETTINGS_VERSION &&
           value->size == sizeof(gun_settings_t) &&
           value->smoothing <= 10u &&
           value->checksum == settings_checksum(value);
}

static void settings_defaults(void) {
    memset(&settings, 0, sizeof(settings));
    settings.magic = SETTINGS_MAGIC;
    settings.version = SETTINGS_VERSION;
    settings.size = (uint16_t)sizeof(settings);
    settings.sequence = 1u;
    settings.corner_x[0] = 0u;
    settings.corner_y[0] = 0u;
    settings.corner_x[1] = 4095u;
    settings.corner_y[1] = 0u;
    settings.corner_x[2] = 4095u;
    settings.corner_y[2] = 4095u;
    settings.corner_x[3] = 0u;
    settings.corner_y[3] = 4095u;
    settings.smoothing = 4u;
    settings.calibrated = 0u;
    settings.quality = 0u;
    settings.checksum = settings_checksum(&settings);
}

static void settings_load(void) {
    const gun_settings_t *a =
        (const gun_settings_t *)(XIP_BASE + SETTINGS_SECTOR_A);
    const gun_settings_t *b =
        (const gun_settings_t *)(XIP_BASE + SETTINGS_SECTOR_B);
    const bool valid_a = settings_valid(a);
    const bool valid_b = settings_valid(b);

    if (valid_a && valid_b) {
        memcpy(&settings, a->sequence >= b->sequence ? a : b, sizeof(settings));
    } else if (valid_a) {
        memcpy(&settings, a, sizeof(settings));
    } else if (valid_b) {
        memcpy(&settings, b, sizeof(settings));
    } else {
        settings_defaults();
    }
}

static bool settings_program_sector(uint32_t offset) {
    enum { PROGRAM_BYTES = ((sizeof(gun_settings_t) + FLASH_PAGE_SIZE - 1u) / FLASH_PAGE_SIZE) * FLASH_PAGE_SIZE };
    uint8_t buffer[PROGRAM_BYTES];
    memset(buffer, 0xFF, sizeof(buffer));
    memcpy(buffer, &settings, sizeof(settings));

    const uint32_t interrupt_state = save_and_disable_interrupts();
    flash_range_erase(offset, FLASH_SECTOR_SIZE);
    flash_range_program(offset, buffer, sizeof(buffer));
    restore_interrupts(interrupt_state);

    const gun_settings_t *written = (const gun_settings_t *)(XIP_BASE + offset);
    return settings_valid(written) && written->sequence == settings.sequence;
}

static bool settings_save(void) {
    const gun_settings_t *a =
        (const gun_settings_t *)(XIP_BASE + SETTINGS_SECTOR_A);
    const gun_settings_t *b =
        (const gun_settings_t *)(XIP_BASE + SETTINGS_SECTOR_B);
    const bool valid_a = settings_valid(a);
    const bool valid_b = settings_valid(b);

    uint32_t target = SETTINGS_SECTOR_A;
    uint32_t newest_sequence = 0u;
    if (valid_a) {
        newest_sequence = a->sequence;
        target = SETTINGS_SECTOR_B;
    }
    if (valid_b && (!valid_a || b->sequence >= newest_sequence)) {
        newest_sequence = b->sequence;
        target = SETTINGS_SECTOR_A;
    }

    settings.sequence = newest_sequence + 1u;
    settings.magic = SETTINGS_MAGIC;
    settings.version = SETTINGS_VERSION;
    settings.size = (uint16_t)sizeof(settings);
    settings.checksum = settings_checksum(&settings);
    return settings_program_sector(target);
}

static void cdc_write_line(const char *text) {
    if (!tud_mounted()) {
        return;
    }
    tud_cdc_write(text, (uint32_t)strlen(text));
    tud_cdc_write("\r\n", 2u);
    tud_cdc_write_flush();
}

static uint16_t read_adc_channel(uint input) {
    adc_select_input(input);
    sleep_us(5u);
    return adc_read();
}

static void read_raw(uint16_t *x, uint16_t *y) {
    *x = read_adc_channel(X_ADC_INPUT);
    *y = read_adc_channel(Y_ADC_INPUT);
}

static bool read_average(
    uint16_t *x,
    uint16_t *y,
    uint16_t *spread_x,
    uint16_t *spread_y
) {
    uint32_t sum_x = 0u;
    uint32_t sum_y = 0u;
    uint16_t samples_x[CALIBRATION_SAMPLES];
    uint16_t samples_y[CALIBRATION_SAMPLES];

    for (size_t index = 0u; index < CALIBRATION_SAMPLES; ++index) {
        read_raw(&samples_x[index], &samples_y[index]);
        sum_x += samples_x[index];
        sum_y += samples_y[index];
        sleep_us(400u);
    }

    uint16_t minimum_x = samples_x[0];
    uint16_t maximum_x = samples_x[0];
    uint16_t minimum_y = samples_y[0];
    uint16_t maximum_y = samples_y[0];
    for (size_t index = 1u; index < CALIBRATION_SAMPLES; ++index) {
        if (samples_x[index] < minimum_x) minimum_x = samples_x[index];
        if (samples_x[index] > maximum_x) maximum_x = samples_x[index];
        if (samples_y[index] < minimum_y) minimum_y = samples_y[index];
        if (samples_y[index] > maximum_y) maximum_y = samples_y[index];
    }

    const uint32_t trimmed_x = sum_x - minimum_x - maximum_x;
    const uint32_t trimmed_y = sum_y - minimum_y - maximum_y;
    *x = (uint16_t)(trimmed_x / (CALIBRATION_SAMPLES - 2u));
    *y = (uint16_t)(trimmed_y / (CALIBRATION_SAMPLES - 2u));
    *spread_x = (uint16_t)(maximum_x - minimum_x);
    *spread_y = (uint16_t)(maximum_y - minimum_y);
    return *spread_x <= CALIBRATION_MAX_SPREAD &&
           *spread_y <= CALIBRATION_MAX_SPREAD;
}

static bool gp19_active(void) {
    return gpio_get(GP19_ENABLE_PIN) == 0u;
}

static bool software_motion_active(uint32_t now_ms) {
    return deadline_reached(now_ms, software_off_until_ms);
}

static bool effective_motion_active(uint32_t now_ms) {
    return gp19_active() && software_motion_active(now_ms) && !calibrating;
}

static void adaptive_filter(uint16_t raw_x, uint16_t raw_y, float *out_x, float *out_y) {
    if (!filter_initialized) {
        filtered_x = (float)raw_x;
        filtered_y = (float)raw_y;
        filter_initialized = true;
    }

    const float dx = (float)raw_x - filtered_x;
    const float dy = (float)raw_y - filtered_y;
    const float speed = sqrtf(dx * dx + dy * dy);
    const float strength = (float)settings.smoothing / 10.0f;
    float slow_alpha = 1.0f - strength * 0.90f;
    if (slow_alpha < 0.08f) {
        slow_alpha = 0.08f;
    }
    const float speed_mix = clamp_float(speed / 350.0f, 0.0f, 1.0f);
    const float alpha = slow_alpha + (1.0f - slow_alpha) * speed_mix;
    filtered_x += dx * alpha;
    filtered_y += dy * alpha;
    *out_x = filtered_x;
    *out_y = filtered_y;
}

static bool calibration_geometry_valid(
    const uint16_t *x,
    const uint16_t *y,
    uint8_t *quality,
    const char **reason
) {
    point_f_t p[4];
    for (size_t index = 0u; index < 4u; ++index) {
        p[index].x = (float)x[index];
        p[index].y = (float)y[index];
    }

    const float top = point_distance(p[0], p[1]);
    const float right = point_distance(p[1], p[2]);
    const float bottom = point_distance(p[2], p[3]);
    const float left = point_distance(p[3], p[0]);
    float minimum_edge = top;
    float maximum_edge = top;
    const float edges[4] = {top, right, bottom, left};
    for (size_t index = 1u; index < 4u; ++index) {
        if (edges[index] < minimum_edge) minimum_edge = edges[index];
        if (edges[index] > maximum_edge) maximum_edge = edges[index];
    }

    if (minimum_edge < 350.0f) {
        *reason = "EDGE_TOO_SMALL";
        return false;
    }

    if (segments_intersect(p[0], p[1], p[2], p[3]) ||
        segments_intersect(p[1], p[2], p[3], p[0])) {
        *reason = "CORNERS_CROSSED";
        return false;
    }

    const float area_twice = fabsf(
        p[0].x * p[1].y - p[1].x * p[0].y +
        p[1].x * p[2].y - p[2].x * p[1].y +
        p[2].x * p[3].y - p[3].x * p[2].y +
        p[3].x * p[0].y - p[0].x * p[3].y
    );
    if (area_twice < 300000.0f) {
        *reason = "AREA_TOO_SMALL";
        return false;
    }

    const float edge_score = clamp_float(minimum_edge / maximum_edge, 0.0f, 1.0f);
    const float area_score = clamp_float(area_twice / 12000000.0f, 0.0f, 1.0f);
    const float combined = 100.0f * (0.65f * edge_score + 0.35f * area_score);
    *quality = (uint8_t)clamp_float(combined, 1.0f, 100.0f);
    *reason = "OK";
    return true;
}

static bool bilinear_inverse(float raw_x, float raw_y, float *u, float *v) {
    const point_f_t p00 = {(float)settings.corner_x[0], (float)settings.corner_y[0]};
    const point_f_t p10 = {(float)settings.corner_x[1], (float)settings.corner_y[1]};
    const point_f_t p11 = {(float)settings.corner_x[2], (float)settings.corner_y[2]};
    const point_f_t p01 = {(float)settings.corner_x[3], (float)settings.corner_y[3]};

    const point_f_t b = {p10.x - p00.x, p10.y - p00.y};
    const point_f_t c = {p01.x - p00.x, p01.y - p00.y};
    const point_f_t d = {
        p00.x - p10.x - p01.x + p11.x,
        p00.y - p10.y - p01.y + p11.y
    };
    const point_f_t target = {raw_x - p00.x, raw_y - p00.y};

    const float affine_det = b.x * c.y - b.y * c.x;
    if (fabsf(affine_det) < 0.001f) {
        return false;
    }

    float current_u = (target.x * c.y - target.y * c.x) / affine_det;
    float current_v = (b.x * target.y - b.y * target.x) / affine_det;

    for (size_t iteration = 0u; iteration < 8u; ++iteration) {
        const float fx = p00.x + b.x * current_u + c.x * current_v +
                         d.x * current_u * current_v - raw_x;
        const float fy = p00.y + b.y * current_u + c.y * current_v +
                         d.y * current_u * current_v - raw_y;
        const float j00 = b.x + d.x * current_v;
        const float j01 = c.x + d.x * current_u;
        const float j10 = b.y + d.y * current_v;
        const float j11 = c.y + d.y * current_u;
        const float determinant = j00 * j11 - j01 * j10;
        if (fabsf(determinant) < 0.001f) {
            break;
        }
        const float delta_u = (fx * j11 - fy * j01) / determinant;
        const float delta_v = (j00 * fy - j10 * fx) / determinant;
        current_u -= delta_u;
        current_v -= delta_v;
        if (fabsf(delta_u) + fabsf(delta_v) < 0.0001f) {
            break;
        }
    }

    *u = clamp_float(current_u, 0.0f, 1.0f);
    *v = clamp_float(current_v, 0.0f, 1.0f);
    return true;
}

static void map_raw(float raw_x, float raw_y, int16_t *mapped_x, int16_t *mapped_y) {
    float u = raw_x / 4095.0f;
    float v = raw_y / 4095.0f;
    if (settings.calibrated) {
        (void)bilinear_inverse(raw_x, raw_y, &u, &v);
    }
    *mapped_x = (int16_t)((int32_t)(clamp_float(u, 0.0f, 1.0f) * 65534.0f) - 32767);
    *mapped_y = (int16_t)((int32_t)(clamp_float(v, 0.0f, 1.0f) * 65534.0f) - 32767);
}

static void send_info(void) {
    char line[128];
    snprintf(
        line,
        sizeof(line),
        "INFO NAME=TG_GUN_P%u VERSION=4.0.0 BOARD=RP2040",
        (unsigned)TG_PLAYER_ID
    );
    cdc_write_line(line);
}

static void send_config(void) {
    char line[128];
    snprintf(
        line,
        sizeof(line),
        "CONFIG SMOOTH=%u CAL=%u QUALITY=%u",
        (unsigned)settings.smoothing,
        settings.calibrated ? 1u : 0u,
        (unsigned)settings.quality
    );
    cdc_write_line(line);
}

static void send_status(uint32_t now_ms, uint16_t raw_x, uint16_t raw_y) {
    float filtered_raw_x;
    float filtered_raw_y;
    int16_t mapped_x;
    int16_t mapped_y;
    adaptive_filter(raw_x, raw_y, &filtered_raw_x, &filtered_raw_y);
    map_raw(filtered_raw_x, filtered_raw_y, &mapped_x, &mapped_y);

    const float horizontal_dx =
        ((float)settings.corner_x[1] + settings.corner_x[2]) -
        ((float)settings.corner_x[0] + settings.corner_x[3]);
    const float horizontal_dy =
        ((float)settings.corner_y[1] + settings.corner_y[2]) -
        ((float)settings.corner_y[0] + settings.corner_y[3]);
    const float vertical_dx =
        ((float)settings.corner_x[2] + settings.corner_x[3]) -
        ((float)settings.corner_x[0] + settings.corner_x[1]);
    const float vertical_dy =
        ((float)settings.corner_y[2] + settings.corner_y[3]) -
        ((float)settings.corner_y[0] + settings.corner_y[1]);
    const bool swap = fabsf(horizontal_dy) > fabsf(horizontal_dx);
    const bool invert_x = swap ? horizontal_dy < 0.0f : horizontal_dx < 0.0f;
    const bool invert_y = swap ? vertical_dx < 0.0f : vertical_dy < 0.0f;

    char line[280];
    snprintf(
        line,
        sizeof(line),
        "GUNSTATUS ID=P%u X=%u Y=%u MX=%d MY=%d GP19=%u MOTION=%u "
        "CAL=%u QUALITY=%u SMOOTH=%u CALIBRATING=%u SWAP=%u INVX=%u INVY=%u",
        (unsigned)TG_PLAYER_ID,
        (unsigned)raw_x,
        (unsigned)raw_y,
        (int)mapped_x,
        (int)mapped_y,
        gp19_active() ? 1u : 0u,
        effective_motion_active(now_ms) ? 1u : 0u,
        settings.calibrated ? 1u : 0u,
        (unsigned)settings.quality,
        (unsigned)settings.smoothing,
        calibrating ? 1u : 0u,
        swap ? 1u : 0u,
        invert_x ? 1u : 0u,
        invert_y ? 1u : 0u
    );
    cdc_write_line(line);
}

static void calibration_start(uint32_t now_ms) {
    calibrating = true;
    pending_index = 0u;
    calibration_deadline_ms = now_ms + CALIBRATION_TIMEOUT_MS;
    filter_initialized = false;
    cdc_write_line("EVENT CALREADY INDEX=0 POINT=TL");
}

static void calibration_cancel(const char *event_text) {
    calibrating = false;
    pending_index = 0u;
    filter_initialized = false;
    cdc_write_line(event_text);
}

static void calibration_capture(uint32_t now_ms) {
    if (!calibrating || pending_index >= 4u) {
        cdc_write_line("ERR CAL NOT ACTIVE");
        return;
    }

    uint16_t x;
    uint16_t y;
    uint16_t spread_x;
    uint16_t spread_y;
    const bool stable = read_average(&x, &y, &spread_x, &spread_y);

    char line[128];
    if (!stable) {
        snprintf(
            line,
            sizeof(line),
            "EVENT CALUNSTABLE INDEX=%u SPREADX=%u SPREADY=%u",
            (unsigned)pending_index,
            (unsigned)spread_x,
            (unsigned)spread_y
        );
        cdc_write_line(line);
        calibration_deadline_ms = now_ms + CALIBRATION_TIMEOUT_MS;
        return;
    }

    pending_x[pending_index] = x;
    pending_y[pending_index] = y;

    snprintf(
        line,
        sizeof(line),
        "EVENT CALPOINT INDEX=%u X=%u Y=%u",
        (unsigned)pending_index,
        (unsigned)x,
        (unsigned)y
    );
    cdc_write_line(line);
    ++pending_index;
    calibration_deadline_ms = now_ms + CALIBRATION_TIMEOUT_MS;

    if (pending_index < 4u) {
        static const char *POINTS[4] = {"TL", "TR", "BR", "BL"};
        snprintf(
            line,
            sizeof(line),
            "EVENT CALREADY INDEX=%u POINT=%s",
            (unsigned)pending_index,
            POINTS[pending_index]
        );
        cdc_write_line(line);
        return;
    }

    uint8_t quality = 0u;
    const char *reason = "UNKNOWN";
    if (!calibration_geometry_valid(pending_x, pending_y, &quality, &reason)) {
        snprintf(line, sizeof(line), "EVENT CALERROR REASON=%s", reason);
        calibration_cancel(line);
        return;
    }

    const gun_settings_t previous_settings = settings;
    for (size_t index = 0u; index < 4u; ++index) {
        settings.corner_x[index] = pending_x[index];
        settings.corner_y[index] = pending_y[index];
    }
    settings.calibrated = 1u;
    settings.quality = quality;
    if (!settings_save()) {
        settings = previous_settings;
        calibration_cancel("EVENT CALERROR REASON=FLASH_SAVE_FAILED");
        return;
    }

    calibrating = false;
    pending_index = 0u;
    filter_initialized = false;
    snprintf(
        line,
        sizeof(line),
        "EVENT CALDONE VALID=1 QUALITY=%u",
        (unsigned)quality
    );
    cdc_write_line(line);
}

static void update_calibration_timeout(uint32_t now_ms) {
    if (calibrating && deadline_reached(now_ms, calibration_deadline_ms)) {
        calibration_cancel("EVENT CALERROR REASON=TIMEOUT");
    }
}

static void process_command(const char *command, uint32_t now_ms) {
    unsigned value = 0u;
    if (strcmp(command, "PING") == 0) {
        char line[64];
        snprintf(
            line,
            sizeof(line),
            "PONG TG_GUN_P%u PRO_V4.0.0",
            (unsigned)TG_PLAYER_ID
        );
        cdc_write_line(line);
    } else if (strcmp(command, "INFO") == 0) {
        send_info();
    } else if (strcmp(command, "STATUS") == 0) {
        uint16_t x;
        uint16_t y;
        read_raw(&x, &y);
        send_status(now_ms, x, y);
    } else if (strcmp(command, "CONFIG") == 0 || strcmp(command, "CAL GET") == 0) {
        send_config();
    } else if (strcmp(command, "MOTION ON") == 0) {
        software_off_until_ms = now_ms;
        cdc_write_line("OK MOTION ON");
    } else if (strcmp(command, "MOTION OFF") == 0) {
        software_off_until_ms = now_ms + SOFTWARE_OFF_LEASE_MS;
        cdc_write_line("OK MOTION OFF");
    } else if (strcmp(command, "CAL START") == 0) {
        calibration_start(now_ms);
    } else if (strcmp(command, "CAL CAPTURE") == 0) {
        calibration_capture(now_ms);
    } else if (strcmp(command, "CAL CANCEL") == 0) {
        calibration_cancel("EVENT CALCANCELLED");
    } else if (strcmp(command, "CAL RESET") == 0 || strcmp(command, "RESET CAL") == 0) {
        settings.calibrated = 0u;
        settings.quality = 0u;
        settings_save();
        filter_initialized = false;
        cdc_write_line("EVENT CALRESET");
    } else if (sscanf(command, "SET SMOOTH %u", &value) == 1 && value <= 10u) {
        settings.smoothing = (uint8_t)value;
        filter_initialized = false;
        cdc_write_line("OK SET SMOOTH");
    } else if (sscanf(command, "SMOOTH %u", &value) == 1 && value <= 10u) {
        settings.smoothing = (uint8_t)value;
        filter_initialized = false;
        cdc_write_line("OK SMOOTH");
    } else if (strcmp(command, "SAVE") == 0) {
        cdc_write_line(settings_save() ? "OK SAVE" : "ERR SAVE");
    } else if (strcmp(command, "BOOTSEL") == 0) {
        cdc_write_line("OK BOOTSEL");
        sleep_ms(100u);
        reset_usb_boot(0u, 0u);
    } else {
        cdc_write_line("ERR UNKNOWN COMMAND");
    }
}

static void cdc_task(uint32_t now_ms) {
    while (tud_cdc_available()) {
        const char ch = (char)tud_cdc_read_char();
        if (ch == '\r' || ch == '\n') {
            if (rx_len > 0u) {
                rx_line[rx_len] = '\0';
                process_command(rx_line, now_ms);
                rx_len = 0u;
            }
        } else if (rx_len < RX_LINE_MAX - 1u) {
            rx_line[rx_len++] = ch;
        } else {
            rx_len = 0u;
            cdc_write_line("ERR LINE TOO LONG");
        }
    }
}

static void hid_task(uint32_t now_ms, uint16_t raw_x, uint16_t raw_y) {
    if (!effective_motion_active(now_ms) ||
        !deadline_reached(now_ms, next_hid_ms) ||
        !tud_mounted() || !tud_hid_ready()) {
        return;
    }
    next_hid_ms = now_ms + HID_PERIOD_MS;

    float filtered_raw_x;
    float filtered_raw_y;
    int16_t mapped_x;
    int16_t mapped_y;
    adaptive_filter(raw_x, raw_y, &filtered_raw_x, &filtered_raw_y);
    map_raw(filtered_raw_x, filtered_raw_y, &mapped_x, &mapped_y);
    const absolute_mouse_report_t report = {
        .buttons = 0u,
        .x = mapped_x,
        .y = mapped_y,
    };
    (void)tud_hid_report(REPORT_ID_MOUSE, &report, sizeof(report));
}

int main(void) {
    board_init();
    adc_init();
    adc_gpio_init(X_ADC_GPIO);
    adc_gpio_init(Y_ADC_GPIO);
    gpio_init(GP19_ENABLE_PIN);
    gpio_set_dir(GP19_ENABLE_PIN, GPIO_IN);
    gpio_pull_up(GP19_ENABLE_PIN);
    settings_load();
    tusb_init();

    while (true) {
        tud_task();
        const uint32_t now_ms = to_ms_since_boot(get_absolute_time());
        cdc_task(now_ms);
        update_calibration_timeout(now_ms);

        uint16_t x;
        uint16_t y;
        read_raw(&x, &y);
        hid_task(now_ms, x, y);

        if (deadline_reached(now_ms, next_status_ms)) {
            next_status_ms = now_ms + STATUS_PERIOD_MS;
            send_status(now_ms, x, y);
        }
        sleep_ms(1u);
    }
}
