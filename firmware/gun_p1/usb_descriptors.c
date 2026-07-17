#include <string.h>

#include "tusb.h"
#include "usb_descriptors.h"

#define USB_VID 0xCafe
#define USB_PID 0x4011
#define USB_BCD 0x0100

enum {
    ITF_NUM_CDC = 0,
    ITF_NUM_CDC_DATA,
    ITF_NUM_HID,
    ITF_NUM_TOTAL
};

#define EPNUM_CDC_NOTIF 0x81
#define EPNUM_CDC_OUT   0x02
#define EPNUM_CDC_IN    0x82
#define EPNUM_HID_IN    0x83

#define CONFIG_TOTAL_LEN (TUD_CONFIG_DESC_LEN + TUD_CDC_DESC_LEN + TUD_HID_DESC_LEN)

static const tusb_desc_device_t device_descriptor = {
    .bLength = sizeof(tusb_desc_device_t),
    .bDescriptorType = TUSB_DESC_DEVICE,
    .bcdUSB = 0x0200,
    .bDeviceClass = TUSB_CLASS_MISC,
    .bDeviceSubClass = MISC_SUBCLASS_COMMON,
    .bDeviceProtocol = MISC_PROTOCOL_IAD,
    .bMaxPacketSize0 = CFG_TUD_ENDPOINT0_SIZE,
    .idVendor = USB_VID,
    .idProduct = USB_PID,
    .bcdDevice = USB_BCD,
    .iManufacturer = 0x01,
    .iProduct = 0x02,
    .iSerialNumber = 0x03,
    .bNumConfigurations = 0x01
};

static const uint8_t hid_report_descriptor[] = {
    0x05, 0x01,
    0x09, 0x02,
    0xA1, 0x01,
    0x85, REPORT_ID_MOUSE,
    0x09, 0x01,
    0xA1, 0x00,
    0x05, 0x09,
    0x19, 0x01,
    0x29, 0x03,
    0x15, 0x00,
    0x25, 0x01,
    0x95, 0x03,
    0x75, 0x01,
    0x81, 0x02,
    0x95, 0x01,
    0x75, 0x05,
    0x81, 0x01,
    0x05, 0x01,
    0x09, 0x30,
    0x09, 0x31,
    0x16, 0x01, 0x80,
    0x26, 0xFF, 0x7F,
    0x75, 0x10,
    0x95, 0x02,
    0x81, 0x02,
    0xC0,
    0xC0
};

static const uint8_t configuration_descriptor[] = {
    TUD_CONFIG_DESCRIPTOR(1, ITF_NUM_TOTAL, 0, CONFIG_TOTAL_LEN, 0x00, 100),
    TUD_CDC_DESCRIPTOR(ITF_NUM_CDC, 4, EPNUM_CDC_NOTIF, 8, EPNUM_CDC_OUT, EPNUM_CDC_IN, 64),
    TUD_HID_DESCRIPTOR(ITF_NUM_HID, 5, HID_ITF_PROTOCOL_NONE,
                       sizeof(hid_report_descriptor), EPNUM_HID_IN, 16, 2)
};

static const char *string_descriptors[] = {
    (const char[]){0x09, 0x04},
    "TG Arcade",
    "TG GUN PLAYER 1",
    "TG-GUN-P1-V004",
    "TG GUN P1 CDC",
    "TG GUN P1 HID"
};

uint8_t const *tud_descriptor_device_cb(void) {
    return (uint8_t const *)&device_descriptor;
}

uint8_t const *tud_hid_descriptor_report_cb(uint8_t instance) {
    (void)instance;
    return hid_report_descriptor;
}

uint8_t const *tud_descriptor_configuration_cb(uint8_t index) {
    (void)index;
    return configuration_descriptor;
}

uint16_t const *tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
    (void)langid;
    static uint16_t buffer[32];
    uint8_t count;

    if (index == 0) {
        memcpy(&buffer[1], string_descriptors[0], 2);
        count = 1;
    } else {
        if (index >= (sizeof(string_descriptors) / sizeof(string_descriptors[0]))) {
            return NULL;
        }

        const char *str = string_descriptors[index];
        count = (uint8_t)strlen(str);
        if (count > 31) {
            count = 31;
        }

        for (uint8_t i = 0; i < count; ++i) {
            buffer[1 + i] = (uint16_t)str[i];
        }
    }

    buffer[0] = (uint16_t)((TUSB_DESC_STRING << 8) | (2 * count + 2));
    return buffer;
}

uint16_t tud_hid_get_report_cb(uint8_t instance, uint8_t report_id,
                               hid_report_type_t report_type,
                               uint8_t *buffer, uint16_t reqlen) {
    (void)instance;
    (void)report_id;
    (void)report_type;
    (void)buffer;
    (void)reqlen;
    return 0;
}

void tud_hid_set_report_cb(uint8_t instance, uint8_t report_id,
                           hid_report_type_t report_type,
                           uint8_t const *buffer, uint16_t bufsize) {
    (void)instance;
    (void)report_id;
    (void)report_type;
    (void)buffer;
    (void)bufsize;
}
