# Run inside the KiCad automation container, e.g.:
#   distrobox enter pcb -- make
# CI uses the same image: ghcr.io/inti-cmnb/kicad10_auto_full
#
#   make            circuit -> netlist -> board -> renders + fit-check PDF -> DRC
#   make bom        docs/bom.md with live JLCPCB stock (needs internet)
#   make fab        JLCPCB order files in build/jlcpcb/
#   make parts      re-fetch JLC footprints/symbols/3D models (needs internet)

PCB  := hardware/das4-controller.kicad_pcb
NET  := hardware/das4-controller.net
FAB  := Edge.Cuts,F.Fab,B.Fab,F.Courtyard,Dwgs.User,Cmts.User,F.SilkS
DEPS := .deps
PY   := PYTHONPATH=$(DEPS) python3
# 3D models for renders: the KiCad Flatpak library as seen from a distrobox.
# Override with KICAD10_3DMODEL_DIR=/path/to/3dmodels if yours live elsewhere.
KICAD10_3DMODEL_DIR ?= /run/host/var/lib/flatpak/runtime/org.kicad.KiCad.Library.Packages3D/x86_64/stable/active/files/3dmodels
export KICAD10_3DMODEL_DIR
RENDER := kicad-cli pcb render --width 1600 --height 2000 --zoom 0.9 --quality high --floor

.PHONY: all netlist board docs drc bom fab parts clean

all: board docs drc

# SKiDL + easyeda2kicad, installed next to the repo (the container's Python
# has no venv/ensurepip, and pcbnew must stay importable)
$(DEPS): hardware/requirements.txt
	pip3 install -q --break-system-packages --target $(DEPS) -r hardware/requirements.txt
	touch $(DEPS)

netlist: $(DEPS)
	$(PY) hardware/circuit/das4.py $(NET)

board: netlist
	$(PY) hardware/scripts/gen_board.py

docs: board
	kicad-cli pcb export pdf --mode-single --black-and-white --sp --ibt --scale 1 \
		-l $(FAB) -o docs/fit-check-1to1.pdf $(PCB)
	$(RENDER) --side top -o docs/render-top.png $(PCB)
	$(RENDER) --side bottom -o docs/render-bottom.png $(PCB)
	kicad-cli pcb render --width 1600 --height 1200 --quality high --floor --perspective --zoom 0.8 --rotate '-45,0,-60' -o docs/render-3d.png $(PCB)

drc: board
	mkdir -p build
	kicad-cli pcb drc -o build/drc.rpt $(PCB)

bom: netlist
	python3 hardware/scripts/bom.py

# JLCPCB upload files -> build/jlcpcb/ (gerber zip, bom.csv, cpl.csv)
fab: board
	$(PY) hardware/scripts/jlc_fab.py

# LCSC parts fetched into hardware/lib with easyeda2kicad (plain Rs/Cs, the
# AMS1117 and the diode use KiCad's stock footprints)
JLC_PARTS := C42415655 C4154405 C165948 C456018 C97521 C20625731 C42411119 \
             C2837531 C318884 C351238 C4154875
parts: $(DEPS)
	cd hardware/lib && PYTHONPATH=../../$(DEPS) python3 -m easyeda2kicad --full --project-relative \
		--overwrite --lcsc_id $(JLC_PARTS) --output $$PWD/jlc
	sed -i 's|$${KIPRJMOD}/jlc.3dshapes/|$${KIPRJMOD}/lib/jlc.3dshapes/|' hardware/lib/jlc.pretty/*.kicad_mod
	sed -i 's/AF90°WJDG/AF90-WJDG/g' hardware/lib/jlc.kicad_sym

clean:
	rm -rf build $(DEPS)
