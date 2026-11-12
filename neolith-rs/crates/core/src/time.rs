use serde::{Deserialize, Serialize};
use std::fmt;

/// Signed year: negative = BCE. The one year type used everywhere; it is only
/// formatted ("7500 BCE") at the UI edge.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct Year(pub i32);

impl fmt::Display for Year {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.0 < 0 {
            write!(f, "{} BCE", -(self.0 as i64))
        } else {
            write!(f, "{} CE", self.0)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn display() {
        assert_eq!(Year(-7500).to_string(), "7500 BCE");
        assert_eq!(Year(200).to_string(), "200 CE");
    }

    #[test]
    fn ordering_is_chronological() {
        assert!(Year(-10000) < Year(-3000));
        assert!(Year(-1) < Year(1));
    }
}
