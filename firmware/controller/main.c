#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "bsp/board_api.h"
#include "hardware/flash.h"
#include "hardware/gpio.h"
#include "hardware/sync.h"
#include "pico/bootrom.h"
#include "pico/stdlib.h"
#include "tusb.h"
#include "usb_descriptors.h"

#define PIN_COIN       2u
#define PIN_P1_START   3u
#define PIN_P1_TRIGGER 4u
#define PIN_P1_BOMB    5u
#define PIN_P2_START   6u
#define PIN_P2_TRIGGER 7u
#define PIN_P2_BOMB    8u
#define PIN_MANUAL_MACRO 9u
#define PIN_RELAY_2    26u
#define PIN_RELAY_1    27u

#define BTN_COUNT 8u
#define DEBOUNCE_MS 20u
#define STATUS_PERIOD_MS 100u
#define KEY_PULSE_MS_DEFAULT 90u
#define CALIBRATION_HOLD_MS 10000u
#define MAINTENANCE_TIMEOUT_MS 180000u
#define MAX_CREDITS 99u
#define RX_LINE_MAX 160u
#define MACRO_MAX_STEPS 32u
#define FIXED_MACRO_HOLD_MS 100u
#define FIXED_MACRO_WAIT_MS 300u

static const char FIXED_MACRO_SEQUENCE[] =
    "345455535455535455335555555544";
#define FIXED_MACRO_COUNT ((uint8_t)(sizeof(FIXED_MACRO_SEQUENCE) - 1u))

#define SETTINGS_MAGIC 0x54474334u
#define SETTINGS_VERSION 4u
#define SETTINGS_SECTOR_A (PICO_FLASH_SIZE_BYTES - (2u * FLASH_SECTOR_SIZE))
#define SETTINGS_SECTOR_B (PICO_FLASH_SIZE_BYTES - FLASH_SECTOR_SIZE)

enum {
    BTN_COIN = 0,
    BTN_P1_START,
    BTN_P1_TRIGGER,
    BTN_P1_BOMB,
    BTN_P2_START,
    BTN_P2_TRIGGER,
    BTN_P2_BOMB,
    BTN_MANUAL_MACRO,
};

typedef struct {
    bool stable;
    bool raw;
    bool previous;
    uint32_t changed_ms;
    uint32_t pressed_ms;
} button_state_t;

typedef struct {
    uint8_t keycode;
    uint32_t release_ms;
} pulse_key_t;

typedef struct {
    uint8_t keycode;
    uint16_t hold_ms;
    uint32_t wait_ms;
} macro_step_t;

typedef struct {
    uint32_t magic;
    uint16_t version;
    uint16_t size;
    uint32_t sequence;
    uint8_t relay_active_low;
    uint8_t macro_enabled;
    uint8_t macro_count;
    uint8_t reserved0;
    uint16_t inactivity_s;
    uint16_t key_pulse_ms;
    macro_step_t macro_steps[MACRO_MAX_STEPS];
    uint32_t checksum;
} controller_settings_t;

typedef enum {
    ACCESS_WAIT_MACRO = 0,
    ACCESS_WAIT_CREDIT = 1,
    ACCESS_READY = 2,
} access_state_t;

static const uint8_t INPUT_PINS[BTN_COUNT] = {
    PIN_COIN,
    PIN_P1_START,
    PIN_P1_TRIGGER,
    PIN_P1_BOMB,
    PIN_P2_START,
    PIN_P2_TRIGGER,
    PIN_P2_BOMB,
    PIN_MANUAL_MACRO,
};

static button_state_t buttons[BTN_COUNT];
static pulse_key_t pulse_keys[6];
static controller_settings_t settings;

static uint8_t credits = 0u;
static access_state_t access_state = ACCESS_WAIT_MACRO;
static bool gameplay_armed = false;
static bool relay_awake = false;
static uint32_t last_activity_ms = 0u;
static bool calibration_chord_latched = false;
static bool start_pair_seen = false;
static bool coin_long_latched = false;
static bool maintenance_mode = false;
static bool calibration_request = false;
static uint32_t maintenance_deadline_ms = 0u;

static bool macro_running = false;
static uint8_t macro_index = 0u;
static uint8_t macro_keycode = 0u;
static uint32_t macro_key_release_ms = 0u;
static uint32_t macro_next_step_ms = 0u;

static uint32_t next_status_ms = 0u;
static char rx_line[RX_LINE_MAX];
static size_t rx_len = 0u;

static inline bool deadline_reached(uint32_t now, uint32_t deadline) {
    return (int32_t)(now - deadline) >= 0;
}

static inline bool elapsed_ms(uint32_t now, uint32_t since, uint32_t duration) {
    return (uint32_t)(now - since) >= duration;
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

static uint32_t settings_checksum(const controller_settings_t *value) {
    return checksum_bytes(value, offsetof(controller_settings_t, checksum));
}

static bool settings_valid(const controller_settings_t *value) {
    return value->magic == SETTINGS_MAGIC &&
           value->version == SETTINGS_VERSION &&
           value->size == sizeof(controller_settings_t) &&
           value->macro_count <= MACRO_MAX_STEPS &&
           value->checksum == settings_checksum(value);
}

static void settings_defaults(void) {
    memset(&settings, 0, sizeof(settings));
    settings.magic = SETTINGS_MAGIC;
    settings.version = SETTINGS_VERSION;
    settings.size = (uint16_t)sizeof(settings);
    settings.sequence = 1u;
    settings.relay_active_low = 0u;
    settings.macro_enabled = 1u;
    settings.macro_count = FIXED_MACRO_COUNT;
    settings.inactivity_s = 120u;
    settings.key_pulse_ms = KEY_PULSE_MS_DEFAULT;
    settings.checksum = settings_checksum(&settings);
}

static void settings_load(void) {
    const controller_settings_t *a =
        (const controller_settings_t *)(XIP_BASE + SETTINGS_SECTOR_A);
    const controller_settings_t *b =
        (const controller_settings_t *)(XIP_BASE + SETTINGS_SECTOR_B);
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
    enum { PROGRAM_BYTES = ((sizeof(controller_settings_t) + FLASH_PAGE_SIZE - 1u) / FLASH_PAGE_SIZE) * FLASH_PAGE_SIZE };
    uint8_t buffer[PROGRAM_BYTES];
    memset(buffer, 0xFF, sizeof(buffer));
    memcpy(buffer, &settings, sizeof(settings));

    const uint32_t interrupt_state = save_and_disable_interrupts();
    flash_range_erase(offset, FLASH_SECTOR_SIZE);
    flash_range_program(offset, buffer, sizeof(buffer));
    restore_interrupts(interrupt_state);

    const controller_settings_t *written =
        (const controller_settings_t *)(XIP_BASE + offset);
    return settings_valid(written) && written->sequence == settings.sequence;
}

static bool settings_save(void) {
    const controller_settings_t *a =
        (const controller_settings_t *)(XIP_BASE + SETTINGS_SECTOR_A);
    const controller_settings_t *b =
        (const controller_settings_t *)(XIP_BASE + SETTINGS_SECTOR_B);
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

static void set_relay(uint8_t pin, bool active) {
    const bool output_high = settings.relay_active_low ? !active : active;
    gpio_put(pin, output_high ? 1u : 0u);
}

static void all_relays_off(void) {
    set_relay(PIN_RELAY_1, false);
    set_relay(PIN_RELAY_2, false);
}

static bool all_gameplay_buttons_released(void) {
    for (size_t index = BTN_P1_START; index <= BTN_P2_BOMB; ++index) {
        if (buttons[index].stable) {
            return false;
        }
    }
    return true;
}

static void update_gameplay_arming(void) {
    if (access_state != ACCESS_READY) {
        gameplay_armed = false;
        return;
    }
    if (!gameplay_armed && all_gameplay_buttons_released()) {
        gameplay_armed = true;
        cdc_write_line("EVENT BUTTONS ARMED");
    }
}

static bool gameplay_outputs_enabled(void) {
    return access_state == ACCESS_READY &&
           gameplay_armed &&
           !maintenance_mode &&
           !macro_running;
}

static uint8_t fixed_macro_keycode(char token) {
    if (token == '3') {
        return HID_KEY_3;
    }
    if (token == '4') {
        return HID_KEY_4;
    }
    if (token == '5') {
        return HID_KEY_5;
    }
    return 0u;
}

static void register_activity(uint32_t now_ms) {
    if (relay_awake) {
        last_activity_ms = now_ms;
    }
}

static void wake_relays_from_coin(uint32_t now_ms) {
    relay_awake = true;
    last_activity_ms = now_ms;
    cdc_write_line("EVENT RELAY AWAKE");
}

static void pulse_key(uint8_t keycode, uint32_t now_ms) {
    for (size_t index = 0u; index < 6u; ++index) {
        if (pulse_keys[index].keycode == 0u ||
            deadline_reached(now_ms, pulse_keys[index].release_ms)) {
            pulse_keys[index].keycode = keycode;
            pulse_keys[index].release_ms = now_ms + settings.key_pulse_ms;
            return;
        }
    }
}

static void macro_clear_runtime(void) {
    macro_running = false;
    macro_index = 0u;
    macro_keycode = 0u;
    macro_key_release_ms = 0u;
    macro_next_step_ms = 0u;
}

static void macro_stop(const char *message) {
    const bool was_running = macro_running;
    macro_clear_runtime();

    if (was_running) {
        access_state = ACCESS_WAIT_MACRO;
        gameplay_armed = false;
        credits = 0u;
        relay_awake = false;
        all_relays_off();
    }

    if (message != NULL) {
        cdc_write_line(message);
    }
}

static void macro_start(uint32_t now_ms, const char *source) {
    if (maintenance_mode) {
        cdc_write_line("ERR MACRO MAINTENANCE");
        return;
    }
    if (macro_running) {
        cdc_write_line("ERR MACRO ALREADY RUNNING");
        return;
    }

    access_state = ACCESS_WAIT_MACRO;
    gameplay_armed = false;
    credits = 0u;
    relay_awake = false;
    memset(pulse_keys, 0, sizeof(pulse_keys));
    all_relays_off();

    macro_running = true;
    macro_index = 0u;
    macro_keycode = 0u;
    macro_next_step_ms = now_ms;

    char line[96];
    snprintf(
        line,
        sizeof(line),
        "EVENT MACRO START SOURCE=%s",
        source != NULL ? source : "UNKNOWN"
    );
    cdc_write_line(line);
}

static void macro_complete(void) {
    macro_clear_runtime();
    access_state = ACCESS_WAIT_CREDIT;
    gameplay_armed = false;
    credits = 0u;
    relay_awake = false;
    all_relays_off();
    cdc_write_line("EVENT MACRO DONE");
    cdc_write_line("EVENT BUTTONS WAIT_CREDIT");
}

static void macro_task(uint32_t now_ms) {
    if (!macro_running) {
        return;
    }

    if (macro_keycode != 0u && deadline_reached(now_ms, macro_key_release_ms)) {
        macro_keycode = 0u;
    }

    if (!deadline_reached(now_ms, macro_next_step_ms)) {
        return;
    }

    if (macro_index >= FIXED_MACRO_COUNT) {
        macro_complete();
        return;
    }

    const char token = FIXED_MACRO_SEQUENCE[macro_index];
    macro_keycode = fixed_macro_keycode(token);
    macro_key_release_ms = now_ms + FIXED_MACRO_HOLD_MS;
    macro_next_step_ms =
        now_ms + FIXED_MACRO_HOLD_MS + FIXED_MACRO_WAIT_MS;
    ++macro_index;

    char line[112];
    snprintf(
        line,
        sizeof(line),
        "EVENT MACRO STEP=%u TOTAL=%u TOKEN=%c",
        (unsigned)macro_index,
        (unsigned)FIXED_MACRO_COUNT,
        token
    );
    cdc_write_line(line);
}

static void maintenance_enter(uint32_t now_ms) {
    maintenance_mode = true;
    calibration_request = true;
    maintenance_deadline_ms = now_ms + MAINTENANCE_TIMEOUT_MS;
    macro_stop(NULL);
    all_relays_off();
    cdc_write_line("EVENT CALIBRATION MENU");
}

static void maintenance_exit(void) {
    maintenance_mode = false;
    calibration_request = false;
    all_relays_off();
    cdc_write_line("EVENT MAINTENANCE END");
}

static void update_maintenance_timeout(uint32_t now_ms) {
    if (maintenance_mode && deadline_reached(now_ms, maintenance_deadline_ms)) {
        maintenance_exit();
        cdc_write_line("EVENT MAINTENANCE TIMEOUT");
    }
}

static void update_relay_idle(uint32_t now_ms) {
    const uint32_t timeout_ms = (uint32_t)settings.inactivity_s * 1000u;
    if (relay_awake && timeout_ms > 0u &&
        elapsed_ms(now_ms, last_activity_ms, timeout_ms)) {
        relay_awake = false;
        all_relays_off();
        cdc_write_line("EVENT RELAY SLEEP");
    }
}

static void handle_button_events(uint32_t now_ms) {
    const bool gameplay_enabled = gameplay_outputs_enabled();
    const bool both_start =
        gameplay_enabled &&
        buttons[BTN_P1_START].stable &&
        buttons[BTN_P2_START].stable;

    if (both_start) {
        start_pair_seen = true;
    }

    if (both_start && !calibration_chord_latched &&
        elapsed_ms(now_ms, buttons[BTN_P1_START].pressed_ms, CALIBRATION_HOLD_MS) &&
        elapsed_ms(now_ms, buttons[BTN_P2_START].pressed_ms, CALIBRATION_HOLD_MS)) {
        calibration_chord_latched = true;
        maintenance_enter(now_ms);
    }

    if (!both_start) {
        calibration_chord_latched = false;
    }

    if (buttons[BTN_MANUAL_MACRO].stable &&
        !buttons[BTN_MANUAL_MACRO].previous) {
        macro_start(now_ms, "GP9");
    }

    if (buttons[BTN_COIN].stable && !coin_long_latched &&
        elapsed_ms(now_ms, buttons[BTN_COIN].pressed_ms, CALIBRATION_HOLD_MS)) {
        coin_long_latched = true;
        macro_start(now_ms, "GP2_LONG");
    }

    if (!buttons[BTN_COIN].stable && buttons[BTN_COIN].previous) {
        if (!coin_long_latched && !maintenance_mode) {
            if (access_state == ACCESS_WAIT_MACRO || macro_running) {
                cdc_write_line("EVENT COIN BLOCKED WAIT_MACRO");
            } else {
                if (credits < MAX_CREDITS) {
                    ++credits;
                }
                pulse_key(HID_KEY_1, now_ms);
                wake_relays_from_coin(now_ms);

                if (access_state == ACCESS_WAIT_CREDIT) {
                    access_state = ACCESS_READY;
                    gameplay_armed = false;
                    cdc_write_line("EVENT BUTTONS UNLOCKED");
                }
            }
        }
        coin_long_latched = false;
    }

    if (!buttons[BTN_P1_START].stable && buttons[BTN_P1_START].previous) {
        if (gameplay_enabled && !start_pair_seen && credits > 0u) {
            --credits;
            pulse_key(HID_KEY_2, now_ms);
        }
    }

    if (!buttons[BTN_P2_START].stable && buttons[BTN_P2_START].previous) {
        if (gameplay_enabled && !start_pair_seen && credits > 0u) {
            --credits;
            pulse_key(HID_KEY_5, now_ms);
        }
    }

    if (!buttons[BTN_P1_BOMB].stable && buttons[BTN_P1_BOMB].previous &&
        gameplay_enabled) {
        pulse_key(HID_KEY_4, now_ms);
    }

    if (!buttons[BTN_P2_BOMB].stable && buttons[BTN_P2_BOMB].previous &&
        gameplay_enabled) {
        pulse_key(HID_KEY_7, now_ms);
    }

    if (!buttons[BTN_P1_START].stable && !buttons[BTN_P2_START].stable) {
        start_pair_seen = false;
    }
}

static void scan_buttons(uint32_t now_ms) {
    for (size_t index = 0u; index < BTN_COUNT; ++index) {
        const bool raw_pressed = !gpio_get(INPUT_PINS[index]);
        if (raw_pressed != buttons[index].raw) {
            buttons[index].raw = raw_pressed;
            buttons[index].changed_ms = now_ms;
        }

        if (raw_pressed != buttons[index].stable &&
            elapsed_ms(now_ms, buttons[index].changed_ms, DEBOUNCE_MS)) {
            buttons[index].stable = raw_pressed;
            if (raw_pressed) {
                buttons[index].pressed_ms = now_ms;
                register_activity(now_ms);
            }
        }
    }

    update_gameplay_arming();
    handle_button_events(now_ms);
    update_gameplay_arming();
    update_maintenance_timeout(now_ms);
    update_relay_idle(now_ms);

    const bool relay1_active =
        gameplay_outputs_enabled() &&
        relay_awake &&
        buttons[BTN_P1_TRIGGER].stable;
    const bool relay2_active =
        gameplay_outputs_enabled() &&
        relay_awake &&
        buttons[BTN_P2_TRIGGER].stable;
    set_relay(PIN_RELAY_1, relay1_active);
    set_relay(PIN_RELAY_2, relay2_active);

    for (size_t index = 0u; index < BTN_COUNT; ++index) {
        buttons[index].previous = buttons[index].stable;
    }
}

static bool append_key(uint8_t *report, size_t *count, uint8_t keycode) {
    if (keycode == 0u || *count >= 6u) {
        return false;
    }
    for (size_t index = 0u; index < *count; ++index) {
        if (report[index] == keycode) {
            return false;
        }
    }
    report[*count] = keycode;
    ++(*count);
    return true;
}

static void keyboard_task(uint32_t now_ms) {
    if (!tud_mounted() || !tud_hid_ready()) {
        return;
    }

    uint8_t report[6] = {0u};
    size_t count = 0u;
    const bool access_open =
        access_state == ACCESS_READY &&
        !maintenance_mode &&
        !macro_running;

    for (size_t index = 0u; index < 6u; ++index) {
        if (pulse_keys[index].keycode != 0u &&
            deadline_reached(now_ms, pulse_keys[index].release_ms)) {
            pulse_keys[index].keycode = 0u;
        }
        if (access_open) {
            (void)append_key(report, &count, pulse_keys[index].keycode);
        }
    }

    if (gameplay_outputs_enabled()) {
        if (buttons[BTN_P1_TRIGGER].stable) {
            (void)append_key(report, &count, HID_KEY_3);
        }
        if (buttons[BTN_P2_TRIGGER].stable) {
            (void)append_key(report, &count, HID_KEY_6);
        }
    }

    if (!maintenance_mode) {
        (void)append_key(report, &count, macro_keycode);
    }

    (void)tud_hid_keyboard_report(REPORT_ID_KEYBOARD, 0u, report);
}

static void send_status(void) {
    char line[384];
    snprintf(
        line,
        sizeof(line),
        "STATUS C=%u S1=%u T1=%u B1=%u S2=%u T2=%u B2=%u M9=%u "
        "R1=%u R2=%u CREDIT=%u CALREQ=%u MAINT=%u MACRO=%u "
        "MACROSTEP=%u MACROTOTAL=%u RELAYAWAKE=%u RELAYLOW=%u IDLE=%u "
        "GATE=%u BUTTONS=%u ARMED=%u",
        buttons[BTN_COIN].stable ? 1u : 0u,
        buttons[BTN_P1_START].stable ? 1u : 0u,
        buttons[BTN_P1_TRIGGER].stable ? 1u : 0u,
        buttons[BTN_P1_BOMB].stable ? 1u : 0u,
        buttons[BTN_P2_START].stable ? 1u : 0u,
        buttons[BTN_P2_TRIGGER].stable ? 1u : 0u,
        buttons[BTN_P2_BOMB].stable ? 1u : 0u,
        buttons[BTN_MANUAL_MACRO].stable ? 1u : 0u,
        (gameplay_outputs_enabled() &&
         relay_awake &&
         buttons[BTN_P1_TRIGGER].stable) ? 1u : 0u,
        (gameplay_outputs_enabled() &&
         relay_awake &&
         buttons[BTN_P2_TRIGGER].stable) ? 1u : 0u,
        credits,
        calibration_request ? 1u : 0u,
        maintenance_mode ? 1u : 0u,
        macro_running ? 1u : 0u,
        (unsigned)macro_index,
        (unsigned)FIXED_MACRO_COUNT,
        relay_awake ? 1u : 0u,
        settings.relay_active_low ? 1u : 0u,
        (unsigned)settings.inactivity_s,
        (unsigned)access_state,
        gameplay_outputs_enabled() ? 1u : 0u,
        gameplay_armed ? 1u : 0u
    );
    cdc_write_line(line);
}

static void send_config(void) {
    char line[160];
    snprintf(
        line,
        sizeof(line),
        "CONFIG RELAYLOW=%u IDLE=%u KEYPULSE=%u MACROEN=1 MACROCOUNT=%u MACROFIX=1",
        settings.relay_active_low ? 1u : 0u,
        (unsigned)settings.inactivity_s,
        (unsigned)settings.key_pulse_ms,
        (unsigned)FIXED_MACRO_COUNT
    );
    cdc_write_line(line);
}

static void process_command(const char *command, uint32_t now_ms) {
    unsigned a = 0u;

    if (strcmp(command, "PING") == 0) {
        cdc_write_line("PONG TG_CONTROLLER_PRO V4.4.0");
    } else if (strcmp(command, "INFO") == 0) {
        cdc_write_line("INFO NAME=TG_CONTROLLER VERSION=4.4.0 BOARD=RP2040 MACRO=FIXED_NUMBERS GP9=MANUAL");
    } else if (strcmp(command, "STATUS") == 0) {
        send_status();
    } else if (strcmp(command, "CONFIG") == 0) {
        send_config();
    } else if (strcmp(command, "MAINT START") == 0) {
        maintenance_enter(now_ms);
    } else if (strcmp(command, "MAINT KEEP") == 0) {
        if (maintenance_mode) {
            maintenance_deadline_ms = now_ms + MAINTENANCE_TIMEOUT_MS;
            cdc_write_line("OK MAINT KEEP");
        } else {
            cdc_write_line("ERR MAINT NOT ACTIVE");
        }
    } else if (strcmp(command, "MAINT END") == 0) {
        maintenance_exit();
    } else if (strcmp(command, "CAL ACK") == 0) {
        calibration_request = false;
        cdc_write_line("OK CAL ACK");
    } else if (strcmp(command, "CREDIT CLEAR") == 0) {
        credits = 0u;
        cdc_write_line("OK CREDIT CLEAR");
    } else if (strcmp(command, "RELAY WAKE") == 0) {
        wake_relays_from_coin(now_ms);
    } else if (strcmp(command, "RELAY SLEEP") == 0) {
        relay_awake = false;
        all_relays_off();
        cdc_write_line("OK RELAY SLEEP");
    } else if (sscanf(command, "SET RELAY_ACTIVE_LOW %u", &a) == 1) {
        settings.relay_active_low = a ? 1u : 0u;
        all_relays_off();
        cdc_write_line("OK SET RELAY_ACTIVE_LOW");
    } else if (sscanf(command, "SET INACTIVITY_S %u", &a) == 1 && a <= 3600u) {
        settings.inactivity_s = (uint16_t)a;
        cdc_write_line("OK SET INACTIVITY_S");
    } else if (sscanf(command, "SET KEY_PULSE_MS %u", &a) == 1 && a >= 20u && a <= 500u) {
        settings.key_pulse_ms = (uint16_t)a;
        cdc_write_line("OK SET KEY_PULSE_MS");
    } else if (strcmp(command, "MACRO CLEAR") == 0 ||
               strncmp(command, "MACRO ADD ", 10u) == 0 ||
               strncmp(command, "MACRO ENABLE ", 13u) == 0) {
        cdc_write_line("ERR MACRO FIXED");
    } else if (strcmp(command, "MACRO START") == 0 || strcmp(command, "MAKRO") == 0) {
        macro_start(now_ms, "PC");
    } else if (strcmp(command, "MACRO STOP") == 0) {
        macro_stop("EVENT MACRO STOPPED");
    } else if (strcmp(command, "SAVE") == 0) {
        cdc_write_line(settings_save() ? "OK SAVE" : "ERR SAVE");
    } else if (strcmp(command, "DEFAULTS") == 0) {
        settings_defaults();
        all_relays_off();
        cdc_write_line("OK DEFAULTS");
    } else if (strcmp(command, "BOOTSEL") == 0) {
        all_relays_off();
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

static void init_hardware(void) {
    const uint32_t now_ms = to_ms_since_boot(get_absolute_time());
    for (size_t index = 0u; index < BTN_COUNT; ++index) {
        gpio_init(INPUT_PINS[index]);
        gpio_set_dir(INPUT_PINS[index], GPIO_IN);
        gpio_pull_up(INPUT_PINS[index]);
        const bool pressed = !gpio_get(INPUT_PINS[index]);
        buttons[index].stable = pressed;
        buttons[index].raw = pressed;
        buttons[index].previous = pressed;
        buttons[index].changed_ms = now_ms;
        buttons[index].pressed_ms = pressed ? now_ms : 0u;
    }

    gpio_init(PIN_RELAY_1);
    gpio_set_dir(PIN_RELAY_1, GPIO_OUT);
    gpio_init(PIN_RELAY_2);
    gpio_set_dir(PIN_RELAY_2, GPIO_OUT);
    all_relays_off();
    last_activity_ms = now_ms;
}

void tud_umount_cb(void) {
    all_relays_off();
}

void tud_suspend_cb(bool remote_wakeup_en) {
    (void)remote_wakeup_en;
    all_relays_off();
}

int main(void) {
    board_init();
    settings_load();
    init_hardware();
    tusb_init();

    while (true) {
        tud_task();
        const uint32_t now_ms = to_ms_since_boot(get_absolute_time());
        scan_buttons(now_ms);
        macro_task(now_ms);
        keyboard_task(now_ms);
        cdc_task(now_ms);

        if (deadline_reached(now_ms, next_status_ms)) {
            next_status_ms = now_ms + STATUS_PERIOD_MS;
            send_status();
        }
        sleep_ms(1u);
    }
}
