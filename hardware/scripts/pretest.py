#!/usr/bin/env python3
"""Check the hand layout before a 20-minute autoroute.

    make pretest     # -> build/pre.kicad_pcb + build/pre_drc.json

Applies the planes, the keep-outs and the hand pre-routes (critical.py,
plane fanout, switch ties) to the *placed* board, then DRC shows any clash in
the hand geometry right away. Router-only keep-outs are removed first, like
route.py does. Expect "unconnected" items (nothing is routed yet) and
dangling vias; everything else should be empty.
"""
import os
import shutil
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import route as R                      # noqa: E402
from critical import keepouts, pair_via_band  # noqa: E402

HW = os.path.dirname(HERE)
ROOT = os.path.dirname(HW)
OUT = os.path.join(ROOT, "build", "pre.kicad_pcb")


def main():
    b = pcbnew.LoadBoard(os.path.join(HW, "das4-controller.kicad_pcb"))
    R.setup_netclasses(b)
    o = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(o, True)
    edge = o.Outline(0)
    for layer, net in R.PLANES:
        R.add_zone(b, layer, net, edge)
    router_only = keepouts(b)
    R.preroute(b)
    router_only += pair_via_band(b)
    for z in router_only:
        b.Remove(z)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pcbnew.SaveBoard(OUT, b)
    shutil.copy(os.path.join(HW, "das4-controller.kicad_pro"), OUT.replace(".kicad_pcb", ".kicad_pro"))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
