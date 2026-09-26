# das4-controller: firmware readiness check (2026-09-26)

## Verdict

**Yes, with caveats. No hardware change is required before ordering.**

- **pico-sdk + TinyUSB** supports every pin and feature on this board today. A test firmware using this exact pinout builds to a `.uf2` (see Build).
- **CircuitPython/KMK** also works, but it needs a small custom board definition and a custom inverted PIO LED driver.
- **QMK cannot target this board today.** It has no RP2350 support in master or develop. The only RP2350 port is an out-of-tree proof of concept, and it explicitly does not support RP2350B GPIO above 31. This board uses GPIO32–47 for 8 matrix lines, all 5 buttons and the LED.
- **No pin swap can fix the QMK problem.** The board needs 36 signals, but only 32 GPIO (0–31) exist below GPIO32.
- **One doc error to fix.** `docs/design.md` says to use QMK `WS2812_EXTERNAL_PULLUP` for the inverted LED line. That is wrong for this circuit (details in the table notes).

## Firmware options × requirements

| Requirement | pico-sdk 2.3.1 + TinyUSB | CircuitPython 10.3.1 + KMK | QMK (master/develop, 2026-09-26) | QMK POC branch `emolitor/em-rp2350` (2026-07-22) |
|---|---|---|---|---|
| RP2350B (QFN-80) | ✅ `PICO_RP2350A=0`. Stock example: `pimoroni_pga2350.h` (RP2350B + 16 MB) | ✅ `CHIP_PACKAGE = B`. Example: `adafruit_metro_rp2350` (RP2350B, W25Q128JV) | ❌ No RP2350 at all. Schema lists only `RP2040`. Issue #25881 was closed "not planned" pending ChibiOS | ⚠️ RP2350**A** pinout only |
| GPIO30–47 | ✅ `gpio_get_all64()`. PIO uses `GPIOBASE=16`, which the SDK handles automatically (`pio_claim_free_sm_and_add_program_for_gpio_range`) | ✅ `microcontroller.pin.GPIO32…47`. rp2pio computes the GPIO base | ❌ | ❌ "GPIO banks above 31 … not yet supported" |
| 16 MB flash | ✅ `PICO_FLASH_SIZE_BYTES`, `boot2_w25q080` | ✅ `EXTERNAL_FLASH_DEVICES = "W25Q128JVxQ"` | ❌ | ⚠️ `RP_FLASH_SIZE` override (default 4 MB) |
| Inverted WS2812 | ✅ Standard PIO program plus `gpio_set_outover(44, GPIO_OVERRIDE_INVERT)`. Built and verified here | ⚠️ `neopixel_write` can't invert. Use `rp2pio.StateMachine` with the ws2812 program's side-set values swapped and `initial_sideset_pin_state=1`, then pass it to KMK's RGB extension via `pixels=`. Or set OUTOVER through `memorymap` | ❌ `WS2812_EXTERNAL_PULLUP` is open-drain and **non-inverting** (side-set on pindirs). On this 2N7002 gate it would leave the LEDs stuck. You'd have to patch in `PAL_RP_IOCTRL_OUTOVER_DRVINVPERI` | ❌ (pins) |
| Encoder (GPIO13/8, pull-ups) | ✅ Write it yourself (quadrature state table) or use a PIO quadrature example | ✅ `kmk/modules/encoder.py` | (✅ on RP2040) | ❌ (pins ≥32 elsewhere) |
| 26-line matrix + direct pins | ✅ Write it yourself (example included). 26 lines fit in one `gpio_get_all64()` read | ✅ `keypad.KeyMatrix` / KMK `keypad` scanner. **Pass the anode-side lines as columns and keep `columns_to_anodes=True`**: `False` switches to pull-downs, which E9 affects | (✅ on RP2040) | ❌ |
| UF2 / BOOTSEL | ✅ ROM bootloader. `picotool reboot -f -u` via `pico_usb_reset_interface` | ✅ | ❌ | ✅ `bootloader: rp2350`, `QK_BOOT` |

**Recommendation: pico-sdk + TinyUSB now.**
- It's the only path that fully covers RP2350B today, and it has already been built here.
- A keyboard is roughly 500 lines on top of the test firmware: matrix, debounce, keymap, HID with NKRO and consumer keys, lock-LED output report, encoder.
- CircuitPython/KMK is a good second choice for quick hacking. It supports the chip; it just needs a board definition without the Metro's status NeoPixel on GPIO25 and PSRAM chip-select on GPIO47 (both are pins this board uses) and the inverted LED driver.
- Move to QMK/Vial once QMK adds RP2350B GPIOBASE support. Nothing on the PCB blocks that; it's purely a software gap.

## Flashing and bring-up

- **BOOTSEL wiring is correct.** It's QSPI_SS → 1 kΩ → button → GND, with a 10 kΩ pull-up (about 0.3 V when pressed), the same as RPi's reference.
  - The bootrom enters BOOTSEL when QSPI CSn is low at reset (datasheet §5.2).
  - It picks USB rather than UART boot because QSPI SD1 is not driven high. SD1 has a default pull-down, and the W25Q128 DO pin is high-Z with no command.
  - Hold BOOTSEL, press RUN, and it enumerates as the RP2350 UF2 drive / picotool device.
- **Behind the CH334R hub: no issue.**
  - The RP2350 is a full-speed device. The CH334R is a multi-TT high-speed hub, so the FS device is handled by the hub's transaction translator, which is normal.
  - The ROM bootloader and TinyUSB don't care about a hub.
  - The RP2350 has no VBUS pin; the SDK and TinyUSB force VBUS-detect in software.
  - After the first flash, the BOOTSEL button isn't needed: `picotool reboot -u`, or a firmware key calling `rom_reset_usb_boot()`, gets back to the bootloader.
- **SWD is a usable fallback.** Pads TP1–TP5 (SWCLK, SWDIO, GND, 3V3, RUN) work with a Raspberry Pi Debug Probe or a Pico running debugprobe, plus RPi's OpenOCD fork (`target/rp2350.cfg`, full support) or upstream OpenOCD master (Arm cores).
- **12 MHz** is the SDK default: `XOSC_HZ 12000000` in `rp2350/.../platform_defs.h`. The bootrom's USB PLL also assumes 12 MHz unless OTP says otherwise (datasheet §5.2).
- **Board header needed** (`boards/das4_controller.h`, modelled on `pimoroni_pga2350.h`):
  - `PICO_RP2350A 0`
  - `PICO_FLASH_SIZE_BYTES (16*1024*1024)`
  - `PICO_BOOT_STAGE2_CHOOSE_W25Q080 1`
  - `PICO_FLASH_SPI_CLKDIV 2`
  - `PICO_PLATFORM rp2350` (arm-s)
  - As a shortcut, `-DPICO_BOARD=pimoroni_pga2350` also works as-is. The RP2350 has no separate boot2 stage like the RP2040; the SDK embeds an IMAGE_DEF block for the bootrom.

## Build attempt: succeeded

The host had git and g++ but no cmake or arm-none-eabi-gcc (the `pcb` distrobox has neither). Everything was installed in the scratchpad in about 5 minutes:

```sh
cd scratchpad/fw
python3 -m venv venv && ./venv/bin/pip install cmake ninja        # cmake 4.4.3
git clone --depth 1 https://github.com/raspberrypi/pico-sdk.git   # SDK 2.3.1 (079c6f3, 2026-09-04)
git -C pico-sdk submodule update --init --depth 1 lib/tinyusb
curl -L https://developer.arm.com/-/media/Files/downloads/gnu/15.2.rel1/binrel/arm-gnu-toolchain-15.2.rel1-x86_64-arm-none-eabi.tar.xz | tar xJ
./build.sh     # PICO_SDK_PATH/PICO_TOOLCHAIN_PATH; cmake -G Ninja; ninja  (picotool auto-fetched and built)
```

Result: `fw/build/das4fw.uf2` (39 KB), 0 warnings. `picotool info -a` reports family `rp2350-arm-s`, `pico_board: das4_controller`, `boot2_w25q080`, SDK 2.3.1. Compile-time asserts check `NUM_BANK0_GPIOS == 48` and `PICO_FLASH_SIZE_BYTES == 16 MB`.

What the test firmware (`fw/das4fw/`) does:
- Enumerates as a TinyUSB HID keyboard.
- Scans an 8×18 placeholder split of GPIO14–39: drives lines low one at a time and reads the others with pull-ups.
- Reads SW1 on GPIO45 (pull-up) and sets pull-ups on the encoder pins GPIO13/8.
- Drives 3 × WS2812 on GPIO44 with the standard PIO program and pad-level output inversion. PIO idles low, so the pad sits high, the FET is on, and DIN is held low (the WS2812 reset state).

Not tested on hardware (there is no board yet).

## Hardware checks

- **E9 (datasheet build 2025-07-29, p.1366):**
  - What it is: on **A2** silicon, an input-enabled pad sitting between VIL and VIH leaks about 120 µA and latches near 2.2 V, which beats the internal pull-down. Pull-ups work normally.
  - Status: fixed in A3/A4 silicon ("Fixed by RP2350 A3"). The workaround is to avoid internal pull-downs, or use an external pull-down of 8.2 kΩ or less.
  - JLC's C42415655 (4,271 in stock) doesn't state the stepping. The design doesn't depend on it; at runtime, `rp2350_chip_version()` reports it.
  - Matrix: always scan by driving low and reading with pull-ups. With diodes, drive the cathode-side lines and read the anode side; either diode direction can be scanned this way, so the unknown row/column split doesn't matter. Without diodes, E9 isn't a factor either, but ghosting is: firmware must block ghosts.
  - Buttons (pull-ups, active low) and encoder (common to GND, pull-ups): unaffected.
  - The LED gate relies on the power-on pull-down, which E9 doesn't affect: it only applies once IE is set, and firmware drives the pin by then.
- **ADC pins as digital inputs:** GPIO40–47 are ordinary digital I/O that also have the ADC. Digital input works once `gpio_init` sets IE and clears ISO; the SDK and CircuitPython do this. Just don't enable their ADC channels. They are **not** 5 V tolerant (VPIN ≤ IOVDD + 0.5 V), and nothing on them exceeds 3.3 V: buttons to GND, and the 2N7002 gate.
- **5 V tolerance:** J4 is on GPIO14–39, which are FT pins (up to 5.5 V with IOVDD at 3.3 V). The key PCB is passive, so it's moot anyway.
- **LED level shifter timing:** the 1 kΩ pull-up with about 40 pF gives about 50 ns to reach 0.7·VDD. That shortens each DIN high pulse by about 50 ns. A 0-bit is then about 325 ns high, still inside WS2812D T0H (220–380 ns). Fine.

## Hardware changes before ordering

**Required: none.**

Optional, cheap, and useful:
1. **Put GPIO0/GPIO1 (spare, UART0 TX/RX) on two test pads.** This gives a debug console during bring-up that doesn't depend on USB enumeration. It's the only change I'd actually make.
2. **Only if you want unpatched QMK/KMK LED drivers someday:** replace the 2N7002 + 1 kΩ inverter with a non-inverting 5 V buffer, e.g. 74AHCT1G125 (VCC 5 V, OE to GND). Not needed: pad inversion is one register write in every framework.

Doc fix (not hardware): in `docs/design.md`, replace "QMK: `WS2812_EXTERNAL_PULLUP`" with "invert the pad output (`IO_BANK0 GPIO44_CTRL.OUTOVER = INVERT`)". Also note that QMK doesn't yet support RP2350B.

## Sources (fetched 2026-09-26)

- RP2350 datasheet, build-date 2025-07-29: E9 p.1366–1367, A3 changes, pin types/FT §14.8.2, BOOTSEL/UART boot §5.2/§5.8. https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf
- A4 stepping / E9 fix: CNX Software 2025-07-29, https://www.cnx-software.com/2025/07/29/raspberry-pi-rp2350-a4-stepping-fixes-e9-gpio-erratum-9-glitching-bugs-introduces-2mb-flash-variants/ ; Hackaday 2025-07-31, https://hackaday.com/2025/07/31/raspberry-pi-rp2350-a4-stepping-addresses-e9-current-leakage-bug/
- pico-sdk 2.3.1 (2026-09-04): https://github.com/raspberrypi/pico-sdk (`pimoroni_pga2350.h`, `hardware_pio` GPIOBASE, `platform_defs.h`)
- QMK master b1aea25 / develop 5060d75 trees (2026-09-26), no RP2350 files: https://github.com/qmk/qmk_firmware ; issue #25881 (comments to 2026-07-22): https://github.com/qmk/qmk_firmware/issues/25881 ; QMK `ws2812_vendor.c` (develop): https://github.com/qmk/qmk_firmware/blob/develop/platforms/chibios/drivers/vendor/RP/RP2040/ws2812_vendor.c
- QMK RP2350 POC `docs/platformdev_rp2350.md` (2026-07-22): https://github.com/emolitor/qmk_firmware/blob/em-rp2350/docs/platformdev_rp2350.md
- ChibiOS RP2350 commit 532dcc8 (2026-01-18); latest tag still ver21.11.5: https://github.com/ChibiOS/ChibiOS
- CircuitPython 10.3.1 (2026-09-14); `rp2pio/StateMachine.c` GPIO-base handling; `adafruit_metro_rp2350` board; `shared-module/keypad/KeyMatrix.c`: https://github.com/adafruit/circuitpython ; rp2pio docs: https://docs.circuitpython.org/en/latest/shared-bindings/rp2pio/index.html
- KMK main (2026-04-09): `kmk/extensions/rgb.py` (`pixels=`), `kmk/modules/encoder.py`: https://github.com/KMKfw/kmk_firmware
- OpenOCD RP2350: https://github.com/raspberrypi/openocd/blob/sdk-2.0.0/tcl/target/rp2350.cfg ; https://review.openocd.org/c/openocd/+/8449
- JLCPCB part C42415655 stock (API, 2026-09-26): https://jlcpcb.com/partdetail/C42415655
- Arm GNU Toolchain 15.2.rel1: https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads
