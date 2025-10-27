//! Time management for the simulation
//!
//! The simulation operates in discrete ticks. Multiple ticks form a day.
//! This module provides deterministic time advancement.

use serde::{Deserialize, Serialize};

/// Manages simulation time in discrete ticks and days
///
/// # Example
/// ```
/// use payment_simulator_core_rs::TimeManager;
///
/// let mut time = TimeManager::new(100); // 100 ticks per day
/// assert_eq!(time.current_tick(), 0);
/// assert_eq!(time.current_day(), 0);
///
/// time.advance_tick();
/// assert_eq!(time.current_tick(), 1);
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimeManager {
    /// Total ticks elapsed since simulation start
    current_tick: usize,
    /// Number of ticks in one day
    ticks_per_day: usize,
}

impl TimeManager {
    /// Create a new TimeManager
    ///
    /// # Arguments
    /// * `ticks_per_day` - Number of ticks in one business day
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::TimeManager;
    ///
    /// let time = TimeManager::new(100);
    /// ```
    pub fn new(ticks_per_day: usize) -> Self {
        assert!(ticks_per_day > 0, "ticks_per_day must be positive");
        Self {
            current_tick: 0,
            ticks_per_day,
        }
    }

    /// Advance time by one tick
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::TimeManager;
    ///
    /// let mut time = TimeManager::new(100);
    /// time.advance_tick();
    /// assert_eq!(time.current_tick(), 1);
    /// ```
    pub fn advance_tick(&mut self) {
        self.current_tick += 1;
    }

    /// Get the current tick (total ticks since start)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::TimeManager;
    ///
    /// let time = TimeManager::new(100);
    /// assert_eq!(time.current_tick(), 0);
    /// ```
    pub fn current_tick(&self) -> usize {
        self.current_tick
    }

    /// Get the current day (0-indexed)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::TimeManager;
    ///
    /// let mut time = TimeManager::new(100);
    /// for _ in 0..100 {
    ///     time.advance_tick();
    /// }
    /// assert_eq!(time.current_day(), 1);
    /// ```
    pub fn current_day(&self) -> usize {
        self.current_tick / self.ticks_per_day
    }

    /// Get the tick within the current day (0-indexed)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::TimeManager;
    ///
    /// let mut time = TimeManager::new(100);
    /// for _ in 0..50 {
    ///     time.advance_tick();
    /// }
    /// assert_eq!(time.tick_within_day(), 50);
    /// ```
    pub fn tick_within_day(&self) -> usize {
        self.current_tick % self.ticks_per_day
    }

    /// Check if current tick is the last tick of the day
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::TimeManager;
    ///
    /// let mut time = TimeManager::new(100);
    /// for _ in 0..99 {
    ///     time.advance_tick();
    /// }
    /// assert!(time.is_end_of_day());
    /// ```
    pub fn is_end_of_day(&self) -> bool {
        self.tick_within_day() == self.ticks_per_day - 1
    }

    /// Get ticks per day
    pub fn ticks_per_day(&self) -> usize {
        self.ticks_per_day
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[should_panic(expected = "ticks_per_day must be positive")]
    fn test_zero_ticks_per_day_panics() {
        TimeManager::new(0);
    }
}
