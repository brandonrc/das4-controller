# Plan and status

Last updated 2026-09-29.

## Where we are

**The board is finished and ready to order**, pending a 1:1 fit print in the
case. It's routed, and DRC is clean (0 unconnected, 0 non-cosmetic
violations). CI checks this on every push.

## How we got here

1. **Requirements** (2026-09-24): the same outline, holes and connector
   positions as the original. RP2350B; USB 2.0 hub with 2 × USB-A plus the
   MCU; volume encoder (no push); 5 buttons on their own GPIOs; RGB lock LEDs;
   26-line key matrix.
2. **Measurements:** photos and calipers, then a fit-check print. That fixed
   the USB-A notch (9.35 × 3.5 mm) and the knob position. See
   [measurements.md](measurements.md).
3. **Circuit as code:** SKiDL in `hardware/circuit/das4.py`, with parts
   picked from JLCPCB's library. Extended parts were cut from 15 to 6 to keep
   the order cheap.
4. **Circuit review:** [review-2026-09-25.md](review-2026-09-25.md).
5. **Placement and routing:** generated placement plus Freerouting.
   - First routed board: e51b12c.
6. **Layout review 1:** [review-layout-2026-09-25.md](review-layout-2026-09-25.md).
   - The MCU corner was redone after Raspberry Pi's minimal design: U1
     rotated, the critical nets hand-drawn in `critical.py`, In2 turned into
     a solid 3.3 V plane.
   - Commit 16007bf.
7. **Layout review 2:** [review-layout-2-2026-09-25.md](review-layout-2-2026-09-25.md).
   - Added keep-outs (under L1/LX, the USB-A shells, the screw heads, the
     crystal).
   - DVDD caps, a windowpane paste pattern on the exposed pad, and other
     fixes.
   - Commit f079e2b.
8. **J4:** the key PCB's flex cable is soldered at both ends (photos,
   2026-09-26), so J4 became 26 solder pads at 1.0 mm pitch. There's no
   connector, and the lines are keys only, with no 5 V.
9. **Checked against Raspberry Pi's "Hardware design with RP2350":**
   [rpi-guide-check-2026-09-26.md](rpi-guide-check-2026-09-26.md).
   - The circuit matches their reference.
   - A cap was added at DVDD pin 51.
   - L1's orientation was confirmed.
10. **Firmware check:** [firmware-check-2026-09-26.md](firmware-check-2026-09-26.md).
    - pico-sdk + TinyUSB builds for this pinout (`firmware/bringup`).
    - KMK/CircuitPython works with a custom board definition.
    - QMK has no RP2350 support yet.
    - UART debug pads were added on the strength of this check.

## Next steps

1. **Fit print (owner):** print `docs/fit-check-1to1.pdf` at 100 % (Actual
   size) and lay it in the case. Check the J4 pad strip against the flex, the
   USB-C/USB-A mouths, the 3 mounting holes, the knob and the buttons.
2. **Order at JLCPCB.** Follow "Ordering at JLCPCB" in [design.md](design.md):
   - 4 layers, JLC04161H-7628 stackup with impedance control
   - top-side assembly with `bom.csv` and `cpl.csv`
   - check L1's dot and the rotations in the placement preview
   - order the hand-solder parts from [bom.md](bom.md)
3. **Hand-solder:** USB-A ×2, encoder, WS2812D ×3, 6 mm switches ×5, and the
   J4 flex onto its pads.
4. **Bring-up** (see below).
5. **Keyboard firmware** (see below).

## Bring-up plan

Do it in this order, and stop at the first surprise.

1. **Before power:** look for solder bridges, especially at U1 (0.4 mm pitch)
   and the hub. Check the ohms from 5V, 3V3 and 1V1 to GND: none should be a
   short.
2. **First power**, from USB-C, ideally through a current-limited USB meter.
   Use the test pads:
   - **5V:** about 5 V
   - **3V3:** 3.3 V
   - **1V1:** about 1.1 V, from the RP2350's internal regulator
3. **The hub** should enumerate on the PC as a USB 2.0 hub. Test both USB-A
   ports with a USB stick.
4. **Hold BOOT and tap RST:** an RP2350 drive should appear. If it doesn't,
   use the SWD pads (SWC, SWD, GND) with a Raspberry Pi Debug Probe.
5. **Flash `firmware/bringup`:**
   - it should enumerate as a USB keyboard
   - the LEDs should light
   - SW1 should respond
   - a USB-serial adapter on TX/RX/GND (115200 baud) shows `printf` output
     even if USB fails
6. **Map the key matrix:** press keys and log which J4 lines connect, to get
   rows vs columns and whether the key PCB has diodes. Unpowered continuity
   checks on the key PCB work too.

## Firmware plan

1. **pico-sdk + TinyUSB keyboard**, built from `firmware/bringup`:
   - matrix scan with debounce and ghost-key handling (if the key PCB has no
     diodes), and a keymap
   - media keys on the encoder and the 5 buttons
   - lock-LED report onto the RGB LEDs (red by default, changeable)
2. **Later:** port to QMK/Vial once QMK supports the RP2350B, including
   GPIO above 31. Nothing on the PCB blocks that. KMK/CircuitPython is an
   option for easy hacking in the meantime.

## Known deviations (accepted)

- The USB 22 Ω resistors sit at the hub end, not at the RP2350. It works at
  12 Mbit/s; the guide prefers 27 Ω close to the chip.
- DVDD pin 32's nearest cap is about 11 mm away, because there's no room
  beside it.
- A few vias touch same-net pads (SW3 GND, TP8), which is harmless.
- Some footprints' own silkscreen outlines touch pads; JLC trims them.
