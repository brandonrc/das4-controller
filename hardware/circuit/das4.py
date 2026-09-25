#!/usr/bin/env python3
"""das4-controller circuit, written with SKiDL.

    make netlist        # -> hardware/das4-controller.net

Block diagram:

    USB-C (to PC) -> CH334R USB 2.0 hub -> USB-A port 1  (J2)
                                         -> USB-A port 2  (J3)
                                         -> RP2350B       (port 3; port 4 unused)

    RP2350B GPIO -> 26 x key matrix (J4), 5 buttons, encoder A/B, 3 lock LEDs

Every JLCPCB-assembled part carries its LCSC number in the "LCSC" field, which
ends up in the BOM. Parts come from:
  - hardware/lib/jlc.kicad_sym  (fetched from LCSC with easyeda2kicad, so
    symbol pins and footprint pads always agree)
  - KiCad's stock "Device" library for plain Rs, Cs and LEDs
References:
  - RP2350 core: Raspberry Pi "Hardware design with RP2350" minimal design
  - Hub: WCH CH334/CH335 datasheet v2.91, section 6.1 (bus powered)
"""
import os
import sys

from skidl import (KICAD9, Net, Part, generate_netlist, lib_search_paths,
                   set_default_tool)

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
JLC = os.path.join(HW, "lib", "jlc.kicad_sym")

set_default_tool(KICAD9)  # KiCad 10 uses the same library format
lib_search_paths[KICAD9].append(os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols"))

# ---------------------------------------------------------------------------
# GPIO assignment. Any RP2350 GPIO can do any of these jobs, so this table is
# the only thing to change when layout wants a different pin order.
# J4 pin k -> GPIO(40 - k): pin 1 -> GPIO39 ... pin 26 -> GPIO14. That order
# follows the RP2350B's pins round the package, and J4's pins run in order
# too, so the 26 lines fan out to J4 without crossing each other. It also
# keeps them off GPIO40-47, which (unlike GPIO0-39) are not 5 V tolerant.
J4_GPIO = [40 - k for k in range(1, 27)]
# Buttons and the LED data line sit on GPIO42-47. Those are the RP2350B's
# ADC pins (not 5 V tolerant), which is fine for buttons/LED but keeps J4 on
# 5 V-tolerant pins. With U1 rotated 90 degrees on the board they face up,
# towards the buttons.
BUTTON_GPIO = [45, 46, 47, 43, 42]     # SW1..SW5
ENC_A_GPIO, ENC_B_GPIO = 9, 10
LED_DATA_GPIO = 44                     # WS2812 chain: NUM -> CAPS -> SCROLL
# spare: GPIO0-8, GPIO11-13, GPIO40-41

# ---------------------------------------------------------------------------
R0402 = "Resistor_SMD:R_0402_1005Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"

# value -> LCSC basic parts (all checked in stock, see docs/bom.md)
RES = {"0": "C17168", "22": "C25092", "33": "C25105", "330": "C25104",
       "1k": "C11702", "5.1k": "C25905", "10k": "C25744"}
CAP = {"100n": ("C1525", C0402), "1u": ("C52923", C0402), "4.7u": ("C23733", C0402),
       "15p": ("C1548", C0402), "10u": ("C19702", C0603), "22u": ("C45783", C0805)}


def lcsc(part, code):
    part.fields["LCSC"] = code
    return part


def hand(part):
    """Soldered by hand: kept out of the JLCPCB BOM/CPL (no Extended fee).
    The LCSC number stays so docs/bom.md can list what to buy."""
    part.fields["Assembly"] = "hand"
    return part


def jlc(name, ref=None, code=None, value=None):
    p = Part(JLC, name, ref=ref) if ref else Part(JLC, name)
    if value:
        p.value = value
    if code:
        lcsc(p, code)
    return p


def R(value, a, b, ref=None):
    kw = {"ref": ref} if ref else {}
    p = lcsc(Part("Device", "R", value=value, footprint=R0402, **kw), RES[value])
    p[1] += a
    p[2] += b
    return p


def C(value, a, b=None, ref=None):
    code, fp = CAP[value]
    kw = {"ref": ref} if ref else {}
    p = lcsc(Part("Device", "C", value=value, footprint=fp, **kw), code)
    p[1] += a
    p[2] += b if b is not None else gnd
    return p


# ---------------------------------------------------------------------------
gnd = Net("GND")
vbus = Net("+5V")          # from the PC, via USB-C
v33 = Net("+3V3")
v11 = Net("+1V1")          # RP2350 core, from its on-chip switching regulator

# --- USB-C upstream --------------------------------------------------------
usb_up_dp, usb_up_dm = Net("USB_UP_D+"), Net("USB_UP_D-")
j1 = jlc("TYPE-C-31-M-12", "J1", "C165948", "USB-C")
# Only the A4/B9 VBUS pair is wired: B4/A9 sits boxed in by SW4's leg with no
# room to escape. A USB-C plug ties all four VBUS contacts together, so either
# orientation reaches A4/B9 (2 contacts, ~1.25 A each: plenty here).
vbus += j1["A4B9"]
gnd += j1["A1B12"], j1["B1A12"], j1["EH"]
usb_up_dp += j1["A6"], j1["B6"]
usb_up_dm += j1["A7"], j1["B7"]
R("5.1k", j1["A5"], gnd)   # CC1/CC2 pull-downs: we're a USB device (UFP)
R("5.1k", j1["B5"], gnd)
C("22u", vbus)
C("100n", vbus)


# No separate ESD chips: the CH334R has 6 kV ESD protection on all its USB
# pins (datasheet, features), and the RP2350B sits behind the hub.


# --- 3.3 V regulator (hub + MCU + flash, ~150-200 mA) ------------------------
# ME6211: ~0.1 V dropout and stable with ceramic caps. (An AMS1117 would be a
# Basic part but drops out when VBUS sags, e.g. hot-plugging a USB-A device,
# which would brown out the hub and MCU; design review 2026-09-25.)
ldo = jlc("ME6211C33M5G-N", "U4", "C82942")
vbus += ldo["VIN"], ldo["CE"]
gnd += ldo["VSS"]
v33 += ldo["VOUT"]
C("10u", vbus)
C("10u", v33)
C("10u", v33)

# --- CH334R USB 2.0 hub ------------------------------------------------------
# Powered from 3.3 V on both V5 and VDD33 (datasheet 6.1: cooler, and our LDO
# is there anyway). XI/XO have built-in ~16 pF load caps: no external caps.
hub = jlc("CH334R", "U2", "C4154405")
v33 += hub["V5"], hub["VDD33"]
gnd += hub["GND"]
usb_up_dm += hub["DMU"]
usb_up_dp += hub["DPU"]
C("1u", hub["V5"])
C("100n", hub["VDD33"])
C("10u", hub["VDD33"])
xh = jlc("ABM8-272-T3_C20625731", "Y2", "C20625731", "12MHz")
hub["XI"] += xh[1]
hub["XO"] += xh[3]
gnd += xh[2], xh[4]
# RESET#/CDP left open (internal pull-up), port 4 unused

# --- USB-A downstream ports --------------------------------------------------
# VBUS straight from the PC's 5 V: the PC's port already limits current, so
# no polyfuses (they're JLCPCB Extended parts).
for ref, n, dm, dp in (("J2", 1, "DM1", "DP1"), ("J3", 2, "DM2", "DP2")):
    port_dp, port_dm, port_vbus = Net(f"USB_A{n}_D+"), Net(f"USB_A{n}_D-"), vbus
    j = hand(jlc("AF90-WJDG", ref, "C456018", f"USB-A {n}"))
    # pins: 1 VCC, 2 D-, 3 D+, 4 GND, 5 shield
    port_vbus += j[1]
    gnd += j[4], j[5]
    port_dp += j[3], hub[dp]
    port_dm += j[2], hub[dm]
    C("22u", port_vbus)
    C("100n", port_vbus)

# --- RP2350B -----------------------------------------------------------------
# Parts around the MCU get references that encode the MCU pin they serve
# (C164 = the cap on pin 64, R231 = the resistor on pin 31, ...), so board
# placement can put each one next to its pin.
mcu = jlc("RP2350B_C42415655", "U1", "C42415655", "RP2350B")
gnd += mcu["GND"], mcu["VREG_PGND"]
for n in (5, 15, 24, 29, 41, 50, 60, 76):      # IOVDD, 100 nF each
    v33 += mcu[n]
    C("100n", mcu[n], ref=f"C{100 + n}")
for n in (59, 68, 69):                          # ADC_AVDD, USB_OTP_VDD, QSPI_IOVDD
    v33 += mcu[n]
    C("100n", mcu[n], ref=f"C{100 + n}")
v33 += mcu["VREG_VIN"]                          # pin 64
C("4.7u", mcu["VREG_VIN"], ref="C164")
C("10u", v33, ref="C190")                       # bulk
vreg_avdd = Net("VREG_AVDD")                    # pin 61: 33R + 4.7u RC filter
R("33", v33, vreg_avdd, ref="R161")
vreg_avdd += mcu["VREG_AVDD"]
C("4.7u", vreg_avdd, ref="C161")
# Core regulator: VREG_LX -> 3.3 uH -> +1V1. RPi wants the inductor's
# polarity dot on the +1V1 end. This footprint (easyeda2kicad) puts the dot on
# pad 2, so pad 2 goes to +1V1 (design review 2026-09-25: RPi's own board has
# the dot next to +1V1).
lx = Net("VREG_LX")
lx += mcu["VREG_LX"]
l1 = jlc("AOTA-B201610S3R3-101-T", "L1", "C42411119", "3.3uH")
l1[2] += v11
l1[1] += lx
v11 += mcu["VREG_FB"]                           # pin 65
C("4.7u", v11, ref="C165")                      # regulator output cap, at L1
C("4.7u", v11, ref="C166")                      # 2nd, at a DVDD pin away from the LX loop
for n in (10, 32, 51):                          # DVDD, 100 nF each
    v11 += mcu[n]
    C("100n", mcu[n], ref=f"C{100 + n}")

# Crystal: XIN direct, XOUT through 1k, 15 pF load caps (RPi minimal design)
xm = jlc("ABM8-272-T3_C20625731", "Y1", "C20625731", "12MHz")
xin, xout_x = Net("XIN"), Net("XOUT_XTAL")
xin += mcu["XIN"], xm[1]
xout_x += xm[3]
gnd += xm[2], xm[4]
R("1k", mcu["XOUT"], xout_x, ref="R231")
C("15p", xin, ref="C230")
C("15p", xout_x, ref="C231")

# QSPI flash, 16 MB
fl = jlc("W25Q128JVSIQTR", "U3", "C97521", "W25Q128JVS")
qspi_ss = Net("QSPI_SS")
qspi_ss += mcu["QSPI_SS"], fl[1]   # pin 1 = /CS
Net("QSPI_SCLK").connect(mcu["QSPI_SCLK"], fl["CLK"])
Net("QSPI_SD0").connect(mcu["QSPI_SD0"], fl["DI"])
Net("QSPI_SD1").connect(mcu["QSPI_SD1"], fl["DO"])
Net("QSPI_SD2").connect(mcu["QSPI_SD2"], fl["IO2"])
Net("QSPI_SD3").connect(mcu["QSPI_SD3"], fl["IO3"])
v33 += fl["VCC"]
gnd += fl["GND"]
C("100n", fl["VCC"], ref="C300")
R("10k", v33, qspi_ss, ref="R301")

# BOOTSEL (QSPI_SS -> 1k -> button -> GND) and RUN (reset) buttons
boot = Net("USB_BOOT")
R("1k", qspi_ss, boot, ref="R302")
sb = jlc("TS-1187A-B-A-B", "SW6", "C318884", "BOOTSEL")   # pads 1-2 | 3-4
sb[1] += boot
sb[2] += boot
gnd += sb[3], sb[4]
run = Net("RUN")
run += mcu["RUN"]
run_btn = Net("RUN_BTN")
sr = jlc("TS-1187A-B-A-B", "SW7", "C318884", "RESET")
sr[1] += run
sr[2] += run
run_btn += sr[3], sr[4]
R("1k", run_btn, gnd, ref="R303")

# USB from hub port 3, series resistors at the MCU (RPi uses 27R; 22R is a
# JLCPCB Basic part and fine at full speed)
mcu_dp, mcu_dm = Net("USB_MCU_D+"), Net("USB_MCU_D-")
mcu_dp += hub["DP3"]
mcu_dm += hub["DM3"]
R("22", mcu_dp, mcu["USB_DP"], ref="R267")
R("22", mcu_dm, mcu["USB_DM"], ref="R266")

# SWD debug pads (not assembled: bare copper)
for ref, sig in (("TP1", mcu["SWCLK"]), ("TP2", mcu["SWDIO"]), ("TP3", gnd), ("TP4", v33),
                 ("TP5", run)):
    tp = Part("Connector", "TestPoint", ref=ref, footprint="TestPoint:TestPoint_Pad_D1.5mm")
    tp[1] += sig


def gpio(n):
    for p in mcu.pins:
        if p.name == f"GPIO{n}" or p.name.startswith(f"GPIO{n}_"):
            return p
    raise KeyError(f"GPIO{n}")


# --- Key matrix connector J4 --------------------------------------------------
# 26 lines straight to GPIO; firmware decides rows vs columns. Pitch/type are
# still unknown (placeholder footprint), and it's hand-fitted: no LCSC part.
# Before plugging in, check that no J4 pin carries 5 V (see docs/design.md).
j4 = Part("Connector_Generic", "Conn_01x26", ref="J4", value="Key matrix",
          footprint="Connector_PinSocket_1.00mm:PinSocket_1x26_P1.00mm_Vertical")
for i, g in enumerate(J4_GPIO, start=1):
    Net(f"KM{i}").connect(j4[i], gpio(g))

# --- Buttons (internal pull-ups, active low) --------------------------------
for i, g in enumerate(BUTTON_GPIO, start=1):
    sw = hand(jlc("KH-6X6X5H-STM", f"SW{i}", "C2837531", f"Button {i}"))
    btn = Net(f"BTN{i}")
    btn += gpio(g), sw[1], sw[2]
    gnd += sw[3], sw[4]

# --- Volume encoder (no switch; A/B with internal pull-ups, C to GND) -------
enc = hand(jlc("EC12E24204A2", "ENC1", "C351238", "EC12E24204A2"))
Net("ENC_A").connect(enc["A"], gpio(ENC_A_GPIO))
Net("ENC_B").connect(enc["B"], gpio(ENC_B_GPIO))
gnd += enc["C"], enc["D"], enc["E"]

# --- Lock LEDs: 3 x WS2812D (5 mm THT, RGB), any colour from firmware -------
# One GPIO drives the chain NUM -> CAPS -> SCROLL. WS2812s want data above
# 0.7 x VDD = 3.5 V at 5 V, more than a 3.3 V GPIO gives. Level shift with a
# JLCPCB-Basic 2N7002 (open drain) and a 1k pull-up to 5 V. This INVERTS the
# signal: firmware must drive the data line inverted (QMK: WS2812_EXTERNAL_PULLUP,
# or invert the pin in the PIO program).
q = jlc("2N7002", "Q1", "C8545")
din = Net("LED_DIN1")
Net("LED_DATA_N").connect(q["G"], gpio(LED_DATA_GPIO))
gnd += q["S"]
din += q["D"]
R("1k", vbus, din)
for i, label in enumerate(("NUM", "CAPS", "SCROLL"), start=1):
    led = hand(jlc("WS2812D-F5-12MA-C1", f"D{i}", "C4154875", f"{label} (RGB)"))
    vbus += led["VDD"]
    gnd += led["GND"]
    din += led["Din"]
    C("100n", led["VDD"])
    din = Net(f"LED_DIN{i + 1}") if i < 3 else None
    if din is not None:
        din += led["Dout"]

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HW, "das4-controller.net")
    generate_netlist(file_=open(out, "w"))
    print("wrote", out)
