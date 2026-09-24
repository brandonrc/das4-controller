# Run inside the KiCad automation container, e.g.:
#   distrobox enter pcb -- make
# CI uses the same image: ghcr.io/inti-cmnb/kicad10_auto_full

PCB  := hardware/das4-controller.kicad_pcb
FAB  := Edge.Cuts,F.Fab,B.Fab,F.Courtyard,Dwgs.User,Cmts.User,F.SilkS

.PHONY: all board docs drc clean

all: board docs drc

board:
	python3 hardware/scripts/gen_board.py

docs: board
	kicad-cli pcb export pdf --mode-single --black-and-white --sp --ibt --scale 1 \
		-l $(FAB) -o docs/fit-check-1to1.pdf $(PCB)
	kicad-cli pcb render --side top --width 1200 --height 1500 --zoom 1 -o docs/render-top.png $(PCB)
	kicad-cli pcb render --side bottom --width 1200 --height 1500 --zoom 1 -o docs/render-bottom.png $(PCB)

drc: board
	mkdir -p build
	kicad-cli pcb drc -o build/drc.rpt $(PCB)

clean:
	rm -rf build
