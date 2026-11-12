//! Headless core of Neolith: the hex grid, time, the world data model and
//! the editing commands. No UI or rendering dependencies; everything here is
//! unit-tested and is the only thing a future `sim` crate needs.

pub mod edit;
pub mod elevation;
pub mod geom;
pub mod grid;
pub mod io;
pub mod lake;
pub mod river;
pub mod time;
pub mod timeline;
pub mod values;
pub mod world;

pub use edit::{fill, lasso, pencil, Command, Edit, History, KeyMode, Selection};
pub use grid::{GridSpec, HexId, LonLat};
pub use lake::{Lake, LakeShape, NO_SHAPE};
pub use river::{River, RiverClass, RiverState};
pub use time::Year;
pub use timeline::Timeline;
pub use elevation::NO_ELEVATION;
pub use values::{Koeppen, Landform, MapMode, PopDensity, Prop, Terrain, Value};
pub use world::{Settlement, Snapshot, World, NO_DATA};
