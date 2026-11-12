# Coasts: sources and reasoning

The board's coast is ETOPO1 plus the sea curve. ETOPO1 is today's surface,
so wherever rivers have since filled in former sea, the board shows land
where there was sea or open lagoon. `coasts.toml` adds dated polygons of that
former sea; `pipeline/coasts.py` turns hexes mostly inside a polygon to
Water for the polygon's years, right after the sea step. Rivers end where
Water begins, so their lower courses shorten to match. The polygons are drawn
by hand from the sources' maps and descriptions and are approximate to about
0.1°. `build/coasts.geojson` has them for checking in QGIS.

Years are BCE (BCE = cal BP − 1950).

## Persian Gulf head (low confidence)

| Source | Claim | Used |
|---|---|---|
| Bogemans et al. 2016, 2017 | Transgression from about 7.8 cal ka, estuarine for 2000–2500 years, progradation from about 4.9 ka; tidal influence confined to channels, no general flooding | Timing: −5850 to past the map's end |
| Cooke 1987 | Sea reached Diwaniyah and Kut | Rejected: would put Uruk under the sea |
| Hritz & Pournelle 2015 | Sea reached Samawah | Rejected, same reason |
| Aqrawi 1995, 2001 | Nasiriyah and Amarah | Maximum, from −5000 |
| Jotheri et al. 2017 | Uruk stayed freshwater throughout the Holocene | The western limit |

Two stages: the estuary up to Qurna and Basra from −5850, Aqrawi's limit
from −5000. Bogemans et al.'s "channels only" reading would mean no Water
hexes at all; this is the generous reading of a contested question. The
summary of the competing limits is Jotheri et al. 2017 §5.1.

## Po coastal plain (medium confidence)

- Bruno et al. 2017: a wave-dominated estuary migrated landward 11.5–7.0
  cal ka (137 radiocarbon dates); the shoreline reached its furthest inland
  position about 7.7 cal ka. A separate review puts the maximum at about
  5–6 ka and about 30 km inland of today.
- The strip, about 30 km wide, is Water from −5750. The late-Holocene delta
  built out from about 5.5 ka, but Adria was still near the coast about
  2.5 ka, so the strip is kept to the map's end.

## Northern Nile delta (low confidence)

- Marine and shallow-marine sediments 12.0–7.5 ka in the Burullus area, with
  the coastline further south (Arbouille & Stanley 1991, via Giaime et al.
  2022); locally as much as 30 km south of today's eastern delta coast
  (Manzala region).
- The delta built seaward from about 7.5 ka; peat at Burullus shows the
  coast seaward again by 7–5.7 ka (Giaime et al. 2022). A marsh at Buto,
  30 km inland, dates to 6–4.5 ka (Wunderlich 1988).
- Stages: a northern strip (15–30 km) from −7000 to −5000, then the Manzala
  region only. The onset is set where the board's sea curve has risen enough
  for a drowned delta surface to be plausible; before then the board's coast
  is well north of today's.

## References

- Jotheri, J. et al., 2017. Holocene fluvial and anthropogenic processes in
  the region of Uruk in southern Mesopotamia. *Quaternary International*.
  https://doi.org/10.1016/j.quaint.2017.11.037;
  https://www.ancientportsantiques.com/wp-content/uploads/Documents/PLACES/IndOc-Gulf/Uruk-Jotheri2018.pdf
- Bogemans, F. et al., 2016, 2017; Cooke, G.A., 1987; Hritz, C. &
  Pournelle, J., 2015; Aqrawi, A.A.M., 1995, 2001 (all via Jotheri et al.
  2017).
- Bruno, L. et al., 2017. Early Holocene transgressive palaeogeography in the
  Po coastal plain (northern Italy). *Sedimentology* 64:1792.
  https://doi.org/10.1111/sed.12374;
  https://iris.unimore.it/bitstream/11380/1169644/3/sed.12374.pdf
- Po maximum transgression about 5–6 ka, about 30 km inland: Paleogeographic
  and paleoclimatic evolution of the Po Plain from 150-ky core records.
  https://www.researchgate.net/publication/238634586_Paleogeographic_and_paleoclimatic_evolution_of_the_Po_Plain_from_150-ky_core_records
- Giaime, M. et al., 2022. Holocene evolution and signature of environmental
  change of the Burullus lagoon (Nile Delta) deciphered from a long sediment
  record. *Palaeogeography, Palaeoclimatology, Palaeoecology* 590:110861.
  https://www.ancientportsantiques.com/wp-content/uploads/Documents/PLACES/Egypt-Libya/NileDelta/NileDelta-Giaime2022.pdf
- Arbouille, D. & Stanley, D.J., 1991; Wunderlich, J., 1988 (via Giaime et
  al. 2022).
- The modern Nile delta continental shelf, with an evolving record of relict
  deposits (2023): coastline up to 30 km south of today's eastern delta in
  the early Holocene; progradation about 7500 to 3000–2000 BP.
  https://www.mdpi.com/2673-7086/3/3/22
