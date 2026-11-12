# Hex-map pipeline. `make maps` rebuilds the Rust app's world file
# (neolith-rs/assets/world.bin) from raw/, via build/combined_map.geojson.
PY := .venv/bin/python
ETOPO_URL := https://coastwatch.pfeg.noaa.gov/erddap/griddap/etopo180.esriAscii?altitude%5B(76.5):2:(5.5)%5D%5B(-17.0):2:(66.5)%5D

# `make settlements` output when present, else the original hand-made list.
SETTLEMENTS := $(firstword $(wildcard data/settlements/settlements.geojson) \
	game/static/game/assets/settlements.geojson)
WORLD := neolith-rs/assets/world.bin

.PHONY: maps test settlements cultures-check
BIOME_URL := https://ndownloader.figshare.com/files/22659026
HYDRORIVERS := $(foreach r,af eu as,build/hydrorivers/HydroRIVERS_v10_$(r)_shp/HydroRIVERS_v10_$(r).shp)

maps: .venv build/etopo.asc build/biome.npz $(HYDRORIVERS)
	$(PY) -m pipeline build
	cd neolith-rs && cargo run --release -q -p neolith-convert -- \
		../build/combined_map.geojson ../$(SETTLEMENTS) --rivers ../build/rivers.geojson --lakes ../build/lakes.geojson -o ../$(WORLD)

# Downloads to build/settlements/ once (about 660 MB; the Wikidata part can take an hour), writes data/settlements/.
settlements: .venv
	$(PY) -m pipeline settlements

# Fetches the Wikipedia article each entry of data/cultures/cultures.toml
# cites and records which traits it supports. Rerun `make settlements` after.
cultures-check: .venv
	$(PY) -m pipeline cultures-check

test: .venv
	$(PY) -m unittest discover -s pipeline/tests -t .

.venv: pipeline/requirements.txt
	/opt/homebrew/bin/python3.13 -m venv .venv
	.venv/bin/pip install -q -r pipeline/requirements.txt
	touch .venv

# Beyer et al. 2020 BIOME4 biomes (1.3 GB NetCDF, CC BY 4.0), cut to our box
# and years. After changing [paleobiome] box/bp_*, delete build/biome.npz.
build/biome.npz: build/LateQuaternary_Environment.nc | .venv
	$(PY) -m pipeline biome

build/LateQuaternary_Environment.nc:
	mkdir -p build
	curl -fSL -o $@.part '$(BIOME_URL)' && mv $@.part $@

# HydroRIVERS v1.0 (Lehner & Grill 2013), Africa/Europe/Asia, about 270 MB zipped.
build/hydrorivers/HydroRIVERS_v10_%_shp/HydroRIVERS_v10_%.shp:
	mkdir -p build/hydrorivers
	curl -fSL -o build/hydrorivers/$*.zip.part https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_$*_shp.zip
	cd build/hydrorivers && unzip -oq $*.zip.part && rm $*.zip.part
	touch $@

build/etopo.asc:
	mkdir -p build
	curl -fsS -o $@ '$(ETOPO_URL)'
