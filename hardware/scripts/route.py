#!/usr/bin/env python3
"""Autoroute the placed board with Freerouting.

    make route        # placed board -> routed board (same file)

Stack-up: F.Cu signals / In1 solid GND plane / In2 signals + 3V3 pour /
B.Cu signals + GND pour. In1 stays unbroken so the USB pairs on F.Cu have a
continuous reference. Power nets get wider tracks, the board goes out as
Specctra DSN, Freerouting routes it headless, the session comes back in, and
the pours are filled.
"""
import os
import subprocess
import sys

import pcbnew

HW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HW)
PCB = os.path.join(HW, "das4-controller.kicad_pcb")
WORK = os.environ.get("ROUTE_WORK", os.path.join(ROOT, "build", "route"))
OUT = os.environ.get("ROUTE_OUT", PCB)           # where the routed board goes
PASSES = int(os.environ.get("ROUTE_PASSES", "60"))
THREADS = os.environ.get("ROUTE_THREADS")
STRATEGY = os.environ.get("ROUTE_STRATEGY")     # greedy | global | hybrid

mm = pcbnew.FromMM

# net class name: (track width, clearance, nets)
CLASSES = {
    # 0.1 mm clearance: the USB-C's VBUS/GND pads are 0.10 mm apart, so any
    # bigger clearance makes Freerouting treat them as unreachable
    "Power": (0.5, 0.1, ["+5V"]),        # ~1 A total to the USB-A ports
    "Supply": (0.3, 0.1, ["+3V3"]),
    "Core": (0.3, 0.1, ["+1V1", "VREG_LX", "VREG_AVDD"]),
    # USB: 0.2 mm tracks keep the pairs tight; proper 90 ohm tuning comes later
    "USB": (0.2, 0.1, ["USB_UP_D+", "USB_UP_D-", "USB_MCU_D+", "USB_MCU_D-",
                        "USB_A1_D+", "USB_A1_D-", "USB_A2_D+", "USB_A2_D-"]),
}
# In1 solid GND, In2 solid +3V3 (layout review: 3V3 was starved when In2
# carried signals); signals on F.Cu and B.Cu only
PLANES = [(pcbnew.In1_Cu, "GND"), (pcbnew.In2_Cu, "+3V3")]
POURS = [(pcbnew.F_Cu, "GND"), (pcbnew.B_Cu, "GND")]


def add_zone(board, layer, netname, outline, priority=0):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(board.FindNet(netname))
    z.SetAssignedPriority(priority)
    z.SetLocalClearance(mm(0.25))
    z.SetMinThickness(mm(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(mm(0.25))
    z.SetThermalReliefSpokeWidth(mm(0.3))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.Outline().AddOutline(outline)
    board.Add(z)
    return z


# --- GND vias --------------------------------------------------------------
VIA_D, VIA_DRILL, GAP = 0.6, 0.3, 0.15


def obstacles(board, net, all_pads=False):
    """(kind, geometry, half-width) for every copper item not on `net`
    (all_pads: every pad counts, even same-net ones, e.g. so stitching vias
    never land inside a pad)."""
    obs = []
    for t in board.GetTracks():
        if t.GetNetname() == net:
            continue
        if t.GetClass() == "PCB_VIA":
            obs.append(("pt", t.GetPosition(), t.GetWidth(pcbnew.F_Cu) / 2))
        else:
            obs.append(("seg", (t.GetStart(), t.GetEnd()), t.GetWidth() / 2))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == net and p.GetNetname() and not all_pads:
                continue
            obs.append(("box", p.GetBoundingBox(), 0))
    return obs


def seg_dist(p, a, b):
    ax, ay, bx, by, px, py = a.x, a.y, b.x, b.y, p.x, p.y
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return ((ax + t * dx - px) ** 2 + (ay + t * dy - py) ** 2) ** 0.5


def clear(p, r, obs):
    for kind, g, hw in obs:
        if kind == "pt":
            d = ((g.x - p.x) ** 2 + (g.y - p.y) ** 2) ** 0.5 - hw
        elif kind == "seg":
            d = seg_dist(p, *g) - hw
        else:
            dx = max(g.GetLeft() - p.x, 0, p.x - g.GetRight())
            dy = max(g.GetTop() - p.y, 0, p.y - g.GetBottom())
            d = (dx * dx + dy * dy) ** 0.5
        if d < r:
            return False
    return True


def blocked(board, p, r, tracks_on=None):
    """True if a via of radius r at p would break a keep-out rule area (or,
    with tracks_on=layer, a track there would)."""
    for z in board.Zones():
        if not z.GetIsRuleArea():
            continue
        if tracks_on is None:
            if not z.GetDoNotAllowVias():
                continue
        elif not (z.GetDoNotAllowTracks() and z.IsOnLayer(tracks_on)):
            continue
        if z.Outline().Contains(p) or z.Outline().SquaredDistance(p) < r * r:
            return True
    return False


def add_via(board, p, net):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(p)
    v.SetWidth(mm(VIA_D))
    v.SetDrill(mm(VIA_DRILL))
    v.SetNet(board.FindNet(net))
    board.Add(v)
    return v


def fanout(board, pads):
    """Short track + via from each listed (ref, pad, net) into that net's
    plane/pour."""
    for ref, num, net in pads:
        obs = obstacles(board, net)
        pad = next(p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == num)
        c, fpc = pad.GetPosition(), board.FindFootprintByReference(ref).GetPosition()
        vx, vy = c.x - fpc.x, c.y - fpc.y
        n = (vx * vx + vy * vy) ** 0.5 or 1
        for dist in (0.9, 1.1, 1.3, 1.6, 2.0):
            p = pcbnew.VECTOR2I(int(c.x + vx / n * mm(dist)), int(c.y + vy / n * mm(dist)))
            path_ok = all(clear(pcbnew.VECTOR2I(int(c.x + (p.x - c.x) * f), int(c.y + (p.y - c.y) * f)),
                                mm(0.125 + 0.1), obs) for f in (0.35, 0.5, 0.65, 0.8))
            if path_ok and clear(p, mm(VIA_D / 2 + GAP), obs):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(c)
                t.SetEnd(p)
                t.SetWidth(mm(0.25))
                t.SetLayer(pcbnew.F_Cu)
                t.SetNet(board.FindNet(net))
                board.Add(t)
                add_via(board, p, net)
                break
        else:
            print(f"fanout: no room for a via at {ref}.{num}")


def stitch(board, edge, net="GND", pitch=1.25, spacing=2.0):
    """GND vias wherever the outer GND pours actually filled: ties the pours
    to the In1 plane (and so to each other) and shields the signal layers.
    Needs the pours filled first."""
    obs = obstacles(board, net, all_pads=True)
    holes = [(v.GetPosition(), v.GetDrill() / 2) for v in board.GetTracks()
             if v.GetClass() == "PCB_VIA"]
    holes += [(p.GetPosition(), max(p.GetDrillSizeX(), p.GetDrillSizeY()) / 2)
              for fp in board.GetFootprints() for p in fp.Pads() if p.HasHole()]
    pours = [z for z in board.Zones() if z.GetNetname() == net
             and z.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu)]
    placed = []
    bb = edge.BBox()
    y = bb.GetTop() + mm(1)
    while y < bb.GetBottom():
        x = bb.GetLeft() + mm(1)
        while x < bb.GetRight():
            p = pcbnew.VECTOR2I(int(x), int(y))
            if (edge.PointInside(p) and edge.SquaredDistance(p, True) > mm(0.9) ** 2
                    and any(z.HitTestFilledArea(z.GetLayer(), p, 0) for z in pours)
                    and all(((p.x - q.x) ** 2 + (p.y - q.y) ** 2) ** 0.5 > mm(spacing) for q in placed)
                    and all(((p.x - q.x) ** 2 + (p.y - q.y) ** 2) ** 0.5 > r + mm(VIA_DRILL / 2 + 0.35)
                            for q, r in holes)
                    and clear(p, mm(VIA_D / 2 + GAP), obs)
                    and not blocked(board, p, mm(VIA_D / 2))):
                v = add_via(board, p, net)
                placed.append(p)
                holes.append((p, mm(VIA_DRILL / 2)))
            x += mm(pitch)
        y += mm(pitch)
    print(f"stitching: {len(placed)} GND vias")


# --- Hand pre-routes (locked, Freerouting routes around them) ------------------
def track(board, a, b, layer, net, w):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(a)
    t.SetEnd(b)
    t.SetLayer(layer)
    t.SetWidth(mm(w))
    t.SetNet(board.FindNet(net))
    t.SetLocked(True)
    board.Add(t)


def pad_pos(board, ref, num):
    return next(p for p in board.FindFootprintByReference(ref).Pads()
                if p.GetNumber() == num).GetPosition()


def decouple_vias(board, center_ref="U1", radius=9.0, supplies=("+3V3", "+1V1", "VREG_AVDD"),
                  extra=()):
    """GND via beside the GND pad of every MCU decoupling cap (and of the
    `extra` two-pad parts, e.g. the USB-C CC pull-downs)."""
    u = board.FindFootprintByReference(center_ref).GetPosition()
    obs = obstacles(board, "GND")
    n = 0
    for fp in board.GetFootprints():
        pads = list(fp.Pads())
        ref = fp.GetReference()
        if len(pads) != 2 or not (ref.startswith("C") or ref in extra):
            continue
        c = fp.GetPosition()
        if ref not in extra and ((c.x - u.x) ** 2 + (c.y - u.y) ** 2) ** 0.5 > mm(radius):
            continue
        g = next((p for p in pads if p.GetNetname() == "GND"), None)
        o = next((p for p in pads if p.GetNetname() != "GND" and
                  (ref in extra or p.GetNetname() in supplies)), None)
        if not g or not o:
            continue
        gp, op = g.GetPosition(), o.GetPosition()
        dx, dy = gp.x - op.x, gp.y - op.y
        L = (dx * dx + dy * dy) ** 0.5 or 1
        for dist in (0.95, 1.1, 1.3):
            v = pcbnew.VECTOR2I(int(gp.x + dx / L * mm(dist)), int(gp.y + dy / L * mm(dist)))
            if clear(v, mm(VIA_D / 2 + 0.1), obs):
                track(board, gp, v, pcbnew.F_Cu, "GND", 0.3)
                add_via(board, v, "GND").SetLocked(True)
                obs.append(("pt", v, mm(VIA_D / 2)))
                n += 1
                break
        else:
            print(f"decouple: no room for a GND via at {fp.GetReference()}")
    print(f"decouple: {n} GND vias")


def tie_switch_pads(board, refs=("SW1", "SW2", "SW3", "SW4", "SW5", "SW6", "SW7")):
    """Tact switches connect pads 1-2 and 3-4 inside the part. Mirror that
    with a short F.Cu track under the body, so each pair is also joined on the
    board (and no pad ends up alone on a small piece of pour)."""
    n = 0
    for ref in refs:
        fp = board.FindFootprintByReference(ref)
        pads = {p.GetNumber(): p for p in fp.Pads()}
        for a, b in (("1", "2"), ("3", "4")):
            pa, pb = pads[a], pads[b]
            if pa.GetNetname() != pb.GetNetname():
                continue
            obs = obstacles(board, pa.GetNetname())
            A, B = pa.GetPosition(), pb.GetPosition()
            pts = [pcbnew.VECTOR2I(int(A.x + (B.x - A.x) * f), int(A.y + (B.y - A.y) * f))
                   for f in (0.2, 0.35, 0.5, 0.65, 0.8)]
            if all(clear(q, mm(0.15 + 0.1), obs) for q in pts):
                track(board, A, B, pcbnew.F_Cu, pa.GetNetname(), 0.3)   # locked
                n += 1
            else:
                print(f"tie: {ref} pads {a}-{b} blocked")
    return n


def plane_fanout(board, nets=("+3V3", "GND"), d=0.45, drill=0.2, skip=("U1",)):
    """Every SMD pad on a plane net that nothing hand-routed touches gets its
    own short stub and via into the plane (In2 +3V3, In1 GND). Tries the
    direction away from the part first, then the others, nearest first."""
    import math
    holes = [(v.GetPosition(), v.GetDrill() / 2) for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
    holes += [(p.GetPosition(), max(p.GetDrillSizeX(), p.GetDrillSizeY()) / 2)
              for fp in board.GetFootprints() for p in fp.Pads() if p.HasHole()]
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, True)
    edge = outline.Outline(0)
    added, failed = 0, []
    for fp in board.GetFootprints():
        if fp.GetReference() in skip:
            continue
        for pad in fp.Pads():
            net = pad.GetNetname()
            if net not in nets or pad.HasHole() or not pad.IsOnLayer(pcbnew.F_Cu):
                continue
            if any(t.GetNetname() == net and t.GetLayer() == pcbnew.F_Cu
                   and (pad.HitTest(t.GetStart()) or pad.HitTest(t.GetEnd()))
                   for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"):
                continue
            obs = [o for o in obstacles(board, net, all_pads=True)
                   if not (o[0] == "box" and o[1].GetCenter() == pad.GetBoundingBox().GetCenter())]
            c, fc = pad.GetPosition(), fp.GetPosition()
            a0 = math.atan2(c.y - fc.y, c.x - fc.x) if c != fc else 0.0
            bb = pad.GetBoundingBox()
            reach = max(bb.GetWidth(), bb.GetHeight()) / 2
            done = False
            for extra in (0.35, 0.5, 0.7, 0.9, 1.2):
                for k in (0, 1, -1, 2, -2, 3, -3, 4):
                    a = a0 + k * math.pi / 4
                    r = reach + mm(extra)
                    v = pcbnew.VECTOR2I(int(c.x + r * math.cos(a)), int(c.y + r * math.sin(a)))
                    if pad.HitTest(v):
                        continue
                    path_ok = all(clear(pcbnew.VECTOR2I(int(c.x + (v.x - c.x) * f), int(c.y + (v.y - c.y) * f)),
                                        mm(0.125 + 0.11), obs) for f in (0.5, 0.65, 0.8, 0.9))
                    own = pad.GetBoundingBox()
                    ox = max(own.GetLeft() - v.x, 0, v.x - own.GetRight())
                    oy = max(own.GetTop() - v.y, 0, v.y - own.GetBottom())
                    mid = pcbnew.VECTOR2I((c.x + v.x) // 2, (c.y + v.y) // 2)
                    if (path_ok and clear(v, mm(d / 2 + 0.12), obs)
                            and (ox * ox + oy * oy) ** 0.5 >= mm(d / 2 + 0.05)   # not touching its own pad
                            and not blocked(board, v, mm(d / 2))
                            and not blocked(board, mid, mm(0.125), tracks_on=pcbnew.F_Cu)
                            and edge.PointInside(v) and edge.SquaredDistance(v, True) > mm(d / 2 + 0.35) ** 2
                            and all(((v.x - q.x) ** 2 + (v.y - q.y) ** 2) ** 0.5 > rr + mm(drill / 2 + 0.22)
                                    for q, rr in holes)):
                        t = track(board, c, v, pcbnew.F_Cu, net, 0.25)
                        via = add_via(board, v, net)
                        via.SetWidth(mm(d))
                        via.SetDrill(mm(drill))
                        via.SetLocked(True)
                        holes.append((v, mm(drill / 2)))
                        added += 1
                        done = True
                        break
                if done:
                    break
            if not done:
                failed.append(f"{fp.GetReference()}.{pad.GetNumber()}")
    print(f"plane fanout: {added} vias" + (f", no room at {', '.join(failed)}" if failed else ""))


def drop_unused_vias(board, keep_nets=("GND", "+3V3")):
    """Signal vias Freerouting didn't use (tracks on only one layer): remove
    the via, and the stub too if it's the only thing that reached it."""
    removed = 0
    for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]:
        if v.GetNetname() in keep_nets:
            continue
        p, r = v.GetPosition(), v.GetWidth(pcbnew.F_Cu) / 2
        # touching, not just ending there: Freerouting also runs tracks
        # straight through vias
        at = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"
              and t.GetNetname() == v.GetNetname()
              and seg_dist(p, t.GetStart(), t.GetEnd()) <= r + t.GetWidth() / 2]
        if len({t.GetLayer() for t in at}) >= 2:
            continue
        board.Remove(v)
        ends = lambda t: min(((q.x - p.x) ** 2 + (q.y - p.y) ** 2) ** 0.5
                             for q in (t.GetStart(), t.GetEnd())) <= r
        if len(at) == 1 and ends(at[0]):    # a stub that only led to the via
            board.Remove(at[0])
        removed += 1
    print(f"cleanup: {removed} unused signal vias removed")


def preroute(board):
    from critical import critical     # hand layout of the critical nets
    critical(board)
    print(f"tie: {tie_switch_pads(board)} switch pad pairs joined")
    plane_fanout(board)


def patch_fragments(board, net="GND", d=0.45, drill=0.2):
    """After filling: any piece of an outer GND pour with no GND via in it
    gets one (a small 0.45/0.2 mm via, placed where it fits inside the
    piece and clears everything on the other layers)."""
    obs = obstacles(board, net, all_pads=True)
    holes = [(v.GetPosition(), v.GetDrill() / 2) for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
    holes += [(p.GetPosition(), max(p.GetDrillSizeX(), p.GetDrillSizeY()) / 2)
              for fp in board.GetFootprints() for p in fp.Pads() if p.HasHole()]
    added = 0
    for z in board.Zones():
        if z.GetNetname() != net or z.GetLayer() not in (pcbnew.F_Cu, pcbnew.B_Cu):
            continue
        polys = z.GetFilledPolysList(z.GetLayer())
        vias = [t.GetPosition() for t in board.GetTracks()
                if t.GetClass() == "PCB_VIA" and t.GetNetname() == net]
        for i in range(polys.OutlineCount()):
            ol = polys.Outline(i)
            if any(ol.PointInside(v) for v in vias):
                continue
            bb, step, done = ol.BBox(), mm(0.1), False
            y = bb.GetTop()
            while y <= bb.GetBottom() and not done:
                x = bb.GetLeft()
                while x <= bb.GetRight():
                    p = pcbnew.VECTOR2I(int(x), int(y))
                    if (ol.PointInside(p) and ol.SquaredDistance(p, True) >= mm(d / 2) ** 2
                            and all(((p.x - q.x) ** 2 + (p.y - q.y) ** 2) ** 0.5 > r + mm(drill / 2 + 0.3)
                                    for q, r in holes)
                            and clear(p, mm(d / 2 + 0.1), obs)
                            and not blocked(board, p, mm(d / 2))):
                        v = pcbnew.PCB_VIA(board)
                        v.SetPosition(p)
                        v.SetWidth(mm(d))
                        v.SetDrill(mm(drill))
                        v.SetNet(board.FindNet(net))
                        board.Add(v)
                        holes.append((p, mm(drill / 2)))
                        added += 1
                        done = True
                        break
                    x += step
                y += step
            if not done:
                print(f"patch: no room for a via in a {z.GetLayerName()} GND piece at "
                      f"({pcbnew.ToMM(bb.GetCenter().x):.1f}, {pcbnew.ToMM(bb.GetCenter().y):.1f})")
    print(f"patch: {added} vias into isolated GND pour pieces")
    return added


def main():
    os.makedirs(WORK, exist_ok=True)
    board = pcbnew.LoadBoard(PCB)
    for z in list(board.Zones()):
        board.Remove(z)
    for t in list(board.GetTracks()):   # start clean
        board.Remove(t)
    setup_netclasses(board)

    for layer, _ in PLANES:
        board.SetLayerType(layer, pcbnew.LT_POWER)

    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, True)
    edge = outline.Outline(0)
    route(board, edge)


def setup_netclasses(board):
    ns = board.GetDesignSettings().m_NetSettings
    dflt = ns.GetDefaultNetclass()
    dflt.SetTrackWidth(mm(0.15))       # fits between the RP2350B's 0.4 mm-pitch pads
    dflt.SetClearance(mm(0.1))         # JLCPCB 4-layer minimum is 0.09 mm
    for name, (w, cl, nets) in CLASSES.items():
        nc = pcbnew.NETCLASS(name)
        nc.SetTrackWidth(mm(w))
        nc.SetClearance(mm(cl))
        nc.SetViaDiameter(mm(0.6))
        nc.SetViaDrill(mm(0.3))
        ns.SetNetclass(name, nc)
        for n in nets:
            ns.SetNetclassPatternAssignment(n, name)
    board.SynchronizeNetsAndNetClasses(True)


def route(board, edge):
    for layer, net in PLANES:
        add_zone(board, layer, net, edge)
    from critical import keepouts
    router_only = keepouts(board)
    preroute(board)

    # Round 1 routes everything; rounds 2-3 start from the previous result so
    # Freerouting can finish the stragglers with the rest already in place.
    # (Same process on purpose: reloading a routed board trips a pcbnew SWIG
    # bug in KiCad 10.0.5.)
    for rnd, passes in ((1, PASSES), (2, max(10, PASSES // 2)), (3, max(10, PASSES // 3))):
        dsn = os.path.join(WORK, f"board{rnd}.dsn")
        ses = os.path.join(WORK, f"board{rnd}.ses")
        if os.path.exists(ses):
            os.remove(ses)
        pcbnew.ExportSpecctraDSN(board, dsn)
        print(f"freerouting round {rnd}: {passes} passes max ...", flush=True)
        cmd = ["freerouting", "-de", dsn, "-do", ses, "-mp", str(passes)]
        if THREADS:
            cmd += ["-mt", THREADS]
        if STRATEGY:
            cmd += ["-us", STRATEGY]
        subprocess.run(cmd + ["--gui.enabled=false"], check=True, cwd=WORK,
                       stdout=open(os.path.join(WORK, f"freerouting{rnd}.log"), "w"),
                       stderr=subprocess.STDOUT)
        if not os.path.exists(ses):
            sys.exit(f"freerouting produced no session file, see build/route/freerouting{rnd}.log")
        pcbnew.ImportSpecctraSES(board, ses)

    # Freerouting sometimes necks tracks down below JLCPCB's 0.09 mm minimum
    # right at a pad; widen those stubs
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetWidth() < mm(0.1):
            t.SetWidth(mm(0.1))
    drop_unused_vias(board)
    for z in router_only:           # they cover hand-drawn tracks; DRC would flag them
        board.Remove(z)

    for layer, net in POURS:
        add_zone(board, layer, net, edge, priority=0)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    stitch(board, edge)
    filler.Fill(board.Zones())
    for _ in range(2):          # new vias can change the fill; check twice
        if not patch_fragments(board):
            break
        filler.Fill(board.Zones())

    pcbnew.SaveBoard(OUT, board)
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    print(f"routed: {len(tracks)} track segments, {len(vias)} vias -> {OUT}")


if __name__ == "__main__":
    main()
