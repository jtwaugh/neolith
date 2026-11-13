//! The "Credits & data" window: every upstream source shipped in the app,
//! with its licence and citation, from `assets/credits.json` (generated from
//! `data/ATTRIBUTIONS.toml` by `python -m pipeline attributions`).

use eframe::egui::{self, RichText};
use serde::Deserialize;
use std::sync::OnceLock;

pub const REPO: &str = "https://github.com/jtwaugh/neolith";

#[derive(Deserialize)]
pub struct Credit {
    pub name: String,
    pub licence: String,
    pub url: String,
    pub citation: String,
    pub used_in: String,
}

pub fn credits() -> &'static [Credit] {
    static C: OnceLock<Vec<Credit>> = OnceLock::new();
    C.get_or_init(|| {
        serde_json::from_str(include_str!("../assets/credits.json")).unwrap_or_else(|e| {
            log::error!("assets/credits.json: {e}");
            Vec::new()
        })
    })
}

fn open_id() -> egui::Id {
    egui::Id::unique("credits_open")
}

/// Ask for the window to be shown on the next frame.
pub fn open(ctx: &egui::Context) {
    ctx.data_mut(|d| d.insert_temp(open_id(), true));
}

/// Draw the window if it is open. Call once per frame.
pub fn show(ctx: &egui::Context) {
    let mut open = ctx.data(|d| d.get_temp::<bool>(open_id()).unwrap_or(false));
    if !open {
        return;
    }
    egui::Window::new("Credits & data")
        .open(&mut open)
        .default_width(480.0)
        .default_height(520.0)
        .vscroll(true)
        .show(ctx, |ui| {
            ui.label(
                "This map is built from open archaeological and palaeoenvironmental data. \
                 Code is MIT; the derived data is CC BY-SA 4.0. Each source below keeps its own \
                 licence and is owed its own credit.",
            );
            ui.horizontal_wrapped(|ui| {
                ui.hyperlink_to("Full list (ATTRIBUTIONS.md)", format!("{REPO}/blob/main/ATTRIBUTIONS.md"));
                ui.label("·");
                ui.hyperlink_to("Source code", REPO);
            });
            ui.weak(
                "Speculative and inferred values are judgements drawn beside the records, \
                 never in place of them.",
            );
            ui.separator();
            for c in credits() {
                ui.add_space(4.0);
                ui.hyperlink_to(RichText::new(&c.name).strong(), &c.url);
                ui.label(RichText::new(format!("Licence: {}", c.licence)).small());
                ui.label(RichText::new(&c.citation).small().weak());
                ui.label(RichText::new(format!("Used for: {}", c.used_in)).small().weak());
            }
        });
    ctx.data_mut(|d| d.insert_temp(open_id(), open));
}

#[cfg(test)]
mod tests {
    #[test]
    fn credits_parse_and_are_not_empty() {
        let c = super::credits();
        assert!(c.len() > 10);
        assert!(c.iter().any(|c| c.name.contains("XRONOS")));
        assert!(c.iter().all(|c| c.url.starts_with("http")));
    }
}
