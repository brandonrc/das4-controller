#!/usr/bin/env python3
"""Route the board N times in parallel and keep the best result.

    make route            # ROUTE_RUNS=4 by default

Freerouting is deterministic for a given input and settings, so each run gets
different settings (pass count, update strategy). Each candidate is
DRC-checked; the winner has the fewest unconnected items, then the fewest
real (non-silkscreen) violations. Net classes live in the .kicad_pro, so the
winner's project file is copied along with its board.
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
ROOT = os.path.dirname(HW)
PCB = os.path.join(HW, "das4-controller.kicad_pcb")
# (passes, Freerouting update strategy) per parallel run
# Freerouting is not fully deterministic here, so more variants = more chances
VARIANTS = [(36, "greedy"), (44, "global"), (30, "hybrid"), (52, "greedy"), (40, "hybrid"), (48, "greedy")]
RUNS = int(os.environ.get("ROUTE_RUNS", str(len(VARIANTS))))
COSMETIC = {"silk_overlap", "silk_over_copper", "silk_edge_clearance",
            "malformed_courtyard", "isolated_copper", "starved_thermal"}


def score(board, report):
    subprocess.run(["kicad-cli", "pcb", "drc", "--refill-zones", "--format", "json",
                    "-o", report, board], check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    r = json.load(open(report))
    real = [v for v in r.get("violations", []) if v["type"] not in COSMETIC]
    return len(r.get("unconnected_items", [])), len(real)


def main():
    placed = os.path.join(ROOT, "build", "placed.kicad_pcb")
    os.makedirs(os.path.dirname(placed), exist_ok=True)
    shutil.copy(PCB, placed)
    threads = str(max(2, (os.cpu_count() or 4) // RUNS - 1))
    procs = []
    for i in range(RUNS):
        work = os.path.join(ROOT, "build", f"route{i}")
        os.makedirs(work, exist_ok=True)
        out = os.path.join(work, "routed.kicad_pcb")
        passes, strategy = VARIANTS[i % len(VARIANTS)]
        env = dict(os.environ, ROUTE_WORK=work, ROUTE_OUT=out, ROUTE_THREADS=threads,
                   ROUTE_PASSES=str(passes), ROUTE_STRATEGY=strategy)
        log = open(os.path.join(work, "route.log"), "w")
        procs.append((i, out, subprocess.Popen([sys.executable, os.path.join(HERE, "route.py")],
                                               env=env, stdout=log, stderr=subprocess.STDOUT)))
    results = []
    for i, out, p in procs:
        p.wait()
        if p.returncode or not os.path.exists(out):
            print(f"run {i}: failed (see build/route{i}/route.log)")
            continue
        unc, real = score(out, os.path.join(ROOT, "build", f"route{i}", "drc.json"))
        print(f"run {i} {VARIANTS[i % len(VARIANTS)]}: {unc} unconnected, {real} real violations")
        results.append((unc, real, i, out))
    if not results:
        sys.exit("all routing runs failed")
    unc, real, i, out = min(results)
    shutil.copy(out, PCB)
    shutil.copy(out.replace(".kicad_pcb", ".kicad_pro"), PCB.replace(".kicad_pcb", ".kicad_pro"))
    print(f"kept run {i}: {unc} unconnected, {real} real violations -> {PCB}")


if __name__ == "__main__":
    main()
