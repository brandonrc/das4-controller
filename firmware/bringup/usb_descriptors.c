#include "tusb.h"
static const tusb_desc_device_t dev = {
    .bLength = sizeof(tusb_desc_device_t), .bDescriptorType = TUSB_DESC_DEVICE, .bcdUSB = 0x0200,
    .bDeviceClass = 0, .bDeviceSubClass = 0, .bDeviceProtocol = 0, .bMaxPacketSize0 = CFG_TUD_ENDPOINT0_SIZE,
    .idVendor = 0xCafe, .idProduct = 0x4D44, .bcdDevice = 0x0100,
    .iManufacturer = 1, .iProduct = 2, .iSerialNumber = 3, .bNumConfigurations = 1 };
uint8_t const *tud_descriptor_device_cb(void) { return (uint8_t const *)&dev; }
static const uint8_t hid_report[] = { TUD_HID_REPORT_DESC_KEYBOARD() };
uint8_t const *tud_hid_descriptor_report_cb(uint8_t i) { return hid_report; }
#define CFG_LEN (TUD_CONFIG_DESC_LEN + TUD_HID_DESC_LEN)
static const uint8_t cfg[] = {
    TUD_CONFIG_DESCRIPTOR(1, 1, 0, CFG_LEN, TUSB_DESC_CONFIG_ATT_REMOTE_WAKEUP, 100),
    TUD_HID_DESCRIPTOR(0, 0, HID_ITF_PROTOCOL_KEYBOARD, sizeof(hid_report), 0x81, 8, 1) };
uint8_t const *tud_descriptor_configuration_cb(uint8_t i) { return cfg; }
static const char *str[] = { (const char[]){0x09, 0x04}, "das4", "das4-controller", "0001" };
static uint16_t buf[32];
uint16_t const *tud_descriptor_string_cb(uint8_t idx, uint16_t langid) {
    uint8_t n;
    if (idx == 0) { buf[1] = 0x0409; n = 1; }
    else { if (idx >= 4) return NULL; const char *s = str[idx]; n = strlen(s); if (n > 31) n = 31;
           for (uint8_t i = 0; i < n; i++) buf[1 + i] = s[i]; }
    buf[0] = (TUSB_DESC_STRING << 8) | (2 * n + 2);
    return buf;
}
