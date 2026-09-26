"""Hand layout of the critical nets, placed and locked before autorouting.

Everything here follows either Raspberry Pi's "Hardware design with RP2350"
minimal-design layout (regulator block, DVDD distribution) or the layout
review (docs/review-layout-2026-09-25.md). The autorouter then only does the
ordinary signals around these.

Coordinates are board mm (origin bottom-left of the main body, +Y up), like
gen_board.py. Most points are derived from pad positions, so small placement
changes carry through.
"""
import pcbnew

from route import add_via, mm, track

OX, OY = 100.0, 150.0


def P(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY - y))


def xy(v):
    return pcbnew.ToMM(v.x) - OX, OY - pcbnew.ToMM(v.y)


def pad(board, ref, num):
    fp = board.FindFootprintByReference(ref)
    return next(p for p in fp.Pads() if p.GetNumber() == str(num))


def pp(board, ref, num):
    return xy(pad(board, ref, num).GetPosition())


def path(board, pts, layer, net, w):
    """Locked polyline through board-mm points."""
    for a, b in zip(pts, pts[1:]):
        track(board, P(*a), P(*b), layer, net, w)


def via(board, x, y, net, d=0.5, drill=0.25):
    v = add_via(board, P(x, y), net)
    v.SetWidth(mm(d))
    v.SetDrill(mm(drill))
    v.SetLocked(True)
    return v


F, B = pcbnew.F_Cu, pcbnew.B_Cu

# RP2350B power pins that get a via straight down from the pad (inward, under
# the chip): +3V3 ones land on the In2 plane, +1V1 ones on the B.Cu spine
V33_PINS = (5, 15, 24, 29, 41, 50, 59, 60, 64, 68, 69, 76)
V11_PINS = (10, 32, 51)
# signal pins that also leave inward and escape on B.Cu (no room outside)
INWARD_SIGNALS = (33, 34, 35, 66, 67)       # SWCLK, SWDIO, RUN, USB_DM, USB_DP


def inward_via_pos(board, n):
    """Via position for MCU pin n: 0.95 or 1.65 mm in from the pad centre
    (alternating so neighbours at 0.4 mm pitch don't collide: with 0.4 mm
    vias and 0.15 mm stubs a long stub clears the short via by 0.125 mm)."""
    ux, uy = xy(board.FindFootprintByReference("U1").GetPosition())
    px, py = pp(board, "U1", n)
    dx, dy = ux - px, uy - py
    if abs(dx) > abs(dy):           # left/right side
        d = (1 if dx > 0 else -1, 0)
    else:
        d = (0, 1 if dy > 0 else -1)
    off = 0.95 if n % 2 == 0 else 1.65
    return px + d[0] * off, py + d[1] * off


def mcu_core(board):
    # 1. Exposed pad: 5 GND vias into In1 in a "+", in the gaps between the
    # 4 paste windows gen_board.py cuts (so paste never sits over a hole)
    ux, uy = xy(board.FindFootprintByReference("U1").GetPosition())
    for dx, dy in ((0, 0), (1.2, 0), (-1.2, 0), (0, 1.2), (0, -1.2)):
        via(board, ux + dx, uy + dy, "GND")

    # 2. Power pins: short inward stub + via
    for n in V33_PINS + V11_PINS + INWARD_SIGNALS:
        net = pad(board, "U1", n).GetNetname()
        vx, vy = inward_via_pos(board, n)
        path(board, [pp(board, "U1", n), (vx, vy)], F, net, 0.15)
        via(board, vx, vy, net, 0.4, 0.2)

    # 3. Core regulator, RPi layout (review blocker 2): C164 (VREG_VIN) right
    # at pins 64/62, C165 (+1V1) next, L1 beyond; LX (pin 63) runs straight
    # out between the two caps' pads into L1 pad 1.
    p61, p62, p63, p64, p65 = (pp(board, "U1", n) for n in (61, 62, 63, 64, 65))
    c164_1, c164_2 = pp(board, "C164", 1), pp(board, "C164", 2)
    c165_1, c165_2 = pp(board, "C165", 1), pp(board, "C165", 2)
    l1_lx, l1_v11 = pp(board, "L1", 1), pp(board, "L1", 2)
    lx_x = c165_1[0] - 0.54                         # just left of C165's pads
    path(board, [p63, (lx_x, p63[1])], F, "VREG_LX", 0.15)   # 0.4 mm gap between 0402 pads
    path(board, [(lx_x, p63[1]), (lx_x, l1_lx[1]), l1_lx], F, "VREG_LX", 0.25)
    path(board, [p64, c164_1], F, "+3V3", 0.25)
    path(board, [p62, c164_2], F, "GND", 0.25)
    path(board, [c164_2, c165_2], F, "GND", 0.3)
    for c in (c164_2, c165_2):                      # GND vias just outside
        path(board, [c, (c[0], c[1] + 0.62)], F, "GND", 0.3)
        via(board, c[0], c[1] + 0.62, "GND")
    path(board, [l1_v11, (c165_1[0] - 0.6, l1_v11[1]), c165_1], F, "+1V1", 0.3)
    fb_y = c164_1[1] - 0.57                         # FB passes under C164's VIN pad
    path(board, [p65, (p65[0] - 0.45, p65[1]), (p65[0] - 0.45 - abs(p65[1] - fb_y), fb_y),
                 (c165_1[0], fb_y), c165_1], F, "+1V1", 0.2)
    vl = (c165_1[0] - 0.39, c165_1[1] - 0.62)       # +1V1 spine via, clear of the flash pads
    path(board, [c165_1, vl], F, "+1V1", 0.3)
    via(board, *vl, "+1V1")
    # VREG_AVDD: pin 61 -> C161 (4.7u) -> R161 (33R) -> +3V3 via
    c161_1, c161_2 = pp(board, "C161", 1), pp(board, "C161", 2)
    r161_1, r161_2 = pp(board, "R161", 1), pp(board, "R161", 2)
    ay = c164_2[1] + 1.07
    path(board, [p61, (p61[0] - 0.79, ay), (c161_1[0] + 0.56, ay), c161_1], F, "VREG_AVDD", 0.2)
    path(board, [r161_2, c161_1], F, "VREG_AVDD", 0.25)
    path(board, [c161_2, (c161_2[0] + 0.73, c161_2[1] - 0.35)], F, "GND", 0.3)
    via(board, c161_2[0] + 0.73, c161_2[1] - 0.35, "GND")
    path(board, [r161_1, (r161_1[0] - 0.75, r161_1[1])], F, "+3V3", 0.3)
    via(board, r161_1[0] - 0.75, r161_1[1], "+3V3")
    return vl


def spine(board, vl):
    """+1V1 on B.Cu (like RPi's), a 'C' around the left of the chip so the
    USB/SWD vias under it can still get out to the right. Both legs leave
    V_left under U1's left pad row: clear of the L1/LX keep-out, and the
    B.Cu gap to the QSPI flash stays free."""
    v10 = inward_via_pos(board, 10)
    v32 = inward_via_pos(board, 32)
    v51 = inward_via_pos(board, 51)
    top_y, bot_y = 26.6, 16.55
    col = [pp(board, r, 1) for r in ("C132", "C166")]
    col_x = col[0][0] - 0.55
    ux = pp(board, "U1", 61)[0] + 0.46      # under the pads, 0.14 mm off the inward vias
    # top: V_left -> under the left pad row -> across the top -> V51 and the cap column
    path(board, [vl, (ux, vl[1]), (ux, top_y)], B, "+1V1", 0.3)
    path(board, [(ux, top_y), (v51[0] - 1.2, top_y), (v51[0] - 1.2, v51[1]), v51], B, "+1V1", 0.5)
    path(board, [(v51[0] - 1.2, top_y), (col_x, top_y), (col_x, col[-1][1])], B, "+1V1", 0.5)
    for c in col:
        path(board, [c, (col_x, c[1])], F, "+1V1", 0.3)
        via(board, col_x, c[1], "+1V1", 0.45, 0.2)
    # bottom: down under the left pad row too (leaves the gap to the QSPI
    # flash free on B.Cu) -> under the chip bottom -> V10 -> V32
    path(board, [(ux, vl[1]), (ux, bot_y)], B, "+1V1", 0.3)
    path(board, [(ux, bot_y), (v10[0], bot_y), v10], B, "+1V1", 0.5)
    path(board, [(v10[0], bot_y), (15.7, bot_y), (15.7, v32[1]), v32], B, "+1V1", 0.5)


def decaps(board):
    """Decoupling caps next to the MCU: supply pad straight to its pin where
    it's adjacent, otherwise a via to the plane; GND vias shared between
    neighbouring caps' GND pads."""
    # direct: pin 41 -> C141, pin 60 -> C160, pin 59 -> C159, pin 5 -> C105
    for pin, ref in ((41, "C141"), (60, "C160"), (59, "C159")):
        a, b = pp(board, "U1", pin), pp(board, ref, 1)
        path(board, [a, (a[0], b[1]), b], F, "+3V3", 0.25)
    a, b = pp(board, "U1", 5), pp(board, "C105", 1)
    path(board, [a, (a[0], b[1] + 0.35), (b[0], b[1] + 0.35), b], F, "+3V3", 0.25)
    # +3V3 caps without an adjacent pin: via next to the supply pad (In2 plane)
    for ref in ("C150", "C124", "C129", "C169", "C115"):
        c = pp(board, ref, 1)
        path(board, [c, (c[0] - 0.55, c[1])], F, "+3V3", 0.3)
        via(board, c[0] - 0.55, c[1], "+3V3", 0.45, 0.2)
    for ref in ("C176", "C168"):
        c = pp(board, ref, 1)
        path(board, [c, (c[0] + 0.55, c[1])], F, "+3V3", 0.3)
        via(board, c[0] + 0.55, c[1], "+3V3", 0.45, 0.2)
    # GND: one via between each pair of stacked caps (their GND pads face the
    # same way; the 1.2 mm pitch leaves the via clear of both pads), plus one
    # past the last
    for column in (("C141", "C132", "C166", "C150", "C124", "C129", "C169", "C115"),
                   ("C160", "C159", "C176", "C168")):
        g = [pp(board, r, 2) for r in column]
        for a, b in zip(g, g[1:] + [None]):
            vy = (a[1] + b[1]) / 2 if b else a[1] + 0.6
            via(board, a[0], vy, "GND", 0.45, 0.2)
            path(board, [a, (a[0], vy)] + ([b] if b else []), F, "GND", 0.3)
    # DVDD pin 51: its 100 nF right above the pin, GND via just past it
    a, c1, c2 = pp(board, "U1", 51), pp(board, "C151", 1), pp(board, "C151", 2)
    path(board, [a, c1], F, "+1V1", 0.2)
    path(board, [c2, (c2[0], c2[1] + 0.65)], F, "GND", 0.3)
    via(board, c2[0], c2[1] + 0.65, "GND", 0.45, 0.2)
    # DVDD pin 10: its 100 nF right under the pin, GND straight into the
    # encoder's GND pin (layout review 2: DVDD caps were 12-32 mm away)
    a, c1, c2 = pp(board, "U1", 10), pp(board, "C110", 1), pp(board, "C110", 2)
    path(board, [a, c1], F, "+1V1", 0.25)
    path(board, [c2, (c2[0], pp(board, "ENC1", "C")[1])], F, "GND", 0.3)
    g = pp(board, "C105", 2)
    path(board, [g, (g[0] - 0.6, g[1])], F, "GND", 0.3)
    via(board, g[0] - 0.6, g[1], "GND", 0.45, 0.2)


def crystal(board):
    """Y1 right next to XIN/XOUT (pins 30/31); XOUT through R231 in line.
    Nothing else runs between the MCU and the crystal (review: short, no vias,
    not under the crystal)."""
    p30, p31 = pp(board, "U1", 30), pp(board, "U1", 31)
    y1, y2, y3, y4 = (pp(board, "Y1", n) for n in (1, 2, 3, 4))
    r1, r2 = pp(board, "R231", 1), pp(board, "R231", 2)
    c230_1, c230_2 = pp(board, "C230", 1), pp(board, "C230", 2)
    c231_1, c231_2 = pp(board, "C231", 1), pp(board, "C231", 2)
    path(board, [p30, (y1[0], p30[1]), y1], F, "XIN", 0.2)
    path(board, [y1, c230_1], F, "XIN", 0.2)
    path(board, [p31, (p31[0] + 0.39, p31[1]), r1], F, pad(board, "U1", 31).GetNetname(), 0.2)
    xo_y = y3[1] + 0.95
    path(board, [r2, (r2[0], xo_y), (y3[0], xo_y), y3], F, "XOUT_XTAL", 0.2)
    path(board, [y3, c231_1], F, "XOUT_XTAL", 0.2)
    path(board, [y4, y2], F, "GND", 0.3)             # tie the GND pads under the can
    path(board, [y2, (y2[0] + 1.15, y2[1])], F, "GND", 0.3)
    via(board, y2[0] + 1.15, y2[1], "GND")
    path(board, [c230_2, (c230_2[0], c230_2[1] - 0.6)], F, "GND", 0.3)
    via(board, c230_2[0], c230_2[1] - 0.6, "GND", 0.45, 0.2)
    path(board, [c231_2, (c231_2[0] + 0.6, c231_2[1])], F, "GND", 0.3)
    via(board, c231_2[0] + 0.6, c231_2[1], "GND", 0.45, 0.2)


def usb_up(board):
    """USB_UP D+/D- (480 Mbit/s) as a coupled pair on F.Cu over the solid In1
    GND plane, J1 -> hub pins 10/11, >3 mm from H1 (review blocker 3).
    0.25 mm tracks, 0.15 mm gap (~90 ohm diff on JLC04161H-7628, estimated).
    J1's D+/D- pads interleave (B6 +, A7 -, A6 +, B7 -): D+ joins its pads on
    F.Cu, D- hops its A7 pad over on B.Cu (two vias, ~1 mm stub)."""
    w = 0.25
    b6, a7, a6, b7 = (pp(board, "J1", n) for n in ("B6", "A7", "A6", "B7"))
    by = b6[1] - 1.5                                 # D+ bridge below the pads
    path(board, [b6, (b6[0], by), (a6[0], by)], F, "USB_UP_D+", w)
    path(board, [a6, (a6[0], by)], F, "USB_UP_D+", w)
    vy = a7[1] - 1.0
    path(board, [a7, (a7[0], vy)], F, "USB_UP_D-", 0.2)
    via(board, a7[0], vy, "USB_UP_D-", 0.45, 0.2)
    via(board, b7[0], vy, "USB_UP_D-", 0.45, 0.2)
    path(board, [(a7[0], vy), (b7[0], vy)], B, "USB_UP_D-", 0.2)
    h10, h11 = pp(board, "U2", 10), pp(board, "U2", 11)
    pad_x = h10[0] - 0.95                            # left end of the hub pads
    xp, xm = a6[0], a6[0] + 0.4                      # D+ west, D- east, 0.4 pitch
    y_jog1, x2p = 68.0, 25.95                        # jog right before H1
    y_jog2, x3p = 36.4, pad_x - 0.67                 # jog left before the hub
    k = 0.4 * (2 ** 0.5 - 1)                         # keeps the gap on 45-degree bends
    dp = [(xp, by), (xp, y_jog1), (x2p, y_jog1 - (x2p - xp)),
          (x2p, y_jog2), (x3p, y_jog2 - (x2p - x3p)), (x3p, h11[1]), (h11[0], h11[1])]
    dm = [(b7[0], vy), (xm, vy - 0.4), (xm, y_jog1 + k), (x2p + 0.4, y_jog1 + k - (x2p - xp)),
          (x2p + 0.4, y_jog2 - k), (x3p + 0.4, y_jog2 - k - (x2p - x3p)), (x3p + 0.4, h10[1]),
          (h10[0], h10[1])]
    path(board, dp, F, "USB_UP_D+", w)
    path(board, dm, F, "USB_UP_D-", w)
    path(board, [b7, (b7[0], vy)], F, "USB_UP_D-", 0.2)


def cc(board):
    """USB-C CC pull-downs: CC1 (A5) to R1 just right of the pair, CC2 (B5)
    down the 0.35 mm channel between SW4's leg and the D+ bridge to R2."""
    a5, b5 = pp(board, "J1", "A5"), pp(board, "J1", "B5")
    r1, r1g = pp(board, "R1", 1), pp(board, "R1", 2)
    r2, r2g = pp(board, "R2", 1), pp(board, "R2", 2)
    # leave each pad straight down past the pad row before bending
    path(board, [a5, (a5[0], a5[1] - 1.0), r1], F, pad(board, "J1", "A5").GetNetname(), 0.2)
    path(board, [r1g, (r1g[0], r1g[1] - 0.7)], F, "GND", 0.3)
    via(board, r1g[0], r1g[1] - 0.7, "GND", 0.45, 0.2)
    # CC2: under A8 (0.14 mm) and over SW4's leg (0.175 mm), then down the
    # channel between SW4 and the D+ bridge
    ccy = b5[1] - 0.865
    path(board, [b5, (b5[0], ccy), (r2[0] - 0.03, ccy), (r2[0] - 0.03, r2[1])], F, pad(board, "J1", "B5").GetNetname(), 0.15)
    path(board, [r2g, (r2g[0], r2g[1] - 0.7)], F, "GND", 0.3)
    via(board, r2g[0], r2g[1] - 0.7, "GND", 0.45, 0.2)


def encoder(board):
    """ENC_B (pin 6) down left of C110 and under C105 to pad B; ENC_A (pin
    12) straight down into pad A. Both pass the encoder's GND pin C."""
    b6, a12 = pp(board, "U1", 6), pp(board, "U1", 12)
    eb, ea = pp(board, "ENC1", "B"), pp(board, "ENC1", "A")
    y = 14.45
    path(board, [b6, (b6[0], y), (eb[0], y), eb], F, "ENC_B", 0.2)
    path(board, [a12, (a12[0], 14.6), ea], F, "ENC_A", 0.2)


def leds(board):
    """Lock-LED 5 V: a 0.5 mm spine up the cap column (C37 -> C36 -> R10)
    with a tee over each LED's pad row into its +5V pin (the autorouter kept
    failing to thread the 0.5 mm +5V class in here)."""
    c37, c36, r10 = pp(board, "C37", 1), pp(board, "C36", 1), pp(board, "R10", 1)
    path(board, [c37, c36, (c36[0], r10[1] - 0.03), r10], F, "+5V", 0.5)
    for cap, led in (("C37", "D3"), ("C36", "D2")):
        c, d = pp(board, cap, 1), pp(board, led, 2)
        ty = c[1] + 1.0                    # clear of the cap's GND pad
        path(board, [(c[0], ty), (d[0] - 0.53, ty), (d[0], ty - 0.53), d], F, "+5V", 0.5)


def j4_vias(board):
    """A via just inboard of each J4 flex pad (bottom side), so matrix lines
    can arrive on either layer; route.py drops the ones the router didn't use."""
    for p in board.FindFootprintByReference("J4").Pads():
        (x, y) = xy(p.GetPosition())
        x0 = x - pcbnew.ToMM(p.GetSizeX()) / 2       # bbox of a flipped pad reads wrong here
        path(board, [(x, y), (x0 - 0.45, y)], B, p.GetNetname(), 0.15)
        via(board, x0 - 0.45, y, p.GetNetname(), 0.45, 0.2)


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def box(board, ref, grow=0.0):
    bb = board.FindFootprintByReference(ref).GetCourtyard(F).BBox()
    x0, y1 = xy(bb.GetOrigin())
    x1, y0 = xy(bb.GetEnd())
    return x0 - grow, y0 - grow, x1 + grow, y1 + grow


def rule_area(board, pts, layers, tracks=True, vias=True, pour=True, name=""):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowTracks(tracks)
    z.SetDoNotAllowVias(vias)
    z.SetDoNotAllowZoneFills(pour)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    for layer in layers:
        ls.AddLayer(layer)
    z.SetLayerSet(ls)
    z.SetZoneName(name)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        v = P(x, y)
        ol.Append(v.x, v.y)
    board.Add(z)
    return z


def keepouts(board):
    """Keep-out rule areas. Returns the router-only ones: route.py removes
    them again after autorouting (they cover hand-drawn tracks, which DRC
    would otherwise flag)."""
    import math
    I1, I2 = pcbnew.In1_Cu, pcbnew.In2_Cu
    # 1. no copper at all under L1 and VREG_LX on the inner layers and
    # B.Cu (RP2350 datasheet 6.3.8: "cut away any copper immediately
    # underneath L/VREG_LX")
    x0, y0, x1, y1 = box(board, "L1", 0.1)
    p63 = pp(board, "U1", 63)
    lx_x = pp(board, "C165", 1)[0] - 0.54
    rule_area(board, [(x0, y0), (x1, y0), (x1, p63[1] - 0.25), (p63[0], p63[1] - 0.25),
                      (p63[0], p63[1] + 0.25), (lx_x + 0.17, p63[1] + 0.25), (lx_x + 0.17, y1), (x0, y1)],
              (I1, I2, B), name="no copper under L1/LX")
    # 2. no top pour round the regulator block: CIN/COUT GND reach main GND
    # only through their via pair (datasheet: "connect to main GND at one point")
    rule_area(board, [(1.3, 22.4), (5.6, 22.4), (5.6, 24.85), (lx_x + 0.17, 24.85),
                      (lx_x + 0.17, 25.7), (1.3, 25.7)], (F,), tracks=False, vias=False,
              name="regulator GND single point")
    # 3. nothing but GND under the USB-A shells (one scuff would short VBUS
    # or a matrix line to the grounded shell)
    for ref in ("J2", "J3"):
        _, y0, _, y1 = box(board, ref)
        x0 = pp(board, ref, 1)[0] + 0.55
        rule_area(board, rect(x0, y0, 45.0, y1), (F,), pour=False, name=f"{ref} shell")
    # 4. nothing under the M2.5 screw heads (4.5 mm pan head + 0.25 mm)
    for ref in ("H1", "H2", "H3"):
        cx, cy = xy(board.FindFootprintByReference(ref).GetPosition())
        rule_area(board, [(cx + 2.5 * math.cos(k * math.pi / 12), cy + 2.5 * math.sin(k * math.pi / 12))
                          for k in range(24)], (F, B), pour=False, name=f"{ref} screw head")
    # router only: no other tracks or vias through the crystal block (review 2:
    # a matrix line ran between the load caps' pads, vias beside XIN/XOUT)
    router = []
    for ref in ("Y1", "C230", "C231", "R231"):
        x0, y0, x1, y1 = box(board, ref, 0.2)
        router.append(rule_area(board, rect(max(x0, 16.3), y0, x1, y1), (F,), pour=False))
    xo = pp(board, "R231", 2)
    router.append(rule_area(board, rect(16.3, 20.45, 18.3, 21.0), (F,), pour=False))   # XIN
    router.append(rule_area(board, rect(xo[0] - 0.4, 22.0, pp(board, "Y1", 3)[0] + 0.25, 22.95),
                            (F,), pour=False))                                       # XOUT
    return router


def pair_via_band(board, nets=("USB_UP_D+", "USB_UP_D-"), gap=0.5):
    """Router-only: no foreign vias within `gap` of the USB_UP pair (layout
    review 2: a KM via sat 0.16 mm from D-, its In1 anti-pad under the
    trace). 0.5 mm keeps a via's In1 anti-pad clear of the trace edge. One
    rule area per pair segment."""
    import math
    areas = []
    for t in board.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetNetname() not in nets or t.GetLayer() != F:
            continue
        (ax, ay), (bx, by) = xy(t.GetStart()), xy(t.GetEnd())
        L = math.hypot(bx - ax, by - ay)
        if L < 0.05:
            continue
        r = gap + pcbnew.ToMM(t.GetWidth()) / 2
        ux, uy = (bx - ax) / L * r, (by - ay) / L * r      # along, then normal
        nx, ny = -uy, ux
        areas.append(rule_area(board, [(ax - ux + nx, ay - uy + ny), (bx + ux + nx, by + uy + ny),
                                       (bx + ux - nx, by + uy - ny), (ax - ux - nx, ay - uy - ny)],
                               (F, B), tracks=False, pour=False))
    return areas


def critical(board):
    vl = mcu_core(board)
    spine(board, vl)
    decaps(board)
    crystal(board)
    encoder(board)
    leds(board)
    j4_vias(board)
    usb_up(board)
    cc(board)
