//! Famous sites: the places a player looks for first (Jericho, Çatalhöyük,
//! Göbekli Tepe …), from `assets/renown.json` (written up in
//! `data/renown/SOURCES.md`). Renown never changes a piece or a recorded
//! value; it only decides which names the map shows first, and from how far
//! out, and gives every record of one famous site the same name.

use neolith_core::{LonLat, Settlement, World};
use serde::Deserialize;
use std::sync::OnceLock;

#[derive(Debug, Deserialize)]
pub struct Entry {
    pub name: String,
    #[serde(default)]
    pub aliases: Vec<String>,
    /// 1-3: 3 is named at every zoom, 2 from regional zoom, 1 only ahead
    /// of ordinary sites.
    pub renown: u8,
    pub lon: f64,
    pub lat: f64,
    pub known_for: String,
    pub wikipedia: String,
    #[serde(default = "default_radius")]
    pub radius_km: f64,
    /// The piece to draw ("town", "monument", "cave"), overriding the
    /// record's kind ([`crate::board::scene::Shape`]).
    #[serde(default)]
    pub piece: Option<String>,
}

fn default_radius() -> f64 {
    15.0
}

#[derive(Deserialize)]
struct File {
    site: Vec<Entry>,
}

pub fn entries() -> &'static [Entry] {
    static ENTRIES: OnceLock<Vec<Entry>> = OnceLock::new();
    ENTRIES.get_or_init(|| {
        serde_json::from_str::<File>(include_str!("../assets/renown.json")).map(|f| f.site).unwrap_or_else(|e| {
            log::error!("assets/renown.json: {e}");
            Vec::new()
        })
    })
}

/// A settlement's famous-site entry.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Renowned {
    /// Index into [`entries`].
    pub entry: usize,
    /// The entry's renown for the primary record; at most 1 for the others.
    pub renown: u8,
    /// The record that stands for the site when several match it (the
    /// nearest to its coordinates, then one spelled exactly as the entry): only it carries the
    /// famous-site star, so four Çatalhöyük records don't show four.
    pub primary: bool,
}

impl Renowned {
    pub fn entry(&self) -> &'static Entry {
        &entries()[self.entry]
    }
}

/// Lower case, accents folded, punctuation dropped, words separated by one
/// space: "Qala’at Jarmo" → "qalaat jarmo", "Çatalhöyük" → "catalhoyuk".
pub fn fold(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for ch in s.chars().flat_map(char::to_lowercase) {
        let c = match ch {
            'à' | 'á' | 'â' | 'ã' | 'ä' | 'å' | 'ā' => 'a',
            'ç' | 'ć' | 'č' => 'c',
            'ď' => 'd',
            'è' | 'é' | 'ê' | 'ë' | 'ē' | 'ě' => 'e',
            'ğ' | 'ġ' => 'g',
            'ì' | 'í' | 'î' | 'ï' | 'ı' | 'ī' => 'i',
            'ñ' | 'ń' | 'ň' => 'n',
            'ò' | 'ó' | 'ô' | 'õ' | 'ö' | 'ø' | 'ō' => 'o',
            'ř' => 'r',
            'ş' | 'ś' | 'š' => 's',
            'ţ' | 'ť' => 't',
            'ù' | 'ú' | 'û' | 'ü' | 'ū' | 'ů' => 'u',
            'ý' | 'ÿ' => 'y',
            'ź' | 'ż' | 'ž' => 'z',
            '\'' | '’' | '‘' | 'ʿ' | 'ʾ' => continue,
            c if c.is_alphanumeric() => c,
            _ => ' ',
        };
        out.push(c);
    }
    out.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// Whether `needle` occurs in `hay` as whole words (both already folded).
fn has_words(hay: &str, needle: &str) -> bool {
    !needle.is_empty() && format!(" {hay} ").contains(&format!(" {needle} "))
}

fn km(a: LonLat, b: LonLat) -> f64 {
    let (p1, p2) = (a.lat.to_radians(), b.lat.to_radians());
    let dl = (a.lon - b.lon).to_radians();
    let c = p1.sin() * p2.sin() + p1.cos() * p2.cos() * dl.cos();
    6371.0 * c.clamp(-1.0, 1.0).acos()
}

fn keys() -> &'static [(LonLat, f64, Vec<String>)] {
    static KEYS: OnceLock<Vec<(LonLat, f64, Vec<String>)>> = OnceLock::new();
    KEYS.get_or_init(|| {
        entries()
            .iter()
            .map(|e| {
                let names = std::iter::once(&e.name).chain(&e.aliases).map(|n| fold(n)).collect();
                (LonLat::new(e.lon, e.lat), e.radius_km, names)
            })
            .collect()
    })
}

/// The famous-site entry of one settlement: its name contains the entry's
/// name or an alias as whole words and it lies within the entry's radius
/// (the nearest entry, if several match).
pub fn lookup(s: &Settlement) -> Option<Renowned> {
    let name = fold(&s.name);
    keys()
        .iter()
        .enumerate()
        .filter(|(_, (at, r, names))| km(*at, s.pos) <= *r && names.iter().any(|n| has_words(&name, n)))
        .min_by(|a, b| km(a.1 .0, s.pos).total_cmp(&km(b.1 .0, s.pos)))
        .map(|(entry, _)| Renowned { entry, renown: entries()[entry].renown, primary: true })
}

/// [`lookup`] for each settlement in `world`, by index, with one primary
/// record per entry.
pub fn index(world: &World) -> Vec<Option<Renowned>> {
    let mut out: Vec<Option<Renowned>> = world.settlements.iter().map(lookup).collect();
    let score = |i: usize, f: &Renowned| {
        let s = &world.settlements[i];
        let e = f.entry();
        let exact = fold(&s.name) == fold(&e.name);
        // Nearest to the site's own coordinates, to the kilometre; then the
        // exact spelling.
        (km(LonLat::new(e.lon, e.lat), s.pos).round(), !exact, s.id)
    };
    for entry in 0..entries().len() {
        let ids: Vec<usize> = (0..out.len()).filter(|&i| out[i].is_some_and(|f| f.entry == entry)).collect();
        let best = ids.iter().copied().min_by(|&a, &b| {
            let (sa, sb) = (score(a, &out[a].unwrap()), score(b, &out[b].unwrap()));
            sa.partial_cmp(&sb).unwrap_or(std::cmp::Ordering::Equal)
        });
        for i in ids {
            if let Some(f) = out[i].as_mut() {
                f.primary = Some(i) == best;
                // The other records rank below it, so the name goes on the
                // piece with the star whenever that site is on the map.
                if !f.primary {
                    f.renown = f.renown.min(1);
                }
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn entries_parse() {
        let e = entries();
        assert!(e.len() >= 40, "{}", e.len());
        assert!(e.iter().all(|e| (1..=3).contains(&e.renown) && e.wikipedia.starts_with("https://")));
    }

    #[test]
    fn names_fold() {
        assert_eq!(fold("Çatalhöyük"), "catalhoyuk");
        assert_eq!(fold("Qala’at Jarmo"), "qalaat jarmo");
        assert_eq!(fold("Mané-Miguel Y (Mont St. Michel, Carnac)"), "mane miguel y mont st michel carnac");
        assert_eq!(fold("Nevalı Çori"), fold("Nevali Cori"));
        assert!(has_words("varna cemetery", "varna"));
        assert!(!has_words("varnaville", "varna"));
    }
}
