# Transcription scripts for the tracked date tables

These scripts made `data/settlements/aadr_dates.csv` and
`data/settlements/literature_dates.csv`. They are kept as a record of how each
row was produced; the build reads only the CSVs. Every row in the CSVs carries
its own source, page and precision note, which `pipeline/tests/test_local_tables.py`
checks.

Paths are relative to a working directory holding the downloaded PDFs and
their extracted text (`dl_*` folders, not kept in the repo: each PDF is linked
from the row's `source`/`refs` and from `data/settlements/SOURCES.md`).

- `aadr.py`: Russian direct-dated individuals from AADR v66.p1, as burial sites.
- `zaretskaya.py`: Zaretskaya et al. 2005 and 2012 (Upper Volga bogs; Shigir, Gorbunovo).
- `don_volga.py`: Tsybrij et al. 2017 (Lower Don) and Kulkova et al. 2019 (Algay, Oroshaemoe I).
- `karelia_kama/`: Tarasov et al. 2017 (Karelia; `tarasov_rows.py`, `tparse.py`),
  Seitsonen et al. 2012 (Karelian Isthmus; `seits_rows.py`, `sgeo.py`, `sdots.py`),
  Lychagina & Vybornov 2017 (Kama; `kama_rows.py`, `kgeo.py`, `dots.py`, `blobs.py`).
  The `*geo*.py` and `*dots.py` scripts georeference map figures to place
  sites given only by map locality; those rows are flagged `approximate`.
- `lower_volga.py`: Vybornov et al. 2013, Vybornov 2016, Vybornov et al. 2017
  (Documenta Praehistorica) and Vybornov et al. 2022 (Vestnik VolGU): Lower Volga
  and North Caspian Neolithic-Eneolithic (Kairshak, Baibek, Tenteksor, Kugat,
  Jangar, Varfolomeevka, Algay, Oroshaemoe I). Writes rows whose lab numbers
  are not yet in `literature_dates.csv`; these were appended to it directly.
  It georeferences Vybornov 2016 Fig. 1 with an affine fit for sites known
  only from that map.
- `merge.py`: merges the per-paper CSVs into `literature_dates.csv`, dropping
  lab numbers printed for two different dates or sites.
- `count.py`: counts sites per place box (`data/places/places.toml`).

No script was kept for Zaitseva et al. 2000: its rows went straight from the
paper's extracted text into `zaitseva2000.csv`.
