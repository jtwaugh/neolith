//! Rivers: polylines drawn over the board, each with a step function saying
//! when it flows. Hexes don't become water; they carry a derived
//! [`RiverClass`] per year (`World::river`) for later game rules.

use crate::grid::LonLat;
use crate::time::Year;
use crate::timeline::Timeline;
use serde::{Deserialize, Serialize};

/// Whether a river flows in a given year.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u8)]
pub enum RiverState {
    Absent = 0,
    Seasonal = 1,
    Perennial = 2,
}

impl RiverState {
    pub const ALL: [RiverState; 3] = [RiverState::Absent, RiverState::Seasonal, RiverState::Perennial];

    pub fn name(self) -> &'static str {
        match self {
            RiverState::Absent => "absent",
            RiverState::Seasonal => "seasonal",
            RiverState::Perennial => "perennial",
        }
    }

    pub fn from_name(s: &str) -> Option<Self> {
        Self::ALL.into_iter().find(|v| v.name() == s)
    }
}

/// What a hex's rivers amount to in a year (`World::river`, one byte per hex).
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
#[repr(u8)]
pub enum RiverClass {
    None = 0,
    /// A small or seasonal river crosses the hex.
    Minor = 1,
    /// A large perennial river crosses the hex.
    Major = 2,
}

impl RiverClass {
    pub fn from_u8(v: u8) -> Option<Self> {
        match v {
            0 => Some(RiverClass::None),
            1 => Some(RiverClass::Minor),
            2 => Some(RiverClass::Major),
            _ => None,
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            RiverClass::None => "none",
            RiverClass::Minor => "minor",
            RiverClass::Major => "major",
        }
    }
}

/// One stretch of a river with a single history. A river whose lower course
/// drowns as the sea rises is split into several of these (same `key`).
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct River {
    pub id: u32,
    /// Catalogue key shared by all stretches of one river (`nile`, `rhine`).
    pub key: String,
    pub name: String,
    /// 1 minor, 2 large, 3 great.
    pub size: u8,
    /// Course from upstream to downstream.
    pub points: Vec<LonLat>,
    pub state: Timeline<RiverState>,
}

impl River {
    /// The state at `year`; absent before the first key.
    pub fn state_at(&self, year: Year) -> RiverState {
        self.state.at(year).unwrap_or(RiverState::Absent)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn state_names_round_trip() {
        for s in RiverState::ALL {
            assert_eq!(RiverState::from_name(s.name()), Some(s));
        }
        assert_eq!(RiverState::from_name("dry"), None);
    }

    #[test]
    fn absent_before_first_key() {
        let r = River {
            id: 1,
            key: "k".into(),
            name: "K".into(),
            size: 1,
            points: vec![LonLat::new(0.0, 0.0), LonLat::new(1.0, 1.0)],
            state: Timeline::from_keys([(Year(-8500), RiverState::Seasonal), (Year(-5300), RiverState::Absent)]),
        };
        assert_eq!(r.state_at(Year(-9000)), RiverState::Absent);
        assert_eq!(r.state_at(Year(-6000)), RiverState::Seasonal);
        assert_eq!(r.state_at(Year(-5000)), RiverState::Absent);
    }
}
