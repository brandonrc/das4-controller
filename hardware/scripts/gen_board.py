#!/usr/bin/env python3
"""Generate the draft das4-controller board: outline, mounting holes, and
placeholder footprints for everything that has to line up with the case.

All positions live in the tables below, in millimetres, measured from the
bottom-left corner of the main body with +Y pointing *up* (USB-C end is "top",
knob end is "bottom", USB-A ports face right). Fix a number, re-run, done:

    distrobox enter pcb -- python3 hardware/scripts/gen_board.py

Numbers marked (photo) were traced from a top-down photo scaled so the main
body is 83.9 mm long; expect +/-1-2 mm until they are replaced by caliper
measurements. See docs/measurements.md.
"""
import math
import os
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "das4-controller.kicad_pcb")
FP = "/usr/share/kicad/footprints/"

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
NOTCH_Y, NOTCH_R = 7.1, 3.3     # half-moon notch on the USB-A edge (photo)

# --- Mounting holes (photo) -----------------------------------------------
HOLES = [("H1", 22.6, 57.5), ("H2", 26.4, 18.6), ("H3", -4.6, 19.9)]

# --- Parts ----------------------------------------------------------------
# (ref, value, lib, footprint, rotation, side, anchor, x, y)
# anchor says which point of the footprint's courtyard lands on (x, y):
#   "center", "top" (top edge, centred), "right" (right edge, centred)
PARTS = [
    ("J1", "USB-C (upstream, USB 2.0)", "Connector_USB",
     "USB_C_Receptacle_HRO_TYPE-C-31-M-12", 180, "F", "top", 23.9, 90.2),
    ("J2", "USB-A (hub port 1)", "Connector_USB",
     "USB_A_Molex_67643_Horizontal", 90, "F", "right", 49.4, 37.4),
    ("J3", "USB-A (hub port 2)", "Connector_USB",
     "USB_A_Molex_67643_Horizontal", 90, "F", "right", 49.4, 18.4),
    ("J4", "Key matrix 26p (TBD: pitch/type)", "Connector_PinSocket_1.00mm",
     "PinSocket_1x26_P1.00mm_Vertical", 0, "B", "center", 34.6, 63.8),
    ("ENC1", "Volume encoder (PEC12R-42xxF-S0024?)", "Rotary_Encoder",
     "RotaryEncoder_Alps_EC12E-Switch_Vertical_H20mm", -90, "F", "shaft", 10.6, 2.5),
    ("SW1", "Button", "Button_Switch_SMD",
     "SW_Push_1TS009xxxx-xxxx-xxxx_6x6x5mm", 90, "F", "center", 3.2, 70.8),
    ("SW2", "Button", "Button_Switch_SMD",
     "SW_Push_1TS009xxxx-xxxx-xxxx_6x6x5mm", 90, "F", "center", 3.3, 54.0),
    ("SW3", "Button", "Button_Switch_SMD",
     "SW_Push_1TS009xxxx-xxxx-xxxx_6x6x5mm", 90, "F", "center", 3.4, 37.1),
    ("SW4", "Button", "Button_Switch_SMD",
     "SW_Push_1TS009xxxx-xxxx-xxxx_6x6x5mm", 90, "F", "center", 19.7, 75.4),
    ("SW5", "Button", "Button_Switch_SMD",
     "SW_Push_1TS009xxxx-xxxx-xxxx_6x6x5mm", 90, "F", "center", 20.0, 32.0),
    ("D1", "NUM", "LED_THT", "LED_D5.0mm", 0, "F", "led", 16.9, 63.1),
    ("D2", "CAPS", "LED_THT", "LED_D5.0mm", 0, "F", "led", 16.9, 54.0),
    ("D3", "SCROLL", "LED_THT", "LED_D5.0mm", 0, "F", "led", 16.9, 44.5),
]


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
            # right edge with a half-moon notch cut into the board
            segs.append(("line", (HUB_W, 0), (HUB_W, NOTCH_Y - NOTCH_R)))
            segs.append(("arc", (HUB_W, NOTCH_Y - NOTCH_R),
                         (HUB_W - NOTCH_R, NOTCH_Y), (HUB_W, NOTCH_Y + NOTCH_R)))
            segs.append(("line", (HUB_W, NOTCH_Y + NOTCH_R), b))
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


def pad_center(fp, names):
    ps = [p.GetPosition() for p in fp.Pads() if p.GetNumber() in names]
    return (sum(p.x for p in ps) / len(ps), sum(p.y for p in ps) / len(ps))


def place(board, ref, value, lib, name, rot, side, anchor, x, y):
    fp = pcbnew.FootprintLoad(FP + lib + ".pretty", name)
    fp.SetReference(ref)
    fp.SetValue(value)
    fp.SetPosition(pt(0, 0))
    fp.SetOrientationDegrees(rot)
    board.Add(fp)  # must be on the board before Flip, or pcbnew segfaults
    if side == "B":
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    box = courtyard_bbox(fp)
    tx, ty = pt(x, y).x, pt(x, y).y
    if anchor == "top":
        cx, cy = box.GetCenter().x, box.GetTop()
    elif anchor == "right":
        cx, cy = box.GetRight(), box.GetCenter().y
    elif anchor == "shaft":
        # encoder shaft sits midway between the two mounting lugs
        cx, cy = pad_center(fp, ["MP"]) if any(
            p.GetNumber() == "MP" for p in fp.Pads()) else box.GetCenter()
    elif anchor == "led":
        cx, cy = pad_center(fp, ["1", "2"])
    else:
        cx, cy = box.GetCenter().x, box.GetCenter().y
    fp.Move(pcbnew.VECTOR2I(int(tx - cx), int(ty - cy)))
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


def main():
    board = pcbnew.CreateEmptyBoard()
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(pcbnew.FromMM(1.6))
    # JLCPCB-friendly 2-layer defaults
    ds.m_TrackMinWidth = pcbnew.FromMM(0.15)
    ds.m_MinClearance = pcbnew.FromMM(0.15)
    ds.m_ViasMinSize = pcbnew.FromMM(0.5)
    ds.m_MinThroughDrill = pcbnew.FromMM(0.3)
    board.SetCopperLayerCount(2)

    add_edge(board)

    for ref, x, y in HOLES:
        h = pcbnew.FootprintLoad(FP + "MountingHole.pretty", "MountingHole_2.7mm_M2.5_Pad")
        h.SetReference(ref)
        h.SetPosition(pt(x, y))
        board.Add(h)

    for p in PARTS:
        place(board, *p)

    # Front silkscreen labels for the lock LEDs
    for ref, label in (("D1", "NUM"), ("D2", "CAPS"), ("D3", "SCROLL")):
        y = next(p for p in PARTS if p[0] == ref)[8]
        note(board, label, 20.0, y - 0.5, 0.8, pcbnew.F_SilkS)

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

    note(board, "DRAFT - outline traced from a photo, scaled to the 83.9 mm body.",
         -8, -9, 1.0)
    note(board, "Verify with calipers before ordering. See docs/measurements.md.",
         -8, -11, 1.0)

    # Put the drill/place origin at our (0,0) so KiCad coordinates match the docs
    board.GetDesignSettings().SetAuxOrigin(pt(0, 0))
    board.GetDesignSettings().SetGridOrigin(pt(0, 0))

    pcbnew.SaveBoard(os.path.abspath(OUT), board)
    print("wrote", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
