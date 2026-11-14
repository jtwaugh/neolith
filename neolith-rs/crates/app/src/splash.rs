//! The start screen's text: README.md in brief, plus short answers to the
//! questions people bring to the period (docs/AUDIENCE_QUESTIONS.md). Keep it
//! in step with both. Every term is explained where it first appears.
//!
//! Markup in the strings: `**term**` is highlighted, `*text*` is italic.

use egui::text::{LayoutJob, TextFormat};
use egui::epaint::RectShape;
use egui::{Align, Color32, FontId, Key, RichText, Sense, Shape, Stroke, TextureHandle, TextureOptions, pos2, vec2};

use crate::labels::{book, book_italic, display};

/// Width of the text column, at most.
pub const COLUMN: f32 = 680.0;

const BODY: f32 = 17.0;
const INK: Color32 = Color32::from_rgb(0xd8, 0xcf, 0xbb);
const STRONG: Color32 = Color32::from_rgb(0xf0, 0xe6, 0xcc);
const HEAD: Color32 = Color32::from_rgb(0xc9, 0xa8, 0x6a);
const WEAK: Color32 = Color32::from_rgb(0x8a, 0x81, 0x70);
const LEDE: Color32 = Color32::from_rgb(0xb9, 0xad, 0x94);
const CARD: Color32 = Color32::from_rgb(0x24, 0x21, 0x1c);
const RULE: Color32 = Color32::from_rgb(0x4a, 0x43, 0x36);

pub enum Block {
    /// A section heading.
    H(&'static str),
    P(&'static str),
    Bullet(&'static str),
    /// A question and its answer.
    Q(&'static str, &'static str),
}
use Block::*;

pub const LEDE_TEXT: &str = "Or: why we can't have a Grand Strategy Game named GrugScape. \r\n
DESKTOP RECOMMENDED; RIP mobile users";

/// The header's bullets: the time range, then what the map shows. The
/// numbers repeat the ones in `BLOCKS`; change both together.
pub const SCOPE: &[&str] = &[
    "**Timeline:** 10,000 to 3,000 BCE (12,000 to 5,000 years ago). Watch the land change.",
    "**Mapmodes:** settlements, pottery, cereals, livestock, megaliths, ancient DNA, pollen, spread of farming.",
    "**Sources:** everything we could find on the public internet.",
];

pub const BLOCKS: &[Block] = &[
    H("Here's the Deal"),
    P("A grand-strategy game, such as Europa Universalis or Civilization, needs every province filled: who lived \
there, how many, what they made, what they ate. Why has nobody built one set in the Neolithic, the age of the \
first farmers?"),
    P("We know far less than we think. What we know depends more on where archaeologists have dug \
and published than on where people lived."),
P("**The Upshot:**"),
    Bullet("**Sites show up where people happen to dig.** Our model of where people lived barely predicts where sites \
are found. How much later-period archaeology happened nearby predicts it well."),
    Bullet("**Modern borders show through.** Britain and Ireland have 17.8 radiocarbon dates per 1,000 km²; \
Ukraine, Belarus and European Russia have 0.11, a 160-fold gap. Hungary has 13.2, Romania 1.6."),
    Bullet("**Whole literatures are missing.** Nobody has published an open, downloadable compilation for the \
Neolithic of Ukraine, Belarus, European Russia, the Caucasus, the Baltic states or Finland. Those sites were dug \
and published, just not as downloadable data."),
    Bullet("**The emptiest places are interesting ones.** The Amu Darya delta, the Horn of Africa coast, Sistan \
and Doggerland (the drowned land under the North Sea) have no dated site in any period."),
    H("FAQ"),
    Q("Where were the Yamnaya and the first Indo-European speakers?",
      "The Yamnaya were herders on the steppe, the grassland north of the Black Sea. Indo-European is the language \
family that includes English and Hindi. The Yamnaya appear about 3,300 BCE and spread after 3,000 BCE, where our \
window ends. Where Indo-European began is still argued. The steppe is also the emptiest region in the open data. \
The ancient-DNA layers show what the record holds up to 3,000 BCE; the story continues past the map's edge."),
    Q("Was \"Old Europe\", the early farming world of the Balkans, peaceful or centred on women?",
      "The record is mixed. Çatalhöyük, a large farming town in Turkey from about 7,000 BCE, looks neither \
matriarchal nor patriarchal; massacres such as Talheim (about 5,000 BCE) show organised violence among early \
farmers. We have no layers yet for figurines, burials by sex, or violence."),
    Q("Was farming a mistake?",
      "The map can't judge, but it shows the parts of the argument that leave traces: where farming began, how \
fast it spread, where it stalled for a thousand years, and where foragers held out (the Baltic, Scandinavia, the \
Atlantic edge). We have no health or height layer."),
    Q("Is there a lost civilisation under the sea?",
      "Land is missing: Doggerland and the floor of the Persian Gulf were dry. Drowned land shows blank, and the \
**Missing sites** map says why each blank is blank. Blank means unrecorded, not hidden. Göbekli Tepe, the carved \
stone enclosures in Turkey from about 9,500 BCE, has local forerunners, and the open record shows no advanced \
civilisation before it."),
    Q("When were the Gulf and the Black Sea dry?",
      "Move the timeline in the **Terrain** map: coastlines follow a sea-level curve, date by date."),
    Q("Is my country's site the oldest?",
      "\"Oldest\" usually means \"most dug.\" The 160-fold gap between Britain and Ukraine is about excavation, \
not ancestry. **Missing sites** compares each area's known sites with what the model expects."),
    Q("Where did my ancestry-test groups live?",
      "The spread of farming and the ancient-DNA layers give a rough arrival date for farmers in each region. \
Skin, eye colour and other traits are not covered."),
    Q("Did climate shocks break societies?",
      "Compare the **Köppen** climate map and the **Productivity** map with settlement numbers across a cold snap \
such as 6,200 BCE, or the drying of the Sahara."),
    Q("Can I quote the speculative layer as evidence?",
      "No. It is a labelled guess about a gap, not a find. Please keep the label in any screenshot."),
    H("Using the map"),
    P("Drag to pan, and scroll or pinch to zoom. Choose a map mode: **Terrain**, **Köppen**, **Productivity**, \
**Expected population**, **Evidence** (what the record holds) or **Missing sites** (the gap between the two). \
Click a hex (one of the map's six-sided cells) to inspect it, and move the timeline to change the date."),
];

/// Lays out `s` with `**strong**` and `*italic*` spans, wrapped to `width`,
/// in `roman` (and Alegreya italic for `*…*`).
fn job(s: &str, roman: fn(f32) -> FontId, size: f32, colour: Color32, italic: bool, width: f32) -> LayoutJob {
    let mut job = LayoutJob::default();
    job.wrap.max_width = width;
    let (mut strong, mut em) = (false, italic);
    let mut rest = s;
    while !rest.is_empty() {
        let (text, marker, after) = match rest.find('*') {
            Some(i) if rest[i..].starts_with("**") => (&rest[..i], 2, &rest[i + 2..]),
            Some(i) => (&rest[..i], 1, &rest[i + 1..]),
            None => (rest, 0, ""),
        };
        if !text.is_empty() {
            let font: FontId = if em { book_italic(size) } else { roman(size) };
            let color = if strong { STRONG } else { colour };
            job.append(text, 0.0, TextFormat { font_id: font, color, line_height: Some(size * 1.45), ..Default::default() });
        }
        match marker {
            2 => strong = !strong,
            1 => em = !em,
            _ => {}
        }
        rest = after;
    }
    job
}

/// Shows a laid-out job. It is turned into a galley here because a `Label`
/// given a `LayoutJob` replaces its wrap width with the layout's, which is
/// unbounded inside a horizontal row.
fn text(ui: &mut egui::Ui, job: LayoutJob) -> egui::Response {
    let galley = ui.painter().layout_job(job);
    ui.label(galley)
}

fn para(ui: &mut egui::Ui, w: f32, s: &str, size: f32, colour: Color32, italic: bool) {
    text(ui, job(s, book, size, colour, italic, w));
}

fn heading(ui: &mut egui::Ui, t: &str) {
    ui.add_space(26.0);
    ui.label(RichText::new(t).font(display(23.0)).color(HEAD));
    ui.separator();
}

/// Grug, uploaded once and kept in egui's memory.
fn grug(ctx: &egui::Context) -> TextureHandle {
    let id = egui::Id::unique("splash_grug");
    if let Some(t) = ctx.data(|d| d.get_temp::<TextureHandle>(id)) {
        return t;
    }
    // 220×190 RGBA from assets/grug.jpg (see data/ATTRIBUTIONS.toml, key "grug").
    // Raw so the web build needs no image decoder. Regenerate with Pillow:
    // Image.open("grug.jpg").convert("RGBA").resize((220, 190)).tobytes()
    let img = egui::ColorImage::from_rgba_unmultiplied([220, 190], include_bytes!("../assets/grug.rgba"));
    let t = ctx.load_texture("grug", img, TextureOptions::LINEAR);
    ctx.data_mut(|d| d.insert_temp(id, t.clone()));
    t
}

/// The common questions as a carousel: one card at a time, stepped by the
/// arrow buttons, the dots, a swipe or the ← → keys. The card is as tall as
/// its tallest question, so the controls under it never jump.
fn faq(ui: &mut egui::Ui, w: f32) {
    let qs: Vec<(&str, &str)> = BLOCKS.iter().filter_map(|b| if let Q(q, a) = *b { Some((q, a)) } else { None }).collect();
    let n = qs.len();
    let id = egui::Id::unique("splash_faq");
    let mut i = ui.ctx().data(|d| d.get_temp::<usize>(id)).unwrap_or(0).min(n - 1);
    if !ui.ctx().egui_wants_keyboard_input() {
        ui.input(|inp| {
            if inp.key_pressed(Key::ArrowRight) {
                i = (i + 1) % n;
            }
            if inp.key_pressed(Key::ArrowLeft) {
                i = (i + n - 1) % n;
            }
        });
    }
    let pad = 20.0;
    let inner = w - 2.0 * pad - 2.0;
    let gap = 8.0;
    let tallest = qs
        .iter()
        .map(|(q, a)| {
            let p = ui.painter();
            p.layout_job(job(q, display, 21.0, STRONG, false, inner)).size().y
                + p.layout_job(job(a, book, BODY, INK, false, inner)).size().y
        })
        .fold(0.0, f32::max);
    let (q, a) = qs[i];
    let card = egui::Frame::new()
        .fill(CARD)
        .stroke(Stroke::new(1.0, RULE))
        .corner_radius(8.0)
        .inner_margin(pad)
        .show(ui, |ui| {
            ui.set_width(inner);
            ui.label(RichText::new(format!("Question {} of {}", i + 1, n)).font(book(13.0)).color(WEAK));
            ui.add_space(4.0);
            ui.vertical(|ui| {
                ui.set_min_height(tallest + gap);
                text(ui, job(q, display, 21.0, STRONG, false, inner));
                ui.add_space(gap);
                text(ui, job(a, book, BODY, INK, false, inner));
            });
        });
    // A horizontal swipe across the card turns it.
    let swipe = ui.interact(card.response.rect, id.with("swipe"), Sense::drag());
    if swipe.drag_stopped() {
        let dx = ui.input(|inp| match (inp.pointer.press_origin(), inp.pointer.interact_pos()) {
            (Some(o), Some(p)) => p.x - o.x,
            _ => 0.0,
        });
        if dx < -50.0 {
            i = (i + 1) % n;
        } else if dx > 50.0 {
            i = (i + n - 1) % n;
        }
    }
    ui.add_space(8.0);
    ui.horizontal(|ui| {
        let dot = 14.0;
        let row = 2.0 * 40.0 + n as f32 * dot + 2.0 * ui.spacing().item_spacing.x;
        ui.add_space(((w - row) / 2.0).max(0.0));
        let arrow = |t| egui::Button::new(RichText::new(t).font(display(22.0)).color(HEAD)).frame(false).min_size(vec2(40.0, 28.0));
        if ui.add(arrow("‹")).on_hover_text("Previous question").clicked() {
            i = (i + n - 1) % n;
        }
        ui.spacing_mut().item_spacing.x = 0.0;
        for k in 0..n {
            let (rect, r) = ui.allocate_exact_size(vec2(dot, 28.0), Sense::click());
            let on = k == i;
            let fill = if on { HEAD } else if r.hovered() { LEDE } else { RULE };
            ui.painter().circle_filled(rect.center(), if on { 4.5 } else { 3.5 }, fill);
            if r.on_hover_text(qs[k].0).clicked() {
                i = k;
            }
        }
        ui.spacing_mut().item_spacing.x = 8.0;
        if ui.add(arrow("›")).on_hover_text("Next question").clicked() {
            i = (i + 1) % n;
        }
    });
    ui.ctx().data_mut(|d| d.insert_temp(id, i));
}

/// One run of text in one style.
fn plain(s: &str, font: FontId, colour: Color32, spacing: f32, width: f32) -> LayoutJob {
    let mut job = LayoutJob::default();
    job.wrap.max_width = width;
    let line_height = Some(font.size * 1.3);
    job.append(s, 0.0, TextFormat { font_id: font, color: colour, extra_letter_spacing: spacing, line_height, ..Default::default() });
    job
}

/// Shows `job` with every line centred in a column `w` wide.
fn centred(ui: &mut egui::Ui, w: f32, mut job: LayoutJob) {
    job.halign = Align::Center;
    let galley = ui.painter().layout_job(job);
    let (rect, _) = ui.allocate_exact_size(vec2(w, galley.size().y), Sense::hover());
    ui.painter().galley(pos2(rect.center().x, rect.top()), galley, INK);
}

/// One bulleted line, `w` wide including the bullet.
fn bullet(ui: &mut egui::Ui, w: f32, t: &str, size: f32) {
    ui.horizontal_top(|ui| {
        let dot = ui.label(RichText::new("•  ").font(book(size)).color(HEAD)).rect.width();
        para(ui, w - dot - ui.spacing().item_spacing.x, t, size, INK, false);
    });
    ui.add_space(6.0);
}

/// Grug's entrance, in seconds on the drop's own clock: a pause on the empty
/// page, the fall from above the window, then two bounces.
const WAIT: f32 = 0.35;
const FALL: f32 = 0.5;
const BOUNCE_1: f32 = 0.3;
const BOUNCE_2: f32 = 0.16;
const LAND_1: f32 = FALL;
const LAND_2: f32 = FALL + BOUNCE_1;
const LAND_3: f32 = FALL + BOUNCE_1 + BOUNCE_2;
/// When the dust and the shake have died away.
const SETTLED: f32 = LAND_3 + 0.8;

/// How far above his resting place Grug is at time `t`, as a share of the
/// fall (1 at the start) or, once he has landed, in points.
fn height(t: f32) -> (f32, f32) {
    let arc = |t0: f32, len: f32, top: f32| {
        let u = (t - t0) / len;
        top * 4.0 * u * (1.0 - u)
    };
    if t < LAND_1 {
        (1.0 - (t.max(0.0) / FALL).powi(2), 0.0)
    } else if t < LAND_2 {
        (0.0, arc(LAND_1, BOUNCE_1, 30.0))
    } else if t < LAND_3 {
        (0.0, arc(LAND_2, BOUNCE_2, 7.0))
    } else {
        (0.0, 0.0)
    }
}

/// A decaying kick that starts at `t0`.
fn kick(t: f32, t0: f32, size: f32, decay: f32) -> f32 {
    if t < t0 { 0.0 } else { size * (-(t - t0) * decay).exp() }
}

/// How far the page is jolted down (or up) by the landing, in points.
fn shake(t: f32) -> f32 {
    kick(t, LAND_1, 9.0, 9.0) * ((t - LAND_1) * 52.0).cos()
}

/// Grug, dropped from above the window into a slot centred in the column.
/// He lands with a thud, a squash, a puff of dust and a jolt to the page.
/// Clicking him drops him again.
fn mascot(ui: &mut egui::Ui, w: f32, size: egui::Vec2) {
    let id = egui::Id::unique("splash_drop");
    let tex = grug(ui.ctx());
    let before = ui.ctx().data(|d| d.get_temp::<f32>(id));
    if before.is_none() {
        crate::sound::warm();
    }
    // Long frames (the world is still loading behind the first ones) advance
    // the drop by one ordinary frame, so it is never skipped.
    let dt = ui.input(|i| i.stable_dt).min(0.05);
    let before = before.unwrap_or(-WAIT - dt);
    let mut t = (before + dt).min(SETTLED);

    ui.add_space((24.0 + shake(t)).max(0.0));
    let (slot, _) = ui.allocate_exact_size(vec2(w, size.y), Sense::hover());
    let rest = egui::Rect::from_center_size(slot.center(), size);
    let click = ui.interact(rest, id.with("click"), Sense::click()).on_hover_cursor(egui::CursorIcon::PointingHand);
    if click.on_hover_text("Drop Grug again").clicked() && t >= LAND_3 {
        t = 0.0;
    }

    for (land, volume) in [(LAND_1, 1.0), (LAND_2, 0.3)] {
        if before < land && t >= land {
            crate::sound::thud(volume);
        }
    }

    let screen = ui.ctx().content_rect();
    let (share, points) = height(t);
    let lift = share * (rest.bottom() - screen.top() + 40.0) + points;
    // Stretched by speed on the way down, squashed by each landing.
    let stretch = if t < LAND_1 { 0.16 * (t.max(0.0) / FALL) } else { 0.0 };
    let squash = kick(t, LAND_1, 0.26, 16.0) + kick(t, LAND_2, 0.1, 22.0);
    let drawn = vec2(size.x * (1.0 - 0.5 * stretch + 0.7 * squash), size.y * (1.0 + stretch - squash));
    let feet = pos2(rest.center().x, rest.bottom() - lift);
    let body = egui::Rect::from_min_size(pos2(feet.x - drawn.x / 2.0, feet.y - drawn.y), drawn);

    // While he is in the air he is drawn over everything above the column.
    let p = if t < LAND_3 { ui.painter().clone().with_clip_rect(screen) } else { ui.painter().clone() };
    if t >= 0.0 {
        let near = 1.0 - (lift / 260.0).min(1.0);
        let shadow = Color32::from_black_alpha((near * 120.0) as u8);
        p.add(Shape::ellipse_filled(pos2(rest.center().x, rest.bottom() + 3.0), vec2(size.x * (0.25 + 0.3 * near), 5.0), shadow));
        let uv = egui::Rect::from_min_max(pos2(0.0, 0.0), pos2(1.0, 1.0));
        p.add(RectShape::filled(body, 10.0, Color32::WHITE).with_texture(tex.id(), uv));
    }
    // Dust thrown out to both sides by the first landing.
    let age = (t - LAND_1) / 0.65;
    if (0.0..1.0).contains(&age) {
        let out = 1.0 - (1.0 - age).powi(2);
        for side in [-1.0, 1.0] {
            for (reach, rise, radius) in [(34.0, 4.0, 9.0), (62.0, 12.0, 13.0), (88.0, 7.0, 8.0)] {
                let at = pos2(rest.center().x + side * (size.x * 0.42 + reach * out), rest.bottom() - 4.0 - rise * out);
                p.circle_filled(at, radius * (0.5 + out), LEDE.gamma_multiply(0.3 * (1.0 - age)));
            }
        }
    }

    ui.ctx().data_mut(|d| d.insert_temp(id, t));
    if t < SETTLED {
        ui.ctx().request_repaint();
    }
}

/// The title block and every section, in a column `w` wide. Widths are
/// passed down explicitly: inside a horizontal row the available width is
/// unbounded, so text would never wrap.
///
/// The header reads top to bottom in falling weight: Grug, "Welcome to",
/// the name, what the map is, its time range and layers, and last the
/// mascot's credit.
pub fn show(ui: &mut egui::Ui, w: f32) {
    let narrow = w < 480.0;
    mascot(ui, w, if narrow { vec2(150.0, 130.0) } else { vec2(176.0, 152.0) });
    ui.add_space(16.0);
    let spacing = std::mem::replace(&mut ui.spacing_mut().item_spacing.y, 0.0);
    centred(ui, w, plain("Welcome to", book_italic(if narrow { 20.0 } else { 24.0 }), HEAD, 0.5, w));
    centred(ui, w, plain("The Neolith", display(if narrow { 50.0 } else { 76.0 }), STRONG, 0.0, w));
    ui.add_space(10.0);
    let (rule, _) = ui.allocate_exact_size(vec2(w, 2.0), Sense::hover());
    ui.painter().hline((rule.center().x - 36.0)..=(rule.center().x + 36.0), rule.center().y, Stroke::new(2.0, HEAD));
    ui.add_space(18.0);
    let lede = w.min(560.0);
    centred(ui, w, job(LEDE_TEXT, book, if narrow { 17.0 } else { 19.0 }, LEDE, true, lede));
    ui.add_space(22.0);
    ui.spacing_mut().item_spacing.y = spacing;
    ui.horizontal_top(|ui| {
        ui.add_space((w - lede) / 2.0);
        ui.vertical(|ui| {
            ui.set_width(lede);
            for t in SCOPE {
                bullet(ui, lede, t, 16.0);
            }
        });
    });
    ui.spacing_mut().item_spacing.y = 0.0;
    ui.add_space(12.0);
    centred(ui, w, plain("Mascot: Grug, an internet caveman of unknown authorship.", book(12.0), WEAK, 0.0, w));
    ui.spacing_mut().item_spacing.y = spacing;
    let mut faq_done = false;
    for b in BLOCKS {
        match *b {
            H(t) => heading(ui, t),
            P(t) => {
                para(ui, w, t, BODY, INK, false);
                ui.add_space(6.0);
            }
            Bullet(t) => bullet(ui, w, t, BODY),
            Q(..) if !faq_done => {
                faq_done = true;
                ui.add_space(6.0);
                faq(ui, w);
            }
            Q(..) => {}
        }
    }
    heading(ui, "Credits");
    para(
        ui,
        w,
        "Code is MIT; derived data is CC BY-SA 4.0. Every source, with its licence and citation, is under Credits & \
data below. Grug is an anonymous internet meme, not covered by those licences.",
        14.0,
        WEAK,
        false,
    );
    ui.hyperlink_to(RichText::new("Source: github.com/jtwaugh/neolith").font(book(14.0)), "https://github.com/jtwaugh/neolith");
}

#[cfg(test)]
mod tests {
    #[test]
    fn grug_bytes_match_size() {
        assert_eq!(include_bytes!("../assets/grug.rgba").len(), 220 * 190 * 4);
    }

    #[test]
    fn drop_falls_bounces_and_rests() {
        use super::{LAND_1, LAND_2, LAND_3, height};
        assert_eq!(height(0.0), (1.0, 0.0));
        assert!(height(LAND_1 - 0.01).0 < 0.1);
        assert!(height((LAND_1 + LAND_2) / 2.0).1 > 25.0);
        assert_eq!(height(LAND_3 + 0.1), (0.0, 0.0));
    }

    #[test]
    fn markup_is_balanced() {
        for t in super::SCOPE {
            assert_eq!(t.matches("**").count() % 2, 0, "{t}");
        }
        for b in super::BLOCKS {
            let texts: Vec<&str> = match *b {
                super::H(t) | super::P(t) | super::Bullet(t) => vec![t],
                super::Q(q, a) => vec![q, a],
            };
            for t in texts {
                assert_eq!(t.matches("**").count() % 2, 0, "{t}");
            }
        }
    }
}
