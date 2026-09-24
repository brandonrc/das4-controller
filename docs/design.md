# Design notes

## Goal

A drop-in replacement for the **Das Keyboard 4 Professional** controller board
(original: `HK-D4215-2-10-03`, 2021-07-27), using an open, reprogrammable MCU.
It must keep the same outline, mounting holes and connector positions, so it
fits the stock case and the stock key-matrix cable.

## What the original board has

| Ref (orig.) | Part | Keep? |
|---|---|---|
| U4 | ~80-pin LQFP MCU, markings removed, 12 MHz crystal | **Replace** with RP2350B |
| U3 | VIA Labs (VLI) USB 3.0 hub | **Replace** with a USB 2.0 hub |
| J5 | USB-C, upstream to the PC | Keep (position) |
| J2, J3 | USB 3.0 Type-A | Keep (position), USB 2.0 is fine |
| J4 | 26-pin connector to the key-switch PCB (bottom side) | Keep (position + pinout TBD) |
| P1 | Rotary encoder, no push switch, 20 detents (5 per quarter turn) | Keep |
| SW1–SW5 | Tact switches | Keep, each on its own GPIO |
| NUM / CAPS / SCROLL | 5 mm THT LEDs | Keep |
| GND/CLK/DIO/5V pads | SWD programming header for U4 | Replace with our own SWD pads |

## Architecture

```
PC ──USB-C──► USB 2.0 hub ──► USB-A port 1
                         ├──► USB-A port 2
                         └──► RP2350B (USB HID keyboard + media keys)
                                 ├─ 26 × key matrix (J4)
                                 ├─ encoder A/B
                                 ├─ 5 × buttons
                                 └─ 3 × lock LEDs
```

The PC has to connect to the **hub**, and the MCU hangs off one of the hub's
downstream ports. If the PC plugged into the MCU instead (for example, a
dev board's own USB-C), the USB-A ports would have nowhere to get data from.

## GPIO budget

| Function | Pins |
|---|---|
| Key matrix via J4 (if all 26 are matrix lines) | 26 |
| Encoder: A, B | 2 |
| Buttons | 5 |
| Lock LEDs | 3 |
| **Total** | **36** |

- Seeed XIAO: 11 GPIO, so it doesn't fit.
- Raspberry Pi Pico / Pico 2: 26, so it doesn't fit without an expander.
- **RP2350B: 48, so everything fits on one chip with spare pins.**

The USB hub IC has to be factory-assembled anyway, since it only comes as a
tiny SMD part. So the whole board is factory-assembled (e.g. JLCPCB PCBA)
with a bare RP2350B, not a hand-soldered module.

Fallback: a Pico 2 module plus a 16-bit I²C expander (e.g. TCA9555) for the
buttons and LEDs.

## Circuit

The circuit is code: [`hardware/circuit/das4.py`](../hardware/circuit/das4.py)
([SKiDL](https://github.com/devbisme/skidl)). `make` turns it into a netlist and
places it on the board. The full parts list with live stock is in [bom.md](bom.md).

| Block | Part | Notes |
|---|---|---|
| MCU | RP2350B (QFN-80) | Copied from Raspberry Pi's minimal design: 12 MHz ABM8-272-T3 crystal (15 pF, 1 kΩ), 16 MB W25Q128JV flash, 3.3 µH AOTA-B201610S3R3 inductor for the on-chip 1.1 V regulator (pad 1 to +1V1), 33 Ω/4.7 µF on VREG_AVDD, 100 nF on every IOVDD/DVDD pin, 27 Ω on USB |
| USB hub | WCH CH334R (QSOP-16) | 4-port USB 2.0, built-in pull-ups/downs. Powered from 3.3 V on both V5 and VDD33 (datasheet §6.1). 12 MHz crystal with no load caps (they're on-chip). Port 1 → USB-A 1, port 2 → USB-A 2, port 3 → RP2350B, port 4 unused |
| 3.3 V | ME6211C33 LDO, 500 mA | Low dropout (0.1 V), so USB voltage sag doesn't matter. Runs hub + MCU + flash (~200 mA) |
| USB-C | HRO TYPE-C-31-M-12 | 5.1 kΩ on CC1/CC2 (we're a device), USBLC6-2SC6 ESD on D+/D- |
| USB-A ×2 | SHOU HAN AF 90 WJDG | USB 2.0, right angle, through-hole. 500 mA polyfuse, 22 µF bulk and USBLC6-2SC6 ESD per port |
| Encoder | Alps EC12E24204A2 | 12 mm, no switch, 24 detents, 15 mm D-shaft. A push switch can't fit: the body sits flush with the board edge, so switch pins would land off the board |
| Buttons ×5 | 6 × 6 × 5 mm SMD tact | Other heights (4.3–10 mm) exist in the same footprint if the case needs them |
| Lock LEDs ×3 | 5 mm white THT | 5 V → 330 Ω → LED → 2N7002 low-side switch on a GPIO, so any colour works |
| BOOTSEL / RESET | 4 × 3 mm SMD tact | BOOTSEL via 1 kΩ on QSPI_SS; RESET pulls RUN low through 1 kΩ |
| SWD | 4 test pads | SWCLK, SWDIO, GND, 3V3 |
| J4 | 26-pin, **placeholder** | Pitch/type unknown, not factory-assembled: reuse the original connector or fit one by hand |

### GPIO map

Picked for routing: on the RP2350B, GPIO21-46 sit along the package's bottom and
right edges (towards J4 and the hub), and GPIO4-13 along the left (towards the
buttons, LED drivers and encoder). Any GPIO can do any job, so firmware just
follows this table ([`das4.py`](../hardware/circuit/das4.py) has the same thing).

| Function | GPIO |
|---|---|
| J4 pin 1–26 (key matrix) | GPIO21–GPIO46 |
| SW1–SW5 (active low, use internal pull-ups) | GPIO4–GPIO8 |
| Encoder A / B (internal pull-ups) | GPIO9 / GPIO10 |
| NUM / CAPS / SCROLL LED (high = on) | GPIO11 / GPIO12 / GPIO13 |
| Spare | GPIO0–3, GPIO14–20, GPIO47 |

### Board

- **4 layers** (signal / GND / power / signal). The hub's upstream link runs
  at USB high speed (480 Mbit/s) and needs 90 Ω pairs over a solid ground
  plane. The inner layers also make it much easier to fan out the RP2350B's
  0.4 mm pads. At JLCPCB a small 4-layer board costs a few dollars more than
  2-layer.
- **Everything assembled on the top side**, so JLCPCB assembly is
  single-sided. That makes the MCU corner tight: the original put its MCU on
  the back.
- Design rules match JLCPCB 4-layer capabilities with margin (0.12 mm
  clearance, 0.2 mm tracks, 0.5/0.25 mm vias).

## Firmware

QMK (RP2040/RP2350 support, encoder, lock LEDs, VIA/Vial remapping), or
KMK/CircuitPython for easy hacking. The buttons are plain GPIO, so any
firmware can give them "fun" functions.

## Open questions

- [ ] J4 pinout: which of the 26 pins are rows, columns, GND or LED power? Needs photos/continuity checks on the key-switch PCB side.
- [ ] Does the key PCB have per-key LEDs or diodes? The diode direction sets the scan direction.
- [ ] Encoder: confirm 15 mm shaft / 24 detents is close enough (original: ~14 mm, 20 detents).
- [ ] J4: check with a multimeter that no pin carries 5 V before connecting (they go straight to RP2350 GPIO).
- [ ] Cut JLCPCB fees: 14 Extended part types (~$3 each). Candidates: hand-solder the LEDs/switches, merge values.
- [ ] Route the board (next step).
- [ ] Caliper pass on everything marked *photo* in [measurements.md](measurements.md).
- [ ] Case clearance under the board (bottom-side parts and J4 height).
