//! xorshift64* random number generator
//!
//! This is a fast, high-quality PRNG that is deterministic and suitable
//! for simulation purposes.
//!
//! # Algorithm
//!
//! xorshift64* is a variant of xorshift that passes TestU01's BigCrush
//! statistical tests. It uses 64-bit state and produces 64-bit output.
//!
//! # Determinism
//!
//! Same seed → same sequence of random numbers. This is CRITICAL for:
//! - Debugging (reproduce exact simulation)
//! - Testing (verify behavior)
//! - Research (validate results)

use serde::{Deserialize, Serialize};

/// Deterministic random number generator using xorshift64*
///
/// # Example
/// ```
/// use payment_simulator_core_rs::RngManager;
///
/// let mut rng = RngManager::new(12345);
/// let value = rng.next();
/// let range_value = rng.range(0, 100); // [0, 100)
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RngManager {
    /// Internal state (64-bit)
    state: u64,
}

impl RngManager {
    /// Create a new RNG with given seed
    ///
    /// # Arguments
    /// * `seed` - Initial seed value (u64)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::RngManager;
    ///
    /// let rng = RngManager::new(12345);
    /// ```
    pub fn new(seed: u64) -> Self {
        // Ensure seed is never zero (xorshift requirement)
        let state = if seed == 0 { 1 } else { seed };
        Self { state }
    }

    /// Generate next random u64 value
    ///
    /// This advances the internal state and returns a random value.
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::RngManager;
    ///
    /// let mut rng = RngManager::new(12345);
    /// let value = rng.next();
    /// ```
    pub fn next(&mut self) -> u64 {
        // xorshift64* algorithm
        let mut x = self.state;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.state = x;
        x.wrapping_mul(0x2545F4914F6CDD1D)
    }

    /// Generate random value in range [min, max)
    ///
    /// # Arguments
    /// * `min` - Minimum value (inclusive)
    /// * `max` - Maximum value (exclusive)
    ///
    /// # Panics
    /// Panics if min >= max
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::RngManager;
    ///
    /// let mut rng = RngManager::new(12345);
    /// let amount = rng.range(10000, 100000); // $100 to $1000 in cents
    /// ```
    pub fn range(&mut self, min: i64, max: i64) -> i64 {
        assert!(min < max, "min must be less than max");

        let value = self.next();
        let range_size = (max - min) as u64;
        min + (value % range_size) as i64
    }

    /// Get current RNG state (for checkpointing/replay)
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::RngManager;
    ///
    /// let rng = RngManager::new(12345);
    /// let state = rng.get_state();
    ///
    /// // Later, can recreate RNG from this state
    /// let rng2 = RngManager::new(state);
    /// ```
    pub fn get_state(&self) -> u64 {
        self.state
    }

    /// Generate random f64 in range [0.0, 1.0)
    ///
    /// Useful for sampling from probability distributions.
    ///
    /// # Example
    /// ```
    /// use payment_simulator_core_rs::RngManager;
    ///
    /// let mut rng = RngManager::new(12345);
    /// let probability = rng.next_f64();
    /// assert!(probability >= 0.0 && probability < 1.0);
    /// ```
    pub fn next_f64(&mut self) -> f64 {
        let value = self.next();
        // Convert to [0.0, 1.0) by dividing by 2^64
        (value >> 11) as f64 * (1.0 / ((1u64 << 53) as f64))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_zero_seed_converted_to_nonzero() {
        let rng = RngManager::new(0);
        assert_ne!(rng.get_state(), 0, "Zero seed should be converted to 1");
    }

    #[test]
    #[should_panic(expected = "min must be less than max")]
    fn test_range_invalid_bounds() {
        let mut rng = RngManager::new(12345);
        rng.range(100, 50); // min > max should panic
    }

    #[test]
    fn test_next_f64_in_range() {
        let mut rng = RngManager::new(12345);

        for _ in 0..1000 {
            let val = rng.next_f64();
            assert!(
                val >= 0.0 && val < 1.0,
                "next_f64() produced value {} outside [0.0, 1.0)",
                val
            );
        }
    }

    #[test]
    fn test_next_f64_deterministic() {
        let mut rng1 = RngManager::new(99999);
        let mut rng2 = RngManager::new(99999);

        for _ in 0..100 {
            let val1 = rng1.next_f64();
            let val2 = rng2.next_f64();
            assert_eq!(val1, val2, "next_f64() not deterministic");
        }
    }
}
