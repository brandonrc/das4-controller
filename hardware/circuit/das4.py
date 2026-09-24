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
# Chosen for layout: on the RP2350B, GPIO21-46 run along the package's bottom
# and right edges (towards J4 and the hub), GPIO4-13 along the left edge
# (towards the buttons, LED drivers and encoder).
J4_GPIO = list(range(21, 47))          # J4 pin 1..26 -> GPIO21..GPIO46
BUTTON_GPIO = [4, 5, 6, 7, 8]          # SW1..SW5
ENC_A_GPIO, ENC_B_GPIO = 9, 10
LED_GPIO = {"NUM": 11, "CAPS": 12, "SCROLL": 13}
# spare: GPIO0-3, GPIO14-20, GPIO47

# ---------------------------------------------------------------------------
R0402 = "Resistor_SMD:R_0402_1005Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"

# value -> LCSC basic parts (all checked in stock, see docs/bom.md)
RES = {"0": "C17168", "27": "C25100", "33": "C25105", "330": "C25104",
       "1k": "C11702", "5.1k": "C25905", "10k": "C25744"}
CAP = {"100n": ("C1525", C0402), "1u": ("C52923", C0402), "4.7u": ("C23733", C0402),
       "15p": ("C1548", C0402), "10u": ("C19702", C0603), "22u": ("C45783", C0805)}


def lcsc(part, code):
    part.fields["LCSC"] = code
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


def C(value, a, b=None):
    code, fp = CAP[value]
    p = lcsc(Part("Device", "C", value=value, footprint=fp), code)
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
vbus += j1["A4B9"], j1["B4A9"]
gnd += j1["A1B12"], j1["B1A12"], j1["EH"]
usb_up_dp += j1["A6"], j1["B6"]
usb_up_dm += j1["A7"], j1["B7"]
R("5.1k", j1["A5"], gnd)   # CC1/CC2 pull-downs: we're a USB device (UFP)
R("5.1k", j1["B5"], gnd)
C("22u", vbus)
C("100n", vbus)


def esd(ref, dp, dm):
    """USBLC6-2SC6: I/O1 = pins 1+6, I/O2 = pins 3+4, VBUS = 5, GND = 2."""
    u = jlc("USBLC6-2SC6", ref, "C7519")
    dm += u[1], u[6]
    dp += u[3], u[4]
    vbus.connect(u[5])
    gnd.connect(u[2])
    return u


esd("U5", usb_up_dp, usb_up_dm)

# --- 3.3 V regulator (hub + MCU + flash, ~200 mA) ----------------------------
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
for ref, fref, eref, n, dm, dp in (("J2", "F1", "U6", 1, "DM1", "DP1"),
                                   ("J3", "F2", "U7", 2, "DM2", "DP2")):
    port_dp, port_dm, port_vbus = Net(f"USB_A{n}_D+"), Net(f"USB_A{n}_D-"), Net(f"VBUS_A{n}")
    j = jlc("AF90-WJDG", ref, "C456018", f"USB-A {n}")
    # pins: 1 VCC, 2 D-, 3 D+, 4 GND, 5 shield
    port_vbus += j[1]
    gnd += j[4], j[5]
    port_dp += j[3], hub[dp]
    port_dm += j[2], hub[dm]
    f = jlc("SMD1206P050TF", fref, "C20799", "500mA")
    f[1] += vbus
    f[2] += port_vbus
    C("22u", port_vbus)
    C("100n", port_vbus)
    esd(eref, port_dp, port_dm)

# --- RP2350B -----------------------------------------------------------------
mcu = jlc("RP2350B_C42415655", "U1", "C42415655", "RP2350B")
gnd += mcu["GND"], mcu["VREG_PGND"]
for p in mcu["IOVDD"]:                   # 8 pins, 100 nF each
    v33 += p
    C("100n", p)
for name in ("ADC_AVDD", "USB_OTP_VDD", "QSPI_IOVDD"):
    v33 += mcu[name]
    C("100n", mcu[name])
v33 += mcu["VREG_VIN"]
C("4.7u", mcu["VREG_VIN"])
C("10u", v33)
vreg_avdd = Net("VREG_AVDD")             # 33R + 4.7u RC filter
R("33", v33, vreg_avdd)
vreg_avdd += mcu["VREG_AVDD"]
C("4.7u", vreg_avdd)
# Core regulator: VREG_LX -> 3.3 uH -> +1V1. The inductor is polarised in the
# RPi reference (pad 1 to +1V1); keep that orientation.
lx = Net("VREG_LX")
lx += mcu["VREG_LX"]
l1 = jlc("AOTA-B201610S3R3-101-T", "L1", "C42411119", "3.3uH")
l1[1] += v11
l1[2] += lx
v11 += mcu["VREG_FB"]
for p in mcu["DVDD"]:                    # 3 pins, 100 nF each
    v11 += p
    C("100n", p)
C("4.7u", v11)

# Crystal: XIN direct, XOUT through 1k, 15 pF load caps (RPi minimal design)
xm = jlc("ABM8-272-T3_C20625731", "Y1", "C20625731", "12MHz")
xin, xout_x = Net("XIN"), Net("XOUT_XTAL")
xin += mcu["XIN"], xm[1]
xout_x += xm[3]
gnd += xm[2], xm[4]
R("1k", mcu["XOUT"], xout_x)
C("15p", xin)
C("15p", xout_x)

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
C("100n", fl["VCC"])
R("10k", v33, qspi_ss)

# BOOTSEL (QSPI_SS -> 1k -> button -> GND) and RUN (reset) buttons
boot = Net("USB_BOOT")
R("1k", qspi_ss, boot)
sb = jlc("TS-1088R-02026", "SW6", "C455280", "BOOTSEL")
sb[1] += boot
sb[2] += gnd
run = Net("RUN")
run += mcu["RUN"]
run_btn = Net("RUN_BTN")
sr = jlc("TS-1088R-02026", "SW7", "C455280", "RESET")
sr[1] += run
sr[2] += run_btn
R("1k", run_btn, gnd)

# USB from hub port 3, 27R series resistors at the MCU
mcu_dp, mcu_dm = Net("USB_MCU_D+"), Net("USB_MCU_D-")
mcu_dp += hub["DP3"]
mcu_dm += hub["DM3"]
R("27", mcu_dp, mcu["USB_DP"])
R("27", mcu_dm, mcu["USB_DM"])

# SWD debug pads (not assembled: bare copper)
for ref, sig in (("TP1", mcu["SWCLK"]), ("TP2", mcu["SWDIO"]), ("TP3", gnd), ("TP4", v33)):
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
    sw = jlc("KH-6X6X5H-STM", f"SW{i}", "C2837531", f"Button {i}")
    btn = Net(f"BTN{i}")
    btn += gpio(g), sw[1], sw[2]
    gnd += sw[3], sw[4]

# --- Volume encoder (no switch; A/B with internal pull-ups, C to GND) -------
enc = jlc("EC12E24204A2", "ENC1", "C351238", "EC12E24204A2")
Net("ENC_A").connect(enc["A"], gpio(ENC_A_GPIO))
Net("ENC_B").connect(enc["B"], gpio(ENC_B_GPIO))
gnd += enc["C"], enc["D"], enc["E"]

# --- Lock LEDs: 5 V -> 330R -> LED -> 2N7002 (gate on GPIO) -------------------
# Driven from 5 V so any colour works (white/blue need ~3 V, more than a
# 3.3 V GPIO can give through a resistor).
for i, (label, g) in enumerate(LED_GPIO.items(), start=1):
    led = lcsc(Part("Device", "LED", ref=f"D{i}", value=f"{label} (white)",
                    footprint="LED_THT:LED_D5.0mm"), "C74067")
    q = jlc("2N7002", f"Q{i}", "C8545")
    a, k = Net(f"LED_{label}_A"), Net(f"LED_{label}_K")
    R("330", vbus, a)
    a += led["A"]
    k += led["K"], q["D"]
    gnd += q["S"]
    Net(f"LED_{label}").connect(q["G"], gpio(g))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HW, "das4-controller.net")
    generate_netlist(file_=open(out, "w"))
    print("wrote", out)
