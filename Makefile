# Hex-map pipeline. `make maps` rebuilds the Rust app's world file
# (neolith-rs/assets/world.bin) from raw/, via build/combined_map.geojson.
PY := .venv/bin/python
ETOPO_URL := https://coastwatch.pfeg.noaa.gov/erddap/griddap/etopo180.esriAscii?altitude%5B(76.5):2:(5.5)%5D%5B(-17.0):2:(66.5)%5D
# 6 arc-min, 12 degrees beyond the map on every side: sea off the map's edge ([edge_sea]).
ETOPO_WIDE_URL := https://coastwatch.pfeg.noaa.gov/erddap/griddap/etopo180.esriAscii?altitude%5B(84):6:(-6)%5D%5B(-29):6:(78)%5D

# Settlements: `pipeline build` reads the `make settlements` output when
# present, else the original hand-made list, and writes build/settlements.geojson
# with occupation cut where the sea takes a site ([settled_land]); that's what
# gets converted.
WORLD := neolith-rs/assets/world.bin

# Inferred settlements (data/settlements/INFERRED.md): `make inferred` after
# `make maps`, then `make maps` again to put them in the world file.
.PHONY: inferred maps maps-unlocked test settlements cultures-check anchors residuals residuals-unlocked
BIOME_URL := https://ndownloader.figshare.com/files/22659026
GEOGLOWS_URL := https://geoglows-v2.s3.amazonaws.com
GEOGLOWS := build/geoglows/v2-model-table.parquet build/geoglows/global_streams_simplified.gpkg

# The whole recipe runs under build/.lock (pipeline/lock.py), so no other
# pipeline run can rewrite build/ between the two steps.
maps: .venv build/etopo.asc build/etopo_wide.asc build/biome.npz $(GEOGLOWS)
	$(PY) -m pipeline.lock build -- $(MAKE) --no-print-directory maps-unlocked

maps-unlocked:
	$(PY) -m pipeline build
	cd neolith-rs && cargo run --release -q -p neolith-convert -- \
		../build/combined_map.geojson ../build/settlements.geojson --rivers ../build/rivers.geojson --lakes ../build/lakes.geojson \
		$(if $(wildcard data/settlements/dates.csv.gz),--dates ../data/settlements/dates.csv.gz) \
		$(if $(wildcard data/isostyle/speculative/evidence_layers.json),--evidence ../data/isostyle/speculative/evidence_layers.json) \
		$(if $(wildcard data/population/residuals.csv.gz),--residuals ../data/population/residuals.csv.gz) \
		$(if $(wildcard data/settlements/inferred.geojson),--inferred ../data/settlements/inferred.geojson) \
		--heightmap ../build/etopo.asc \
		--cultures ../data/cultures/cultures.json -o ../$(WORLD)

# Where the site list falls short of what its own pattern predicts, and why
# (data/population/), then put into the world file for the app's Missing
# sites map mode. Needs `make maps` and the `make settlements` downloads.
# Runs under the build lock: it reads and rewrites the world file.
residuals: .venv
	$(PY) -m pipeline.lock build -- $(MAKE) --no-print-directory residuals-unlocked

residuals-unlocked:
	mkdir -p build/population
	cd neolith-rs && cargo run --release -q -p neolith-convert -- assets/world.bin --expected ../build/population/expected.csv
	$(PY) -m pipeline residuals
	cd neolith-rs && cargo run --release -q -p neolith-convert -- assets/world.bin --residuals ../data/population/residuals.csv.gz -o assets/world.bin

inferred: .venv
	$(PY) -m pipeline inferred

# Downloads to build/settlements/ once (about 660 MB; the Wikidata part can take an hour), writes data/settlements/.
settlements: .venv
	$(PY) -m pipeline settlements

# Fetches the Wikipedia article each entry of data/cultures/cultures.toml
# cites and records which traits it supports. Rerun `make settlements` after.
cultures-check: .venv
	$(PY) -m pipeline cultures-check

# Pollen anchor records for checking the biome maps (data/terrain/anchors*.csv).
# Downloads about 30 MB once to build/anchors/, plus one Neotoma record per anchor.
anchors: .venv build/combined_map.geojson
	$(PY) -m pipeline anchors

test: .venv
	$(PY) -m unittest discover -s pipeline/tests -t .
	$(PY) -m unittest discover -s isostyle/tests -t .

.venv: pipeline/requirements.txt isostyle/requirements.txt
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

# GEOGLOWS v2 stream network (CC BY 4.0; TDX-Hydro, CC BY-SA 4.0): the global
# attribute table (245 MB) and simplified stream lines (2.1 GB), joined on
# LINKNO by pipeline/geoglows.py. curl -C - resumes an interrupted download.
build/geoglows/v2-model-table.parquet:
	mkdir -p build/geoglows
	curl -fSL -C - -o $@.part $(GEOGLOWS_URL)/tables/v2-model-table.parquet && mv $@.part $@
build/geoglows/global_streams_simplified.gpkg:
	mkdir -p build/geoglows
	curl -fSL -C - -o $@.part $(GEOGLOWS_URL)/hydrography-global/global_streams_simplified.gpkg && mv $@.part $@

build/etopo.asc:
	mkdir -p build
	curl -fsS -o $@ '$(ETOPO_URL)'

build/etopo_wide.asc:
	mkdir -p build
	curl -fsS -o $@ '$(ETOPO_WIDE_URL)'
