# Hand-extracted inputs

## `jordan2016_africa.csv`

The African rows of the earliest-pottery table in the online supplement
(S0003598X16000685sup001.pdf) to Jordan, P., Gibbs, K., Hommel, P.,
Piezonka, H., Silva, F. & Steele, J. 2016. Modelling the diffusion of
pottery technologies across Afro-Eurasia: emerging insights and future
research. *Antiquity* 90(351): 590–603.
https://doi.org/10.15184/aqy.2016.68

- Extracted from the PDF's text on 2026-11-12. One row per site: the
  earliest pottery-bearing date the authors list.
- `cal_bp` is the authors' median calibrated age. `c14_bp` is unreliable
  where the PDF wrapped the date onto a second line (it then reads 0, 2, 5,
  8, 9 or 50); the pipeline ignores it.
- Country names in `site` are the authors' ("Gobero, Mali" is in Niger;
  the coordinates are right).
- Coordinates are to 0.1°.
- The supplement states no licence. These are bibliographic facts
  (site, place, date) restated with citation; check before redistributing.
