//! The Ancestry map mode's own UI: the legend, the hex inspector's strip of
//! individuals over time, and the sample pins on the board.
//!
//! Everything here reads [`neolith_core::ancestry`]: per-genome qpAdm
//! proportions computed by the pipeline (`data/ancestry/SOURCES.md` in the
//! parent repo). Nothing is estimated in the app, and movement is shown only
//! as change over time in place: there are no arrows.

use crate::app::Session;
use crate::board::camera::View;
use crate::board::relief::Relief;
use crate::palette;
use eframe::egui::{self, vec2, Color32, Pos2, Rect, RichText, Sense, Shape, Stroke};
use neolith_core::ancestry::{Ancestry, Sample, Status};
use neolith_core::geom::point_in_polygon;
use neolith_core::{HexId, LonLat, Year};

/// What the proportions are and are not; shown under the legend.
pub const FOOTNOTE: &str = "Proportions come from a statistical model fitted to six reference groups. \
     They describe shared ancestry, not peoples, languages or cultures. Unsampled land is left blank, not guessed.";

/// Shown at the end of the map's span, where the next chapter starts.
pub const STEPPE_NOTE: &str = "Steppe ancestry, a mixture of eastern hunter-gatherer and Iranian/Caucasus ancestry, \
     spreads across Europe after the end of this map.";

/// The year from which [`STEPPE_NOTE`] shows.
pub const STEPPE_NOTE_FROM: Year = Year(-3300);

/// How far the inspector looks for individuals round a hex, in km.
pub const NEARBY_KM: f64 = 300.0;

/// Pins appear once a hex is at least this many pixels across.
pub const PIN_MIN_HEX_PX: f64 = 9.0;

/// A genome counts as alive in the current view when this much of its date
/// distribution falls within [`neolith_core::World::ANCESTRY_HALF_YEARS`].
const PIN_MIN_OVERLAP: f32 = 0.05;

/// A named region where ancestry is unknown for a known reason (the Sahel:
/// no ancient DNA survives), from `assets/unknown_ancestry.json`. Unknown
/// hexes inside one say why, instead of only "no genome in reach".
#[derive(serde::Deserialize)]
pub struct UnknownRegion {
    pub label: String,
    pub short: String,
    pub why: String,
    pub polygon: Vec<[f64; 2]>,
}

pub fn unknown_regions() -> &'static [UnknownRegion] {
    #[derive(serde::Deserialize)]
    struct File {
        region: Vec<UnknownRegion>,
    }
    static REGIONS: std::sync::OnceLock<Vec<UnknownRegion>> = std::sync::OnceLock::new();
    REGIONS.get_or_init(|| {
        serde_json::from_str::<File>(include_str!("../assets/unknown_ancestry.json")).map(|f| f.region).unwrap_or_else(|e| {
            log::error!("assets/unknown_ancestry.json: {e}");
            Vec::new()
        })
    })
}

/// The named unknown region whose polygon holds `pos`, if any.
pub fn unknown_region(pos: LonLat) -> Option<&'static UnknownRegion> {
    unknown_regions().iter().find(|r| point_in_polygon(&r.polygon, [pos.lon, pos.lat]))
}

fn rgb(c: palette::Rgb) -> Color32 {
    Color32::from_rgb(c[0], c[1], c[2])
}

fn component_colour(k: usize) -> Color32 {
    palette::ANCESTRY.get(k).copied().map_or(Color32::GRAY, rgb)
}

/// "62% Anatolian farmer, 38% Western hunter-gatherer": the shares of at
/// least 1%, largest first.
pub fn describe(table: &Ancestry, shares: &[f32]) -> String {
    let mut parts: Vec<(usize, f32)> = shares.iter().copied().enumerate().filter(|(_, v)| *v >= 0.005).collect();
    parts.sort_by(|a, b| b.1.total_cmp(&a.1));
    parts
        .iter()
        .map(|(k, v)| format!("{:.0}% {}", v * 100.0, table.components.get(*k).map_or("?", |c| c.name.as_str())))
        .collect::<Vec<_>>()
        .join(", ")
}

/// [`describe`] for a smoothed mean: shares under 3% are smoothing residue,
/// not a finding, so they fold into one "other".
pub fn describe_smoothed(table: &Ancestry, shares: &[f32]) -> String {
    let mut kept = shares.to_vec();
    let mut other = 0.0;
    for v in &mut kept {
        if *v < 0.03 {
            other += *v;
            *v = 0.0;
        }
    }
    let text = describe(table, &kept);
    if other >= 0.005 && !text.is_empty() {
        format!("{text}, {:.0}% other", other * 100.0)
    } else {
        text
    }
}

/// One sample in words, for a tooltip: who, when, how the model came out, and the paper.
pub fn sample_lines(table: &Ancestry, s: &Sample) -> Vec<String> {
    let mut out = vec![
        format!("{} · {}", s.id, s.group),
        format!("{} ± {} years{}", s.year, s.sd, if s.locality.is_empty() { String::new() } else { format!(" · {}", s.locality) }),
    ];
    match (s.status, s.shares()) {
        (Status::Fit, Some(shares)) => {
            out.push(describe(table, &shares));
            out.push(match s.p_milli {
                Some(p) => format!("Model {} fits (p = {:.2}); {} SNPs", s.model.replace('+', " + "), p as f32 / 1000.0, s.snps),
                None => format!("Model {}; {} SNPs", s.model, s.snps),
            });
        }
        (Status::Reference, _) => out.push(format!(
            "Reference individual: part of the {} group the others are measured against, so 100% by construction.",
            table.components.iter().find(|c| c.key == s.model).map_or(s.model.as_str(), |c| c.name.as_str())
        )),
        (status, _) => out.push(format!("No proportions: {} ({} SNPs)", status.label(), s.snps)),
    }
    if !s.publication.is_empty() {
        out.push(format!("First published: {}", s.publication));
    }
    out
}

/// A horizontal bar of shares, left to right in component order.
fn share_bar(ui: &mut egui::Ui, shares: &[f32], width: f32, height: f32) -> egui::Response {
    let (rect, response) = ui.allocate_exact_size(vec2(width, height), Sense::hover());
    let painter = ui.painter_at(rect);
    let mut x = rect.left();
    for (k, v) in shares.iter().enumerate() {
        let w = rect.width() * v.clamp(0.0, 1.0);
        if w > 0.0 {
            painter.rect_filled(Rect::from_min_size(Pos2::new(x, rect.top()), vec2(w, rect.height())), 0.0, component_colour(k));
            x += w;
        }
    }
    painter.rect_stroke(rect, 2.0, Stroke::new(1.0, ui.visuals().weak_text_color()), egui::StrokeKind::Inside);
    response
}

/// The legend: one row per component, how thin and unknown land is drawn,
/// and what the proportions mean.
pub fn legend(ui: &mut egui::Ui, s: &Session) {
    let Some(table) = s.world.ancestry.as_ref().filter(|_| s.world.has_ancestry()) else {
        ui.weak("This file has no ancestry table.");
        return;
    };
    // The dated note goes first: at the bottom a short window cut it off.
    let year = s.year();
    if year >= STEPPE_NOTE_FROM {
        ui.add(egui::Label::new(RichText::new(STEPPE_NOTE).small().italics()).wrap());
        ui.add_space(2.0);
    }
    for (k, c) in table.components.iter().enumerate() {
        ui.horizontal(|ui| {
            let (rect, _) = ui.allocate_exact_size(vec2(14.0, 14.0), Sense::hover());
            ui.painter().rect_filled(rect, 3.0, component_colour(k));
            ui.add(egui::Label::new(&c.name).truncate()).on_hover_text(&c.name);
        });
    }
    ui.horizontal(|ui| {
        let mut half = [0.0f32; neolith_core::ancestry::COMPONENTS];
        (half[0], half[2]) = (0.5, 0.5);
        let (rect, _) = ui.allocate_exact_size(vec2(14.0, 14.0), Sense::hover());
        ui.painter().rect_filled(rect, 3.0, rgb(palette::ancestry_mix(&half)));
        ui.label("Mixed: the colour in between");
    });
    ui.horizontal(|ui| {
        let (rect, _) = ui.allocate_exact_size(vec2(14.0, 14.0), Sense::hover());
        let mut pure = [0.0f32; neolith_core::ancestry::COMPONENTS];
        pure[2] = 1.0;
        ui.painter().rect_filled(rect, 3.0, rgb(palette::ancestry(neolith_core::ancestry::code(&pure, true))));
        ui.label("Paler: fewer than two genomes nearby");
    });
    ui.horizontal(|ui| {
        let (rect, _) = ui.allocate_exact_size(vec2(14.0, 14.0), Sense::hover());
        let p = ui.painter_at(rect);
        p.rect_filled(rect, 3.0, Color32::from_gray(150));
        for k in -2..=2 {
            let o = k as f32 * 5.0;
            p.line_segment([rect.left_bottom() + vec2(o, 0.0), rect.right_top() + vec2(o, 0.0)], Stroke::new(1.5, Color32::from_gray(50)));
        }
        ui.label("Hatched: no genome, so unknown");
    });
    for r in unknown_regions() {
        ui.add(egui::Label::new(RichText::new(format!("{}: {}", r.label, r.short.to_lowercase())).small()).wrap())
            .on_hover_text(&r.why);
    }
    let fitted = table.samples.iter().filter(|x| x.status == Status::Fit && x.overlap(year, neolith_core::World::ANCESTRY_HALF_YEARS) > 0.5).count();
    ui.weak(format!("{fitted} modelled genomes within 500 years of {year}"));
    ui.add_space(2.0);
    ui.add(egui::Label::new(RichText::new(FOOTNOTE).small().weak()).wrap());
}

/// The inspector's ancestry section for a hex: its smoothed proportions, and
/// one stacked bar per individual within [`NEARBY_KM`], placed by date on a
/// 10,000–3,000 BCE axis.
pub fn inspector(ui: &mut egui::Ui, s: &Session, hex: HexId) {
    let Some(table) = s.world.ancestry.as_ref().filter(|_| s.world.has_ancestry()) else {
        return;
    };
    let year = s.year();
    let width = ui.available_width().min(320.0);
    match s.world.ancestry_shares(hex, year) {
        Some(shares) => {
            ui.label(RichText::new("Ancestry here").strong());
            share_bar(ui, &shares, width, 14.0).on_hover_text("Smoothed over the genomes in reach of this hex, weighted by distance and date.");
            ui.label(describe_smoothed(table, &shares));
        }
        None => match unknown_region(s.world.grid.centre(hex)) {
            Some(r) => {
                ui.label(RichText::new(format!("Ancestry here: {}", r.label.to_lowercase())).strong());
                ui.add(egui::Label::new(RichText::new(&r.short).italics()).wrap());
                ui.add(egui::Label::new(RichText::new(&r.why).small()).wrap());
            }
            None => {
                ui.label(RichText::new("Ancestry here: unknown").strong());
                ui.weak("No modelled genome is in reach of this hex at this date. Nothing is guessed.");
            }
        },
    }
    let centre = s.world.grid.centre(hex);
    let near = table.near(centre, NEARBY_KM);
    ui.add_space(4.0);
    ui.label(format!("{} individuals within {NEARBY_KM:.0} km, by date", near.len()));
    if near.is_empty() {
        ui.separator();
        return;
    }
    // The strip: time runs left to right; each individual is a thin stacked
    // bar at its date. Unmodelled individuals are grey ticks on the baseline.
    let (first, last) = (
        s.keyframes.first().map_or(-10000.0, |y| y.0 as f32),
        s.keyframes.last().map_or(-3000.0, |y| y.0 as f32),
    );
    let (rect, response) = ui.allocate_exact_size(vec2(width, 96.0), Sense::hover());
    let painter = ui.painter_at(rect);
    let plot = Rect::from_min_max(rect.min, Pos2::new(rect.right(), rect.bottom() - 14.0));
    painter.rect_filled(plot, 2.0, ui.visuals().extreme_bg_color);
    let x_of = |y: f32| plot.left() + (y - first) / (last - first).max(1.0) * plot.width();
    let bar_w = (plot.width() / 110.0).clamp(2.0, 4.0);
    for (smp, _) in &near {
        let x = x_of(smp.year.0 as f32).clamp(plot.left(), plot.right() - bar_w);
        match smp.shares() {
            Some(shares) => {
                let mut y = plot.bottom();
                for (k, v) in shares.iter().enumerate() {
                    let h = plot.height() * v;
                    if h > 0.0 {
                        painter.rect_filled(Rect::from_min_max(Pos2::new(x, y - h), Pos2::new(x + bar_w, y)), 0.0, component_colour(k));
                        y -= h;
                    }
                }
                if smp.status == Status::Reference {
                    painter.rect_stroke(Rect::from_min_max(Pos2::new(x, plot.top()), Pos2::new(x + bar_w, plot.bottom())), 0.0, Stroke::new(1.0, Color32::WHITE), egui::StrokeKind::Outside);
                }
            }
            None => {
                painter.rect_filled(Rect::from_min_max(Pos2::new(x, plot.bottom() - 5.0), Pos2::new(x + bar_w, plot.bottom())), 0.0, Color32::from_gray(120));
            }
        }
    }
    // The axis: a tick per two thousand years, and the current year.
    let ink = ui.visuals().weak_text_color();
    let mut tick = (first / 2000.0).ceil() * 2000.0;
    while tick <= last {
        let x = x_of(tick);
        painter.line_segment([Pos2::new(x, plot.bottom()), Pos2::new(x, plot.bottom() + 3.0)], Stroke::new(1.0, ink));
        // The end ticks' labels sit inside the strip instead of being cut off.
        let align = if x - plot.left() < 14.0 {
            egui::Align2::LEFT_BOTTOM
        } else if plot.right() - x < 14.0 {
            egui::Align2::RIGHT_BOTTOM
        } else {
            egui::Align2::CENTER_BOTTOM
        };
        painter.text(Pos2::new(x, rect.bottom()), align, format!("{}", -tick as i32), egui::FontId::proportional(9.5), ink);
        tick += 2000.0;
    }
    let now_x = x_of(year.0 as f32);
    painter.line_segment([Pos2::new(now_x, plot.top()), Pos2::new(now_x, plot.bottom())], Stroke::new(1.0, Color32::WHITE));
    // Hover: the individual whose bar is nearest the pointer.
    if let Some(pointer) = response.hover_pos() {
        let nearest = near.iter().min_by(|a, b| {
            let d = |smp: &Sample| (x_of(smp.year.0 as f32) + bar_w / 2.0 - pointer.x).abs();
            d(a.0).total_cmp(&d(b.0))
        });
        if let Some((smp, km)) = nearest.filter(|(smp, _)| (x_of(smp.year.0 as f32) + bar_w / 2.0 - pointer.x).abs() <= 6.0) {
            response.on_hover_ui_at_pointer(|ui| {
                for line in sample_lines(table, smp) {
                    ui.label(line);
                }
                ui.weak(format!("{km:.0} km from this hex"));
            });
        }
    }
    let modelled = near.iter().filter(|(smp, _)| smp.status == Status::Fit).count();
    ui.weak(format!("{modelled} modelled; grey ticks have too little DNA or no fitting model. Years BCE."));
    ui.separator();
}

/// A pin to draw: a sample, where, and how big.
pub struct Pin<'a> {
    pub sample: &'a Sample,
    pub pos: Pos2,
    pub radius: f32,
}

/// The pins for the current year: one per genome alive in the window, sized
/// by how much of its date falls there. Genomes from one site fan out round
/// it in rings so each stays visible.
pub fn pins<'a>(table: &'a Ancestry, year: Year, view: &View, relief: &Relief, rect: Rect, hex_px: f64) -> Vec<Pin<'a>> {
    if hex_px < PIN_MIN_HEX_PX {
        return Vec::new();
    }
    let scale = ((hex_px / 24.0) as f32).clamp(0.6, 1.6);
    let mut out: Vec<Pin<'a>> = Vec::new();
    let mut sites: Vec<((i64, i64), usize)> = Vec::new();
    for smp in &table.samples {
        let overlap = smp.overlap(year, neolith_core::World::ANCESTRY_HALF_YEARS);
        if overlap < PIN_MIN_OVERLAP {
            continue;
        }
        let Some(q) = view.project_relief(smp.pos, relief) else { continue };
        let base = Pos2::new(rect.left() + q.x as f32, rect.top() + q.y as f32);
        if !rect.expand(20.0).contains(base) {
            continue;
        }
        let radius = (3.0 + 4.0 * overlap.sqrt()) * scale;
        // The n-th genome at a site: the centre, then rings of six, twelve, ...
        let key = ((smp.pos.lon * 200.0).round() as i64, (smp.pos.lat * 200.0).round() as i64);
        let n = match sites.iter_mut().find(|(k, _)| *k == key) {
            Some((_, n)) => {
                *n += 1;
                *n - 1
            }
            None => {
                sites.push((key, 1));
                0
            }
        };
        let offset = if n == 0 {
            vec2(0.0, 0.0)
        } else {
            let ring = (((n as f32 - 1.0) / 6.0 + 0.25).sqrt() + 0.5).floor().max(1.0);
            let first = 3.0 * ring * (ring - 1.0) + 1.0;
            let a = (n as f32 - first) / (6.0 * ring) * std::f32::consts::TAU + ring * 0.5;
            vec2(a.cos(), a.sin()) * ring * 7.5 * scale
        };
        if n < 37 {
            out.push(Pin { sample: smp, pos: base + offset, radius });
        }
    }
    out
}

/// Draws a pie of `shares` at `centre`.
fn pie(painter: &egui::Painter, centre: Pos2, radius: f32, shares: &[f32]) {
    let mut a0 = -std::f32::consts::FRAC_PI_2;
    for (k, v) in shares.iter().enumerate() {
        if *v <= 0.0 {
            continue;
        }
        let a1 = a0 + v * std::f32::consts::TAU;
        if *v >= 0.999 {
            painter.circle_filled(centre, radius, component_colour(k));
        } else {
            // Wedges of at most a quarter turn, so each polygon is convex.
            let steps = ((a1 - a0) / std::f32::consts::FRAC_PI_2).ceil().max(1.0) as usize;
            for i in 0..steps {
                let (b0, b1) = (a0 + (a1 - a0) * i as f32 / steps as f32, a0 + (a1 - a0) * (i + 1) as f32 / steps as f32);
                let mut pts = vec![centre];
                let n = 6;
                for j in 0..=n {
                    let a = b0 + (b1 - b0) * j as f32 / n as f32;
                    pts.push(centre + vec2(a.cos(), a.sin()) * radius);
                }
                painter.add(Shape::convex_polygon(pts, component_colour(k), Stroke::NONE));
            }
        }
        a0 = a1;
    }
}

/// Draws the pins and returns the one under the pointer. A modelled genome
/// is a pie of its proportions; a reference individual has a white ring; a
/// genome without proportions is a small hollow grey ring.
pub fn draw_pins<'a>(painter: &egui::Painter, pins: &[Pin<'a>], pointer: Option<Pos2>) -> Option<&'a Sample> {
    let mut hovered: Option<(&'a Sample, f32)> = None;
    for p in pins {
        match p.sample.shares() {
            Some(shares) => {
                painter.circle_filled(p.pos, p.radius + 1.2, Color32::from_black_alpha(170));
                pie(painter, p.pos, p.radius, &shares);
                if p.sample.status == Status::Reference {
                    painter.circle_stroke(p.pos, p.radius + 1.2, Stroke::new(1.2, Color32::WHITE));
                }
            }
            None => {
                painter.circle_stroke(p.pos, (p.radius * 0.6).max(2.0), Stroke::new(1.2, Color32::from_gray(190)));
            }
        }
        if let Some(d) = pointer.map(|q| q.distance(p.pos)).filter(|d| *d <= p.radius + 3.0) {
            if hovered.is_none_or(|(_, best)| d < best) {
                hovered = Some((p.sample, d));
            }
        }
    }
    hovered.map(|(s, _)| s)
}

/// A small card of text lines beside the pointer (the pin tooltip).
pub fn card(painter: &egui::Painter, bounds: Rect, at: Pos2, lines: &[String]) {
    let font = egui::FontId::proportional(12.5);
    let galleys: Vec<_> = lines.iter().map(|l| painter.layout(l.clone(), font.clone(), Color32::WHITE, 300.0)).collect();
    let w = galleys.iter().map(|g| g.size().x).fold(0.0, f32::max) + 16.0;
    let h = galleys.iter().map(|g| g.size().y + 2.0).sum::<f32>() + 12.0;
    let mut min = at + vec2(14.0, 14.0);
    min.x = min.x.min(bounds.right() - w - 4.0).max(bounds.left() + 4.0);
    min.y = min.y.min(bounds.bottom() - h - 4.0).max(bounds.top() + 4.0);
    let rect = Rect::from_min_size(min, vec2(w, h));
    painter.rect_filled(rect, 5.0, Color32::from_rgba_unmultiplied(22, 22, 24, 235));
    painter.rect_stroke(rect, 5.0, Stroke::new(1.0, Color32::from_gray(90)), egui::StrokeKind::Inside);
    let mut y = rect.top() + 6.0;
    for g in galleys {
        let hh = g.size().y;
        painter.galley(Pos2::new(rect.left() + 8.0, y), g, Color32::WHITE);
        y += hh + 2.0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use neolith_core::ancestry::Component;
    use neolith_core::LonLat;

    fn table() -> Ancestry {
        let names = ["Western hunter-gatherer", "Eastern hunter-gatherer", "Anatolian farmer", "Iranian farmer", "Levantine forager", "North African forager"];
        let keys = ["whg", "ehg", "ana", "irn", "lev", "naf"];
        let sample = |id: &str, status: Status, weights: &[u16], model: &str| Sample {
            id: id.into(),
            group: "Germany_N_LBK".into(),
            locality: "Derenburg".into(),
            pos: LonLat::new(11.0, 51.9),
            year: Year(-5200),
            sd: 80,
            snps: 800_000,
            status,
            model: model.into(),
            p_milli: (status == Status::Fit).then_some(240),
            weights: weights.to_vec(),
            publication: "LipsonNature2017".into(),
        };
        Ancestry {
            components: keys.iter().zip(names).map(|(k, n)| Component { key: k.to_string(), name: n.to_string() }).collect(),
            samples: vec![
                sample("DER1", Status::Fit, &[60, 0, 940, 0, 0, 0], "whg+ana"),
                sample("DER2", Status::LowCoverage, &[], ""),
                sample("REF", Status::Reference, &[0, 0, 1000, 0, 0, 0], "ana"),
            ],
        }
    }

    #[test]
    fn smoothed_description_folds_residue() {
        let table = Ancestry {
            components: ["Western hunter-gatherer", "Eastern hunter-gatherer", "Anatolian farmer", "Iranian", "Levantine", "North African"]
                .iter()
                .map(|n| Component { key: n.to_lowercase(), name: n.to_string() })
                .collect(),
            samples: Vec::new(),
        };
        let text = describe_smoothed(&table, &[0.01, 0.01, 0.95, 0.01, 0.01, 0.01]);
        assert_eq!(text, "95% Anatolian farmer, 5% other");
        assert_eq!(describe_smoothed(&table, &[0.2, 0.0, 0.8, 0.0, 0.0, 0.0]), "80% Anatolian farmer, 20% Western hunter-gatherer");
    }

    #[test]
    fn words_for_shares_and_samples() {
        let t = table();
        assert_eq!(describe(&t, &[0.06, 0.0, 0.94, 0.0, 0.0, 0.0]), "94% Anatolian farmer, 6% Western hunter-gatherer");
        let fit = sample_lines(&t, &t.samples[0]).join("\n");
        assert!(fit.contains("DER1") && fit.contains("5200 BCE ± 80") && fit.contains("p = 0.24") && fit.contains("LipsonNature2017"), "{fit}");
        let thin = sample_lines(&t, &t.samples[1]).join("\n");
        assert!(thin.contains("too little DNA") && !thin.contains('%'), "{thin}");
        let reference = sample_lines(&t, &t.samples[2]).join("\n");
        assert!(reference.contains("Reference individual") && reference.contains("Anatolian farmer"), "{reference}");
    }

    #[test]
    fn the_legend_says_what_the_numbers_are_not() {
        for needle in ["six reference groups", "not peoples, languages or cultures", "left blank, not guessed"] {
            assert!(FOOTNOTE.contains(needle), "{needle}");
        }
        assert!(STEPPE_NOTE.contains("after the end of this map"));
    }

    #[test]
    fn the_sahel_says_why_it_is_unknown() {
        assert!(!unknown_regions().is_empty(), "assets/unknown_ancestry.json failed to parse");
        let gobero = unknown_region(LonLat::new(9.4, 16.8)).expect("Gobero is in the Sahel region");
        assert_eq!(gobero.label, "Unknown (Sahelian)");
        assert!(gobero.why.contains("Gobero") && gobero.why.contains("Heat"));
        let kadruka = unknown_region(LonLat::new(29.4, 19.3)).expect("Kadruka is in the Sahel region");
        assert_eq!(kadruka.label, "Unknown (Sahelian)");
        for (name, lon, lat) in [("Takarkori", 10.6, 24.8), ("Shum Laka", 10.1, 5.9), ("Mota", 38.2, 6.8), ("Gondar highlands", 37.5, 12.6), ("Derenburg", 11.0, 51.9)] {
            assert!(unknown_region(LonLat::new(lon, lat)).is_none(), "{name} should not be in a named unknown region");
        }
    }
}
