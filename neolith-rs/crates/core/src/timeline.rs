use crate::time::Year;
use serde::{Deserialize, Serialize};
use smallvec::SmallVec;

/// A step function over keyframes. Keys are sorted by year and unique; a
/// value holds from its key until the next key.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Timeline<T> {
    keys: SmallVec<[(Year, T); 8]>,
}

impl<T> Default for Timeline<T> {
    fn default() -> Self {
        Self { keys: SmallVec::new() }
    }
}

impl<T: Copy> Timeline<T> {
    pub fn new() -> Self {
        Self::default()
    }

    /// Builds a timeline from keys in any order. A later duplicate year wins.
    pub fn from_keys(keys: impl IntoIterator<Item = (Year, T)>) -> Self {
        let mut t = Self::new();
        for (y, v) in keys {
            t.set_key(y, v);
        }
        t
    }

    /// Index of the last key with `key <= y`.
    fn index_in_effect(&self, y: Year) -> Option<usize> {
        self.keys.partition_point(|(k, _)| *k <= y).checked_sub(1)
    }

    /// The value in effect at `y`: that of the latest key at or before `y`.
    /// `None` before the first key.
    pub fn at(&self, y: Year) -> Option<T> {
        self.index_in_effect(y).map(|i| self.keys[i].1)
    }

    /// The year of the keyframe in effect at `y`.
    pub fn key_in_effect(&self, y: Year) -> Option<Year> {
        self.index_in_effect(y).map(|i| self.keys[i].0)
    }

    /// The value stored exactly at key `y`, if there is such a key.
    pub fn get_key(&self, y: Year) -> Option<T> {
        self.keys.binary_search_by_key(&y, |(k, _)| *k).ok().map(|i| self.keys[i].1)
    }

    /// Sets (or inserts) the key at `y`. Returns the previous value at that key.
    pub fn set_key(&mut self, y: Year, v: T) -> Option<T> {
        match self.keys.binary_search_by_key(&y, |(k, _)| *k) {
            Ok(i) => Some(std::mem::replace(&mut self.keys[i].1, v)),
            Err(i) => {
                self.keys.insert(i, (y, v));
                None
            }
        }
    }

    /// Removes the key at `y`. Returns its value if it existed.
    pub fn remove_key(&mut self, y: Year) -> Option<T> {
        self.keys.binary_search_by_key(&y, |(k, _)| *k).ok().map(|i| self.keys.remove(i).1)
    }

    pub fn keys(&self) -> &[(Year, T)] {
        &self.keys
    }

    pub fn len(&self) -> usize {
        self.keys.len()
    }

    pub fn is_empty(&self) -> bool {
        self.keys.is_empty()
    }

    /// True when keys are strictly increasing (the invariant; checked on load).
    pub fn is_sorted(&self) -> bool {
        self.keys.windows(2).all(|w| w[0].0 < w[1].0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tl() -> Timeline<u8> {
        Timeline::from_keys([(Year(-8000), 2), (Year(-10000), 1), (Year(-6000), 3)])
    }

    #[test]
    fn step_function() {
        let t = tl();
        assert!(t.is_sorted());
        assert_eq!(t.at(Year(-10001)), None);
        assert_eq!(t.at(Year(-10000)), Some(1));
        assert_eq!(t.at(Year(-8001)), Some(1));
        assert_eq!(t.at(Year(-8000)), Some(2));
        assert_eq!(t.at(Year(-7500)), Some(2));
        assert_eq!(t.at(Year(2000)), Some(3));
        assert_eq!(t.key_in_effect(Year(-7500)), Some(Year(-8000)));
        assert_eq!(t.key_in_effect(Year(-20000)), None);
    }

    #[test]
    fn set_and_remove() {
        let mut t = tl();
        assert_eq!(t.set_key(Year(-8000), 9), Some(2));
        assert_eq!(t.set_key(Year(-7500), 7), None);
        assert_eq!(t.len(), 4);
        assert!(t.is_sorted());
        assert_eq!(t.at(Year(-7400)), Some(7));
        assert_eq!(t.remove_key(Year(-7500)), Some(7));
        assert_eq!(t.remove_key(Year(-7500)), None);
        assert_eq!(t.at(Year(-7400)), Some(9));
        assert_eq!(t.get_key(Year(-7400)), None);
        assert_eq!(t.get_key(Year(-8000)), Some(9));
    }
}
