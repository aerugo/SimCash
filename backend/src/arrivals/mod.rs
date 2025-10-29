//! Arrival generation module for deterministic transaction creation.
//!
//! This module implements the arrival generation system that creates new transactions
//! according to configured distributions. All generation is deterministic based on
//! the RNG seed.
//!
//! # Key Principles
//!
//! 1. **Determinism**: Same seed + same config → same arrivals
//! 2. **Per-Agent Configuration**: Each agent has its own arrival parameters
//! 3. **Poisson Arrivals**: Transaction count per tick follows Poisson distribution
//! 4. **Flexible Amounts**: Support multiple amount distributions
//!
//! # Example
//!
//! ```
//! use payment_simulator_core_rs::arrivals::{ArrivalConfig, AmountDistribution};
//! use payment_simulator_core_rs::rng::RngManager;
//! use std::collections::HashMap;
//!
//! let mut rng = RngManager::new(42);
//! let config = ArrivalConfig {
//!     rate_per_tick: 0.5,
//!     amount_distribution: AmountDistribution::Uniform {
//!         min: 10_000,
//!         max: 100_000,
//!     },
//!     counterparty_weights: HashMap::new(),
//!     deadline_range: (5, 20),
//!     priority: 0,
//!     divisible: false,
//! };
//! ```

use crate::models::Transaction;
use crate::rng::RngManager;
use std::collections::HashMap;

/// Configuration for transaction arrivals for a single agent.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ArrivalConfig {
    /// Expected number of arrivals per tick (Poisson λ parameter)
    pub rate_per_tick: f64,

    /// Distribution for transaction amounts
    pub amount_distribution: AmountDistribution,

    /// Counterparty selection weights (agent_id → weight)
    /// If empty, uniform selection across all agents
    pub counterparty_weights: HashMap<String, f64>,

    /// Deadline range in ticks from arrival (min, max)
    pub deadline_range: (usize, usize),

    /// Priority for generated transactions (0-10)
    pub priority: u8,

    /// Whether generated transactions are divisible
    pub divisible: bool,
}

/// Amount distribution types for transaction generation.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub enum AmountDistribution {
    /// Uniform distribution between min and max (inclusive)
    Uniform { min: i64, max: i64 },

    /// Normal distribution with mean and standard deviation
    Normal { mean: i64, std_dev: i64 },

    /// Log-normal distribution (for heavy-tailed amounts)
    LogNormal { mean: f64, std_dev: f64 },

    /// Exponential distribution with rate parameter
    Exponential { rate: f64 },
}

/// Generator for transaction arrivals across all agents.
pub struct ArrivalGenerator {
    /// Per-agent arrival configurations
    configs: HashMap<String, ArrivalConfig>,

    /// All agent IDs (for counterparty selection)
    all_agent_ids: Vec<String>,

    /// Next transaction ID counter
    next_tx_id: usize,
}

impl ArrivalGenerator {
    /// Create a new arrival generator.
    ///
    /// # Arguments
    ///
    /// * `configs` - Map of agent ID to arrival configuration
    /// * `all_agent_ids` - List of all agent IDs in the simulation
    pub fn new(configs: HashMap<String, ArrivalConfig>, all_agent_ids: Vec<String>) -> Self {
        Self {
            configs,
            all_agent_ids,
            next_tx_id: 0,
        }
    }

    /// Generate arrivals for a specific agent at the given tick.
    ///
    /// # Arguments
    ///
    /// * `agent_id` - ID of the agent generating transactions
    /// * `tick` - Current simulation tick
    /// * `rng` - Mutable reference to RNG manager
    ///
    /// # Returns
    ///
    /// Vector of newly generated transactions
    pub fn generate_for_agent(
        &mut self,
        agent_id: &str,
        tick: usize,
        rng: &mut RngManager,
    ) -> Vec<Transaction> {
        let config = match self.configs.get(agent_id) {
            Some(c) => c,
            None => return Vec::new(), // No arrivals configured for this agent
        };

        // Sample arrival count from Poisson distribution
        let num_arrivals = rng.poisson(config.rate_per_tick);

        let mut transactions = Vec::with_capacity(num_arrivals as usize);

        for _ in 0..num_arrivals {
            // Sample amount
            let amount = self.sample_amount(&config.amount_distribution, rng);

            // Select receiver
            let receiver = self.select_counterparty(agent_id, &config.counterparty_weights, rng);

            // Generate deadline
            let deadline = self.generate_deadline(tick, config.deadline_range, rng);

            // Create transaction
            let tx_id = format!("tx_{:08}", self.next_tx_id);
            self.next_tx_id += 1;

            let mut tx = Transaction::new(
                agent_id.to_string(),
                receiver,
                amount,
                tick,
                deadline,
            );

            // Set priority if configured
            if config.priority > 0 {
                tx = tx.with_priority(config.priority);
            }

            transactions.push(tx);
        }

        transactions
    }

    /// Sample an amount from the configured distribution.
    fn sample_amount(&self, distribution: &AmountDistribution, rng: &mut RngManager) -> i64 {
        match distribution {
            AmountDistribution::Uniform { min, max } => {
                rng.range(*min, *max + 1) // +1 for inclusive range
            }
            AmountDistribution::Normal { mean, std_dev } => {
                let z = self.sample_standard_normal(rng);
                let amount = mean + ((*std_dev as f64) * z) as i64;
                amount.max(1) // Ensure positive
            }
            AmountDistribution::LogNormal { mean, std_dev } => {
                let z = self.sample_standard_normal(rng);
                let log_amount = mean + std_dev * z;
                let amount = log_amount.exp() as i64;
                amount.max(1) // Ensure positive
            }
            AmountDistribution::Exponential { rate } => {
                let u = rng.next_f64();
                let amount = (-u.ln() / rate) as i64;
                amount.max(1) // Ensure positive
            }
        }
    }

    /// Select a counterparty (receiver) based on weights.
    fn select_counterparty(
        &self,
        sender_id: &str,
        weights: &HashMap<String, f64>,
        rng: &mut RngManager,
    ) -> String {
        // Filter out sender from potential receivers
        let potential_receivers: Vec<&String> = self
            .all_agent_ids
            .iter()
            .filter(|id| id.as_str() != sender_id)
            .collect();

        if potential_receivers.is_empty() {
            panic!("Cannot generate transaction: no valid receivers");
        }

        // If no weights configured, use uniform selection
        if weights.is_empty() {
            let idx = rng.range(0, potential_receivers.len() as i64) as usize;
            return potential_receivers[idx].clone();
        }

        // Weighted selection
        let total_weight: f64 = potential_receivers
            .iter()
            .map(|id| weights.get(id.as_str()).unwrap_or(&1.0))
            .sum();

        let mut target = rng.next_f64() * total_weight;

        for receiver_id in &potential_receivers {
            let weight = weights.get(receiver_id.as_str()).unwrap_or(&1.0);
            target -= weight;
            if target <= 0.0 {
                return receiver_id.to_string();
            }
        }

        // Fallback to last receiver (shouldn't reach here)
        potential_receivers.last().unwrap().to_string()
    }

    /// Generate a deadline for the transaction.
    fn generate_deadline(
        &self,
        arrival_tick: usize,
        range: (usize, usize),
        rng: &mut RngManager,
    ) -> usize {
        let (min_offset, max_offset) = range;
        let offset = rng.range(min_offset as i64, max_offset as i64 + 1) as usize;
        arrival_tick + offset
    }

    /// Sample from standard normal distribution using Box-Muller transform.
    fn sample_standard_normal(&self, rng: &mut RngManager) -> f64 {
        let u1 = rng.next_f64();
        let u2 = rng.next_f64();
        (-2.0 * u1.ln()).sqrt() * (2.0 * std::f64::consts::PI * u2).cos()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_arrival_config_creation() {
        let config = ArrivalConfig {
            rate_per_tick: 2.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 1000,
                max: 10000,
            },
            counterparty_weights: HashMap::new(),
            deadline_range: (5, 15),
            priority: 5,
            divisible: true,
        };

        assert_eq!(config.rate_per_tick, 2.0);
        assert_eq!(config.priority, 5);
        assert!(config.divisible);
    }

    #[test]
    fn test_arrival_generator_creation() {
        let mut configs = HashMap::new();
        configs.insert(
            "BANK_A".to_string(),
            ArrivalConfig {
                rate_per_tick: 1.0,
                amount_distribution: AmountDistribution::Uniform {
                    min: 1000,
                    max: 10000,
                },
                counterparty_weights: HashMap::new(),
                deadline_range: (5, 15),
                priority: 0,
                divisible: false,
            },
        );

        let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
        let generator = ArrivalGenerator::new(configs, all_agents);

        assert_eq!(generator.next_tx_id, 0);
    }

    #[test]
    fn test_generate_arrivals_deterministic() {
        let mut configs = HashMap::new();
        configs.insert(
            "BANK_A".to_string(),
            ArrivalConfig {
                rate_per_tick: 2.0,
                amount_distribution: AmountDistribution::Uniform {
                    min: 10000,
                    max: 20000,
                },
                counterparty_weights: HashMap::new(),
                deadline_range: (5, 10),
                priority: 0,
                divisible: false,
            },
        );

        let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];

        // Generate with seed 42
        let mut generator1 = ArrivalGenerator::new(configs.clone(), all_agents.clone());
        let mut rng1 = RngManager::new(42);
        let arrivals1 = generator1.generate_for_agent("BANK_A", 0, &mut rng1);

        // Generate again with same seed
        let mut generator2 = ArrivalGenerator::new(configs, all_agents);
        let mut rng2 = RngManager::new(42);
        let arrivals2 = generator2.generate_for_agent("BANK_A", 0, &mut rng2);

        // Should be identical
        assert_eq!(arrivals1.len(), arrivals2.len());
        for (tx1, tx2) in arrivals1.iter().zip(arrivals2.iter()) {
            assert_eq!(tx1.amount(), tx2.amount());
            assert_eq!(tx1.sender_id(), tx2.sender_id());
            assert_eq!(tx1.receiver_id(), tx2.receiver_id());
            assert_eq!(tx1.deadline_tick(), tx2.deadline_tick());
        }
    }

    #[test]
    fn test_uniform_distribution_range() {
        let config = ArrivalConfig {
            rate_per_tick: 10.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 5000,
                max: 15000,
            },
            counterparty_weights: HashMap::new(),
            deadline_range: (5, 10),
            priority: 0,
            divisible: false,
        };

        let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
        let mut generator = ArrivalGenerator::new(
            vec![("BANK_A".to_string(), config)]
                .into_iter()
                .collect(),
            all_agents,
        );
        let mut rng = RngManager::new(42);

        let arrivals = generator.generate_for_agent("BANK_A", 0, &mut rng);

        // All amounts should be in range
        for tx in arrivals {
            assert!(tx.amount() >= 5000);
            assert!(tx.amount() <= 15000);
        }
    }

    #[test]
    fn test_no_self_transactions() {
        let config = ArrivalConfig {
            rate_per_tick: 5.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 1000,
                max: 10000,
            },
            counterparty_weights: HashMap::new(),
            deadline_range: (5, 10),
            priority: 0,
            divisible: false,
        };

        let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string(), "BANK_C".to_string()];
        let mut generator = ArrivalGenerator::new(
            vec![("BANK_A".to_string(), config)]
                .into_iter()
                .collect(),
            all_agents,
        );
        let mut rng = RngManager::new(42);

        let arrivals = generator.generate_for_agent("BANK_A", 0, &mut rng);

        // No transaction should have BANK_A as receiver
        for tx in arrivals {
            assert_eq!(tx.sender_id(), "BANK_A");
            assert_ne!(tx.receiver_id(), "BANK_A");
        }
    }

    #[test]
    fn test_deadline_range() {
        let config = ArrivalConfig {
            rate_per_tick: 10.0,
            amount_distribution: AmountDistribution::Uniform {
                min: 1000,
                max: 10000,
            },
            counterparty_weights: HashMap::new(),
            deadline_range: (5, 15),
            priority: 0,
            divisible: false,
        };

        let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string()];
        let mut generator = ArrivalGenerator::new(
            vec![("BANK_A".to_string(), config)]
                .into_iter()
                .collect(),
            all_agents,
        );
        let mut rng = RngManager::new(42);

        let arrival_tick = 10;
        let arrivals = generator.generate_for_agent("BANK_A", arrival_tick, &mut rng);

        // All deadlines should be in range [arrival_tick + 5, arrival_tick + 15]
        for tx in arrivals {
            assert!(tx.deadline_tick() >= arrival_tick + 5);
            assert!(tx.deadline_tick() <= arrival_tick + 15);
        }
    }

    #[test]
    fn test_weighted_counterparty_selection() {
        let mut weights = HashMap::new();
        weights.insert("BANK_B".to_string(), 10.0); // High weight
        weights.insert("BANK_C".to_string(), 1.0);  // Low weight

        let config = ArrivalConfig {
            rate_per_tick: 20.0, // Generate many transactions
            amount_distribution: AmountDistribution::Uniform {
                min: 1000,
                max: 10000,
            },
            counterparty_weights: weights,
            deadline_range: (5, 10),
            priority: 0,
            divisible: false,
        };

        let all_agents = vec!["BANK_A".to_string(), "BANK_B".to_string(), "BANK_C".to_string()];
        let mut generator = ArrivalGenerator::new(
            vec![("BANK_A".to_string(), config)]
                .into_iter()
                .collect(),
            all_agents,
        );
        let mut rng = RngManager::new(42);

        let arrivals = generator.generate_for_agent("BANK_A", 0, &mut rng);

        // Count selections
        let mut bank_b_count = 0;
        let mut bank_c_count = 0;

        for tx in arrivals {
            if tx.receiver_id() == "BANK_B" {
                bank_b_count += 1;
            } else if tx.receiver_id() == "BANK_C" {
                bank_c_count += 1;
            }
        }

        // BANK_B should be selected more often (not strict, probabilistic)
        // With 10:1 weight ratio, expect roughly 10x more BANK_B selections
        assert!(bank_b_count > 0);
        assert!(bank_b_count > bank_c_count);
    }
}
