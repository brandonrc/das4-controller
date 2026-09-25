#!/usr/bin/env python3
"""JLCPCB order files: Gerber zip, BOM and CPL (pick-and-place).

    make fab      # -> build/jlcpcb/

Upload on jlcpcb.com: the zip as the board, then enable "PCB Assembly" and
upload bom.csv and cpl.csv. Only parts JLCPCB solders are listed; the
hand-solder parts (Assembly=hand) and non-parts (J4, test pads, holes)
are left out.
"""
import csv
import os
import shutil
import subprocess
import sys
import zipfile

import pcbnew

HW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(HW)
PCB = os.path.join(HW, "das4-controller.kicad_pcb")
OUT = os.path.join(ROOT, "build", "jlcpcb")

LAYERS = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"

# JLCPCB's 0-degree orientation differs from KiCad's for some *KiCad library*
# packages (the jlc: footprints come from JLCPCB's own library and need no
# correction). Check JLCPCB's placement preview after uploading either way.
ROT_FIX = {"SOT-223-3_TabPin2": 180}


def run(*cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    gdir = os.path.join(OUT, "gerbers")
    os.makedirs(gdir)
    run("kicad-cli", "pcb", "export", "gerbers", "--layers", LAYERS, "--subtract-soldermask",
        "--use-drill-file-origin", "-o", gdir + "/", PCB)
    run("kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--drill-origin", "plot",
        "--excellon-separate-th", "-o", gdir + "/", PCB)
    routed = any(t.GetClass() == "PCB_TRACK" for t in pcbnew.LoadBoard(PCB).GetTracks())
    name = "das4-controller-gerbers.zip" if routed else "das4-controller-gerbers-UNROUTED-quote-only.zip"
    with zipfile.ZipFile(os.path.join(OUT, name), "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, f), f)

    board = pcbnew.LoadBoard(PCB)
    origin = board.GetDesignSettings().GetAuxOrigin()
    groups, cpl = {}, []
    for fp in board.GetFootprints():
        if fp.IsExcludedFromBOM() or fp.IsExcludedFromPosFiles() or not fp.HasField("LCSC"):
            continue
        ref, lcsc = fp.GetReference(), fp.GetFieldText("LCSC")
        fpname = fp.GetFPID().GetLibItemName().wx_str()
        g = groups.setdefault(lcsc, {"value": fp.GetValue(), "fp": fpname, "refs": []})
        g["refs"].append(ref)
        pos = fp.GetPosition()
        rot = (fp.GetOrientationDegrees() + ROT_FIX.get(fpname, 0)) % 360
        cpl.append([ref, f"{pcbnew.ToMM(pos.x - origin.x):.4f}mm", f"{pcbnew.ToMM(origin.y - pos.y):.4f}mm",
                    "Top" if fp.GetLayer() == pcbnew.F_Cu else "Bottom", f"{rot:.1f}"])

    with open(os.path.join(OUT, "bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for lcsc, g in sorted(groups.items(), key=lambda kv: kv[1]["refs"][0]):
            w.writerow([g["value"], ",".join(sorted(g["refs"])), g["fp"], lcsc])
    with open(os.path.join(OUT, "cpl.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        w.writerows(sorted(cpl))
    print(f"wrote {OUT}: {name}, bom.csv ({len(groups)} lines), cpl.csv ({len(cpl)} parts)")


if __name__ == "__main__":
    main()
