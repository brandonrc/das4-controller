#include "pico.h"
_Static_assert(NUM_BANK0_GPIOS == 48, "B package");
_Static_assert(PICO_FLASH_SIZE_BYTES == 16*1024*1024, "16MB");
// Minimal bring-up firmware for das4-controller (RP2350B).
// - USB HID keyboard via TinyUSB (enumerates behind the CH334R hub)
// - Key matrix: 26 lines GPIO14..39 (J4 pad k -> GPIO 40-k); demo scans
//   col lines as outputs-low, row lines as inputs with pull-UP (E9-safe).
// - SW1 on GPIO45 (ADC pin used as digital input, pull-up)
// - 3x WS2812D on GPIO44 through an inverting 2N7002 -> pad output inverted.
#include "pico/stdlib.h"
#include "hardware/pio.h"
#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "hardware/platform_defs.h"
#include "tusb.h"
#include "ws2812.pio.h"

#define N_LEDS 3
#define MATRIX_FIRST 14
#define MATRIX_LAST  39
// Placeholder split until the key PCB is mapped: 8 "rows" (inputs) + 18 "cols".
#define N_ROWS 8
static const uint row_pins[N_ROWS] = {39, 38, 37, 36, 35, 34, 33, 32};
#define N_COLS 18
static const uint col_pins[N_COLS] = {31,30,29,28,27,26,25,24,23,22,21,20,19,18,17,16,15,14};
static bool keys[N_ROWS][N_COLS];

static PIO led_pio; static uint led_sm; static uint led_off;

static void ws2812_init(void) {
    // GPIO44 >= 32: PIO must be given a GPIO base of 16 (covers 16..47).
    bool ok = pio_claim_free_sm_and_add_program_for_gpio_range(
        &ws2812_program, &led_pio, &led_sm, &led_off, DAS4_LED_DATA_PIN, 1, true);
    hard_assert(ok);
    pio_sm_config c = ws2812_program_get_default_config(led_off);
    sm_config_set_sideset_pins(&c, DAS4_LED_DATA_PIN);
    sm_config_set_out_shift(&c, false, true, 24);
    sm_config_set_fifo_join(&c, PIO_FIFO_JOIN_TX);
    int cycles = ws2812_T1 + ws2812_T2 + ws2812_T3;
    sm_config_set_clkdiv(&c, clock_get_hz(clk_sys) / (800000.0f * cycles));
    pio_gpio_init(led_pio, DAS4_LED_DATA_PIN);
    pio_sm_set_consecutive_pindirs(led_pio, led_sm, DAS4_LED_DATA_PIN, 1, true);
    // The 2N7002 + 1k pull-up to 5 V inverts: invert at the pad so the PIO
    // program stays standard. Idle (PIO low) -> pad high -> FET on -> DIN low = reset.
    gpio_set_outover(DAS4_LED_DATA_PIN, GPIO_OVERRIDE_INVERT);
    pio_sm_init(led_pio, led_sm, led_off, &c);
    pio_sm_set_enabled(led_pio, led_sm, true);
}

static void ws2812_put(uint8_t r, uint8_t g, uint8_t b) {
    pio_sm_put_blocking(led_pio, led_sm, ((uint32_t)g << 24) | ((uint32_t)r << 16) | ((uint32_t)b << 8));
}

static void matrix_init(void) {
    for (uint i = 0; i < N_ROWS; i++) {
        gpio_init(row_pins[i]); gpio_set_dir(row_pins[i], GPIO_IN); gpio_pull_up(row_pins[i]);
    }
    for (uint i = 0; i < N_COLS; i++) {
        // Unselected columns are hi-Z (input, pull-up) so no ghost paths drive.
        gpio_init(col_pins[i]); gpio_set_dir(col_pins[i], GPIO_IN); gpio_pull_up(col_pins[i]);
        gpio_put(col_pins[i], 0);
    }
}

static void matrix_scan(void) {
    for (uint c = 0; c < N_COLS; c++) {
        gpio_set_dir(col_pins[c], GPIO_OUT);           // drive low
        busy_wait_us_32(5);
        uint64_t all = gpio_get_all64();               // GPIO0..47
        for (uint r = 0; r < N_ROWS; r++) keys[r][c] = !((all >> row_pins[r]) & 1);
        gpio_set_dir(col_pins[c], GPIO_IN);            // release (pull-up)
    }
}

static void hid_task(bool sw1) {
    static bool last_any = false;
    if (!tud_hid_ready()) return;
    uint8_t kc[6] = {0}; uint n = 0;
    if (sw1) kc[n++] = HID_KEY_A;
    for (uint r = 0; r < N_ROWS && n < 6; r++)
        for (uint c = 0; c < N_COLS && n < 6; c++)
            if (keys[r][c]) kc[n++] = HID_KEY_B;
    bool any = n > 0;
    if (any || last_any) tud_hid_keyboard_report(0, 0, any ? kc : NULL);
    last_any = any;
}

int main(void) {
    tusb_init();
    matrix_init();
    gpio_init(DAS4_BTN1_PIN); gpio_set_dir(DAS4_BTN1_PIN, GPIO_IN); gpio_pull_up(DAS4_BTN1_PIN);
    gpio_init(DAS4_ENC_A_PIN); gpio_pull_up(DAS4_ENC_A_PIN);
    gpio_init(DAS4_ENC_B_PIN); gpio_pull_up(DAS4_ENC_B_PIN);
    ws2812_init();
    uint32_t t = 0;
    while (true) {
        tud_task();
        matrix_scan();
        bool sw1 = !gpio_get(DAS4_BTN1_PIN);
        hid_task(sw1);
        if (to_ms_since_boot(get_absolute_time()) - t > 50) {
            t = to_ms_since_boot(get_absolute_time());
            for (int i = 0; i < N_LEDS; i++) ws2812_put(sw1 ? 64 : 0, sw1 ? 0 : 16, 0);
        }
    }
}

// TinyUSB callbacks
uint16_t tud_hid_get_report_cb(uint8_t i, uint8_t id, hid_report_type_t t, uint8_t *b, uint16_t l) { return 0; }
void tud_hid_set_report_cb(uint8_t i, uint8_t id, hid_report_type_t t, uint8_t const *b, uint16_t l) {
    // Lock-LED report from host (NUM/CAPS/SCROLL) arrives here.
}
