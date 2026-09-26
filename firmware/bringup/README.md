# Bring-up firmware (pico-sdk + TinyUSB)

A minimal test firmware for this board, used to prove the design can be
built for (see [../../docs/firmware-check-2026-09-26.md](../../docs/firmware-check-2026-09-26.md)).
It isn't the keyboard firmware yet. What it does:
- enumerates as a USB keyboard
- scans GPIO14–39 (J4) as a placeholder matrix, driving low and reading with pull-ups
- reads SW1 (GPIO45) and sets up the encoder pins
- drives the 3 WS2812s on GPIO44 with the output pad inverted (the 2N7002
  level shifter inverts the data)

Board header: `boards/` (RP2350B, 16 MB W25Q128, 12 MHz crystal).

## Build

Needs cmake, ninja, the Arm GNU toolchain (arm-none-eabi) and pico-sdk 2.x
(with the tinyusb submodule):

```sh
export PICO_SDK_PATH=/path/to/pico-sdk
cmake -S firmware/bringup -B build/fw -G Ninja
ninja -C build/fw          # -> build/fw/das4fw.uf2
```

## Flash

Hold BOOTSEL, tap RESET (or plug in): the board shows up as a USB drive.
Copy `das4fw.uf2` onto it. Later, `picotool reboot -u` gets back there
without the button. SWD pads TP1–TP4 work with a Raspberry Pi Debug Probe.
