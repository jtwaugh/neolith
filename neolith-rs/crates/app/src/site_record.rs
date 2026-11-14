//! The settlement popup's body: what the record says about a site — its
//! dated occupation, culture at the current year, recorded population,
//! notable features, links out, and the radiocarbon dates themselves.

use egui::{Color32, RichText};
use neolith_core::{SiteInfo, World, Year};

/// The English Wikipedia URL for an article title.
pub fn wikipedia_url(title: &str) -> String {
    let mut path = String::with_capacity(title.len());
    for c in title.trim().chars() {
        match c {
            ' ' => path.push('_'),
            '%' => path.push_str("%25"),
            '?' => path.push_str("%3F"),
            '#' => path.push_str("%23"),
            '&' => path.push_str("%26"),
            '+' => path.push_str("%2B"),
            c => path.push(c),
        }
    }
    format!("https://en.wikipedia.org/wiki/{path}")
}

/// The id in effect at `year` in a sorted (from year, id) list.
pub fn at_year(keys: &[(Year, String)], year: Year) -> Option<&str> {
    keys.iter().rev().find(|(y, _)| *y <= year).map(|(_, id)| id.as_str())
}

/// One line of the "Culture" section: display name, Wikipedia title, and
/// whether it was inferred from neighbouring sites.
#[derive(Debug, PartialEq)]
pub struct Attribution {
    pub name: String,
    pub wikipedia: Option<String>,
    pub inferred: bool,
}

/// The culture (`stage == false`) or stage the record gives for `year`:
/// the site's own labels first, else what was inferred from neighbours.
/// Before the first key, the earliest key is used (a site's first dated
/// layer stands for its founding).
///
/// Only keys inside `phase` (the stretch of occupation containing `year`,
/// end exclusive) count, so a label never carries across a gap; `None`
/// for `phase` means the site is unoccupied and nothing is attributed.
pub fn attribution(world: &World, info: &SiteInfo, year: Year, phase: Option<(Year, Year)>, stage: bool) -> Option<Attribution> {
    let (start, end) = phase?;
    let (own, inferred) = if stage { (&info.stage, &info.stage_inferred) } else { (&info.culture, &info.culture_inferred) };
    let pick = |keys: &[(Year, String)]| {
        let lo = keys.partition_point(|(y, _)| *y < start);
        let hi = keys.partition_point(|(y, _)| *y < end);
        let keys = &keys[lo..hi];
        at_year(keys, year).or_else(|| keys.first().map(|(_, id)| id.as_str())).map(str::to_string)
    };
    let (id, inferred) = match pick(own) {
        Some(id) => (id, false),
        None => (pick(inferred)?, true),
    };
    let c = world.culture(&id);
    Some(Attribution {
        name: c.map_or_else(|| id.replace('_', " "), |c| c.name.clone()),
        wikipedia: c.and_then(|c| c.wikipedia.clone()),
        inferred,
    })
}

/// "9230–5170 BCE", or "500 BCE – 200 CE" across the era boundary.
pub fn range(a: Year, b: Year) -> String {
    match (a.0 < 0, b.0 < 0) {
        (true, true) => format!("{}–{} BCE", -a.0, -b.0),
        (false, false) => format!("{}–{} CE", a.0, b.0),
        _ => format!("{a} – {b}"),
    }
}

fn heading(ui: &mut egui::Ui, text: &str) {
    ui.add_space(4.0);
    ui.label(RichText::new(text).small().strong().color(Color32::from_rgb(214, 190, 140)));
}

/// The record's tabs. The strip sits at the top of the panel, above the
/// scrolling body, so its controls are in the same place for every site.
#[derive(Clone, Copy, PartialEq, Eq, Default)]
pub enum RecordTab {
    #[default]
    Overview,
    Dates,
    Sources,
}

impl RecordTab {
    pub const ALL: [RecordTab; 3] = [RecordTab::Overview, RecordTab::Dates, RecordTab::Sources];

    pub fn label(self) -> &'static str {
        match self {
            RecordTab::Overview => "Overview",
            RecordTab::Dates => "Dates",
            RecordTab::Sources => "Sources",
        }
    }
}

/// Draws the tab strip and returns the tab chosen. The choice is kept from
/// one site to the next.
pub fn tab_strip(ui: &mut egui::Ui) -> RecordTab {
    let id = egui::Id::unique("site-record-tab");
    let mut tab = ui.data(|d| d.get_temp::<RecordTab>(id)).unwrap_or_default();
    ui.horizontal(|ui| {
        for t in RecordTab::ALL {
            ui.selectable_value(&mut tab, t, t.label());
        }
    });
    ui.data_mut(|d| d.insert_temp(id, tab));
    ui.separator();
    tab
}

/// One line of text that never wraps (cut short with "…"), so what is below
/// it stays where it is; the whole text, and `more`, on hover.
fn line(ui: &mut egui::Ui, text: RichText, more: &str) {
    let full = if more.is_empty() { text.text().to_string() } else { format!("{}\n\n{more}", text.text()) };
    ui.add(egui::Label::new(text).truncate()).on_hover_text(full);
}

/// Draws one tab of the record of settlement `i` as it stands in `year`.
pub fn show(ui: &mut egui::Ui, world: &World, i: usize, year: Year, tab: RecordTab) {
    let empty = SiteInfo::default();
    let info = world.site_info(i).unwrap_or(&empty);
    match tab {
        RecordTab::Overview => overview(ui, world, i, year, info),
        RecordTab::Dates => dates(ui, world, i, year, info),
        RecordTab::Sources => sources(ui, info),
    }
}

/// The overview. Its first part is a fixed form (kind and place, links, dated
/// occupation, population, culture: the same lines at the same height for
/// every site), so nothing moves under the player from one record to the
/// next; what varies in length comes after it.
fn overview(ui: &mut egui::Ui, world: &World, i: usize, year: Year, info: &SiteInfo) {
    let st = &world.settlements[i];
    let famous = crate::renown::lookup(st);

    // Kind and place.
    let kind = if info.is_inferred() {
        "Inferred, not recorded".to_string()
    } else if info.kind.is_empty() || info.kind == "site" {
        "Site".to_string()
    } else {
        capitalise(&info.kind)
    };
    let place = format!("{kind} · {:.2}°{}, {:.2}°{}", st.pos.lat.abs(), if st.pos.lat >= 0.0 { "N" } else { "S" },
        st.pos.lon.abs(), if st.pos.lon >= 0.0 { "E" } else { "W" });
    line(ui, RichText::new(place).weak(), if info.is_inferred() { INFERRED_NOTE } else { "" });

    // Links out: always one row, so the form below keeps its place.
    ui.horizontal(|ui| {
        let article = info.wikipedia.as_deref().map(wikipedia_url).or_else(|| famous.map(|f| f.entry().wikipedia.clone()));
        if let Some(url) = &article {
            ui.hyperlink_to("Wikipedia", url);
        }
        if let Some(q) = &info.wikidata {
            ui.hyperlink_to("Wikidata", format!("https://www.wikidata.org/wiki/{q}"));
        }
        if article.is_none() && info.wikidata.is_none() {
            ui.weak("No encyclopedia article linked");
        }
    });

    heading(ui, "DATED OCCUPATION");
    let n = info.dates.len();
    match st.abandoned_by() {
        None => line(ui, RichText::new(format!("From {}", st.founded)), ""),
        Some(by) => line(ui, RichText::new(format!("{} – abandoned by {by}", st.founded)), "The Dates tab has the phases and the last date."),
    }
    let basis = if n > 0 {
        let so_far = info.dates.iter().filter(|d| d.cal <= year).count();
        format!("{n} radiocarbon date{} · {so_far} by {year}", if n == 1 { "" } else { "s" })
    } else if info.is_inferred() {
        "Years from the inference rule, not from dates".to_string()
    } else if info.sources.iter().any(|s| s == "curated") {
        "Founding year from a curated entry".to_string()
    } else if info.sources.iter().any(|s| s == "wikidata") {
        "Founding year from Wikidata (inception)".to_string()
    } else {
        "No radiocarbon dates".to_string()
    };
    line(ui, RichText::new(basis).weak(), "");

    heading(ui, "POPULATION");
    match st.population_at(year) {
        Some(p) => {
            line(ui, RichText::new(format!("{p} in {year} (recorded estimate)")), "");
            line(ui, RichText::new("Piece sized from the record").weak(), "");
        }
        None => {
            let none = if st.population.keys().is_empty() { "No recorded estimate" } else { "No recorded estimate for this year" };
            line(ui, RichText::new(none).weak(), "");
            const TIER: [&str; 4] = ["minor (a pit, hearth or find-spot)", "ordinary", "notable", "major"];
            line(
                ui,
                RichText::new(format!("Piece sized as {} · importance {} of 3", TIER[st.importance.min(3) as usize], st.importance)).weak(),
                "Inferred, not recorded: from the site type (tells and enclosures highest, pits and hearths lowest), \
                 plus one for a long occupation and one for many dates, each compared with sites within 150 km so heavily \
                 excavated regions don't get bigger pieces for being excavated.",
            );
        }
    }

    // Culture and stage: two lines, filled or not.
    heading(ui, "CULTURE");
    let phase = st.phase_at(year);
    let lines: Vec<Attribution> =
        [attribution(world, info, year, phase, false), attribution(world, info, year, phase, true)].into_iter().flatten().collect();
    for k in 0..2 {
        ui.horizontal(|ui| match lines.get(k) {
            Some(a) => {
                match &a.wikipedia {
                    Some(t) => ui.hyperlink_to(&a.name, wikipedia_url(t)),
                    None => ui.label(&a.name),
                };
                if a.inferred {
                    ui.weak("(inferred)").on_hover_text(
                        "Inferred from nearby sites: the site's own dates carry no label for this; nearby sites with labelled dates do.",
                    );
                }
            }
            None if k == 0 => {
                ui.weak("None recorded for this year");
            }
            None => {
                ui.weak(" ");
            }
        });
    }

    // ---- from here on the length varies with the site ----------------------
    if !info.features.is_empty() {
        heading(ui, "FEATURES");
        ui.label(info.features.iter().map(|f| capitalise(f)).collect::<Vec<_>>().join(" · "));
    }
    ui.add_space(6.0);
    // A famous site: what it is known for.
    if let Some(f) = famous {
        ui.label(RichText::new(&f.entry().known_for).italics());
    }
    if info.is_inferred() {
        ui.label(RichText::new("Inferred, not recorded").strong()).on_hover_text(INFERRED_NOTE);
        for r in &info.references {
            ui.weak(r);
        }
    }
    if !info.aliases.is_empty() {
        ui.weak(format!("Also: {}", info.aliases.iter().take(3).cloned().collect::<Vec<_>>().join(", ")));
    }
    if !info.wikidata_culture.is_empty() {
        ui.weak(format!("Wikidata culture: {}", info.wikidata_culture.join(", ")));
    }
    if st.evidence == 0 && !info.is_inferred() {
        ui.weak("Known from a single date: drawn pale");
    }
    let survey = world.grid.hex_at(st.pos).and_then(|h| world.survey_at(h));
    if let Some(level) = survey.filter(|l| *l < 2) {
        ui.weak(if level == 0 { "Hardly surveyed area" } else { "Thinly surveyed area" }).on_hover_text(
            "Few radiocarbon dates of any period come from around here, so fewer sites on the map may mean less \
             fieldwork rather than fewer people.",
        );
    }
}

const INFERRED_NOTE: &str = "No site is recorded here. The record is thin for a known reason (buried under silt, drowned, never \
     entered in the open compilations), so a settlement is placed where people very probably lived. It \
     disappears from its hex once a recorded site is entered there.";

/// The Dates tab: the phases of occupation, the radiocarbon dates and the
/// period labels they carry.
fn dates(ui: &mut egui::Ui, world: &World, i: usize, year: Year, info: &SiteInfo) {
    let st = &world.settlements[i];
    let n = info.dates.len();
    match st.abandoned_by() {
        None => {
            ui.label(format!("From {}", st.founded));
        }
        Some(by) => {
            ui.label(format!("{} – abandoned by {by}", st.founded));
            if let Some(last) = info.abandoned.filter(|l| *l < by) {
                ui.weak(format!("Last date {last}; assumed abandoned after {} years with none", by.0 - last.0))
                    .on_hover_text("An estimate, not evidence: a site with no radiocarbon dates for this long is taken to have been abandoned. The true end lies between the last date and this year.");
            }
            if st.occupation.len() > 1 {
                let phases: Vec<String> = st.occupation.iter().map(|&(a, b)| range(a, b)).collect();
                ui.weak(format!("{} phases: {}", phases.len(), phases.join(", ")))
                    .on_hover_text("Dates further apart than the abandonment span split the record into phases; the site is shown as empty in between.");
            }
        }
    }
    heading(ui, &format!("RADIOCARBON DATES ({n})"));
    if n == 0 {
        ui.weak("None in the record");
    } else {
        egui::Grid::new(("c14_grid", st.id)).num_columns(4).spacing([10.0, 2.0]).striped(true).show(ui, |ui| {
            for h in ["Lab no.", "¹⁴C BP", "cal.", "data"] {
                ui.label(RichText::new(h).small().strong());
            }
            ui.end_row();
            for d in &info.dates {
                // Dates still in the future of the clock are dimmed.
                let dim = d.cal > year;
                let cell = |ui: &mut egui::Ui, s: String| {
                    let t = RichText::new(s).small();
                    ui.label(if dim { t.weak() } else { t });
                };
                cell(ui, d.lab.clone());
                cell(ui, format!("{} ± {}", d.bp, d.err));
                cell(ui, d.cal.to_string());
                cell(ui, d.dataset.clone());
                ui.end_row();
            }
        });
    }
    if !info.periods.is_empty() {
        heading(ui, &format!("PERIOD LABELS ({})", info.periods.len()));
        ui.label(RichText::new(info.periods.join(" · ")).small());
    }
}

/// The Sources tab: the datasets and references behind the record.
fn sources(ui: &mut egui::Ui, info: &SiteInfo) {
    if info.sources.is_empty() && info.references.is_empty() {
        ui.weak("No source is listed for this record");
    }
    if !info.sources.is_empty() {
        ui.label(RichText::new(format!("Datasets: {}", info.sources.join(", "))).small());
    }
    for r in &info.references {
        ui.label(RichText::new(format!("• {r}")).small().weak());
    }
    ui.add_space(4.0);
    ui.hyperlink_to(
        RichText::new("Full citations (data/settlements/SOURCES.md)").small(),
        format!("{}/blob/main/data/settlements/SOURCES.md", crate::credits::REPO),
    );
}

fn capitalise(s: &str) -> String {
    let mut c = s.chars();
    c.next().map_or_else(String::new, |f| f.to_uppercase().chain(c).collect())
}

#[cfg(test)]
mod tests {
    use super::*;
    use neolith_core::{CultureInfo, GridSpec};

    fn world() -> World {
        let mut w = World::empty(GridSpec { cols: 2, rows: 2, origin_lon: 0.0, origin_lat: 1.0, w: 0.5773502691896262, h: 0.5 });
        w.cultures.push(CultureInfo {
            id: "lbk".into(),
            kind: "culture".into(),
            name: "Linear Pottery culture".into(),
            wikipedia: Some("Linear Pottery culture".into()),
        });
        w
    }

    #[test]
    fn wikipedia_urls() {
        assert_eq!(wikipedia_url("Çatalhöyük"), "https://en.wikipedia.org/wiki/Çatalhöyük");
        assert_eq!(wikipedia_url("Franchthi Cave"), "https://en.wikipedia.org/wiki/Franchthi_Cave");
        assert_eq!(wikipedia_url("A?B#C"), "https://en.wikipedia.org/wiki/A%3FB%23C");
    }

    #[test]
    fn ranges() {
        assert_eq!(range(Year(-9230), Year(-5170)), "9230–5170 BCE");
        assert_eq!(range(Year(-500), Year(200)), "500 BCE – 200 CE");
        assert_eq!(range(Year(100), Year(300)), "100–300 CE");
    }

    #[test]
    fn culture_follows_the_clock() {
        let w = world();
        let info = SiteInfo {
            culture: vec![(Year(-5500), "lbk".into()), (Year(-4900), "rossen".into())],
            stage_inferred: vec![(Year(-5500), "neolithic".into())],
            ..SiteInfo::default()
        };
        let all = Some((Year(-10000), Year(0)));
        let at = |y| attribution(&w, &info, Year(y), all, false).unwrap();
        // Before the first key, the first key stands.
        assert_eq!(at(-6000).name, "Linear Pottery culture");
        assert_eq!(at(-5000).wikipedia.as_deref(), Some("Linear Pottery culture"));
        // An id missing from the table is shown readably, without a link.
        assert_eq!(at(-4500), Attribution { name: "rossen".into(), wikipedia: None, inferred: false });
        let stage = attribution(&w, &info, Year(-5000), all, true).unwrap();
        assert!(stage.inferred);
        assert_eq!(stage.name, "neolithic");
        assert!(attribution(&w, &SiteInfo::default(), Year(-1), all, false).is_none());
        // Labels stay in their phase: none in a later phase, none when unoccupied.
        assert!(attribution(&w, &info, Year(-3000), Some((Year(-3500), Year(-2000))), false).is_none());
        assert!(attribution(&w, &info, Year(-5000), None, false).is_none());
        // The first key of the phase stands for its earlier years.
        let early = attribution(&w, &info, Year(-5600), Some((Year(-5700), Year(-4000))), false).unwrap();
        assert_eq!(early.name, "Linear Pottery culture");
    }
}
