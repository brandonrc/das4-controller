#!/usr/bin/env python3
"""Post-route checks DRC can't do (layout reviews 2 and 3).

    make check

- no foreign copper within 0.2 mm of the crystal block (Y1, C230, C231,
  R231): its keep-out is router-only, so DRC doesn't see it
- vias touching pads (bounding-box test, so round pads can give false
  positives; DRC catches any real short)
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from critical import box, xy  # noqa: E402

PCB = os.path.join(os.path.dirname(HERE), "das4-controller.kicad_pcb")
CRYSTAL_NETS = {"XIN", "XOUT_XTAL", "N$5", "GND"}


def main():
    b = pcbnew.LoadBoard(PCB)
    rects = [box(b, r, 0.2) for r in ("Y1", "C230", "C231", "R231")]

    def inside(x, y):
        return any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in rects)

    foreign = set()
    for t in b.GetTracks():
        is_via = t.GetClass() == "PCB_VIA"
        if t.GetNetname() in CRYSTAL_NETS or (not is_via and t.GetLayer() != pcbnew.F_Cu):
            continue
        if is_via:
            pts = [t.GetPosition()]
        else:
            s, e = t.GetStart(), t.GetEnd()
            pts = [pcbnew.VECTOR2I(int(s.x + (e.x - s.x) * k / 10), int(s.y + (e.y - s.y) * k / 10))
                   for k in range(11)]
        if any(inside(*xy(p)) for p in pts):
            foreign.add((t.GetNetname(), t.GetClass()))
    print("foreign copper in the crystal block:", sorted(foreign) or "none")

    n = 0
    for v in b.GetTracks():
        if v.GetClass() != "PCB_VIA":
            continue
        c, r = v.GetPosition(), v.GetWidth(pcbnew.F_Cu) / 2
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if (not p.IsOnLayer(pcbnew.F_Cu) or p.HasHole()
                        or (fp.GetReference() == "U1" and p.GetNumber() == "81")):
                    continue
                bb = p.GetBoundingBox()
                dx = max(bb.GetLeft() - c.x, 0, c.x - bb.GetRight())
                dy = max(bb.GetTop() - c.y, 0, c.y - bb.GetBottom())
                if (dx * dx + dy * dy) ** 0.5 < r:
                    n += 1
                    print(f"  via ({v.GetNetname()}) at {tuple(round(q, 2) for q in xy(c))} "
                          f"touches {fp.GetReference()}.{p.GetNumber()} ({p.GetNetname()})")
    print(f"vias touching pads (not counting U1's exposed pad): {n}")
    sys.exit(1 if foreign else 0)


if __name__ == "__main__":
    main()
