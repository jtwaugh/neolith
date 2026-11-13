# Inferred settlements

`inferred.toml` turns the settlement speculation in the place plans
(`data/places/plans/<key>.toml`, `[[speculate]] target = "settlements"`) into
points; `python -m pipeline inferred` (`pipeline/inferred.py`) writes
`inferred.geojson`. They are guesses, not records:

- They sit beside the recorded settlements and never join them. Only the app
  reads them (`neolith-convert --inferred`), where they are drawn as pale,
  unlabelled pieces and the site panel says they are inferred and why. The
  residuals, survey intensity, culture inference and importance scores never
  see them, so they cannot feed site counts back into expected population.
- A point is dropped where a recorded site stands in its hex while the point
  would be occupied (`clear = "hex"`). Ingesting real sites retires the
  guesses hex by hex.
- Each has `sources = ["inferred"]`, `evidence = 0`, `importance = 0`, and an
  `inferred` property naming its rule, plan, branch (or shore) and
  confidence, plus `drowned` (the first frame year its hex is sea) where the
  sea later covers it and `tag` where a rule tags it.
- River rules space points down `data/rivers/rivers.toml` branches. Coast
  rules space them along the shore of each slice's own sea level (the
  `[sea]` curve on ETOPO1 at 2 arc-min) inside a box, taking named places
  (lagoons, wadi mouths) first. That shore is finer than the board: a point
  whose board hex is sea while it lives is not placed.
- Point rules (`[rule.points]`) put camps at named places, for lake shores
  the sea-level coast does not see (Lake Tana and Lake Abhe, neither on the
  board as a lake) and for single places such as a sheltered bay. A point
  on a board Water hex is not placed.

## Nile delta (`data/places/plans/nile_delta.toml`)

The delta's Neolithic surface lies under metres of Nile silt, and the open
radiocarbon compilations hold almost none of its excavated Predynastic
sites. The residuals call 16 of 25 land hexes at 4,000 BCE an unexplained
shortfall, in the best-surveyed part of Egypt.

- **`nile_delta_villages`** (medium confidence). Villages on geziras and
  levees 2.5–4 km off the Sebennytic and Pelusiac branches, one per 20 km,
  from 4,000 BCE to the end of the period. The model is the excavated delta
  villages: Buto, Sais, Tell el-Farkha and Tell el-Samara all sit on sand
  islands above the flood plain. Guyot et al. 2022 say the same of every
  prehistoric site known in the eastern delta, and describe Tell el-Samara as
  settled on "a sandy hill protruding above the alluvial plain" to stay out of
  reach of the flood but near the basins. A stopgap until the EES Delta Survey
  (783 sites with period attributions) is ingested; that needs permission
  from the EES.
- **`nile_delta_camps`** (low confidence). Three or four fishing and herding
  camps per millennium at 6,000 and 5,000 BCE off the Canopic branch and the
  southern Pelusiac branch, none north of 30.95°N or east of 31.7°E. Sais has
  a sequence from the sixth millennium BCE (Felbinger, TOPOI); Zhao et al.
  2025 (abstract only) put herding in the delta before about 7000 cal BP and
  argue that the early Holocene delta was too unstable for much settlement.
  The branch positions are those in `data/rivers/rivers.toml`.

## Bab-el-Mandeb (`data/places/plans/bab_el_mandeb.toml`)

No site in the box in any epoch. The emptiness is a hole in the dated
record: nothing prehistoric has been dated on the Djibouti or Eritrean
shore, and the Tihama middens are dune-covered, cut by wadis and mostly
undated. Before 6,000 BCE the shore itself is under water.

- **`bab_el_mandeb_shore_camps`** (medium confidence). Fisher-shellfisher
  camps on both shores, at least 50 km apart, from 6,000 BCE to the end of
  the period, a new set each millennium. Placed first at the Arabian side
  of the narrows, the Khor Angar lagoon, the Khor Umayra lagoon (Gihayu),
  Tadjoura, Djibouti, the wadi mouth at Mocha and Assab bay, then wherever
  the spacing allows. The southern Red Sea has more than 4,200 shell middens
  (Meredith-Williams et al. 2014), dated ones from about 8,000 cal BP in
  Eritrea; Hausmann et al. 2019 explain why mainland middens are rarely
  found or dated. Gihayu (Rosello et al. 2005) is a dated site of the fifth
  to fourth millennium BCE inside the box; it is not entered as a recorded
  site because the paper has not been opened (the plan has it as
  `checked = false`). When it is, it will clear the camp in its hex.
- **Obsidian exchange tag** (low confidence), on the same rule: from 5,000
  BCE the first camp on each shore (the two sides of the narrows) carries
  `tag = "obsidian exchange"`, standing in for the crossing until the game
  has a route layer. Lee 2023 reports obsidian on the al-Salif peninsula by
  5000 BC and Tihama obsidian sourced to Nabro in the Danakil.
- **`bab_el_mandeb_lowstand_camps`** (low confidence). Three forager camps
  per millennium from 10,000 to 7,000 BCE on the lowstand shore, at the two
  sides of the narrows and on the shelf west of Aden, marked drowned where
  the sea later takes their hex. Lambeck et al. 2011: the channels were
  under 4–5 km wide but never closed. Bailey et al. 2019: coastal use was
  episodic and absence of evidence is weak either way.

The plan's other points were for a person. The board drew the strait as
land at 10,000 and 8,000 BCE; since 2026-11-13 `[[sea.channel]]` in
`pipeline/config.toml` keeps it Water in every year (Lambeck et al. 2011).
Asa Koma, filed in Somaliland, is moved to the Gobaad plain by
`records.toml` (2026-11-13); its one date is after 3,000 BCE. Of its research items, Hardt et al. 2026 (Tadjoura) has been
read: all its radiocarbon ages are 51 BCE or later, so it adds nothing to
the period. The Gihayu reports and the Tihama survey lists are still to do;
they need a person to fetch them.

## Dahlak and the Gulf of Zula (`data/places/plans/dahlak.toml`)

Nothing in our data in the box or within 100 km in any epoch: the open
compilations have no Eritrean record at all. The coast has three dated shell
middens (Beyin and Bar-Yosef Mayer 2018) and the islands about 1,200
remote-sensed, undated shell mounds (Meredith-Williams et al. 2014).

- **`dahlak_shell_middens`** (medium confidence). Shell-midden camps at least
  30 km apart on the shore of each millennium from 6,000 BCE, inside the
  dahlak and gulf_of_zula boxes together, taking Massawa, Misse East, Asfet
  and Dahlak Kebir first. Five to seven a slice. None stands on the islands
  yet: the board has the Dahlak Kebir hex Water through the 6,000 BCE slice
  and after (an `islands.py` problem, being fixed), so the island cells are
  not usable and the mainland coast carries the rule. Once the islands are
  land the same rule places camps on them.
- **`dahlak_buri_hilltop_camps`** (medium confidence). Two camps on basalt
  hills inland on the Buri peninsula, Gelalo NW's pattern, each millennium
  from 6,000 BCE.
- **`dahlak_bank_lowstand_camps`** (low confidence). Two or three forager
  camps a slice from 9,000 to 7,000 BCE on the outer edge of the then-dry
  Dahlak bank, all marked drowned (their hexes flood between 7,900 and
  5,400 BCE).

## Lake Abhe (`data/places/plans/lake_abbe.toml`)

Empty in our data because the compilations hold nothing from Djibouti or the
Ethiopian Afar: Khalidi et al. (2020) dated seven sites with 37 dates, and
the Gobaad mission reports over 100. The board has no palaeolake, so the
camps are point rules at Lake Gamarri (Raso), Afambo on the lower Awash, the
north shore of Abhe and the Gobaad plain (Hara Idé, Asa Koma).

- **`lake_abbe_early_holocene_camps`** (medium). Four a slice, 10,000 to
  8,000 BCE, on the high early Holocene lake.
- **`lake_abbe_dry_interval_camp`** (low). One a slice at 7,000 and 6,000
  BCE on the lower Awash: the record's gap around the 8.2 ka dry event.
- **`lake_abbe_mid_holocene_camps`** (medium). Four a slice, 5,000 to 3,000
  BCE, in the second humid phase; at 3,000 BCE the Gobaad camp is tagged
  `first potter-herders` (low), on Khalidi et al.'s 4.8-3.3 ka cal BP for
  herding and pottery.

## Lake Tana (`data/places/plans/lake_tana.toml`)

Empty because the one dated lakeshore site, Kurtiye rock shelter (Firew
2014), and the undated Gorgora rock shelter (Sahle et al. 2024) are in no
open compilation. The board has no Lake Tana.

- **`lake_tana_early_camp`** (low). One aquatic forager camp at Gorgora at
  6,000 BCE, a millennium before Kurtiye's dates.
- **`lake_tana_camps`** (low). Three a slice, 5,000 to 3,000 BCE: Gorgora,
  the Blue Nile outlet at Bahir Dar and the Fogera shore. When Kurtiye is
  entered as a recorded site it clears the camp in its hex.

## Cape Guardafui (`data/places/plans/guardafui.toml`)

Empty because nobody has looked: the only fieldwork is Chittick's 1975
reconnaissance, which found Graeco-Roman landing places at Damo and Hafun.

- **`guardafui_damo_camp`** (low). One coastal forager camp a slice from
  6,000 BCE at Damo, the one sheltered beach by the cape.
- **`guardafui_hafun_camp`** (low). A second at 4,000 and 3,000 BCE by Hafun.
  The board draws the Hafun peninsula as Water, so it stands on the
  mainland side of the neck (51.1 E, 10.4 N).

## References

- Egypt Exploration Society, Delta Survey; Spencer, J. 2024. *Archaeological
  Sites of the Nile Delta of Egypt: A Gazetteer*. EES Excavation Memoir 119.
  https://www.ees.ac.uk/delta-survey
- Guyot, F., Abdel Azim, M.A., Hochstrasser-Petit, C., Lesur, J.,
  Midant-Reynes, B. & Muhammad, R. 2022. Investigating the Nile Delta's first
  settlements: excavations at Tell el-Samara 2016–2019. *BIFAO* 122:309–400
  (read; location 25 km south-east of al-Mansura, levels c. 4500–2900 BCE, no
  radiocarbon dates published). https://www.ifao.egnet.net/bifao/122/11/
- Felbinger, U., The Neolithic in the Nile Delta, TOPOI project A-2-4.
  https://topoi.org/feature/the-neolithic-in-the-nile-delta/
- Zhao, X., Kaniewski, D., Wang, Y., Marriner, N., Salem, A. et al. 2025. On
  the long and winding road: unravelling the late emergence of Neolithic
  agriculture in the Nile Delta. *Quaternary Science Reviews* 359:109368
  (abstract only). https://doi.org/10.1016/j.quascirev.2025.109368
- Meredith-Williams, M.G., Hausmann, N., Bailey, G.N. et al. 2014. 4200 new
  shell mound sites in the southern Red Sea. *Internet Archaeology* 37.
  https://intarch.ac.uk/journal/issue37/2/2.html
- Hausmann, N., Kokkinaki, O. & Leng, M.J. 2019. Red Sea palaeoclimate:
  stable isotope and element-ratio analysis of marine mollusc shells.
  https://nora.nerc.ac.uk/id/eprint/521853/1/Hausmann%20et%20al.%202019.%20Res%20Sea%20book%20chapter.pdf
- Rosello, E., Morales, A. & Popov, S. 2005. Preliminary survey of the Late
  Stone Age faunas from Gihayu (Khor Umayra lagoon, Republic of Yemen).
  *Archaeofauna* 14:253–265 (not opened).
  https://revistas.uam.es/archaeofauna/article/view/7448
- Lee, R. 2023. Crossing the Red Sea: a Yemen and Ethiopian interchange
  (obsidian at al-Salif; Nabro sourcing after Oppenheimer et al. 2019).
  https://eprints.whiterose.ac.uk/id/eprint/206498/1/Yemen_Ethiopia_Lee_.pdf
- Lambeck, K., Purcell, A., Flemming, N.C., Vita-Finzi, C., Alsharekh, A.M. &
  Bailey, G.N. 2011. Sea level and shoreline reconstructions for the Red Sea.
  *Quaternary Science Reviews* 30:3542–3574.
  https://disperse-project.org/sites/disperse-project.org/files/uploads/2011_Lambeck_etal._QSR_RedSea.pdf
- Bailey, G.N., Meredith-Williams, M., Alsharekh, A. & Hausmann, N. 2019. The
  archaeology of Pleistocene coastal environments and human dispersals in the
  Red Sea: insights from the Farasan Islands.
  https://disperse-project.org/sites/disperse-project.org/files/uploads/2019_Chap26_Bailey_etal.pdf
- Meredith-Williams, M.G., Hausmann, N., Inglis, R.H. & Bailey, G.N. 2014.
  4200 new shell mound sites in the southern Red Sea (PDF). *Internet
  Archaeology* 37. https://intarch.ac.uk/journal/issue37/2/ia.37.2.pdf
- Beyin, A. & Bar-Yosef Mayer, D.E. 2018. Prehistoric settlements on the Red
  Sea coast of Eritrea. In *Early Maritime Cultures in East Africa and the
  Western Indian Ocean*, Archaeopress, pp. 1-32 (Fig. 4, the shell dates).
  https://www.archaeopress.com/Archaeopress/DMS/EF8E85A7FCEC4ED5B414B15060004654/9781784917128-sample.pdf
- Khalidi, L., Mologni, C., Ménard, C. et al. 2020. 9000 years of human
  lakeside adaptation in the Ethiopian Afar. *Quaternary Science Reviews*
  243:106459 (abstract only). https://doi.org/10.1016/j.quascirev.2020.106459
- INRAP / Ministère de la Culture, On the banks of Lake Abbe (Gobaad
  mission, Djibouti). https://archeologie.culture.gouv.fr/en/banks-lake-abbe
- Dupuy, C. 2019. Review of Gutherz (dir.) 2017, *Asa Koma*. *Journal des
  africanistes*. https://journals.openedition.org/africanistes/7945
- Firew, G.A. 2014. *Archaeological fieldwork around Lake Tana area of
  Ethiopia* (PhD, Bergen; abstract only). https://hdl.handle.net/1956/8931
- Sahle, Y. et al. 2024. Gorgora rock shelter, Lake Tana. *Scientific
  Reports* 14:17038. https://doi.org/10.1038/s41598-024-67743-x
- Chittick, N. 1976. An archaeological reconnaissance in the Horn: the
  British-Somali expedition, 1975. *Azania* 11:117-133.
  https://www.ancientportsantiques.com/wp-content/uploads/Documents/PLACES/IndOc-Gulf/Somalia-Chittick1976.pdf
