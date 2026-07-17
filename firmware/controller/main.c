#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "bsp/board_api.h"
#include "hardware/gpio.h"
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
#define PIN_RELAY_2    26u
#define PIN_RELAY_1    27u

#define RELAY_ACTIVE_HIGH 1
#define DEBOUNCE_MS 20u
#define STATUS_PERIOD_MS 500u
#define RELAY_TEST_PULSE_MS 250u
#define RX_LINE_MAX 96u

static const uint8_t input_pins[] = {
    PIN_COIN, PIN_P1_START, PIN_P1_TRIGGER, PIN_P1_BOMB,
    PIN_P2_START, PIN_P2_TRIGGER, PIN_P2_BOMB
};

static const uint8_t hid_keys[] = {
    HID_KEY_1, HID_KEY_2, HID_KEY_3, HID_KEY_4,
    HID_KEY_5, HID_KEY_6, HID_KEY_7
};

typedef struct {
    bool stable_pressed;
    bool last_raw_pressed;
    uint32_t changed_at_ms;
} button_state_t;

static button_state_t buttons[sizeof(input_pins) / sizeof(input_pins[0])];
static bool keyboard_dirty = true;
static uint32_t next_status_ms = 0;
static uint32_t relay_test_until_ms[2] = {0u, 0u};
static char rx_line[RX_LINE_MAX];
static size_t rx_len = 0u;

static inline bool elapsed_ms(uint32_t now, uint32_t since, uint32_t duration) {
    return (uint32_t)(now - since) >= duration;
}

static inline bool deadline_reached(uint32_t now, uint32_t deadline) {
    return (int32_t)(now - deadline) >= 0;
}

static void set_relay(uint8_t pin, bool active) {
#if RELAY_ACTIVE_HIGH
    gpio_put(pin, active ? 1 : 0);
#else
    gpio_put(pin, active ? 0 : 1);
#endif
}

static void cdc_write_line(const char *text) {
    if (!tud_cdc_connected()) {
        return;
    }
    tud_cdc_write_str(text);
    tud_cdc_write_str("\r\n");
    tud_cdc_write_flush();
}

static void init_hardware(void) {
    uint32_t now = to_ms_since_boot(get_absolute_time());

    for (size_t i = 0; i < (sizeof(input_pins) / sizeof(input_pins[0])); ++i) {
        gpio_init(input_pins[i]);
        gpio_set_dir(input_pins[i], GPIO_IN);
        gpio_pull_up(input_pins[i]);

        bool pressed = !gpio_get(input_pins[i]);
        buttons[i].stable_pressed = pressed;
        buttons[i].last_raw_pressed = pressed;
        buttons[i].changed_at_ms = now;
    }

    gpio_init(PIN_RELAY_1);
    gpio_set_dir(PIN_RELAY_1, GPIO_OUT);
    gpio_init(PIN_RELAY_2);
    gpio_set_dir(PIN_RELAY_2, GPIO_OUT);
    set_relay(PIN_RELAY_1, false);
    set_relay(PIN_RELAY_2, false);
}

static void scan_buttons(uint32_t now_ms) {
    for (size_t i = 0; i < (sizeof(input_pins) / sizeof(input_pins[0])); ++i) {
        bool raw_pressed = !gpio_get(input_pins[i]);

        if (raw_pressed != buttons[i].last_raw_pressed) {
            buttons[i].last_raw_pressed = raw_pressed;
            buttons[i].changed_at_ms = now_ms;
        }

        if (raw_pressed != buttons[i].stable_pressed &&
            elapsed_ms(now_ms, buttons[i].changed_at_ms, DEBOUNCE_MS)) {
            buttons[i].stable_pressed = raw_pressed;
            keyboard_dirty = true;
        }
    }

    bool relay1_test = !deadline_reached(now_ms, relay_test_until_ms[0]);
    bool relay2_test = !deadline_reached(now_ms, relay_test_until_ms[1]);

    set_relay(PIN_RELAY_1, buttons[2].stable_pressed || relay1_test);
    set_relay(PIN_RELAY_2, buttons[5].stable_pressed || relay2_test);
}

static void send_keyboard_report(void) {
    if (!keyboard_dirty || !tud_mounted() || !tud_hid_ready()) {
        return;
    }

    uint8_t keycodes[6] = {0};
    size_t out = 0;

    for (size_t i = 0; i < (sizeof(buttons) / sizeof(buttons[0])) && out < 6; ++i) {
        if (buttons[i].stable_pressed) {
            keycodes[out++] = hid_keys[i];
        }
    }

    if (tud_hid_keyboard_report(REPORT_ID_KEYBOARD, 0, keycodes)) {
        keyboard_dirty = false;
    }
}

static void send_status(void) {
    char line[160];
    snprintf(
        line, sizeof(line),
        "STATUS C=%u S1=%u T1=%u B1=%u S2=%u T2=%u B2=%u R1=%u R2=%u",
        buttons[0].stable_pressed ? 1u : 0u,
        buttons[1].stable_pressed ? 1u : 0u,
        buttons[2].stable_pressed ? 1u : 0u,
        buttons[3].stable_pressed ? 1u : 0u,
        buttons[4].stable_pressed ? 1u : 0u,
        buttons[5].stable_pressed ? 1u : 0u,
        buttons[6].stable_pressed ? 1u : 0u,
        gpio_get(PIN_RELAY_1) ? 1u : 0u,
        gpio_get(PIN_RELAY_2) ? 1u : 0u
    );
    cdc_write_line(line);
}

static void process_command(const char *command, uint32_t now_ms) {
    if (strcmp(command, "PING") == 0) {
        cdc_write_line("PONG TG_CONTROLLER V005");
    } else if (strcmp(command, "INFO") == 0) {
        cdc_write_line("INFO NAME=TG_CONTROLLER VERSION=0.5.0 BOARD=RP2040");
    } else if (strcmp(command, "STATUS") == 0) {
        send_status();
    } else if (strcmp(command, "RELAY 1 PULSE") == 0) {
        relay_test_until_ms[0] = now_ms + RELAY_TEST_PULSE_MS;
        cdc_write_line("OK RELAY 1 PULSE");
    } else if (strcmp(command, "RELAY 2 PULSE") == 0) {
        relay_test_until_ms[1] = now_ms + RELAY_TEST_PULSE_MS;
        cdc_write_line("OK RELAY 2 PULSE");
    } else {
        cdc_write_line("ERR UNKNOWN COMMAND");
    }
}

static void cdc_rx_task(uint32_t now_ms) {
    while (tud_cdc_available()) {
        char ch = (char)tud_cdc_read_char();

        if (ch == '\r' || ch == '\n') {
            if (rx_len > 0u) {
                rx_line[rx_len] = '\0';
                process_command(rx_line, now_ms);
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

static void cdc_status_task(uint32_t now_ms) {
    if (!tud_cdc_connected() || !deadline_reached(now_ms, next_status_ms)) {
        return;
    }

    next_status_ms = now_ms + STATUS_PERIOD_MS;
    send_status();
}

int main(void) {
    board_init();
    init_hardware();
    tusb_init();

    while (true) {
        tud_task();

        uint32_t now_ms = to_ms_since_boot(get_absolute_time());
        scan_buttons(now_ms);
        send_keyboard_report();
        cdc_rx_task(now_ms);
        cdc_status_task(now_ms);

        sleep_ms(1);
    }
}
