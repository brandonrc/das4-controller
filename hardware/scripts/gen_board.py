#!/usr/bin/env python3
"""Build the das4-controller board from the SKiDL netlist.

    make board        # netlist -> hardware/das4-controller.kicad_pcb

What it does:
  1. draws the measured outline and mounting holes
  2. loads every part in hardware/das4-controller.net with its footprint,
     LCSC number and net connections
  3. places the parts that have to line up with the case (MECH) at their
     measured positions, and everything else in rough groups (GROUPS)
  4. anything not listed lands in a staging area to the right of the board

Coordinates are millimetres from the bottom-left corner of the main body,
+Y up (USB-C end is "top", knob end is "bottom", USB-A ports face right).
Numbers marked (photo) come from photos/prints, see docs/measurements.md.

The board is generated: while placement is still moving, change the tables
here, not the .kicad_pcb, or the next `make` overwrites your edits.
"""
import os
import re

import pcbnew

from netlist import NETLIST, read_netlist

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
OUT = os.path.join(HW, "das4-controller.kicad_pcb")
LIBS = {"jlc": os.path.join(HW, "lib", "jlc.pretty")}
KICAD_FP = os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints")

# KiCad page position of our (0, 0); KiCad Y grows downward, ours grows up.
OX, OY = 100.0, 150.0


def pt(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY - y))


# --- Board outline --------------------------------------------------------
BODY_TOP = 83.9     # main body length (measured, +/-0.5)
TAB_TOP = 88.0      # USB-C tab (measured)
FINGER_TOP = 94.0   # thin finger (measured)
BODY_W = 35.9       # main body width, knob side to J4 side (photo)
HUB_W = 43.6        # width at the USB-A section (photo)
HUB_TOP = 45.5      # where the USB-A section starts (photo)
TAB_X0 = 16.5       # USB-C tab left edge (photo)
FINGER_X0 = 32.0    # finger left edge, 4 mm wide finger (photo + measured)
LTAB_X = -7.55      # left mounting tab reaches this far out (photo)
LTAB_Y0, LTAB_Y1 = 11.4, 23.8   # left tab bottom/top, ~12 mm tall (photo)
NOTCH_TOP = 10.4                # notch upper end, near USB-A port 2 (photo)
NOTCH_LEN, NOTCH_DEPTH = 9.35, 3.5  # notch opening along the edge / cut depth (measured)

# --- Mounting holes (photo) -----------------------------------------------
HOLES = [("H1", 22.6, 57.5), ("H2", 26.4, 18.6), ("H3", -4.6, 19.9)]

# --- Parts that must line up with the case ---------------------------------
# ref: (rotation, side, anchor, x, y). The anchor says which point of the
# footprint lands on (x, y): "center" (courtyard centre), "top"/"right"
# (that courtyard edge, i.e. a connector's mouth), "shaft" (encoder shaft,
# midway between its mounting lugs), "pads" (centre of all pads).
MECH = {
    "J1": (180, "F", "top", 23.9, 89.4),      # USB-C mouth 1.4 mm past the tab (photo: ~2; front legs vs edge)
    "J2": (90, "F", "right", 49.4, 37.0),     # USB-A 1 (photo: 37.4; shell leg vs edge)
    "J3": (90, "F", "right", 49.4, 18.4),     # USB-A 2 (photo)
    "J4": (0, "B", "center", 34.6, 63.8),     # key matrix, bottom side (photo)
    "ENC1": (180, "F", "shaft", 10.0, 5.8),   # volume knob (fit-check print)
    "SW1": (90, "F", "center", 3.35, 70.8),
    "SW2": (90, "F", "center", 3.3, 54.0),
    "SW3": (90, "F", "center", 3.4, 37.1),
    "SW4": (90, "F", "center", 19.5, 75.0),   # photo: (19.7, 75.4); clears USB-C pins + CC2 channel
    "SW5": (90, "F", "center", 20.0, 32.0),
    "D1": (0, "F", "pads", 16.9, 63.1),       # NUM (WS2812D RGB)
    "D2": (0, "F", "pads", 16.9, 54.0),       # CAPS
    "D3": (0, "F", "pads", 16.9, 44.5),       # SCROLL
}

# --- Everything else: rough groups (refine during routing) ------------------
# ref: (x, y, rotation), all on the top side, centred on (x, y).
GROUPS = {
    # --- MCU corner. U1 is rotated 90 degrees so each pin group faces what it
    # connects to: regulator + QSPI flash left, crystal right, J4 and buttons
    # up, encoder down. Coordinates of the regulator block copy Raspberry Pi's
    # own minimal-design layout, translated to this package.
    "U1": (11.0, 21.0, 90),                   # RP2350B
    # regulator block on the left, stacked out from pins 61-65 like RPi's:
    # VIN cap, then +1V1 output cap, then L1; LX runs between the cap pads
    "C164": (4.93, 24.0, 90),                 # VREG_VIN 4.7u (pad1 at pin 64)
    "C165": (3.99, 24.0, 90),                 # +1V1 out 4.7u
    "L1": (2.34, 24.0, 270),                  # pad1 (LX) up, pad2 (+1V1, dot) down
    "C161": (4.49, 26.2, 0),                  # VREG_AVDD 4.7u
    "R161": (2.64, 26.2, 0),                  # VREG_AVDD 33R
    # QSPI flash left of the QSPI pins (70-75), its support parts on the tab
    "U3": (2.52, 17.3, None),                 # rotation picked so pad 5 is on top
    "C300": (-0.8, 22.6, 90), "R301": (-1.3, 14.2, 0), "R302": (-1.3, 15.2, 0),
    "C190": (1.8, 10.0, 90),                  # 3V3 bulk
    # crystal right of XIN/XOUT (pins 30/31), R231 in line with XOUT
    "Y1": (19.9, 20.8, 0), "R231": (17.2, 21.45, 0),
    "C230": (18.8, 18.3, 270), "C231": (22.5, 21.65, 0),
    # decoupling: supply pads face the MCU, each cap gets its own vias to the
    # 3V3 plane (In2) / +1V1 spine (B.Cu) and GND (In1) in route.py
    **{ref: (15.9, 26.9 + 1.2 * i, 0) for i, ref in enumerate(
        # +1V1 caps nearest the chip: their B.Cu riser then stays clear of
        # the +3V3 caps' vias above
        ("C141", "C151", "C132", "C166", "C150", "C124", "C129", "C169", "C115"))},
    **{ref: (6.3, 27.3 + 1.2 * i, 180) for i, ref in enumerate(("C160", "C159", "C176", "C168"))},
    "C105": (6.2, 15.0, 180),
    "C110": (10.32, 15.0, 180),               # DVDD pin 10, pad 1 right under the pin
    # USB series resistors at the hub end (full speed: placement not critical)
    "R266": (34.4, 28.5, 0), "R267": (34.4, 29.7, 0),
    "TP1": (7.8, 39.0, 0), "TP2": (10.5, 39.0, 0), "TP3": (13.2, 39.0, 0), "TP4": (15.9, 39.0, 0),
    "TP5": (7.8, 41.5, 0),                    # RUN, next to the SWD pads
    "SW6": (31.0, 40.0, 0),                   # BOOTSEL (clear of the USB_UP pair)
    "SW7": (26.8, 8.0, 0), "R303": (22.4, 8.0, 90),         # RESET
    # Hub block, next to the USB-A ports; C7/C6 right at VDD33/V5 (pins 13/12)
    "U2": (29.5, 30.0, 90),                   # CH334R
    "Y2": (27.0, 25.2, 0),
    "C7": (24.9, 29.9, 180), "C6": (24.9, 28.8, 180), "C8": (30.0, 34.4, 0),
    # USB-A bulk caps (VBUS is the PC's 5 V directly)
    "C9": (31.0, 43.8, 0), "C10": (34.0, 43.8, 0),
    "C11": (32.6, 7.2, 90), "C12": (34.4, 7.2, 90),
    # USB-C input: CC pull-downs either side of the D+/D- pins (the pair leaves
    # straight down between them), ME6211 3.3 V regulator
    # CC2 (B5) can only escape through a 0.35 mm channel between SW4's right
    # leg and the D+ bridge, so R2 sits below SW4
    "R1": (25.55, 79.6, 270), "R2": (22.85, 67.6, 270),
    "U4": (31.3, 78.6, 0), "C1": (34.8, 78.6, 90), "C2": (29.8, 81.4, 0),
    "C3": (32.2, 81.5, 0), "C4": (30.6, 75.6, 0), "C5": (27.4, 75.6, 0),
    # RGB lock LEDs: 2N7002 level shifter + 5 V pull-up, a cap per LED
    "Q1": (11.2, 60.6, 0), "R10": (11.2, 58.0, 0),
    "C35": (11.2, 64.4, 0), "C36": (11.2, 55.3, 0), "C37": (11.2, 45.8, 0),
}

# Parts whose own pad spacing is tighter than the board default (mm). The
# USB-C VBUS/GND pads sit 0.10 mm apart by design; JLCPCB 4-layer does 0.09 mm.
LOCAL_CLEARANCE = {"J1": 0.09}

# --- Geometry helpers -------------------------------------------------------
def outline():
    """Board edge as a list of segments/arcs, counter-clockwise from (0,0)."""
    P = [
        (0, 0), (HUB_W, 0),
        # notch goes here (handled below)
        (HUB_W, HUB_TOP), (BODY_W, HUB_TOP), (BODY_W, FINGER_TOP),
        (FINGER_X0, FINGER_TOP), (FINGER_X0, TAB_TOP), (TAB_X0, TAB_TOP),
        (TAB_X0, BODY_TOP), (0, BODY_TOP), (0, LTAB_Y1), (LTAB_X, LTAB_Y1),
        (LTAB_X, LTAB_Y0), (0, LTAB_Y0), (0, 0),
    ]
    segs = []
    for (a, b) in zip(P, P[1:]):
        if a == (HUB_W, 0):
            # right edge with a notch: an arc 9.35 mm long on the edge, 3.5 mm deep
            y0 = NOTCH_TOP - NOTCH_LEN
            segs.append(("line", (HUB_W, 0), (HUB_W, y0)))
            segs.append(("arc", (HUB_W, y0),
                         (HUB_W - NOTCH_DEPTH, y0 + NOTCH_LEN / 2), (HUB_W, NOTCH_TOP)))
            segs.append(("line", (HUB_W, NOTCH_TOP), b))
        else:
            segs.append(("line", a, b))
    return segs


def add_edge(board):
    for s in outline():
        sh = pcbnew.PCB_SHAPE(board)
        sh.SetLayer(pcbnew.Edge_Cuts)
        sh.SetWidth(pcbnew.FromMM(0.1))
        if s[0] == "line":
            sh.SetShape(pcbnew.SHAPE_T_SEGMENT)
            sh.SetStart(pt(*s[1]))
            sh.SetEnd(pt(*s[2]))
        else:
            sh.SetShape(pcbnew.SHAPE_T_ARC)
            sh.SetArcGeometry(pt(*s[1]), pt(*s[2]), pt(*s[3]))
        board.Add(sh)


def courtyard_bbox(fp):
    box = None
    for g in fp.GraphicalItems():
        if g.GetLayerName() in ("F.Courtyard", "B.Courtyard", "F.CrtYd", "B.CrtYd"):
            b = g.GetBoundingBox()
            if box is None:
                box = b
            else:
                box.Merge(b)
    return box or fp.GetBoundingBox(False)


def pad_center(fp, names=None):
    ps = [p.GetPosition() for p in fp.Pads() if names is None or p.GetNumber() in names]
    return (sum(p.x for p in ps) / len(ps), sum(p.y for p in ps) / len(ps))


def move_to(fp, anchor, x, y):
    box = courtyard_bbox(fp)
    tx, ty = pt(x, y).x, pt(x, y).y
    if anchor == "top":
        cx, cy = box.GetCenter().x, box.GetTop()
    elif anchor == "right":
        cx, cy = box.GetRight(), box.GetCenter().y
    elif anchor == "shaft":
        cx, cy = pad_center(fp, ["D", "E"])   # EC12E mounting lugs straddle the shaft
    elif anchor == "pads":
        cx, cy = pad_center(fp)
    else:
        cx, cy = box.GetCenter().x, box.GetCenter().y
    fp.Move(pcbnew.VECTOR2I(int(tx - cx), int(ty - cy)))


def hide_small_ref(fp):
    """Dense board: no silkscreen reference on the 0402/0603/0805 passives
    (unreadable and they'd sit on copper). Fab layer and 3D view keep them."""
    ref = fp.GetReference()
    name = fp.GetFPID().GetLibItemName().wx_str()
    if ref[:1] in "CR" and any(k in name for k in ("0402", "0603", "0805")):
        fp.Reference().SetVisible(False)


def load_fp(libref):
    lib, name = libref.split(":", 1)
    path = LIBS.get(lib, os.path.join(KICAD_FP, lib + ".pretty"))
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit(f"footprint not found: {libref} ({path})")
    return fp


def note(board, text, x, y, size=1.0, layer=pcbnew.Cmts_User):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetLayer(layer)
    t.SetPosition(pt(x, y))
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
    t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    board.Add(t)


def dim(board, a, b, offset, layer=pcbnew.Dwgs_User):
    d = pcbnew.PCB_DIM_ALIGNED(board, pcbnew.PCB_DIM_ALIGNED_T)
    d.SetLayer(layer)
    d.SetStart(pt(*a))
    d.SetEnd(pt(*b))
    d.SetHeight(pcbnew.FromMM(offset))
    d.SetUnits(pcbnew.EDA_UNITS_MM)
    d.SetPrecision(pcbnew.DIM_PRECISION_X_X)
    board.Add(d)


def ep_windowpane(fp, num="81", win=1.2, off=1.0):
    """Paste for the RP2350B's exposed pad as 4 windows (~50 % coverage)
    between the 5 GND vias critical.py puts in it: full-pad paste over open
    vias voids and can float a 0.4 mm-pitch QFN (layout review 2)."""
    ep = next(p for p in fp.Pads() if p.GetNumber() == num)
    ls = ep.GetLayerSet()
    ls.RemoveLayer(pcbnew.F_Paste)
    ep.SetLayerSet(ls)
    c = ep.GetPosition()
    paste = pcbnew.LSET()
    paste.AddLayer(pcbnew.F_Paste)
    for sx in (-1, 1):
        for sy in (-1, 1):
            a = pcbnew.PAD(fp)
            a.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
            a.SetShape(pcbnew.PAD_SHAPE_RECT)
            a.SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(win), pcbnew.FromMM(win)))
            a.SetLayerSet(paste)
            fp.Add(a)
            a.SetPosition(pcbnew.VECTOR2I(c.x + sx * pcbnew.FromMM(off), c.y + sy * pcbnew.FromMM(off)))


def main():
    board = pcbnew.CreateEmptyBoard()
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(pcbnew.FromMM(1.6))
    # JLCPCB 4-layer capabilities, with some margin
    ds.m_TrackMinWidth = pcbnew.FromMM(0.1)
    ds.m_MinClearance = pcbnew.FromMM(0.1)
    ds.m_ViasMinSize = pcbnew.FromMM(0.4)
    ds.m_MinThroughDrill = pcbnew.FromMM(0.2)
    ds.m_CopperEdgeClearance = pcbnew.FromMM(0.3)
    ds.m_HoleClearance = pcbnew.FromMM(0.2)    # JLCPCB: via hole to copper 0.2 mm
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(pcbnew.FromMM(0.1))    # JLCPCB 4-layer: 0.09 mm
    nc.SetTrackWidth(pcbnew.FromMM(0.2))
    nc.SetViaDiameter(pcbnew.FromMM(0.5))
    nc.SetViaDrill(pcbnew.FromMM(0.25))
    # 4 layers: signals / GND / power / signals. 90 ohm USB pairs need the
    # ground plane right under the top layer.
    board.SetCopperLayerCount(4)

    add_edge(board)

    for ref, x, y in HOLES:
        h = load_fp("MountingHole:MountingHole_2.7mm_M2.5")
        h.SetReference(ref)
        h.SetPosition(pt(x, y))
        board.Add(h)

    comps, nets = read_netlist(NETLIST)

    netinfo = {}
    for name in nets:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netinfo[name] = ni
    pad_net = {(r, p): n for n, nodes in nets.items() for r, p in nodes}

    placed = dict(GROUPS)
    staging = 0
    for ref in sorted(comps, key=lambda r: (re.sub(r"\d+", "", r), int(re.sub(r"\D", "", r) or 0))):
        c = comps[ref]
        fp = load_fp(c["footprint"])
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        hand = c["fields"].get("Assembly") == "hand"
        if "LCSC" in c["fields"]:
            fp.SetField("LCSC", c["fields"]["LCSC"])
            fp.GetField("LCSC").SetVisible(False)
        if hand or "LCSC" not in c["fields"]:
            # soldered by hand (or not a real part): keep out of JLCPCB BOM/CPL
            fp.SetExcludedFromBOM(True)
            fp.SetExcludedFromPosFiles(True)
        for t in [g for g in fp.GraphicalItems() if hasattr(g, "GetText") and g.GetText() == "REF**"]:
            fp.Remove(t)
        hide_small_ref(fp)
        for pad in fp.Pads():
            # easyeda2kicad exports plastic locating pegs as plated holes with
            # no copper; they're really unplated (NPTH)
            if (not pad.GetNumber() and pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
                    and pad.GetSizeX() <= pad.GetDrillSizeX()):
                pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
            n = pad_net.get((ref, pad.GetNumber()))
            if n:
                pad.SetNet(netinfo[n])
        fp.SetPosition(pt(0, 0))
        board.Add(fp)   # must be on the board before Flip, or pcbnew segfaults
        if ref in LOCAL_CLEARANCE:
            fp.SetLocalClearance(pcbnew.FromMM(LOCAL_CLEARANCE[ref]))
        if ref in MECH:
            rot, side, anchor, x, y = MECH[ref]
            fp.SetOrientationDegrees(rot)
            if side == "B":
                fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            move_to(fp, anchor, x, y)
            fp.SetLocked(True)
        elif ref in placed:
            x, y, rot = placed[ref]
            if rot is None:          # pick 0/180 so pad 5 ends up above pad 1
                fp.SetOrientationDegrees(0)
                pads = {p.GetNumber(): p.GetPosition() for p in fp.Pads()}
                rot = 0 if pads["5"].y < pads["1"].y else 180
            fp.SetOrientationDegrees(rot)
            move_to(fp, "pads" if ref.startswith(("U", "Y", "L")) else "center", x, y)
            if ref == "U1":
                ep_windowpane(fp)
        else:
            # not placed yet: park it right of the board so it's easy to spot
            move_to(fp, "center", 60 + 6 * (staging % 5), 80 - 6 * (staging // 5))
            staging += 1
    if staging:
        print(f"note: {staging} parts not in MECH/GROUPS, parked right of the board")

    # Front silkscreen labels for the lock LEDs
    for ref, label in (("D1", "NUM"), ("D2", "CAPS"), ("D3", "SCROLL")):
        note(board, label, 20.0, MECH[ref][4] - 0.5, 0.8, pcbnew.F_SilkS)

    # Key dimensions on User.Drawings so they show up on the fit-check print
    dim(board, (0, 0), (0, BODY_TOP), 9.0)
    dim(board, (TAB_X0, 0), (TAB_X0, TAB_TOP), 25.0)
    dim(board, (BODY_W, 0), (BODY_W, FINGER_TOP), -12.0)
    dim(board, (0, 0), (HUB_W, 0), -4.0)
    dim(board, (LTAB_X, LTAB_Y0), (LTAB_X, LTAB_Y1), 2.0)

    # 50 mm scale bar: if it doesn't measure 50 mm on paper, the print was scaled
    bar = pcbnew.PCB_SHAPE(board)
    bar.SetShape(pcbnew.SHAPE_T_RECT)
    bar.SetLayer(pcbnew.Cmts_User)
    bar.SetWidth(pcbnew.FromMM(0.2))
    bar.SetStart(pt(-8, -15))
    bar.SetEnd(pt(42, -17))
    board.Add(bar)
    note(board, "This bar must measure exactly 50.0 mm when printed", -8, -19.5, 1.0)
    note(board, "DRAFT - not routed yet. Outline from measurements + photos,", -8, -9, 1.0)
    note(board, "see docs/measurements.md.", -8, -11, 1.0)

    # Put the drill/place origin at our (0,0) so KiCad coordinates match the docs
    ds.SetAuxOrigin(pt(0, 0))
    ds.SetGridOrigin(pt(0, 0))

    pcbnew.SaveBoard(os.path.abspath(OUT), board)
    print("wrote", os.path.abspath(OUT), f"({len(comps)} parts, {len(nets)} nets)")


if __name__ == "__main__":
    main()
