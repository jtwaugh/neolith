# Who wants the Neolithic to say something?

*Research note, 2026-11-13. A companion to `POSITIONING.md`, which sorts audiences by role. This
note sorts them by motive.*

Most educated laypeople who come to 10,000–3,000 BCE bring a thesis about the present. They want
the period to vouch for it: men or women, states or anarchy, farming or foraging, us or them, God
or aliens. Neolith's distinctive asset is that it keeps **recorded, modelled and speculative**
apart and says *why* a region is blank. For each persona that asset is either exactly what they
need or exactly what frustrates them.

Each persona below lists the thesis they bring, the questions they'd ask, what the record roughly
says, and how well Neolith answers today ("fit"). The fit verdicts refer to real things: the map
modes (`Terrain`, `Koeppen`, `Npp`, `Expected`, `Pop`, `Evidence`, `Missing`, `Ancestry` …), the isostyle
layers in `data/isostyle/layers.toml`, and the farming front and sea-level model in the pipeline.

---

## The personae

### 1. The steppe/Yamnaya enthusiast (X/Twitter, Substack, genetics-blog comments)
- **Thesis:** a vigorous, male-led, horse-and-wagon people swept across Europe and India. The
  appeal ranges from an "Indo-European vitalist" aesthetic to outright ethnonationalism.
- **Questions:** Where were the Yamnaya at 3300 BCE? Where do R1b and R1a come from? Did steppe men
  replace local men? Did plague empty Europe first? Was the PIE homeland the steppe, Anatolia or the
  Caucasus? Were the Corded Ware people the same people?
- **Record:** a strong, sex-biased steppe aDNA signal after about 3000 BCE. The homeland is still
  argued. The R1a–Indo-Iranian link is disputed. The late Neolithic population dip has competing
  explanations.
- **Fit: good for the run-up, and honest about the edge** (was poor before the Ancestry map mode,
  2026-11-13). The `Ancestry` mode shows the two halves of what becomes "steppe" ancestry, eastern
  hunter-gatherer and Iranian/Caucasus, as recorded genomes on the Volga and the Caucasus, already mixed
  at Khvalynsk on the Volga (31 genomes, about 5200 to 4400 BCE, roughly three quarters eastern
  hunter-gatherer and a fifth Iranian/Caucasus). The first carriers west of the steppe are in the
  table too: one migrant in Hungary about 4250 BCE, then Yamnaya burials in Moldova, Hungary and
  Bulgaria from about 3200 BCE. By 3250 to 3000 BCE they are still only about 4% of the genomes
  west of 30°E, and the legend says at the 3000 BCE edge that the expansion itself happens after
  the map ends. It answers "where does steppe ancestry come from" with individuals
  and their papers, which the Y-haplogroup layers (`y_r1a`, `y_r1b`, `y_i2`, `y_g2a` …) could not.
  The steppe is still the emptiest region in the open data (Ukraine, Belarus and European Russia
  have 0.11 dates per 1,000 km²), and unsampled land there is drawn as unknown. "The cradle is
  mostly invisible in open data" remains a real finding this audience rarely hears.
- **Risk:** the persona most likely to screenshot a surface as proof. So the ancestry layers
  are recorded only (no speculative fill), there are no arrows, and the legend says the
  proportions are "shared ancestry, not peoples, languages or cultures".

### 2. The feminist / Goddess anthropologist ("Eden before patriarchy")
- **Thesis:** early farming "Old Europe" was egalitarian or woman-centred and goddess-revering
  (Gimbutas; Eisler's *The Chalice and the Blade*). Patriarchy came with the plough, the horse and
  the "Kurgan" peoples.
- **Questions:** Were women at Çatalhöyük equal? Where are the female figurines, and when do they
  stop? Did women farm? Is there a "Kurgan invasion" line? Was Old Europe peaceful? Do burials rank
  by sex?
- **Record:** Çatalhöyük looks more egalitarian than either "matriarchy" or "patriarchy" would
  have it. Gimbutas hedged more than she's credited with, and dropped "matriarchy". Figurines are
  ambiguous. Strontium and aDNA suggest patrilocality in the LBK. The LBK massacres complicate
  "peaceful".
- **Fit: partial** (was weak). The `Ancestry` mode now answers the "Kurgan invasion" half of
  the question with data: Old Europe's farmers carry Anatolian-farmer ancestry with a growing
  hunter-gatherer share (central Europe goes from 2% hunter-gatherer at 5500 to 5000 BCE to 30% at
  3500 to 3000 BCE). Steppe-type mixture is almost absent from them before 3300 BCE (one migrant
  in Hungary about 4250 BCE) and then appears on the lower Danube and the Tisza as Yamnaya
  burials. The legend says the main expansion comes after 3000 BCE. There is still no figurine, sex-by-burial or violence
  layer, and those are the evidence asked for first. A "Gimbutas line" could be added as a
  labelled historiography overlay, not data.

### 3. The "agriculture was a mistake" reader (Diamond, Harari, Scott's *Against the Grain*, primitivists, degrowth)
- **Thesis:** farming made people shorter, sicker, overworked, unequal and ripe for states.
  Foragers were the original affluent society.
- **Questions:** Where did farming start, and how fast did it spread? Did foragers resist? Where
  did they hold out (Baltic, Scandinavia, the Atlantic fringe), and for how long? Did foragers and
  farmers live side by side? Were farmers shorter?
- **Record:** the health decline is real but recovers within a few millennia. The farming front
  stalls for about 1,000 years in places. Ertebølle, Pitted Ware and Dnieper–Donets foragers
  persist.
- **Fit: strong.** The farming front, the forager/farmer density model (`Expected`), `cereals`,
  `domestic_livestock`, `cereal_pollen`, `dung_spores` and the timeline are this persona's whole
  question. The missing piece is a "where foragers held out" map moment, and the data mostly
  supports one. There is no stature or health layer.

### 4. The *Dawn of Everything* reader (Graeber & Wengrow; "we chose this")
- **Thesis:** people experimented consciously with social forms. They "played at farming", built
  big without kings, and the agricultural "revolution" was not one.
- **Questions:** Were there cities without states (the Trypillia mega-sites)? Did domestication in
  the Fertile Crescent really take 3,000 years? Did foragers build Göbekli Tepe? Were there
  seasonal assembly sites?
- **Fit: strong.** Trypillia (about 3900 BCE), Göbekli Tepe and the slow domestication are all in
  the window. `enclosures`, `houses` and `megalithic_tombs` speak to monuments and assembly. The
  pain point is that Ukraine is a data hole, so the mega-sites barely register. That makes them
  a showcase for `Missing`.

### 5. The Hancock / lost-civilisation viewer (*Ancient Apocalypse*, Rogan, Younger Dryas impact)
- **Thesis:** an advanced Ice Age civilisation was wiped out about 12,800 years ago, Göbekli Tepe
  is its legacy, and archaeologists are hiding it.
- **Questions:** What's under the sea (Doggerland, the Gulf)? What happened at the Younger Dryas?
  What came before Göbekli Tepe? Why are some places empty?
- **Record:** Göbekli Tepe is Pre-Pottery Neolithic with local forerunners (Natufian, Karahan Tepe,
  the Taş Tepeler sites). The impact hypothesis is widely rejected.
- **Fit: double-edged and important.** The app's headline ("the open record holds about a third;
  drowned land is blank") *is* their premise, handled honestly. The detection model's causes
  (effort, drowned land, acid soil) let the app say "yes, things are missing, and here is exactly
  why and what kind" without sneering. Speculative fills must be framed so they can't be quoted
  as "even the model finds a lost civilisation".

### 6. The Biblical / Eden-locator ("Eden under the Gulf", the Black Sea flood)
- **Thesis:** Genesis preserves memory of real places and events. Eden is the drowned Gulf Oasis
  (Zarins, and Rose's work as recast by apologetics ministries), and the Flood is the Black Sea
  (Ryan & Pitman).
- **Questions:** When did the Gulf flood? Where did its rivers run? When did the Black Sea rise?
  Where did farming start relative to Mesopotamia? When was Jericho walled?
- **Fit: strong on data.** The sea-level curve and palaeo-coasts in `Terrain` answer "when was
  the Gulf dry" directly. Show it neutrally. This is a very large audience with few
  non-apologetic tools.

### 7. The national-origins seeker (one persona, many flags)
Each flag has a "first X" to claim. Most sit inside the map:
- **Hindutva / Out-of-India:** Mehrgarh (about 7000 BCE) as indigenous farming. Rakhigarhi
  showed no steppe DNA, read as "no Aryan migration". Mature Harappan comes just after the
  window.
- **Turkish (and Kurdish):** Göbekli Tepe as the "zero point of history".
- **Ukrainian / Romanian / Moldovan:** Cucuteni–Trypillia as "Europe's first cities" and a
  deep non-Russian past, with wartime urgency.
- **Israeli / Palestinian:** Jericho and the Natufian.
- **Irish / British:** the Céide Fields, Newgrange, megaliths, and the large population turnover
  at the Beaker arrival.
- **Balkan "Old Europe":** Varna gold (`metallurgy`) and the Vinča "script".
- **Egyptian / Afrocentric:** the Green Sahara, Nabta Playa, and Saharan origins for the Nile.

All of them share one shape: who was here first, were we invaded, is our site the oldest?

**Fit: the "modern borders show through" finding cuts across every one of them.** The most
useful single feature for this persona would be a readout of "this country's apparent density
is N× what the expectation model predicts". It shows politely, and evenly, that "oldest"
usually means "most dug".

### 8. The ancestry-test hobbyist ("you are 12% Early European Farmer")
- **Questions:** Where did my WHG, EEF and steppe slices live? When did farmers reach my
  grandparents' region? What did people look like (skin, eyes, lactase persistence)?
- **Fit: good** (was good for "when" only). The `Ancestry` mode is this persona's own
  vocabulary: western hunter-gatherer, Anatolian (early European) farmer, eastern hunter-gatherer
  and Iranian/Caucasus ancestry as shares, per region and per genome, through time. Hovering a
  hex shows the dated individuals nearby as stacked bars, each with its paper. The farming front
  still gives the arrival date. Phenotype is not covered, and the "steppe" slice only reaches
  the lower Danube and the Tisza inside the window; for most of Europe it arrives after the map
  ends (the legend says so).

### 9. The ancestral-health / paleo person
- **Questions:** What did people eat here, and when? When did dairy start? Were foragers
  healthier? When did cereals arrive?
- **Fit: partial.** `cereals`, `domestic_livestock` and the pollen layers cover arrival. There
  is no dairy-lipid (pottery residue), stature or dental-health layer.

### 10. The violence / human-nature arguer (Pinker vs "noble savage")
- **Questions:** Was there war before states? How common were massacres? Where are the
  fortifications?
- **Record:** the LBK massacres (Talheim, Schöneck-Kilianstädten, Asparn/Schletz, about
  5000 BCE).
- **Fit: weak.** `enclosures` partly covers fortification, but it mixes defensive and ceremonial
  sites. A small, sharply defined trauma/massacre layer would be cheap to add.

### 11. The climate-and-collapse reader (the 8.2 ka event, the end of the Green Sahara, today's analogues)
- **Questions:** Did the 8.2 ka cold event or the 5.9 ka aridification break societies? Did the
  drying Sahara push people to the Nile? Do settlements boom and bust?
- **Fit: strong.** `Koeppen`, `Npp`, the terrain keyframes and settlement counts over time cover
  this directly. A boom-and-bust population curve is a natural map moment.

### 12. The worldbuilder / strategy gamer / novelist (already in `POSITIONING.md`)
- **Questions:** What were the "provinces" and "polities"? What did people trade (obsidian,
  Spondylus shell, jadeite axes)? What did a village feel like?
- **Fit: partial.** `ornaments`, `mines` and `flaked_stone` hint at materials. There are no
  exchange networks or flows.

### Minor but real
- **Pagan revival and earth-mysteries people:** megaliths, alignments, solstices
  (`megalithic_tombs`).
- **Animal people:** when did dogs, cats (Cyprus, about 7500 BCE) and horses arrive? This needs
  a split by species.
- **Brewers and foodies:** the Natufian beer hypothesis (Raqefet Cave).
- **Linguistics hobbyists:** Basque as a farmer-era relic, pre-Indo-European substrates.

---

## Cross-cutting patterns

1. **Five question shapes cover almost everything:** *Where first? How fast did it spread? Who
   replaced whom? Was it better before? What's missing or hidden?* Neolith answers the first,
   second and fifth well. It answers "who replaced whom" through aDNA (since 2026-11-13 as
   ancestry proportions in the `Ancestry` mode, not only haplogroups), and "was it better"
   hardly at all.
2. **The 3000 BCE cutoff lands mid-sentence** for the three loudest debates: the Yamnaya and
   Indo-European origins, Harappa and the Aryans, and Beaker/Stonehenge. Either extend the window
   to about 2500 BCE, or say explicitly in the app that the story continues past the edge.
3. **Every motivated persona wants the blanks filled in their favour.** The
   recorded/modelled/speculative split and the cause-coded gaps are the product's ethical core.
   Speculation should carry its label in the pixels, so a cropped screenshot still says
   "speculative".
4. **"Oldest" mostly means "most dug".** The research-effort finding is new to every persona and
   deflates every national claim equally. That makes it politically safe to lead with.
5. **The evidence layers most in demand that we lack:** violence and trauma; figurines and burial
   by sex; stature and health; exchange materials (obsidian, Spondylus, jadeite) as flows; dairy
   residues; domestic animals by species.

## Sources

Web reading done for this note (mostly commentary and reviews, used to characterise the
discourse, not as archaeological evidence):

- Steppe / Indo-European discourse: [Eurogenes, "The PIE homeland controversy" (2021)](https://eurogenes.blogspot.com/2021/06/the-pie-homeland-controversy-june-2021.html);
  [indo-european.eu on the R1a–Indo-European association](https://indo-european.eu/?p=11213);
  ["Steppe Hypothesis" (Substack)](https://samael.substack.com/p/steppe-hypothesis)
- Goddess / matriarchy: [Scientific American, "Women and Men at Çatalhöyük"](https://www.scientificamerican.com/article/women-and-men-at-atalhyk-2005-01/);
  [Archaeological Dialogues, "Matriarchy, Gimbutas and figurines"](https://www.cambridge.org/core/journals/archaeological-dialogues/article/matriarchy-gimbutas-and-figurines-entanglements-with-the-goddess/07D1A3C4647CC496F4410F70E54075D5);
  [Brooklyn Rail, "Goddess Time" (2025)](https://brooklynrail.org/2025/02/criticspage/goddess-time/);
  [Spretnak, "Anatomy of a Backlash"](https://www.charlenespretnak.com/attachments/JoA_article_by_CS_on_MG.pdf)
- Lost civilisation: [Sapiens on *Ancient Apocalypse*](https://sapiens.org/archaeology/ancient-apocalypse-pseudoscience);
  [Skeptic on Göbekli Tepe](https://www.skeptic.com/?p=43808)
- *Dawn of Everything* reception: [Scheidel's critique](https://zenodo.org/records/5907061/files/Scheidel%20on%20Graeber%20and%20Wengrow.pdf);
  [The Ecologist review](https://theecologist.org/2021/dec/17/all-things-being-equal);
  [a primitivist critique](https://animistsramblings.substack.com/p/primitivist-critique-dawn-of-everything)
- Indian origins debate: [Outlook on the Rakhigarhi findings](https://www.outlookindia.com/national/where-did-we-come-from-from-here-and-theredna-findings-from-rakhigarhi-reveal-hard-truths-news-302129);
  [The Quint on online reaction](https://www.thequint.com/news/india/how-hindutva-twitter-lost-it-over-4500-year-old-harappa-civilization-skeleton);
  [Outlook, "Linking Indus Valley and Vedic civilisations"](https://www.outlookindia.com/national/linking-indus-valley-and-vedic-civilisations-a-hindu-nationalist-project)
- Trypillia: [EASA webinar on the mega-sites and the war (2022)](https://easaonline.org/?p=22615);
  [Greek Reporter, "Europe's first mega-cities"](https://greekreporter.com/2025/06/10/built-europes-first-mega-cities-six-thousand-years-ago/)
- Eden / Gulf: [The Register on the Gulf Oasis](https://www.theregister.com/2010/12/09/ancient_dilmun_garden_eden_gulf_lost_civilisation/);
  [Reasons to Believe on the Gulf (apologetic reading)](https://reasons.org/christianity/bible/lost-civilization-beneath-the-persian-gulf-confirms-genesis-history-of-humanity)
- Health: [Penn State on first European farmers' heights](https://science.psu.edu/news/first-european-farmers-heights-did-not-meet-expectations);
  [Discover, "Early farmers were sicker and shorter"](https://www.discovermagazine.com/early-farmers-were-sicker-and-shorter-than-their-forager-ancestors-944)
- Violence: [Meyer et al., PNAS 2015, Schöneck-Kilianstädten](https://pmc.ncbi.nlm.nih.gov/articles/PMC4568710);
  [The Conversation on organised violence among first farmers](https://theconversation.com/mass-grave-reveals-organised-violence-among-europes-first-farmers-46217)
