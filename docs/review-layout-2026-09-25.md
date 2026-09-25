# Layout review, 2026-09-25

Same setup as the [circuit review](review-2026-09-25.md): an independent
reviewer measured the routed board (commit e51b12c) with pcbnew scripts.
Connectivity was clean (0 unconnected, DRC clean apart from cosmetics); the
findings are about **layout quality**, i.e. what the autorouter did badly.

## Blockers
1. **RP2350B exposed pad (U1.81, the only GND pin) has no GND vias**: it
   reaches ground through a 0.15 mm trace, PGND, one 0.45 mm via and a
   14 mm² F.Cu island. Needs a via array into In1.
2. **Core regulator layout ignores RPi guidance**: nearest cap to VREG_VIN
   (pin 64) is 20 mm away by trace; +1V1 runs 25 mm from L1 before its first
   cap; the 4.7 µF output caps are 44 mm away through 3 vias; VREG_FB is 35 mm
   from L1.
3. **USB_UP_D± (480 Mbit/s) not routed as a pair**: D+ on B.Cu, D- on
   F.Cu/In2, about 2 mm apart. The B.Cu side's reference (In2) is a fragmented
   3V3 island crossed by 13 traces. 2.8 mm length mismatch, 2 vias each, D-
   under H1's screw head. Uncoupled ≈130 Ω diff (target 90).
4. **J4 still a placeholder** (vertical THT vs the real right-angle SMD part).

## Should fix
- +3V3 fed only through 0.15 mm traces (In2 pour is 7 % of the board, eaten
  by the key-matrix bus); ~0.2 Ω to the far loads.
- MCU decoupling 7–14 mm from pins (target ~2 mm).
- USB_MCU_D- 0.1 mm from L1's switching pad.
- Y1 crystal: XOUT runs under the crystal, 14.75 mm + 3 vias to R4, XIN
  12 mm.
- +5V 0.3 mm everywhere (60–80 mm runs, part on an inner layer): ~0.1–0.15 V
  drop at 1 A.
- Stitching vias inside pads of assembled parts (Y1, J1, C4, C5): solder
  wicking.
- Hub decoupling 6–12 mm from VDD33; hub GND pin 14 on a 0.112 mm trace.
- USB_A1_D- under J2's shell; USB_A1 pair splits layers.

## Nice to have
Single-spoke thermals (Y1, Y2, C32); silkscreen cleanup; WS2812 pads are
1.27 mm pitch with 0.22 mm gaps (easy to bridge by hand); define the JLC
stack-up (JLC04161H-7628) for impedance control; USB-C VBUS/GND pad gap
0.1 mm (standard footprint).

## Verified OK
In1 GND plane solid (~90 % of the board, no traces); all geometry within
JLCPCB 4-layer limits (min track 0.112 mm, min clearance 0.10 mm); copper
≥0.3 mm from edges; vias tented; stitching ~2.5 mm pitch; USB_A2 pair
coupled on F.Cu (≈90 Ω est.).

## Plan
Critical nets first, by hand, locked; autorouter only for the rest (key
matrix, buttons, LEDs): EP via array; RPi-style regulator loop (C at
VREG_VIN, L1 and 4.7 µF at pins 62-65); per-pin decoupling routes; crystal
direct; USB_UP as a coupled F.Cu pair clear of H1; wide 5 V / 3V3 feeds;
keepouts under connector shells; stitching never inside pads.
