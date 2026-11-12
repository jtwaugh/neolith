//! The game clock: one fixed-step accumulator for play, pause, speed and
//! scrub.

use neolith_core::Year;

#[derive(Clone, Debug)]
pub struct Clock {
    year: Year,
    pub playing: bool,
    pub years_per_sec: f64,
    acc: f64,
    min: Year,
    max: Year,
}

pub const SPEED_MIN: f64 = 1.0;
pub const SPEED_MAX: f64 = 500.0;

impl Clock {
    pub fn new(min: Year, max: Year) -> Self {
        Self { year: min, playing: false, years_per_sec: 100.0, acc: 0.0, min, max }
    }

    pub fn year(&self) -> Year {
        self.year
    }

    pub fn range(&self) -> (Year, Year) {
        (self.min, self.max)
    }

    /// Scrub: jump to a year (clamped), in either direction.
    pub fn set_year(&mut self, y: Year) {
        self.year = Year(y.0.clamp(self.min.0, self.max.0));
        self.acc = 0.0;
    }

    /// Advances by `dt` seconds of wall time. Returns true if the year changed.
    /// Stops (pauses) at the end of the range.
    pub fn tick(&mut self, dt: f64) -> bool {
        if !self.playing {
            return false;
        }
        let before = self.year;
        // Cap dt so a stalled frame (hidden tab, breakpoint) does not jump centuries.
        self.acc += dt.clamp(0.0, 0.25) * self.years_per_sec.clamp(SPEED_MIN, SPEED_MAX);
        while self.acc >= 1.0 {
            self.acc -= 1.0;
            if self.year >= self.max {
                self.playing = false;
                self.acc = 0.0;
                break;
            }
            self.year.0 += 1;
        }
        self.year != before
    }
}

/// Index of the keyframe in effect at `year` (`None` before the first).
/// The snapshot only needs recomputing when this changes.
pub fn epoch_index(keyframes: &[Year], year: Year) -> Option<usize> {
    keyframes.partition_point(|k| *k <= year).checked_sub(1)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn paused_clock_does_not_move() {
        let mut c = Clock::new(Year(-10000), Year(-2000));
        assert!(!c.tick(1.0));
        assert_eq!(c.year(), Year(-10000));
    }

    #[test]
    fn advances_at_speed_with_fractional_carry() {
        let mut c = Clock::new(Year(-10000), Year(-2000));
        c.playing = true;
        c.years_per_sec = 10.0;
        for _ in 0..100 {
            c.tick(0.016);
        }
        // 1.6 s at 10 years/s = 16 years.
        assert_eq!(c.year(), Year(-9984));
    }

    #[test]
    fn stops_at_end_and_scrubs_both_ways() {
        let mut c = Clock::new(Year(-100), Year(-90));
        c.playing = true;
        c.years_per_sec = 500.0;
        c.tick(0.2);
        assert_eq!(c.year(), Year(-90));
        assert!(!c.playing);
        c.set_year(Year(-95));
        assert_eq!(c.year(), Year(-95));
        c.set_year(Year(-5000));
        assert_eq!(c.year(), Year(-100));
    }

    #[test]
    fn epoch_index_steps_at_keyframes() {
        let k = [Year(-10000), Year(-9000), Year(-8000)];
        assert_eq!(epoch_index(&k, Year(-10001)), None);
        assert_eq!(epoch_index(&k, Year(-10000)), Some(0));
        assert_eq!(epoch_index(&k, Year(-9001)), Some(0));
        assert_eq!(epoch_index(&k, Year(-9000)), Some(1));
        assert_eq!(epoch_index(&k, Year(0)), Some(2));
    }
}
