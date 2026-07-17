#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "bsp/board_api.h"
#include "hardware/adc.h"
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

#define ADC_MIN 0u
#define ADC_MAX 4095u
#define HID_MIN (-32767)
#define HID_MAX 32767

#define STATUS_PERIOD_MS 50u
#define HID_PERIOD_MS 4u
#define RX_LINE_MAX 96u

static uint32_t next_status_ms = 0u;
static uint32_t next_hid_ms = 0u;
static char rx_line[RX_LINE_MAX];
static size_t rx_len = 0u;
static bool motion_enabled = true;

static inline bool deadline_reached(uint32_t now, uint32_t deadline) {
    return (int32_t)(now - deadline) >= 0;
}

static int16_t map_adc_to_hid(uint16_t value) {
    int32_t scaled = ((int32_t)value - (int32_t)ADC_MIN) * (HID_MAX - HID_MIN);
    scaled /= (ADC_MAX - ADC_MIN);
    scaled += HID_MIN;

    if (scaled < HID_MIN) {
        scaled = HID_MIN;
    } else if (scaled > HID_MAX) {
        scaled = HID_MAX;
    }
    return (int16_t)scaled;
}

static void cdc_write_line(const char *text) {
    if (!tud_cdc_connected()) {
        return;
    }

    tud_cdc_write_str(text);
    tud_cdc_write_str("\r\n");
    tud_cdc_write_flush();
}

static void adc_init_inputs(void) {
    adc_init();
    adc_gpio_init(X_ADC_GPIO);
    adc_gpio_init(Y_ADC_GPIO);
}

static uint16_t read_adc_channel(uint input) {
    adc_select_input(input);
    sleep_us(5);
    return adc_read();
}

static void send_info(void) {
    char line[112];
    snprintf(
        line,
        sizeof(line),
        "INFO NAME=TG_GUN_P%u VERSION=0.5.0 BOARD=RP2040",
        (unsigned)TG_PLAYER_ID
    );
    cdc_write_line(line);
}

static void send_status(uint16_t x_raw, uint16_t y_raw) {
    char line[128];
    snprintf(
        line,
        sizeof(line),
        "GUNSTATUS ID=P%u X=%u Y=%u MOTION=%u",
        (unsigned)TG_PLAYER_ID,
        (unsigned)x_raw,
        (unsigned)y_raw,
        motion_enabled ? 1u : 0u
    );
    cdc_write_line(line);
}

static void process_command(const char *command) {
    if (strcmp(command, "PING") == 0) {
        char line[64];
        snprintf(line, sizeof(line), "PONG TG_GUN_P%u V005", (unsigned)TG_PLAYER_ID);
        cdc_write_line(line);
    } else if (strcmp(command, "INFO") == 0) {
        send_info();
    } else if (strcmp(command, "MOTION ON") == 0) {
        motion_enabled = true;
        cdc_write_line("OK MOTION ON");
    } else if (strcmp(command, "MOTION OFF") == 0) {
        motion_enabled = false;
        cdc_write_line("OK MOTION OFF");
    } else if (strcmp(command, "STATUS") == 0) {
        send_status(read_adc_channel(X_ADC_INPUT), read_adc_channel(Y_ADC_INPUT));
    } else {
        cdc_write_line("ERR UNKNOWN COMMAND");
    }
}

static void cdc_rx_task(void) {
    while (tud_cdc_available()) {
        char ch = (char)tud_cdc_read_char();

        if (ch == '\r' || ch == '\n') {
            if (rx_len > 0u) {
                rx_line[rx_len] = '\0';
                process_command(rx_line);
                rx_len = 0u;
            }
        } else if (rx_len < (RX_LINE_MAX - 1u)) {
            rx_line[rx_len++] = ch;
        } else {
            rx_len = 0u;
            cdc_write_line("ERR LINE TOO LONG");
        }
    }
}

typedef struct __attribute__((packed)) {
    uint8_t buttons;
    int16_t x;
    int16_t y;
} absolute_mouse_report_t;

static void hid_task(uint32_t now_ms, uint16_t x_raw, uint16_t y_raw) {
    if (!motion_enabled || !deadline_reached(now_ms, next_hid_ms)) {
        return;
    }

    next_hid_ms = now_ms + HID_PERIOD_MS;

    if (!tud_mounted() || !tud_hid_ready()) {
        return;
    }

    absolute_mouse_report_t report = {
        .buttons = 0u,
        .x = map_adc_to_hid(x_raw),
        .y = map_adc_to_hid(y_raw),
    };

    (void)tud_hid_report(REPORT_ID_MOUSE, &report, sizeof(report));
}

int main(void) {
    board_init();
    adc_init_inputs();
    tusb_init();

    while (true) {
        tud_task();
        cdc_rx_task();

        uint16_t x_raw = read_adc_channel(X_ADC_INPUT);
        uint16_t y_raw = read_adc_channel(Y_ADC_INPUT);
        uint32_t now_ms = to_ms_since_boot(get_absolute_time());

        hid_task(now_ms, x_raw, y_raw);

        if (deadline_reached(now_ms, next_status_ms)) {
            next_status_ms = now_ms + STATUS_PERIOD_MS;
            send_status(x_raw, y_raw);
        }

        sleep_ms(1);
    }
}
