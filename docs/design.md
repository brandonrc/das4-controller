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

## Part candidates (to verify: stock at JLCPCB/LCSC, datasheet footprints)

| Function | Candidate | Notes |
|---|---|---|
| MCU | RP2350B (QFN-80) | + QSPI flash (W25Q128), 12 MHz crystal, 1.1 V core regulator (on-chip SMPS needs an inductor) |
| USB hub | USB 2.0 4-port hub IC (e.g. CH334/CH335, FE1.1s, GL850G, SL2.1A) | Pick by JLC stock and how few external parts it needs |
| 3.3 V regulator | LDO, ≥500 mA | Powers the hub + MCU |
| USB-A power | Current-limit switch or polyfuse per port | 500 mA per port |
| USB-C | HRO TYPE-C-31-M-12 | 5.1 kΩ CC pull-downs (upstream-facing port) |
| USB-A | Molex 67643 or a JLC-stocked equivalent | THT, ~7 mm tall |
| Encoder | 12 mm body, 6 mm D-shaft, **no switch**, 20 detents (original). Bourns PEC12R-42xxF-N0024 is the closest Bourns part (24 detents) | A push switch doesn't fit: the body sits flush with the board edge, so the switch pins would land off the board. Use a button for mute |
| Buttons | 6 × 6 mm SMD tact | Heights to match the case |
| LEDs | 5 mm THT, clear lens | ~9 mm standoff height |
| Boot/reset | Small SMD tacts for BOOTSEL + RUN, or reuse SW4 as BOOTSEL | Needed to flash firmware |
| ESD | TVS array on the USB-C and USB-A data lines | |

## Firmware

QMK (RP2040/RP2350 support, encoder, lock LEDs, VIA/Vial remapping), or
KMK/CircuitPython for easy hacking. The buttons are plain GPIO, so any
firmware can give them "fun" functions.

## Open questions

- [ ] J4 pinout: which of the 26 pins are rows, columns, GND or LED power? Needs photos/continuity checks on the key-switch PCB side.
- [ ] Does the key PCB have per-key LEDs or diodes? The diode direction sets the scan direction.
- [ ] Encoder shaft length and detent count.
- [ ] Caliper pass on everything marked *photo* in [measurements.md](measurements.md).
- [ ] Case clearance under the board (bottom-side parts and J4 height).
