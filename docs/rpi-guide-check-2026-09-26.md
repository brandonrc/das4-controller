# das4-controller vs "Hardware design with RP2350" (RP-008280-DS, release 3, 2026-08-20)

Source: the PDF from pip-assets.raspberrypi.com (25 pages), read in full, including the Appendix B RP2350B schematic (rendered at 400 dpi so I could read the pin numbers and the RUN/decoupling details). Design checked: `hardware/circuit/das4.py`, `critical.py`, and the routed `das4-controller.kicad_pcb`, measured with pcbnew in the `pcb` distrobox. Coordinates are board mm.

**Verdict: the circuit matches the guide. One cheap layout fix, plus one assembly-orientation check, before ordering.** Every RP2350B power, QSPI, crystal, USB, SWD and RUN pin lands on the same net as RPi's RP2350B minimal schematic, and the regulator parts are the exact values and parts RPi specifies. The FIX items are layout and assembly:
- DVDD pin 51 has no local 100 nF, and there is free room for one.
- The L1 polarity dot needs confirming at JLC, because the footprint carries two conflicting markers.

Scope note: the guide says nothing about errata (E9), 5 V tolerance or ADC-pin behaviour. Those come from the RP2350 datasheet. I note the design's handling of them below but can't grade it against this guide.

## Item-by-item

| Guide item (page / section) | What the guide says | What the design does | Status |
|---|---|---|---|
| Regulator parts (p.7, §2.1) | "C6, C7, and C9 - 4.7µF (0402)", "L1 - Abracon AOTA-B201610S3R3-101-T", "R3 - 33Ω" | C164 (VREG_VIN) 4.7 µF, C165 (+1V1) 4.7 µF, C161 (VREG_AVDD) 4.7 µF: all CL05A475 0402 X5R 10 V. L1 is the AOTA-B201610S3R3-101-T (C42411119). R161 is 33 Ω | OK |
| Regulator pin wiring (p.5 Fig.3, App.B) | VREG_VIN 64 to +3V3, LX 63 to L1, PGND 62 to GND, FB 65 to +1V1, AVDD 61 via 33 Ω/4.7 µF | Identical (checked on the board pads: 61 VREG_AVDD, 62 GND, 63 VREG_LX, 64 +3V3, 65 +1V1) | OK |
| Regulator layout (p.6–7, §2.1): "closely follow our layout", "if you choose not to use our example, then you do so at your own risk" | Order from the pins outward: CIN (C6), then COUT (C7), then L1, all parallel to the package edge. LX runs out between the cap pads; FB ties to +1V1 at C7; PGND "must connect to the main GND" so that switching currents return directly | Same order and handedness. C164 pad is 1.16 mm from pin 64; C165 is next; L1 is beyond, parallel to the edge. LX (4.75 mm) runs between the cap pads. FB is a Kelvin tap at C165. GND reaches main GND through one via pair (F.Cu pour keep-out). No copper under L1/LX on In1/In2/B.Cu. The only difference is a 4-layer stackup, and the rule areas follow the datasheet's 4-layer rule | OK |
| Inductor polarity (p.6–7, §2.1) | The dot must be "the right way round". In RPi's layout (Fig.4) the dot is on the **+1V1** pad | Netlist puts +1V1 on L1 pad 2, and the footprint's large silk dot (r 0.13 at 3.44, 23.1) is by pad 2. **But** the same easyeda footprint also has a small pin-1 marker circle at (1.54, 25.0), by pad 1 = VREG_LX. CPL rotation is 270°. If JLC orients the part by "pin 1", and Abracon's dot marks terminal 1 (as it does in RPi's footprint, where the dot pad is pad 1), the dot lands on LX: the wrong way round | **FIX** (verify) |
| VREG_AVDD filter (p.7, §2.1) | 33 Ω + 4.7 µF RC, because AVDD "is very sensitive to noise" | R161 33 Ω + C161 4.7 µF. C161 is 2.5 mm from pin 61 with its own GND via | OK |
| Input supply (p.7–8, §2.2) | LDO with the input/output caps its datasheet asks for (RPi: NCP1117, 10 µF + 10 µF) | ME6211C33, 10 µF in, 2×10 µF out, plus C190 10 µF bulk. Good for 500 mA | OK |
| Decoupling values/count (p.8, §2.2.1, Fig.6, App.B) | "100 nF capacitor per power pin". RPi's RP2350B uses 9×100 nF on +3V3 (ADC_AVDD shares IOVDD pin 60's cap; pins 68/69 share C12), 3×100 nF on +1V1, 10 µF bulk C19 | 11×100 nF on +3V3: one each on IOVDD 5/15/24/29/41/50/60/76, ADC_AVDD 59, USB_OTP_VDD 68, QSPI_IOVDD 69. 3×100 nF on DVDD 10/32/51. Plus 2×4.7 µF on +1V1 and 10 µF bulk. More than the reference | OK |
| Decoupling placement (p.8, §2.2.1) | "important to place decoupling close to the power pins". The only compromise RPi accepts is one cap shared by pins 68/69 | Close: pins 5 (2.4 mm), 10 (1.1), 41 (1.2), 59/60 (1.5–2.7), 64 (1.2). **Far** (pad to pad, straight line): pins 15 (20.6 mm), 69 (16.6), 24 (14.5), 29 (13.7), 76 (10.9), 68 (8.9), 50 (7.2). The +3V3 pins each have a via to the solid In2 plane, and 68/69 sit 2 mm from C164 (4.7 µF) on that plane, so these are acceptable. **DVDD** is weaker: +1V1 is a 0.5 mm B.Cu trace, not a plane. Pin 51's cap is 5.1 mm away (about 11 mm of trace). Pin 32's nearest cap is C110 at pin 10, about 11 mm of trace away. The F.Cu area directly above pin 51 (x 10.2–11.6, y 26.2–28.3) is **empty** apart from a GND stitching via at (10.95, 28.0) | +3V3: deviation-acceptable. DVDD 51: **FIX**. DVDD 32: deviation-acceptable (no room: R231/XOUT and the SWD/RUN escapes occupy it) |
| ADC_AVDD (App.B) | Tied to +3V3 (with IOVDD pin 60) | Tied to +3V3 with its own 100 nF (C159, 2.7 mm). ADC not used | OK |
| USB_OTP_VDD (App.B; p.8) | Tied to +3V3, cap shared with QSPI_IOVDD | Tied to +3V3. C168 is 8.9 mm away, but pin 68 has a plane via and C164 is 1.9 mm away | Deviation-acceptable |
| Flash part (p.10, §3.1; §3.3) | W25Q128JVS, 16 MB (the maximum). The bootrom needs 03h/02h/05h/06h/20h | W25Q128JVSIQ (C97521), the same part | OK |
| QSPI routing (p.10, §3.1) | "QSPI pins … should be wired directly to the flash, using short connections" | Direct, no series parts. SS 11.9 mm, SCLK 5.3, SD0 1.9, SD1 13.2, SD2 7.8 (2 vias), SD3 14.2 (2 vias). C300 100 nF about 1.9 mm from U3 VCC | OK |
| QSPI series resistors (p.10–11, §3.1–3.2) | None on the data lines. R9/R10 are 0 Ω links only for the RP2354/secondary-memory option | None; the option isn't needed on an RP2350B with one flash | OK |
| QSPI_SS pull-up (p.10) | R1 10 kΩ, DNF with the W25Q128JV, footprint kept "just in case" | R301 10 kΩ fitted, 2.4 mm from U3 pin 1. With the button pressed SS sits at about 0.3 V (10 k against 1 k), still a solid low | OK |
| BOOTSEL (p.10–11) | QSPI_SS → R6 1 kΩ → button → GND. "It is important to include resistor R6". R1/R6 "should be placed close to the flash chip" | R302 1 kΩ at U3 (about 2.8 mm from pin 1), then SW6 to GND. The USB_BOOT net behind R302 is 54 mm long with 2 vias. It's isolated by the 1 kΩ, so it's fine | OK |
| Crystal (p.13–14, §4, §4.1) | 12 MHz ABM8-272-T3: "We highly recommend using this crystal along with the accompanying circuitry" | ABM8-272-T3 (C20625731, Abracon, confirmed via JLC API) | OK |
| Load caps (p.13) | CL 10 pF. 15 pF each gives 7.5 pF + about 3 pF stray, about 10.5 pF | C230/C231 15 pF C0G (0402CG150J500NT). XIN 4.9 mm, XOUT_XTAL 6.4 mm, no vias. On the 4-layer board (In1 about 0.2 mm down) that adds roughly 0.5 pF per side, well inside the 3 pF allowance | OK |
| Series resistor (p.13) | R2 1 kΩ between XOUT and the crystal, for IOVDD = 3.3 V. Any deviation "will require extensive testing" | R231 1 kΩ, pin 31 → R231 → Y1.3/C231. IOVDD is 3.3 V | OK |
| XOSC startup (p.13–14) | Copy the circuit exactly, otherwise test start-up over temperature | Exact copy at 3.3 V. Keep the SDK default XOSC start-up delay: the guide gives no reason to change it | OK |
| USB series resistors (p.15, §5.1) | "require 27 Ω series termination resistors … placed close to the chip" | R266/R267 are **22 Ω** and sit at the **hub** end: (34.4, 28.5/29.7), about 1.7–2 mm from CH334R pins 3/4. The MCU side of each resistor is **52 mm (D+) and 42 mm (D−)** of trace, 2 vias each. 27 Ω 0402 is Extended at JLC (C25100, checked). This is an on-board, 12 Mbit/s link: 50 mm is about 0.3 ns against 4–20 ns FS edges, so the line is electrically short and placement doesn't matter. 22 vs 27 Ω shifts the source impedance by about 5 Ω. It will work, but it isn't what the guide says | Deviation-acceptable |
| USB pull-ups/downs (p.15) | None needed on the RP2350 side | None | OK |
| USB impedance (p.15) | 90 Ω differential over unbroken GND (2-layer 1 mm example) | The MCU link is FS and on-board only; the upstream pair was done at about 90 Ω on the 4-layer board (review 2) | OK |
| RUN button (p.18 §5.4; App.B) | RUN → SW2 → **R4 1 kΩ** → GND. No external pull-up, no cap | RUN → SW7 → R303 1 kΩ → GND. TP5 on RUN. RUN is 55 mm long with 2 vias, which is fine | OK |
| SWD (p.17–18, §5.3) | SWCLK/SWDIO brought out (header or JST) with GND | TP1 SWCLK, TP2 SWDIO, TP3 GND, TP4 3V3, TP5 RUN (bare pads, pogo/solder) | OK |
| GPIO assignment (App.B pinout) | QFN-80: GPIO40–47 are the ADC pins (53–60) | Checked pad by pad: GPIO42/43/45/46/47 → BTN5/4/1/2/3 (pins 53/54/56/57/58), GPIO44 → LED gate (pin 55), GPIO8/13 → ENC_B/A (pins 6/12), J4 → GPIO14–39. All match the RP2350B pinout | OK |
| GPIO default pulls (p.11, §3.2) | "the default state of GPIO0 is to be pulled low at power-up" (applies to all GPIO) | GPIO44 → 2N7002 gate is held off, so the WS2812 DIN idles high through its 1 kΩ to 5 V until firmware runs. Harmless. Buttons and encoder use internal pull-ups set by firmware | OK |
| Errata E9 / 5 V tolerance / ADC pins | **Not covered by this guide** | The design uses pull-ups only (per the RP2350 datasheet E9 note, no pull-down scanning). J4 stays on GPIO0–39. GPIO40–47 only see 3.3 V signals. Nothing on the board puts 5 V on a GPIO | n/a (not in guide) |
| Board tech (p.4, §1.3) | 2-layer, top-side-only, 0402 needed at 0.4 mm pitch | 4-layer, top-side assembly, 0402 | OK |

## FIX items

1. **Add a 100 nF on DVDD pin 51.**
   - **Now:** pin 51's nearest cap is C151, 5.1 mm away pad to pad and about 11 mm along the 0.5 mm B.Cu +1V1 spine. The guide wants one right at each power pin; RPi's only accepted compromise is one cap shared by pins 68/69.
   - **Where it fits:** the F.Cu area directly above the pin is free.
   - **Change:**
     - In `critical.py`/`gen_board.py`, move C151 (or add one more 100 nF) to about (10.8, 26.95), vertical, with pad 1 (+1V1) at y ≈ 26.47. Stub it straight to pin 51 (10.8, 25.91).
     - Put pad 2 (GND) at y ≈ 27.43, into the existing GND via at (10.95, 28.0) or a new one just above.
     - Re-run DRC afterwards.
   - **Pin 32:** there's no room beside it (R231 and the XOUT trace, the SWD/RUN escapes). I'd accept it; pin 10's cap is about 11 mm of trace away and pin 51's would then be local. If you ever move the crystal block 1 mm right, put a 100 nF at pin 32 too.

2. **Confirm the L1 dot lands on the +1V1 pad (pad 2, the end nearer U3/C165 at y = 23.0) before paying for assembly.**
   - **Why it's in doubt:** the easyeda footprint has a visible silk dot by pad 2, and also a small pin-1 circle by pad 1 (VREG_LX). JLC places by its library pin 1 and rotation (270° in `cpl.csv`). Nothing in the repo shows which terminal Abracon's dot marks. The guide makes this the one thing that "massively" affects the regulator.
   - **Change:**
     - Pull the AOTA-B201610S3R3-101-T drawing and see whether the dot marks terminal 1.
     - In JLC's DFM/placement preview, check the 3D model's dot is at the +1V1 pad.
     - If it isn't, flip the L1 rotation in the CPL by 180°. Don't re-wire.
     - Add an order note: "L1 polarity dot toward C165 (+1V1)".
     - Remove the contradicting marker from the footprint so the silk shows only the +1V1 dot.

## Deviations accepted (no change needed, listed so they're a conscious choice)

- USB series resistors are 22 Ω at the hub, not 27 Ω "close to the chip". It's electrically irrelevant for a 50 mm FS link, and 27 Ω is an Extended part. If you want strict compliance for free, swap R266/R267 onto the MCU end of the link: the 50 mm run is on B.Cu under U1, so they would go near pins 66/67 where space allows. Otherwise leave them.
- Several +3V3 caps sit 9–21 mm from their pins. This is acceptable because every +3V3 pin has its own via to the solid In2 plane, and the high-activity QSPI_IOVDD/USB_OTP_VDD pins sit 2 mm from C164 (4.7 µF). The refs (C115, C169, …) suggest one cap per pin, but the caps don't sit at their pins; don't read the refdes as meaning they're local.

## Not guide items, noticed in passing

- `docs/bom.md` is stale: it still lists an AMS1117, D4 1N4148W and old refs. `build/jlcpcb/bom.csv` is current (ME6211, R301/R302 etc.). Regenerate bom.md so nobody orders from the wrong one.
- In `bom.csv`, SW6 and SW7 are both commented "RESET" (SW6 is BOOTSEL). This is cosmetic.
- The .kicad_pcb still has no `(stackup)` section (thickness 1.6 mm). The USB_UP pair widths assume JLC04161H-7628, so choose it on the order form.
