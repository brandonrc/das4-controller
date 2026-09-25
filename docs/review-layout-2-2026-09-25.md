# Layout review 2: das4-controller (board as of 16007bf, 2026-09-25)

Method: I copied the board to the scratchpad, refilled the zones, and ran pcbnew scripts plus kicad-cli DRC. I rendered each layer and checked the regulator section against the RP2350 datasheet (section 6.3.8, "External components and PCB layout requirements") and "Hardware design with RP2350". Coordinates are board mm (origin 100,150, +Y up).

DRC: 0 unconnected. 6 errors: 3 starved thermals (Y2.2, Y2.4, J2.4 on B.Cu), and 3 malformed courtyards on D1–D3, which means those three LEDs are silently left out of the courtyard-overlap check. 59 silkscreen warnings.

## Verdict: **fix first**

The MCU corner rework dealt with most of the first review. Three things still stop this going to the fab:
- J4 is still a placeholder.
- The regulator ignores a "must" in the RP2350 datasheet: the inner planes run solid under L1 and VREG_LX.
- VBUS and key-matrix traces run under the grounded USB-A shells.

Everything else is cheap to fix while you're in there.

## Previous review: status

| # | Finding (review 1) | Status | Evidence now |
|---|---|---|---|
| B1 | EP has no GND vias | **Resolved** | 3×3 array of 0.5/0.25 vias in U1.81, straight into the solid In1 |
| B2 | Regulator ignores RPi layout | **Partial** | C164 (CIN) is 1.2 mm from pins 64 and 62. C165 (COUT) is next to L1.2 (1.8 mm). FB is a Kelvin tap at C165+ (2.8 mm), not under L1. C161 has its own GND via. **But** there's no plane cut-out under L1/LX, RUN runs under L1, and LX is a 0.15 mm trace under the L1 body (see Blockers) |
| B3 | USB_UP not a pair | **Resolved** | Coupled on F.Cu, 0.25/0.15 mm, ≈86–90 Ω on JLC04161H-7628 once solder mask and the 0.25 mm coplanar pour are allowed for. Centreline over solid In1 the whole way. Only vias are the D− hop at J1. D+ 56.0 mm vs D− 54.5 mm (≈10 ps). At least 3.2 mm from H1 |
| B4 | J4 is a placeholder | **Not resolved** | Still `PinSocket_1x26_P1.00mm_Vertical` on B.Cu; design.md says pitch and type are unknown |
| S | +3V3 only on 0.15 mm traces | **Resolved** | In2 +3V3 is one piece covering 81 % of the board (In1 GND covers 90 %) |
| S | MCU decoupling 7–14 mm away | **Partial** | Pins 5, 41, 59, 60 and 64 have caps right at the pin. IOVDD pins 15, 24, 29, 50, 68, 69 and 76 reach their caps only through a via, the In2 plane and 8–20 mm of distance. DVDD pins 10, 32 and 51 are 15.5, 24 and ≈12 mm of trace from the nearest +1V1 cap |
| S | USB_MCU_D− 0.1 mm from L1 | **Resolved** | USB_DP/DM now leave inward and run on B.Cu under the chip |
| S | Y1 crystal traces long | **Partial** | XIN is 4.9 mm and XOUT 6.4 mm, no vias. **But** the autorouter put KM18 through C230's and C231's pad gaps, and KM15/KM16 vias sit 0.2–0.5 mm from XIN/XOUT (see Should fix) |
| S | +5V 0.3 mm | **Resolved** | 0.5 mm everywhere (0.375 mm into C12). About 50 mΩ from J1 to J2, 70 mΩ to J3 |
| S | Vias inside pads | **Partial / worse** | Now 22 vias touch pads: 20 shared decoupling GND vias each overlap two 0402 pads by 0.01 mm; Y1.2 by 0.05 mm, Y2.2/Y2.4 by 0.09 mm, L1.2 is 0.008 mm off the pad; plus 9 open vias in the EP |
| S | Hub decoupling far; GND pin 14 on 0.112 mm | **Partial** | C6/C7 are within 1.5 mm of pins 12/13, but connect through plane vias rather than directly. Pin 14 still leaves on a 0.112 mm neck, though pour spokes now also reach it |
| S | USB_A1 under J2's shell, pair splits layers | **Not resolved** | Each line still has a via to B.Cu. On B.Cu the two lines are 1.4 mm apart (uncoupled, ≈125 Ω diff) and referenced to the 3V3 plane. Mismatch 3.4 mm (D− 11.5, D+ 8.1); D− hooks round the D+ via at (33.1–33.9, 35.5) |
| N | Single-spoke thermals | Partial | Y2.2, Y2.4 and J2.4 (B.Cu) are starved |
| N | Silkscreen | Not | 23 silk-over-copper. The **U1** label sits on U3 (2.1, 21.0), **U3** on L1, **L1** over U1 pins 62–65, **Y2** over U2 pins 12/13, **TP1** over TP5 |
| N | WS2812 pads 1.27 mm / 0.22 mm gap | Not | Footprint unchanged |
| N | Define the JLC stackup | Not | The .kicad_pcb has no `(stackup)` section |
| N | USB-C VBUS/GND pads 0.1 mm apart | Not | Footprint unchanged (stock HRO footprint; acceptable) |

## New findings

### Blocker

1. **Solid planes under L1 and VREG_LX, and a signal under L1** (L1 at 2.34, 24.0)
   - **What the datasheet says** (§6.3.8.1): "For a multi-layer board (4 or more layers) please cut away any copper immediately underneath L/VREG_LX". It also says to cut copper under the inductor on the top layer, and that "these guidelines must be strictly followed".
   - **What I measured:**
     - In1 GND is 96 % filled under the L1 body and 100 % under the LX strip. In2 +3V3 is 93 % and 100 %.
     - RUN runs on B.Cu at x = 1.9–2.3 mm, from y 19.1 to 30.2, i.e. right under L1.
     - The +1V1 spine on B.Cu (x = 3.2 mm, 0.5 mm wide) also runs under L1.
   - **Fix:**
     - Add a keep-out rule area (tracks, vias, pours) on In1, In2 and B.Cu covering L1 plus about 0.3 mm, and the LX trace from pin 63 to L1.1.
     - Move RUN out of that area. The +1V1 spine can start at the via (3.35, 22.35) heading away from L1.
     - After the change, check the In2 3V3 path to pin 64 still exists.

2. **J4 footprint unknown** (carried over): don't order until the connector pitch, type and position are confirmed. The 26 key-matrix nets are the board's reason to exist.

3. **VBUS and key-matrix traces under the USB-A metal shells**
   - **Measured:** F.Cu length inside the J3 courtyard: **+5V 13.5 mm** (x = 37.49, y 16–22.6, between the pin row and the shell tabs). Inside J2: KM26 13.4 mm, KM23 11.1 mm, +5V 4.0 mm.
   - **Risk:** the shell is GND and sits on the solder mask. One scuff shorts the host's VBUS to GND, or a matrix line to GND.
   - **Fix:** keep-out on F.Cu over both shell footprints (x > 35.4 inside the J2 and J3 courtyards). Route +5V from J2.1 to J3.1 on B.Cu, on the x < 35.3 side. Move KM23 and KM26 off that area.

### Should fix

1. **DVDD decoupling and the second 4.7 µF**
   - **Measured:** 100 nF caps C110, C132 and C151 sit in a column at x = 15.9, y 28–30. Trace paths from DVDD pins 10, 32 and 51 are about 32, 24 and 12 mm, much of it the 0.5 mm B.Cu spine. C166 (the second COUT) is 25–35 mm of trace from every DVDD pin.
   - **Guidance:** RPi wants 100 nF at every power pin, and the second 4.7 µF "on the bottom edge of the package", away from LX/COUT.
   - **Fix:**
     - Put a 100 nF at pin 10 (≈10.8, 15.2; there's a 1.4 mm strip between U1 and the ENC1 courtyard) with C166 beside it.
     - Put one at pin 32, on the right side, when rerouting around Y1.
     - Same idea for IOVDD: pins 15, 24 and 29 have no cap within 6.5 mm.

2. **Key-matrix lines through the crystal block**
   - **Measured:**
     - KM18 (F.Cu) runs at y = 18.3 between C230's pads, 0.125 mm from each.
     - It then goes up x = 22.50, between C231's pads, 0.8 mm from Y1.3.
     - The KM15 via at (17.20, 22.44) is 0.19 mm from the end of the XOUT trace; the KM16 via at (17.32, 19.99) is 0.46 mm from XIN.
   - **Fix:** F.Cu keep-out over Y1, C230, C231 and R231 plus 0.5 mm, then reroute KM18 on B.Cu (In1 shields it there).

3. **Regulator GND should join main GND at one point** (datasheet: "only connect to main GND at one point").
   - **Measured:** the C164/C165 GND pads are tied to the F.Cu pour by thermal spokes (0.19/0.15 mm² of overlap), in addition to their two vias at (3.99/4.93, 25.1).
   - **Fix:** F.Cu pour keep-out around the C164/C165/L1 block, so that CIN/COUT GND reaches main GND only through that via pair.

4. **LX trace**
   - **Measured:** 0.15 mm wide, 4.75 mm long.
   - **Route:** it runs between both caps' pads with 0.125 mm clearance, then 1 mm under the L1 body into pad 1 from below.
   - **Fix:** make it 0.3–0.4 mm and bring it into L1.1 from outside the body. Rotating or moving L1 so pad 1 faces pin 63 would make this simpler.

5. **EP paste and vias**
   - **Measured:** U1.81 paste is one 3.4 × 3.4 aperture (100 % coverage) over 9 untented, unplugged 0.25 mm vias. That means voids and solder wicking, and on a 0.4 mm pitch QFN, a risk that the part floats and opens pins.
   - **Fix:** a 2×2 or 3×3 windowpane at 50–65 % coverage that sits between the vias. Alternatively order via-in-pad epoxy-filled and capped.

6. **Vias overlapping pads**
   - **Measured:** the 20 shared GND vias in the decoupling columns (x = 16.38 and x = 5.82) each overlap two pads by 0.01 mm. That leaves a mask tent of about 0.31 mm over a 0.2 mm hole.
   - **Fix:** move each via 0.35 mm outboard of the pad ends (x ≈ 16.75 / 5.45) with a short neck. Pull the Y1.2 via at (21.90, 19.95) out to x ≥ 22.1, and the Y2 vias at (28.93, 23.71) and (25.07, 26.69) likewise.

7. **Signals under the mounting-hole screw heads**
   - **Measured:** non-GND copper 0.3–0.9 mm from the 2.7 mm hole edge.
     - H1: KM10/KM11 on B.Cu at 1.65–1.94 mm from the hole centre.
     - H2: KM13, KM21 and KM23 at 1.65–1.8 mm.
   - An M2.5 head or standoff is about 4.5–5 mm across, so these traces sit under the metal.
   - **Fix:** a round keep-out of radius 3 mm on F.Cu and B.Cu around H1–H3. A plated GND ring is optional.

8. **USB_A1**
   - **Fix:** route +5V to J2.1 on B.Cu (or from the outside). That frees F.Cu so D± can run as a coupled 0.2/0.12 pair straight to J2.2/J2.3, like USB_A2 (which is fine at ≈90 Ω, 1.5 mm mismatch). That drops both vias and the 3.4 mm skew.

### Nice to have

- **Foreign vias beside USB_UP:** the KM20 via at (26.88, 50.32) is 0.16 mm from USB_UP_D−, and its In1 anti-pad eats under the trace edge. The KM9 via at (25.27, 60.16) is 0.3 mm from D+. Move both at least 0.75 mm clear.
- **R266/R267** (22 Ω) sit at the hub, 30 mm from the RP2350. The guide says to put them "close to RP2350". It doesn't matter electrically at 12 Mbit/s, but it's the documented rule.
- **LDO:** U4.5 (+3V3) reaches the plane through a single 0.45/0.2 via at (29.75, 80.70). The output caps C4/C5 are 4–5 mm away through the planes. Add 2 more vias and put C4 right at pin 5.
- **Stackup:** add JLC04161H-7628 to the board setup and choose it (with impedance control) on the order form. Otherwise the ≈90 Ω pair widths are only an assumption.
- **Vias:** 94 vias have 0.2 mm drills. Pick JLC's matching "min via hole" option and check whether it adds cost. Everything else is well inside JLC's 4-layer limits: minimum track 0.112 mm, clearance 0.10 mm, annular ring ≥ 0.1 mm, copper ≥ 0.3 mm from the edge.
- **D1–D3 courtyards:** fix them so the courtyard checks run on the LEDs.
- **Silkscreen:** move the refdes labels listed above. Don't rely on the silk for L1's dot; confirm the polarity in JLC's DFM/placement preview. The footprint's r = 0.13 dot is at pad 2 = +1V1, as the circuit review intended.
- **Test points:** add pads for +1V1 and +5V, to check the regulator at bring-up.
- **B4A9:** the USB-C VBUS pad B4A9 is left floating. Tie it to +5V if routing allows.
- **CPL/BOM** (build/jlcpcb, which is current):
  - All 58 assembled parts are present; the hand-solder parts are correctly left out.
  - Gerbers and drill files share the aux origin (100, 150), consistent.
  - The BOM comment for SW6 reads "RESET" (it's BOOTSEL); cosmetic only.
  - Check rotations for U1 (90), U2 (90), J1 (180), L1 (270), Q1, U4 and Y1/Y2 in JLC's preview.

## Verified OK
- In1 is solid GND under every USB and crystal centreline.
- Stitching vias are about 2.5 mm apart.
- Main VREG loop: CIN at the pins and COUT at L1, both returning to PGND in about 2 mm.
- The FB Kelvin tap is not under L1.
- The VREG_AVDD RC has its own GND via.
- Flash: QSPI traces are ≤ 10 mm with only 2 vias (SD2/SD3). The pull-up and BOOTSEL resistors sit at U3.
- CC pull-downs are fine.
- USB_A2 pair is fine.
- The +5V trunk is 0.5 mm.
- The encoder frame is tied to GND.

## Follow-up (same day)

Addressed in the next commit, board re-routed: 0 unconnected, 0 non-cosmetic DRC violations in all 4 router variants.

| Finding | Done |
|---|---|
| Blocker 1: planes/signals under L1 and LX | Rule area: no copper on In1, In2 or B.Cu under L1 or along LX. The +1V1 spine now leaves under U1's left pad row, and RUN is routed elsewhere |
| Blocker 2: J4 | **Open**: waiting on the connector's pitch, type and photos |
| Blocker 3: under the USB-A shells | Rule area: no F.Cu tracks or vias under either shell |
| DVDD decoupling | C110 sits right under pin 10, with GND straight into the encoder's GND pin. Encoder moved to GPIO13 (A) and GPIO8 (B) so it doesn't cross. Pins 32 and 51 still use the cap column: no room beside them |
| Crystal block | Router-only keep-out; checked afterwards that no foreign net comes within 0.2 mm of Y1, C230, C231 or R231 |
| Regulator GND at one point | Rule area: no F.Cu pour round C164/C165/L1 |
| LX trace | Now enters L1 pad 1 from outside the body, 0.25 mm wide there. It stays 0.15 mm between the two 0402 pads (0.4 mm gap), which is Raspberry Pi's own minimal-design pattern |
| EP paste over vias | 5 vias in a "+", with paste as 4 windows between them (about 50 %) |
| Vias touching pads | Decap columns at a 1.2 mm pitch, so the shared GND vias clear both pads. Plane-fanout vias no longer touch their own pad. 2 same-net cases remain: a GND via on SW3's GND pad (hand-soldered) and the SWCLK via on test pad TP1 |
| Screw heads | Rule area: nothing within 2.5 mm of H1, H2 or H3 on F.Cu or B.Cu (4.5 mm pan head plus 0.25 mm) |
| USB_A1 | Router's choice (the shell keep-out now stops F.Cu under the shell) |
| Nice-to-haves | Not done yet: USB_UP foreign vias, R266/R267 placement, extra LDO output vias, stackup definition, D1–D3 courtyards, silkscreen refdes, +1V1/+5V test pads, B4A9 |
