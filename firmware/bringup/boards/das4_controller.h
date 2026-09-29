// Board header for das4-controller (RP2350B QFN-80, W25Q128JV 16 MB, 12 MHz XOSC)
#ifndef _BOARDS_DAS4_CONTROLLER_H
#define _BOARDS_DAS4_CONTROLLER_H

pico_board_cmake_set(PICO_PLATFORM, rp2350)

// QFN-80 package: 48 GPIO. Must be 0 for the B package.
#define PICO_RP2350A 0

// UART0 debug console on the TX/RX test pads (left tab): stdio goes here, so
// printf works even when USB doesn't enumerate. 115200 8N1, 3.3 V levels.
#define PICO_DEFAULT_UART 0
#define PICO_DEFAULT_UART_TX_PIN 0
#define PICO_DEFAULT_UART_RX_PIN 1
#define PICO_DEFAULT_LED_PIN_INVERTED 0

// W25Q128JV: same QSPI boot2 as the Pico 2 / PGA2350
#define PICO_BOOT_STAGE2_CHOOSE_W25Q080 1
#ifndef PICO_FLASH_SPI_CLKDIV
#define PICO_FLASH_SPI_CLKDIV 2
#endif
pico_board_cmake_set_default(PICO_FLASH_SIZE_BYTES, (16 * 1024 * 1024))
#ifndef PICO_FLASH_SIZE_BYTES
#define PICO_FLASH_SIZE_BYTES (16 * 1024 * 1024)
#endif

// 12 MHz ABM8-272-T3 is the SDK default XOSC frequency; stated for clarity.
#define XOSC_HZ 12000000u

// Board-specific pins
#define DAS4_LED_DATA_PIN 44
#define DAS4_BTN1_PIN     45
#define DAS4_ENC_A_PIN    13
#define DAS4_ENC_B_PIN    8

#endif
