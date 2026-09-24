# Run inside the KiCad automation container, e.g.:
#   distrobox enter pcb -- make
# CI uses the same image: ghcr.io/inti-cmnb/kicad10_auto_full

PCB  := hardware/das4-controller.kicad_pcb
FAB  := Edge.Cuts,F.Fab,B.Fab,F.Courtyard,Dwgs.User,Cmts.User,F.SilkS
# 3D models for renders: the KiCad Flatpak library as seen from a distrobox.
# Override with KICAD10_3DMODEL_DIR=/path/to/3dmodels if yours live elsewhere.
KICAD10_3DMODEL_DIR ?= /run/host/var/lib/flatpak/runtime/org.kicad.KiCad.Library.Packages3D/x86_64/stable/active/files/3dmodels
export KICAD10_3DMODEL_DIR
RENDER := kicad-cli pcb render --width 1600 --height 2000 --zoom 0.9 --quality high --floor

.PHONY: all board docs drc clean

all: board docs drc

board:
	python3 hardware/scripts/gen_board.py

docs: board
	kicad-cli pcb export pdf --mode-single --black-and-white --sp --ibt --scale 1 \
		-l $(FAB) -o docs/fit-check-1to1.pdf $(PCB)
	$(RENDER) --side top -o docs/render-top.png $(PCB)
	$(RENDER) --side bottom -o docs/render-bottom.png $(PCB)
	kicad-cli pcb render --width 1600 --height 1200 --quality high --floor --perspective --zoom 0.8 --rotate '-45,0,-60' -o docs/render-3d.png $(PCB)

drc: board
	mkdir -p build
	kicad-cli pcb drc -o build/drc.rpt $(PCB)

clean:
	rm -rf build
