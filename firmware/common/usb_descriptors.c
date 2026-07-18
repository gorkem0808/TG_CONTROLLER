#include <string.h>

#include "tusb.h"
#include "usb_descriptors.h"

enum {
    ITF_NUM_CDC = 0,
    ITF_NUM_CDC_DATA,
    ITF_NUM_HID,
    ITF_NUM_TOTAL
};

enum {
    EPNUM_CDC_NOTIF = 0x81,
    EPNUM_CDC_OUT = 0x02,
    EPNUM_CDC_IN = 0x82,
    EPNUM_HID_IN = 0x83
};

#define CONFIG_TOTAL_LEN (TUD_CONFIG_DESC_LEN + TUD_CDC_DESC_LEN + TUD_HID_DESC_LEN)

static const tusb_desc_device_t DEVICE_DESCRIPTOR = {
    .bLength = sizeof(tusb_desc_device_t),
    .bDescriptorType = TUSB_DESC_DEVICE,
    .bcdUSB = 0x0200,
    .bDeviceClass = TUSB_CLASS_MISC,
    .bDeviceSubClass = MISC_SUBCLASS_COMMON,
    .bDeviceProtocol = MISC_PROTOCOL_IAD,
    .bMaxPacketSize0 = CFG_TUD_ENDPOINT0_SIZE,
    .idVendor = 0xCAFE,
    .idProduct = 0x4010,
    .bcdDevice = 0x0400,
    .iManufacturer = 0x01,
    .iProduct = 0x02,
    .iSerialNumber = 0x03,
    .bNumConfigurations = 0x01,
};

static const uint8_t HID_REPORT_DESCRIPTOR[] = {
    TUD_HID_REPORT_DESC_KEYBOARD(HID_REPORT_ID(REPORT_ID_KEYBOARD))
};

static const uint8_t CONFIGURATION_DESCRIPTOR[] = {
    TUD_CONFIG_DESCRIPTOR(1, ITF_NUM_TOTAL, 0, CONFIG_TOTAL_LEN, 0x00, 100),
    TUD_CDC_DESCRIPTOR(
        ITF_NUM_CDC,
        4,
        EPNUM_CDC_NOTIF,
        8,
        EPNUM_CDC_OUT,
        EPNUM_CDC_IN,
        64
    ),
    TUD_HID_DESCRIPTOR(
        ITF_NUM_HID,
        5,
        HID_ITF_PROTOCOL_KEYBOARD,
        sizeof(HID_REPORT_DESCRIPTOR),
        EPNUM_HID_IN,
        16,
        5
    )
};

static const char *STRING_DESCRIPTORS[] = {
    (const char[]){0x09, 0x04},
    "TG Arcade",
    "TG CONTROLLER PRO V4",
    "TGCTRL-PRO-V4",
    "TG Controller CDC",
    "TG Controller Keyboard"
};

uint8_t const *tud_descriptor_device_cb(void) {
    return (const uint8_t *)&DEVICE_DESCRIPTOR;
}

uint8_t const *tud_hid_descriptor_report_cb(uint8_t instance) {
    (void)instance;
    return HID_REPORT_DESCRIPTOR;
}

uint8_t const *tud_descriptor_configuration_cb(uint8_t index) {
    (void)index;
    return CONFIGURATION_DESCRIPTOR;
}

uint16_t const *tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
    (void)langid;
    static uint16_t buffer[32];
    uint8_t count = 0u;

    if (index == 0u) {
        memcpy(&buffer[1], STRING_DESCRIPTORS[0], 2u);
        count = 1u;
    } else {
        if (index >= (sizeof(STRING_DESCRIPTORS) / sizeof(STRING_DESCRIPTORS[0]))) {
            return NULL;
        }
        const char *text = STRING_DESCRIPTORS[index];
        count = (uint8_t)strlen(text);
        if (count > 31u) {
            count = 31u;
        }
        for (uint8_t i = 0u; i < count; ++i) {
            buffer[1u + i] = (uint16_t)text[i];
        }
    }

    buffer[0] = (uint16_t)((TUSB_DESC_STRING << 8) | (2u * count + 2u));
    return buffer;
}

uint16_t tud_hid_get_report_cb(
    uint8_t instance,
    uint8_t report_id,
    hid_report_type_t report_type,
    uint8_t *buffer,
    uint16_t reqlen
) {
    (void)instance;
    (void)report_id;
    (void)report_type;
    (void)buffer;
    (void)reqlen;
    return 0u;
}

void tud_hid_set_report_cb(
    uint8_t instance,
    uint8_t report_id,
    hid_report_type_t report_type,
    uint8_t const *buffer,
    uint16_t bufsize
) {
    (void)instance;
    (void)report_id;
    (void)report_type;
    (void)buffer;
    (void)bufsize;
}
