//! Typed hex property values. Everything the palette, the editor and the
//! file format handle is one of these; never a string.

use serde::{Deserialize, Serialize};

macro_rules! terrain {
    ($($variant:ident => $name:literal),* $(,)?) => {
        /// Terrain / biome. `Land` and `Unknown` are explicit members (they
        /// exist in the source data).
        #[repr(u8)]
        #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
        pub enum Terrain { $($variant),* }

        impl Terrain {
            pub const ALL: &'static [Terrain] = &[$(Terrain::$variant),*];

            /// The name used in the GeoJSON data and shown in the UI.
            pub fn name(self) -> &'static str {
                match self { $(Terrain::$variant => $name),* }
            }

            pub fn from_name(s: &str) -> Option<Self> {
                match s { $($name => Some(Terrain::$variant),)* _ => None }
            }
        }
    };
}

terrain! {
    Water => "Water",
    Ice => "Ice",
    Plains => "Plains",
    Mountains => "Mountains",
    Land => "Land",
    Chaparral => "Chaparral",
    ExtremeDesert => "Extreme Desert",
    SemiDesert => "Semi-Desert",
    Free => "Free",
    Savannah => "Savannah",
    Woodlands => "Woodlands",
    TropicalForest => "Tropical Forest",
    Grassland => "Grassland",
    TemperateForest => "Temperate Forest",
    SteppeForest => "Steppe-Forest",
    BorealForest => "Boreal Forest",
    Unknown => "Unknown",
    // Appended after Unknown so existing u8 codes in world.bin keep their meaning.
    Tundra => "Tundra",
    // Mountain ground above the treeline. (`Mountains` is a landform, now
    // `Landform`; the variant stays so older files still load.)
    Alpine => "Alpine",
    // Green river bottomland in dry or open country (pipeline `[rivers.floodplain]`).
    Floodplain => "Floodplain",
}

impl Terrain {
    pub fn from_u8(v: u8) -> Option<Self> {
        Self::ALL.get(v as usize).copied()
    }

    /// Classes kept only so old u8 codes keep their meaning (the drawn
    /// palette's Land, Free and Mountains, the old Plains fill, Unknown). The
    /// pipeline no longer writes them, and the editor does not offer them.
    pub fn is_legacy(self) -> bool {
        matches!(self, Terrain::Plains | Terrain::Mountains | Terrain::Land | Terrain::Free | Terrain::Unknown)
    }

    /// The ground cover the Ground map mode paints under this biome's
    /// props; `None` for water.
    pub fn cover(self) -> Option<Cover> {
        Some(match self {
            Terrain::Water => return None,
            Terrain::ExtremeDesert | Terrain::SemiDesert => Cover::Sand,
            Terrain::Plains
            | Terrain::Grassland
            | Terrain::Savannah
            | Terrain::SteppeForest
            | Terrain::Floodplain
            | Terrain::Chaparral
            | Terrain::Land
            | Terrain::Free
            | Terrain::Unknown => Cover::Grass,
            Terrain::BorealForest | Terrain::Tundra => Cover::Moss,
            Terrain::TemperateForest | Terrain::Woodlands | Terrain::TropicalForest => Cover::Litter,
            Terrain::Alpine | Terrain::Mountains => Cover::Rock,
            Terrain::Ice => Cover::Snow,
        })
    }
}

/// Ground cover in the Ground map mode: what the soil surface looks like
/// between the props, drawn as a procedural texture.
#[repr(u8)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Cover {
    Grass,
    Moss,
    Sand,
    Rock,
    Snow,
    /// Forest floor: leaf and needle litter on dark soil.
    Litter,
}

impl Cover {
    pub const ALL: [Cover; 6] = [Cover::Grass, Cover::Moss, Cover::Sand, Cover::Rock, Cover::Snow, Cover::Litter];

    pub fn label(self) -> &'static str {
        match self {
            Cover::Grass => "Grass",
            Cover::Moss => "Moss and heath",
            Cover::Sand => "Sand",
            Cover::Rock => "Bare rock",
            Cover::Snow => "Snow and ice",
            Cover::Litter => "Forest floor",
        }
    }
}

/// Static landform of a hex, from the share of its elevation cells that are
/// mountain (Kapos et al. 2000 bands) and its median elevation. Separate
/// from [`Terrain`], which is the biome.
#[repr(u8)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Landform {
    Flat,
    Hills,
    Mountains,
    HighMountains,
}

impl Landform {
    pub const ALL: [Landform; 4] = [Landform::Flat, Landform::Hills, Landform::Mountains, Landform::HighMountains];

    pub fn from_u8(v: u8) -> Option<Self> {
        Self::ALL.get(v as usize).copied()
    }

    pub fn label(self) -> &'static str {
        match self {
            Landform::Flat => "Flat",
            Landform::Hills => "Hills",
            Landform::Mountains => "Mountains",
            Landform::HighMountains => "High mountains",
        }
    }

    pub fn is_mountain(self) -> bool {
        self >= Landform::Mountains
    }
}

/// Köppen–Geiger climate class index, 0 (Ocean) ..= 30 (EF). The old
/// `climate` string field is exactly [`Koeppen::code`].
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub struct Koeppen(u8);

/// Plain-language names for [`KOEPPEN_CODES`], in the same order.
const KOEPPEN_NAMES: [&str; 31] = [
    "Ocean", "Tropical rainforest", "Tropical monsoon", "Tropical savanna", "Hot desert", "Cold desert",
    "Hot steppe", "Cold steppe", "Mediterranean, hot summer", "Mediterranean, warm summer",
    "Mediterranean, cold summer", "Humid subtropical, dry winter", "Subtropical highland, dry winter",
    "Cold subtropical highland, dry winter", "Humid subtropical", "Temperate oceanic", "Subpolar oceanic",
    "Continental, hot dry summer", "Continental, warm dry summer", "Subarctic, dry summer",
    "Extreme subarctic, dry summer", "Continental, hot summer, dry winter", "Continental, warm summer, dry winter",
    "Subarctic, dry winter", "Extreme subarctic, dry winter", "Humid continental, hot summer",
    "Humid continental, warm summer", "Subarctic", "Extreme subarctic", "Tundra", "Ice cap",
];

const KOEPPEN_CODES: [&str; 31] = [
    "Ocean", "Af", "Am", "Aw/As", "BWh", "BWk", "BSh", "BSk", "Csa", "Csb", "Csc", "Cwa", "Cwb",
    "Cwc", "Cfa", "Cfb", "Cfc", "Dsa", "Dsb", "Dsc", "Dsd", "Dwa", "Dwb", "Dwc", "Dwd", "Dfa",
    "Dfb", "Dfc", "Dfd", "ET", "EF",
];

impl Koeppen {
    pub const COUNT: u8 = 31;
    pub const OCEAN: Koeppen = Koeppen(0);

    pub fn new(index: u8) -> Option<Self> {
        (index < Self::COUNT).then_some(Koeppen(index))
    }

    pub fn index(self) -> u8 {
        self.0
    }

    /// Plain-language climate name, e.g. "Hot desert" for BWh.
    pub fn description(self) -> &'static str {
        KOEPPEN_NAMES[self.0 as usize]
    }

    pub fn code(self) -> &'static str {
        KOEPPEN_CODES[self.0 as usize]
    }

    pub fn from_code(s: &str) -> Option<Self> {
        KOEPPEN_CODES.iter().position(|c| *c == s).map(|i| Koeppen(i as u8))
    }

    pub fn all() -> impl Iterator<Item = Koeppen> {
        (0..Self::COUNT).map(Koeppen)
    }
}

macro_rules! pop_density {
    ($($variant:ident => $value:literal),* $(,)?) => {
        /// Population density bucket (people/km²), in increasing order.
        #[repr(u8)]
        #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
        pub enum PopDensity { $($variant),* }

        impl PopDensity {
            pub const ALL: &'static [PopDensity] = &[$(PopDensity::$variant),*];

            /// People per km².
            pub fn value(self) -> f64 {
                match self { $(PopDensity::$variant => $value),* }
            }

            /// Exact bucket lookup (within 1e-6).
            pub fn from_value(v: f64) -> Option<Self> {
                Self::ALL.iter().copied().find(|p| (p.value() - v).abs() < 1e-6)
            }
        }
    };
}

pop_density! {
    P0_0 => 0.0,
    P0_1 => 0.1,
    P0_3 => 0.3,
    P0_5 => 0.5,
    P0_8 => 0.8,
    P1_0 => 1.0,
    P1_5 => 1.5,
    P2_0 => 2.0,
    P5_0 => 5.0,
}

impl PopDensity {
    pub fn from_u8(v: u8) -> Option<Self> {
        Self::ALL.get(v as usize).copied()
    }
}

/// Which per-hex property (also: which map mode).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Prop {
    Terrain,
    Koeppen,
    Pop,
}

impl Prop {
    pub const ALL: [Prop; 3] = [Prop::Terrain, Prop::Koeppen, Prop::Pop];

    pub fn index(self) -> usize {
        self as usize
    }

    pub fn label(self) -> &'static str {
        match self {
            Prop::Terrain => "Terrain",
            Prop::Koeppen => "Köppen",
            Prop::Pop => "Population",
        }
    }

    /// The values the editor offers: every value but the legacy terrains.
    pub fn palette(self) -> Vec<Value> {
        self.values().into_iter().filter(|v| !matches!(v, Value::Terrain(t) if t.is_legacy())).collect()
    }

    /// Every value of this property, in palette order.
    pub fn values(self) -> Vec<Value> {
        match self {
            Prop::Terrain => Terrain::ALL.iter().map(|t| Value::Terrain(*t)).collect(),
            Prop::Koeppen => Koeppen::all().map(Value::Koeppen).collect(),
            Prop::Pop => PopDensity::ALL.iter().map(|p| Value::Pop(*p)).collect(),
        }
    }
}

/// What the board is coloured by: one of the editable properties, or a
/// read-only layer (static elevation, productivity from the climate model,
/// the biodiversity derived from it, or the population expected from both
/// and the spread of farming), or the selected speculative evidence layer
/// ([`crate::evidence`]).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum MapMode {
    Terrain,
    Koeppen,
    Pop,
    Elevation,
    Npp,
    Biodiversity,
    Expected,
    Evidence,
    /// Sites the list is missing ([`crate::residuals`]).
    Missing,
    /// Autosomal ancestry of ancient genomes ([`crate::ancestry`]): recorded
    /// only, land without genomes is drawn as unknown.
    Ancestry,
    /// The terrain map's props and landforms over a realistic ground cover
    /// ([`Terrain::cover`]) instead of the flat biome colours. Appended
    /// last: the index is the palette row and the shader's mode number.
    Ground,
}

impl MapMode {
    pub const ALL: [MapMode; 11] = [
        MapMode::Terrain,
        MapMode::Koeppen,
        MapMode::Pop,
        MapMode::Elevation,
        MapMode::Npp,
        MapMode::Biodiversity,
        MapMode::Expected,
        MapMode::Evidence,
        MapMode::Missing,
        MapMode::Ancestry,
        MapMode::Ground,
    ];

    /// The modes offered in the top-bar map selector. Population is hidden
    /// for now (not useful yet); it stays in [`MapMode::ALL`] so palette
    /// rows and harness `--mode pop` keep working.
    pub const MENU: [MapMode; 10] = [
        MapMode::Ground,
        MapMode::Terrain,
        MapMode::Koeppen,
        MapMode::Elevation,
        MapMode::Npp,
        MapMode::Biodiversity,
        MapMode::Expected,
        MapMode::Evidence,
        MapMode::Missing,
        MapMode::Ancestry,
    ];

    /// Also the row of the GPU palette texture.
    pub fn index(self) -> usize {
        self as usize
    }

    /// Drawn as the terrain map is (full-colour art, soft biome edges,
    /// sward and snow), not as a data wash over it.
    pub fn terrain_like(self) -> bool {
        matches!(self, MapMode::Terrain | MapMode::Ground)
    }

    /// The editable property this mode shows, if any.
    pub fn prop(self) -> Option<Prop> {
        match self {
            MapMode::Terrain => Some(Prop::Terrain),
            MapMode::Koeppen => Some(Prop::Koeppen),
            MapMode::Pop => Some(Prop::Pop),
            MapMode::Elevation | MapMode::Npp | MapMode::Biodiversity | MapMode::Expected | MapMode::Evidence | MapMode::Missing | MapMode::Ancestry | MapMode::Ground => None,
        }
    }

    pub fn label(self) -> &'static str {
        match self {
            MapMode::Elevation => "Elevation",
            MapMode::Npp => "Productivity",
            MapMode::Biodiversity => "Biodiversity",
            MapMode::Expected => "Expected population",
            MapMode::Evidence => "Evidence",
            MapMode::Missing => "Missing sites",
            MapMode::Ancestry => "Ancestry",
            MapMode::Ground => "Ground cover",
            _ => self.prop().map_or("", Prop::label),
        }
    }

    /// Parses a `--mode` argument.
    pub fn from_arg(s: &str) -> Option<Self> {
        match s {
            "terrain" => Some(MapMode::Terrain),
            "koeppen" => Some(MapMode::Koeppen),
            "pop" | "population" => Some(MapMode::Pop),
            "elevation" | "elev" => Some(MapMode::Elevation),
            "npp" | "productivity" => Some(MapMode::Npp),
            "biodiversity" => Some(MapMode::Biodiversity),
            "expected" => Some(MapMode::Expected),
            "evidence" => Some(MapMode::Evidence),
            "missing" => Some(MapMode::Missing),
            "ancestry" => Some(MapMode::Ancestry),
            "ground" | "cover" => Some(MapMode::Ground),
            _ => None,
        }
    }
}

impl From<Prop> for MapMode {
    fn from(p: Prop) -> Self {
        match p {
            Prop::Terrain => MapMode::Terrain,
            Prop::Koeppen => MapMode::Koeppen,
            Prop::Pop => MapMode::Pop,
        }
    }
}

/// A typed value of one of the three properties.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Value {
    Terrain(Terrain),
    Koeppen(Koeppen),
    Pop(PopDensity),
}

impl Value {
    pub fn prop(self) -> Prop {
        match self {
            Value::Terrain(_) => Prop::Terrain,
            Value::Koeppen(_) => Prop::Koeppen,
            Value::Pop(_) => Prop::Pop,
        }
    }

    /// The compact index used in snapshots and the GPU state texture.
    pub fn as_u8(self) -> u8 {
        match self {
            Value::Terrain(t) => t as u8,
            Value::Koeppen(k) => k.index(),
            Value::Pop(p) => p as u8,
        }
    }

    pub fn from_u8(prop: Prop, v: u8) -> Option<Self> {
        match prop {
            Prop::Terrain => Terrain::from_u8(v).map(Value::Terrain),
            Prop::Koeppen => Koeppen::new(v).map(Value::Koeppen),
            Prop::Pop => PopDensity::from_u8(v).map(Value::Pop),
        }
    }

    /// Human-readable label for palettes and inspectors.
    pub fn label(self) -> String {
        match self {
            Value::Terrain(t) => t.name().to_string(),
            Value::Koeppen(k) => format!("{} ({})", k.code(), k.index()),
            Value::Pop(p) => format!("{} /km²", p.value()),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_land_terrain_has_a_cover() {
        for t in Terrain::ALL {
            assert_eq!(t.cover().is_none(), *t == Terrain::Water, "{t:?}");
        }
        assert_eq!(Terrain::ExtremeDesert.cover(), Some(Cover::Sand));
        assert_eq!(Terrain::Ice.cover(), Some(Cover::Snow));
        assert_eq!(Terrain::Alpine.cover(), Some(Cover::Rock));
    }

    #[test]
    fn ground_mode_is_appended() {
        // Its index is a palette row and the shader's mode number: the
        // modes before it keep theirs.
        assert_eq!(MapMode::Ground.index(), MapMode::ALL.len() - 1);
        assert_eq!(MapMode::Ancestry.index(), 9);
        assert!(MapMode::Ground.terrain_like() && !MapMode::Evidence.terrain_like());
        assert_eq!(MapMode::from_arg("ground"), Some(MapMode::Ground));
    }

    #[test]
    fn terrain_round_trips() {
        for (i, t) in Terrain::ALL.iter().enumerate() {
            assert_eq!(*t as usize, i);
            assert_eq!(Terrain::from_name(t.name()), Some(*t));
            assert_eq!(Terrain::from_u8(i as u8), Some(*t));
        }
        assert_eq!(Terrain::ALL.len(), 20);
        assert_eq!(Terrain::from_name("Lava"), None);
    }

    #[test]
    fn landform_round_trips() {
        for (i, l) in Landform::ALL.iter().enumerate() {
            assert_eq!(*l as usize, i);
            assert_eq!(Landform::from_u8(i as u8), Some(*l));
        }
        assert_eq!(Landform::from_u8(4), None);
        assert!(!Landform::Hills.is_mountain() && Landform::HighMountains.is_mountain());
        let palette = Prop::Terrain.palette();
        assert!(palette.contains(&Value::Terrain(Terrain::Grassland)));
        assert!(!palette.iter().any(|v| matches!(v, Value::Terrain(t) if t.is_legacy())));
    }

    #[test]
    fn koeppen_codes() {
        assert_eq!(Koeppen::new(15).unwrap().code(), "Cfb");
        assert_eq!(Koeppen::from_code("Ocean"), Some(Koeppen::OCEAN));
        assert_eq!(Koeppen::new(31), None);
        for k in Koeppen::all() {
            assert_eq!(Koeppen::from_code(k.code()), Some(k));
        }
    }

    #[test]
    fn pop_density_is_ordered() {
        let vals: Vec<f64> = PopDensity::ALL.iter().map(|p| p.value()).collect();
        assert!(vals.windows(2).all(|w| w[0] < w[1]));
        assert_eq!(PopDensity::from_value(1.5), Some(PopDensity::P1_5));
        assert_eq!(PopDensity::from_value(0.7), None);
    }

    #[test]
    fn value_u8_round_trips() {
        for prop in Prop::ALL {
            for v in prop.values() {
                assert_eq!(v.prop(), prop);
                assert_eq!(Value::from_u8(prop, v.as_u8()), Some(v));
            }
        }
    }

    #[test]
    fn map_modes_line_up_with_props() {
        for prop in Prop::ALL {
            assert_eq!(MapMode::from(prop).prop(), Some(prop));
            assert_eq!(MapMode::from(prop).index(), prop.index());
        }
        assert_eq!(MapMode::Elevation.prop(), None);
        assert_eq!(MapMode::from_arg("elevation"), Some(MapMode::Elevation));
        assert_eq!(MapMode::from_arg("npp"), Some(MapMode::Npp));
        assert_eq!(MapMode::Npp.prop(), None);
        assert_eq!(MapMode::Npp.label(), "Productivity");
        assert_eq!(MapMode::from_arg("biodiversity"), Some(MapMode::Biodiversity));
        assert_eq!(MapMode::Biodiversity.index(), 5);
        assert_eq!(MapMode::from_arg("expected"), Some(MapMode::Expected));
        assert_eq!(MapMode::Expected.index(), 6);
        assert_eq!(MapMode::from_arg("evidence"), Some(MapMode::Evidence));
        assert_eq!(MapMode::Evidence.index(), 7);
        assert_eq!(MapMode::from_arg("missing"), Some(MapMode::Missing));
        assert_eq!((MapMode::Missing.index(), MapMode::Missing.prop(), MapMode::Missing.label()), (8, None, "Missing sites"));
        assert_eq!(MapMode::Evidence.prop(), None);
        assert!(MapMode::ALL.contains(&MapMode::Evidence) && MapMode::MENU.contains(&MapMode::Evidence));
        assert_eq!(MapMode::Pop.label(), Prop::Pop.label());
    }
}
