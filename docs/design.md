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
| J4 | 26-way 1.0 mm flex cable ("CON2") to the key-switch PCB, soldered on (bottom side) | Keep: solder pads, no connector |
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
                                 └─ 3 × RGB lock LEDs (one data line)
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
| MCU | RP2350B (QFN-80) | Copied from Raspberry Pi's minimal design: 12 MHz ABM8-272-T3 crystal (15 pF, 1 kΩ), 16 MB W25Q128JV flash, 3.3 µH AOTA-B201610S3R3 inductor for the on-chip 1.1 V regulator (pad 1 to +1V1), 33 Ω/4.7 µF on VREG_AVDD, 100 nF on every IOVDD/DVDD pin. USB series resistors are 22 Ω (JLCPCB Basic) instead of RPi's 27 Ω |
| USB hub | WCH CH334R (QSOP-16) | 4-port USB 2.0, built-in pull-ups/downs. Powered from 3.3 V on both V5 and VDD33 (datasheet §6.1). 12 MHz crystal with no load caps (they're on-chip). Port 1 → USB-A 1, port 2 → USB-A 2, port 3 → RP2350B, port 4 unused |
| 3.3 V | ME6211C33 LDO, 500 mA | ~0.1 V dropout and stable with ceramic caps. An AMS1117 (Basic) was tried and rejected in review: it drops out when VBUS sags on hot-plug, browning out the hub and MCU |
| USB-C | HRO TYPE-C-31-M-12 | 5.1 kΩ on CC1/CC2 (we're a device). No separate ESD chip: the CH334R has 6 kV ESD protection on all its USB pins |
| USB-A ×2 | SHOU HAN AF 90 WJDG (**hand-soldered**) | USB 2.0, right angle, through-hole. VBUS straight from the PC's 5 V (its port limits current); 22 µF + 100 nF per port |
| Encoder | Alps EC12E24204A2 (**hand-soldered**) | 12 mm, no switch, 24 detents, 15 mm D-shaft. A push switch can't fit: the body sits flush with the board edge, so switch pins would land off the board |
| Buttons ×5 | 6 × 6 × 5 mm SMD tact (**hand-soldered**) | Other heights (4.3–10 mm) exist in the same footprint if the case needs them |
| Lock LEDs ×3 | WS2812D-F5 5 mm THT **RGB** (**hand-soldered**) | Any colour from firmware. One GPIO drives the chain NUM → CAPS → SCROLL through a 2N7002 + 1 kΩ pull-up to 5 V (Basic parts): a 5 V-level signal, **inverted**, so firmware drives the pin inverted (QMK: `WS2812_EXTERNAL_PULLUP`). 100 nF per LED |
| BOOTSEL / RESET | TS-1187A 5 × 5 mm SMD tact (JLCPCB Basic) | BOOTSEL via 1 kΩ on QSPI_SS; RESET pulls RUN low through 1 kΩ |
| SWD + rails | 7 test pads | SWCLK, SWDIO, GND, 3V3, RUN, plus +1V1 and +5V for bring-up |
| J4 | 26 solder pads, 1.0 mm pitch, 0.6 × 2.5 mm, bottom side at the board edge | The key PCB's flex cable is hot-bar soldered at both ends (no connector), so it's soldered straight onto these by hand, like the original. No part, no cost |

### GPIO map

Picked for routing. Any GPIO can do any job, so firmware just follows this
table ([`das4.py`](../hardware/circuit/das4.py) has the same thing).

| Function | GPIO |
|---|---|
| J4 pin *k* (key matrix) | GPIO(40 − *k*): pin 1 → GPIO39 … pin 26 → GPIO14. Follows the package pin order so the bus fans out without crossings; all on 5 V-tolerant GPIO0–39 |
| SW1 / SW2 / SW3 / SW4 / SW5 (active low, use internal pull-ups) | GPIO45 / 46 / 47 / 43 / 42 |
| Encoder A / B (internal pull-ups) | GPIO13 / GPIO8 |
| RGB LED data (WS2812, chain NUM → CAPS → SCROLL; **inverted**) | GPIO44 |
| Spare | GPIO0–7, GPIO9–12, GPIO40–41 |

GPIO40–47 are the ADC pins and aren't 5 V tolerant, which is fine for the
buttons and the LED driver (all 3.3 V). Mind RP2350 erratum E9 on those pins:
use the internal pull-ups, don't rely on pull-downs.

### Board

Stackup: F.Cu signals · In1 solid GND · In2 solid +3V3 · B.Cu signals + GND pour.

The MCU corner follows Raspberry Pi's minimal-design layout, drawn by hand in
[critical.py](../hardware/scripts/critical.py) and locked before autorouting:
- the core regulator block right at pins 61–65: VREG_VIN and +1V1 caps
  against the pins, LX running out between their pads into L1, GND vias
  beside them, and the VREG_AVDD RC filter
- 5 GND vias in the exposed pad, with the solder paste split into 4 windows
  (~50 %) between them so no paste sits over a via
- a via straight inward from every +3V3 pin (to the In2 plane) and every
  +1V1 pin (to a 0.5 mm +1V1 "C" on B.Cu around the chip, like RPi's)
- 100 nF caps in columns beside the pins, with a shared GND via between each
  pair; DVDD pin 10's cap right under the pin
- the crystal right beside XIN/XOUT, with XOUT's series resistor in line and no
  vias or other signals near it
- USB upstream D+/D− as a coupled pair from J1 to the hub over solid GND, kept
  more than 3 mm from the mounting hole; the CC pull-downs
- each tact switch's internally-connected pad pairs joined

Keep-outs (rule areas, from layout review 2):
- no copper on In1, In2 or B.Cu under L1 and VREG_LX (RP2350 datasheet 6.3.8)
- no top-layer pour round the regulator block, so its GND joins main GND at
  one point (the CIN/COUT via pair)
- no top-layer tracks or vias under the USB-A shells
- nothing within 2.5 mm of the mounting holes (screw heads)
- while autorouting only: nothing else through the crystal block

Then Freerouting does the rest (`make route`,
[route.py](../hardware/scripts/route.py)): 4 differently-configured runs in
parallel, best kept. After autorouting: GND stitching vias wherever the outer
pours filled, extra vias into any via-less pour piece, then fill.
Result: 794 track segments, 444 vias; 0 unconnected, 0 non-cosmetic DRC violations.

- **4 layers** (signal / GND / power / signal). The hub's upstream link runs
  at USB high speed (480 Mbit/s) and needs 90 Ω pairs over a solid ground
  plane. The inner layers also make it much easier to fan out the RP2350B's
  0.4 mm pads. At JLCPCB a small 4-layer board costs a few dollars more than
  2-layer.
- **Everything assembled on the top side**, so JLCPCB assembly is
  single-sided. That makes the MCU corner tight: the original put its MCU on
  the back.
- Design rules match JLCPCB 4-layer capabilities with margin (0.1 mm
  clearance, 0.15 mm tracks, 0.5/0.25 mm vias; 0.4/0.2 mm for the vias under
  the MCU).

## Firmware

QMK (RP2040/RP2350 support, encoder, lock LEDs, VIA/Vial remapping), or
KMK/CircuitPython for easy hacking. The buttons are plain GPIO, so any
firmware can give them "fun" functions.

## Open questions

- [x] J4 type: a 26-way 1.0 mm flex, soldered at both ends (photos 2026-09-26). The lines all fan into the switch matrix; firmware maps pad *k* to a row or column (a mirrored flex just reverses the table).
- [ ] Does the key PCB have per-key LEDs or diodes? The diode direction sets the scan direction.
- [ ] Encoder: confirm 15 mm shaft / 24 detents is close enough (original: ~14 mm, 20 detents).
- [ ] J4 (for firmware, not the order): unpowered continuity checks on the key PCB: flex pads open to its ground/copper areas; press keys to map rows vs columns; diode mode to see if per-key diodes exist. The key PCB is keys only (no lights), so nothing on it drives the lines.
- [x] Cut JLCPCB fees: 6 Extended types (RP2350B, CH334R, USB-C, inductor, crystal, ME6211 LDO); 11 easy parts are hand-soldered.
- [x] Independent design review: see [review-2026-09-25.md](review-2026-09-25.md).
- [x] Route the board.
- [x] Layout reviews: [review-layout-2026-09-25.md](review-layout-2026-09-25.md), [review-layout-2-2026-09-25.md](review-layout-2-2026-09-25.md).
- [ ] USB-C: only the A4/B9 VBUS pair is wired (B4/A9 boxed in by SW4); fine since plugs tie all VBUS pins.
- [ ] Caliper pass on everything marked *photo* in [measurements.md](measurements.md).
- [ ] Case clearance under the board (bottom side: only the J4 flex now).
- [ ] Order with JLCPCB's JLC04161H-7628 stackup (impedance control), which the ~90 Ω USB pair widths assume.
