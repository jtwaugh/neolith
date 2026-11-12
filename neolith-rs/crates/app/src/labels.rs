//! Map typography: geography names set along curves on the board (seas,
//! regions, mountain ranges, rivers, lakes) and the cleanup of settlement
//! names for their labels.
//!
//! Sea and region names are sized to their curve on screen, as on a Paradox
//! map: they appear when zoomed out, grow with the zoom, and drop out (with
//! a short fade, never left half-transparent) once they would be bigger than
//! their kind allows. Rivers and lakes are named from
//! the world file, at a fixed size, once there is room on screen.

use crate::board::camera::View;
use crate::board::relief::Relief;
use egui::{Color32, FontFamily, FontId, Painter, Pos2, Rect, Shape};
use glam::DVec2;
use neolith_core::{LonLat, RiverState, Terrain, World, Year};
use std::collections::HashSet;
use std::sync::{Arc, OnceLock};

pub const SERIF: &str = "serif";
pub const SERIF_ITALIC: &str = "serif-italic";

pub fn serif(size: f32) -> FontId {
    FontId::new(size, FontFamily::Name(SERIF.into()))
}

pub fn serif_italic(size: f32) -> FontId {
    FontId::new(size, FontFamily::Name(SERIF_ITALIC.into()))
}

/// Registers EB Garamond (SIL Open Font License, `assets/fonts/OFL.txt`;
/// web-sized by `scripts/subset_fonts.py`) as
/// the `serif` and `serif-italic` families, falling back to egui's fonts for
/// glyphs it lacks.
pub fn install_fonts(ctx: &egui::Context) {
    let mut fonts = egui::FontDefinitions::default();
    fonts.font_data.insert(
        "garamond".into(),
        Arc::new(egui::FontData::from_static(include_bytes!("../assets/fonts/EBGaramond.subset.ttf"))),
    );
    fonts.font_data.insert(
        "garamond-italic".into(),
        Arc::new(egui::FontData::from_static(include_bytes!("../assets/fonts/EBGaramond-Italic.subset.ttf"))),
    );
    let fallback = fonts.families.get(&FontFamily::Proportional).cloned().unwrap_or_default();
    for (family, font) in [(SERIF, "garamond"), (SERIF_ITALIC, "garamond-italic")] {
        let mut list = vec![font.to_string()];
        list.extend(fallback.iter().cloned());
        fonts.families.insert(FontFamily::Name(family.into()), list);
    }
    ctx.set_fonts(fonts);
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, serde::Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Kind {
    Ocean,
    Sea,
    Region,
    Mountains,
}

impl Kind {
    fn is_water(self) -> bool {
        matches!(self, Kind::Ocean | Kind::Sea)
    }

    /// Largest font size; a name that would be much bigger drops out (zoomed in too far).
    fn max_size(self) -> f32 {
        match self {
            Kind::Ocean => 34.0,
            Kind::Sea => 28.0,
            Kind::Region => 30.0,
            Kind::Mountains => 22.0,
        }
    }

    /// Extra letter spacing, in ems.
    fn tracking(self) -> f32 {
        match self {
            Kind::Ocean | Kind::Sea => 0.12,
            Kind::Region => 0.32,
            Kind::Mountains => 0.22,
        }
    }

    fn colours(self) -> (Color32, Color32) {
        match self {
            Kind::Ocean | Kind::Sea => (Color32::from_rgba_unmultiplied(22, 48, 82, 215), Color32::from_rgba_unmultiplied(235, 245, 255, 70)),
            Kind::Region => (Color32::from_rgba_unmultiplied(58, 38, 22, 200), Color32::from_rgba_unmultiplied(255, 246, 228, 95)),
            Kind::Mountains => (Color32::from_rgba_unmultiplied(70, 52, 40, 210), Color32::from_rgba_unmultiplied(255, 246, 228, 95)),
        }
    }
}

#[derive(Clone, Debug, serde::Deserialize)]
pub struct GeoLabel {
    pub name: String,
    pub kind: Kind,
    pub path: [[f64; 2]; 3],
}

impl GeoLabel {
    /// The quadratic Bezier through the path's control points.
    fn at(&self, t: f64) -> LonLat {
        let [a, b, c] = self.path;
        let u = 1.0 - t;
        let f = |i: usize| u * u * a[i] + 2.0 * u * t * b[i] + t * t * c[i];
        LonLat::new(f(0), f(1))
    }
}

#[derive(serde::Deserialize)]
struct LabelFile {
    labels: Vec<GeoLabel>,
}

pub fn geo_labels() -> &'static [GeoLabel] {
    static LABELS: OnceLock<Vec<GeoLabel>> = OnceLock::new();
    LABELS.get_or_init(|| {
        serde_json::from_str::<LabelFile>(include_str!("../assets/geo_labels.json")).map(|f| f.labels).unwrap_or_else(|e| {
            log::error!("assets/geo_labels.json: {e}");
            Vec::new()
        })
    })
}

/// A label as drawn, for the harness.
#[derive(Clone, Debug)]
pub struct DrawnLabel {
    pub name: String,
    pub kind: &'static str,
    pub bounds: Rect,
    pub size: f32,
}

/// The name a settlement is labelled with, or `None` for catalogue entries
/// that have no usable name. Strips bracketed notes and excavation codes:
/// "Kostenki (Kostienki) 14 (Markina gora)" → "Kostenki 14",
/// "Wadi el-Akhdar BOS.83/33" → "Wadi el-Akhdar", "WHS 1065" → none.
pub fn settlement_label(name: &str) -> Option<String> {
    let mut out = String::new();
    let mut depth = 0;
    for ch in name.chars() {
        match ch {
            '(' | '[' => depth += 1,
            ')' | ']' => depth = (depth - 1).max(0),
            _ if depth == 0 => out.push(ch),
            _ => {}
        }
    }
    let words: Vec<&str> = out
        .split_whitespace()
        // Excavation and survey codes: digits mixed with '/' or '.' ("83/33", "BOS.83/33", "30/420-E3-1").
        .filter(|w| !(w.chars().any(|c| c.is_ascii_digit()) && w.contains(['/', '.'])))
        .collect();
    let clean = words.join(" ").trim_matches(|c: char| c == ',' || c == ';' || c == '-' || c.is_whitespace()).to_string();
    // An acronym plus a number and nothing else ("WHS 1065", "BP 12"), or a bare "site 197": no name.
    let letters: Vec<&str> = clean.split_whitespace().filter(|w| !w.chars().all(|c| c.is_ascii_digit())).collect();
    let all_codes = letters.iter().all(|w| w.len() <= 5 && w.chars().all(|c| c.is_ascii_uppercase() || c.is_ascii_digit() || c == '-'));
    let generic = letters.iter().all(|w| matches!(w.to_lowercase().as_str(), "site" | "locality" | "loc." | "area" | "sector"));
    if clean.is_empty() || letters.is_empty() || all_codes || generic {
        return None;
    }
    // "Dakhla site 197" → "Dakhla".
    let clean = match clean.to_lowercase().rfind(" site ") {
        Some(i) if clean[i + 6..].chars().all(|c| c.is_ascii_digit() || c.is_whitespace()) => clean[..i].to_string(),
        _ => clean,
    };
    Some(clean)
}

/// Draws one string along a screen polyline, centred, glyph by glyph.
/// Returns the bounding box, or `None` when the text doesn't fit.
#[allow(clippy::too_many_arguments)]
fn draw_along(painter: &Painter, line: &[Pos2], text: &str, font: FontId, tracking: f32, colour: Color32, halo: Color32) -> Option<Rect> {
    if line.len() < 2 {
        return None;
    }
    let mut cum = vec![0.0f32];
    for w in line.windows(2) {
        cum.push(cum.last().unwrap() + w[0].distance(w[1]));
    }
    let total = *cum.last().unwrap();
    let glyphs: Vec<_> = text.chars().map(|c| painter.layout_no_wrap(c.to_string(), font.clone(), colour)).collect();
    let space = tracking * font.size;
    let width: f32 = glyphs.iter().map(|g| g.size().x).sum::<f32>() + space * (glyphs.len().saturating_sub(1)) as f32;
    if width > total * 0.98 {
        return None;
    }
    let point_at = |s: f32| {
        let k = cum.partition_point(|c| *c < s).clamp(1, line.len() - 1);
        let (a, b) = (line[k - 1], line[k]);
        let seg = (cum[k] - cum[k - 1]).max(1e-3);
        let p = a + (b - a) * ((s - cum[k - 1]) / seg).clamp(0.0, 1.0);
        (p, (b.y - a.y).atan2(b.x - a.x))
    };
    let mut s = (total - width) / 2.0;
    let mut bounds = Rect::NOTHING;
    for g in glyphs {
        let w = g.size().x;
        let h = g.size().y;
        let (p, angle) = point_at(s + w / 2.0);
        let rot = egui::emath::Rot2::from_angle(angle);
        let top_left = p + rot * egui::vec2(-w / 2.0, -h * 0.55);
        for (dx, dy) in [(-1.0, 0.0), (1.0, 0.0), (0.0, -1.0), (0.0, 1.0)] {
            painter.add(Shape::Text(
                egui::epaint::TextShape::new(top_left + egui::vec2(dx, dy), g.clone(), halo).with_angle(angle).with_override_text_color(halo),
            ));
        }
        painter.add(Shape::Text(egui::epaint::TextShape::new(top_left, g.clone(), colour).with_angle(angle)));
        bounds = bounds.union(Rect::from_center_size(p, egui::vec2(w.max(h), w.max(h))));
        s += w + space;
    }
    Some(bounds)
}

fn faded(c: Color32, a: f32) -> Color32 {
    let [r, g, b, al] = c.to_srgba_unmultiplied();
    Color32::from_rgba_unmultiplied(r, g, b, (al as f32 * a).round() as u8)
}

/// Projects lon/lat points to window points; `None` if any is behind the camera.
fn screen_line(view: &View, relief: &Relief, rect: Rect, pts: impl Iterator<Item = LonLat>) -> Option<Vec<Pos2>> {
    let mut out = Vec::new();
    for p in pts {
        let q = view.project_relief(p, relief)?;
        out.push(Pos2::new(rect.left() + q.x as f32, rect.top() + q.y as f32));
    }
    // Read left to right.
    if out.len() >= 2 && out.last().unwrap().x < out[0].x {
        out.reverse();
    }
    Some(out)
}

fn on_screen(view: &View, rect: Rect, p: Pos2, ll: LonLat, grid: &neolith_core::GridSpec) -> bool {
    // In the viewport and not behind the curve of the board.
    let local = DVec2::new((p.x - rect.left()) as f64, (p.y - rect.top()) as f64);
    rect.contains(p) && view.pick(local).and_then(|q| grid.hex_at(q)) == grid.hex_at(ll)
}

/// Smallest font size a sea or region name is set in.
const MIN_SIZE: f32 = 11.0;

/// Draws the geography labels for this frame and returns what it drew.
/// `shown` holds the sea and region names visible last frame (for hysteresis)
/// and is updated.
#[allow(clippy::too_many_arguments)]
pub fn draw_geography(
    painter: &Painter,
    rect: Rect,
    view: &View,
    relief: &Relief,
    world: &World,
    terrain: &[u8],
    year: Year,
    cam_dist: f64,
    shown: &mut HashSet<String>,
) -> Vec<DrawnLabel> {
    let grid = &world.grid;
    let mut drawn = Vec::new();
    let water_at = |ll: LonLat| grid.hex_at(ll).map(|h| terrain[h.index()] == Terrain::Water as u8);

    for l in geo_labels() {
        let mid = l.at(0.5);
        if water_at(mid) != Some(l.kind.is_water()) {
            continue;
        }
        let Some(line) = screen_line(view, relief, rect, (0..=32).map(|i| l.at(i as f64 / 32.0))) else { continue };
        let mid_px = line[line.len() / 2];
        if !on_screen(view, rect, mid_px, mid, grid) {
            continue;
        }
        let len: f32 = line.windows(2).map(|w| w[0].distance(w[1])).sum();
        let text = if l.kind.is_water() { l.name.clone() } else { l.name.to_uppercase() };
        let n = text.chars().count() as f32;
        // Size the name to fill about 80% of its curve.
        let size = len * 0.8 / (n * (0.52 + l.kind.tracking()));
        // Shown or not, never left half-faded: the name is in while its
        // natural size is between MIN_SIZE and 1.3× its kind's maximum (a
        // little wider once shown, so it doesn't flicker at the threshold),
        // and only the 150 ms transition between the two is faded.
        let max = l.kind.max_size();
        let was = shown.contains(&l.name);
        let (lo, hi) = if was { (MIN_SIZE - 1.0, max * 1.4) } else { (MIN_SIZE, max * 1.3) };
        let visible = size >= lo && size <= hi;
        let alpha = painter.ctx().animate_bool_with_time(egui::Id::unique(("geo-label", &l.name)), visible, 0.15);
        if visible {
            if !was {
                shown.insert(l.name.clone());
            }
        } else if was {
            shown.remove(&l.name);
        }
        if alpha <= 0.01 {
            continue;
        }
        let size = size.clamp(MIN_SIZE - 1.0, max);
        let font = if l.kind.is_water() { serif_italic(size) } else { serif(size) };
        let (c, halo) = l.kind.colours();
        if let Some(bounds) = draw_along(painter, &line, &text, font, l.kind.tracking(), faded(c, alpha), faded(halo, alpha)) {
            let kind = match l.kind {
                Kind::Ocean => "ocean",
                Kind::Sea => "sea",
                Kind::Region => "region",
                Kind::Mountains => "mountains",
            };
            if visible {
                drawn.push(DrawnLabel { name: l.name.clone(), kind, bounds, size });
            }
        }
    }

    // Rivers: large and great ones, named along a stretch around the middle
    // of their on-screen course, once zoomed in.
    if cam_dist < 0.55 {
        let mut named: Vec<&str> = Vec::new();
        let font = serif_italic(14.0);
        for r in world.rivers.iter().filter(|r| r.size >= 2 && r.state_at(year) != RiverState::Absent) {
            if named.contains(&r.name.as_str()) || r.points.len() < 2 {
                continue;
            }
            let Some(line) = screen_line(view, relief, rect, r.points.iter().copied()) else { continue };
            // The visible part of the course.
            let visible: Vec<Pos2> = line.iter().copied().filter(|p| rect.shrink(20.0).contains(*p)).collect();
            if visible.len() < 2 {
                continue;
            }
            let text_w = r.name.chars().count() as f32 * 14.0 * 0.5 + 40.0;
            // A window of the course around its middle that is long enough.
            let mid = visible.len() / 2;
            let (mut a, mut b) = (mid, mid);
            let len = |a: usize, b: usize| visible[a..=b].windows(2).map(|w| w[0].distance(w[1])).sum::<f32>();
            while len(a, b) < text_w && (a > 0 || b + 1 < visible.len()) {
                a = a.saturating_sub(1);
                b = (b + 1).min(visible.len() - 1);
            }
            let colour = Color32::from_rgba_unmultiplied(18, 62, 128, 225);
            let halo = Color32::from_rgba_unmultiplied(235, 245, 255, 80);
            let mut seg = visible[a..=b].to_vec();
            if seg.last().unwrap().x < seg[0].x {
                seg.reverse();
            }
            if let Some(bounds) = draw_along(painter, &seg, &r.name, font.clone(), 0.04, colour, halo) {
                named.push(&r.name);
                drawn.push(DrawnLabel { name: r.name.clone(), kind: "river", bounds, size: 14.0 });
            }
        }
    }

    // Lakes: the name across the lake, if it fits.
    for lake in &world.lakes {
        let Some(shape) = lake.shape_at(year) else { continue };
        // The Black Sea and Caspian are named as seas already ("Black Sea lake").
        let lname = lake.name.to_lowercase();
        if drawn.iter().any(|d| d.kind != "lake" && lname.starts_with(&d.name.to_lowercase())) {
            continue;
        }
        let Some(ring) = shape.rings.iter().max_by_key(|r| r.len()) else { continue };
        let Some(pts) = screen_line(view, relief, rect, ring.iter().copied()) else { continue };
        let bb = Rect::from_points(&pts);
        let n = lake.name.chars().count() as f32;
        let size = (bb.width() * 0.7 / (n * 0.55)).min(bb.height() * 0.5).min(24.0);
        if size < 11.0 || !rect.contains(bb.center()) {
            continue;
        }
        let c = ring.iter().fold((0.0, 0.0), |(x, y), p| (x + p.lon, y + p.lat));
        let centre = LonLat::new(c.0 / ring.len() as f64, c.1 / ring.len() as f64);
        let Some(q) = view.project_relief(centre, relief) else { continue };
        let p = Pos2::new(rect.left() + q.x as f32, rect.top() + q.y as f32);
        let half = egui::vec2(n * size * 0.3, 0.0);
        if let Some(bounds) = draw_along(
            painter,
            &[p - half * 1.2, p + half * 1.2],
            &lake.name,
            serif_italic(size),
            0.06,
            Color32::from_rgba_unmultiplied(18, 62, 128, 225),
            Color32::from_rgba_unmultiplied(235, 245, 255, 80),
        ) {
            drawn.push(DrawnLabel { name: lake.name.clone(), kind: "lake", bounds, size });
        }
    }
    drawn
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn settlement_names_are_cleaned() {
        assert_eq!(settlement_label("Kostenki (Kostienki) 14 (Markina gora)").as_deref(), Some("Kostenki 14"));
        assert_eq!(settlement_label("Wadi el-Akhdar BOS.83/33").as_deref(), Some("Wadi el-Akhdar"));
        assert_eq!(settlement_label("Dakhla site 197 (30/420-E3-1)").as_deref(), Some("Dakhla"));
        assert_eq!(settlement_label("WHS 1065"), None);
        assert_eq!(settlement_label("Jericho").as_deref(), Some("Jericho"));
        assert_eq!(settlement_label("Göbekli Tepe").as_deref(), Some("Göbekli Tepe"));
        assert_eq!(settlement_label("Suberde (Görüklük Tepe)").as_deref(), Some("Suberde"));
        assert_eq!(settlement_label("Canal of Xerxes, Bay of Ierissos").as_deref(), Some("Canal of Xerxes, Bay of Ierissos"));
        assert_eq!(settlement_label("(unnamed)"), None);
    }

    #[test]
    fn geo_labels_parse() {
        let l = geo_labels();
        assert!(l.len() >= 40, "{}", l.len());
        for g in l {
            for [lon, lat] in g.path {
                assert!((-17.0..=66.5).contains(&lon) && (6.0..=76.0).contains(&lat), "{} out of the grid", g.name);
            }
        }
    }
}
