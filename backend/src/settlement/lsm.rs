//! LSM (Liquidity-Saving Mechanisms) Module
//!
//! Implements T2-style liquidity optimization through:
//! - Bilateral offsetting (A↔B payment netting)
//! - Cycle detection (A→B→C→A circular dependencies)
//! - Coordinated optimization passes
//!
//! # Overview
//!
//! LSMs reduce liquidity requirements by settling net positions instead of gross flows.
//! From game_concept_doc.md Section 4.3:
//! > "LSM/optimisation tries offsetting and multilateral cycles/batches to release
//! > queued items with minimal net liquidity."
//!
//! # Example: Bilateral Offsetting
//!
//! ```rust
//! // A owes B 500k, B owes A 300k
//! // Without LSM: Need 800k total liquidity
//! // With LSM: Net 200k (A→B), saves 300k liquidity
//! ```
//!
//! # Example: Cycle Settlement
//!
//! ```rust
//! // A→B→C→A cycle, each 500k
//! // Without LSM: Need 500k per bank (1.5M total)
//! // With LSM: Net zero per bank, settles with existing balances
//! ```

use crate::models::state::SimulationState;
use crate::settlement::rtgs::{process_queue, SettlementError};
use std::collections::{HashMap, HashSet};

// ============================================================================
// Configuration Types
// ============================================================================

/// Configuration for LSM optimization behavior
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct LsmConfig {
    /// Enable bilateral offsetting (A↔B netting)
    pub enable_bilateral: bool,

    /// Enable cycle detection and settlement
    pub enable_cycles: bool,

    /// Maximum cycle length to detect (3-5 typical)
    pub max_cycle_length: usize,

    /// Maximum cycles to settle per tick (performance limit)
    pub max_cycles_per_tick: usize,
}

impl Default for LsmConfig {
    fn default() -> Self {
        Self {
            enable_bilateral: true,
            enable_cycles: true,
            max_cycle_length: 4,
            max_cycles_per_tick: 10,
        }
    }
}

// ============================================================================
// Result Types
// ============================================================================

/// Result of bilateral offsetting pass
#[derive(Debug, Clone, PartialEq)]
pub struct BilateralOffsetResult {
    /// Number of bilateral pairs found
    pub pairs_found: usize,

    /// Total value offset (gross, not net)
    pub offset_value: i64,

    /// Number of transactions settled
    pub settlements_count: usize,
}

/// Represents a detected payment cycle
#[derive(Debug, Clone)]
pub struct Cycle {
    /// Agent IDs in cycle order (e.g., [A, B, C, A])
    pub agents: Vec<String>,

    /// Transaction IDs in cycle order
    pub transactions: Vec<String>,

    /// Minimum amount on cycle (bottleneck)
    pub min_amount: i64,

    /// Total value of all transactions in cycle
    pub total_value: i64,
}

/// Result of settling a single cycle
#[derive(Debug, Clone, PartialEq)]
pub struct CycleSettlementResult {
    /// Length of cycle settled
    pub cycle_length: usize,

    /// Value settled on cycle
    pub settled_value: i64,

    /// Number of transactions affected
    pub transactions_affected: usize,
}

/// Result of complete LSM pass
#[derive(Debug, Clone, PartialEq)]
pub struct LsmPassResult {
    /// Number of iterations run
    pub iterations_run: usize,

    /// Total value settled by LSM
    pub total_settled_value: i64,

    /// Queue size after LSM pass
    pub final_queue_size: usize,

    /// Number of bilateral offsets performed
    pub bilateral_offsets: usize,

    /// Number of cycles settled
    pub cycles_settled: usize,
}

// ============================================================================
// Bilateral Offsetting
// ============================================================================

/// Find and settle bilateral offsetting opportunities
///
/// Scans the queue for pairs of banks with mutual obligations (A→B and B→A)
/// and settles the net flow, reducing liquidity requirements.
///
/// # Algorithm
///
/// 1. Build bilateral payment matrix from queue
/// 2. For each pair (A,B), calculate sum(A→B) and sum(B→A)
/// 3. If both > 0, offset min(sum_AB, sum_BA)
/// 4. Settle in net direction only
///
/// # Example
///
/// ```rust
/// use payment_simulator_core_rs::{Agent, Transaction, SimulationState};
/// use payment_simulator_core_rs::settlement::lsm::bilateral_offset;
///
/// let agents = vec![
///     Agent::new("BANK_A".to_string(), 100_000, 0),
///     Agent::new("BANK_B".to_string(), 100_000, 0),
/// ];
/// let mut state = SimulationState::new(agents);
///
/// // A→B 500k (queued), B→A 300k (queued)
/// // Bilateral offset will settle both, net 200k A→B
/// ```
pub fn bilateral_offset(
    state: &mut SimulationState,
    tick: usize,
) -> BilateralOffsetResult {
    let mut pairs_found = 0;
    let mut offset_value = 0i64;
    let mut settlements_count = 0;

    // Build bilateral payment matrix: (sender, receiver) -> [tx_ids]
    let mut bilateral_map: HashMap<(String, String), Vec<String>> = HashMap::new();

    for tx_id in state.rtgs_queue() {
        if let Some(tx) = state.get_transaction(tx_id) {
            let sender = tx.sender_id().to_string();
            let receiver = tx.receiver_id().to_string();
            let key = (sender.clone(), receiver.clone());

            bilateral_map.entry(key).or_insert_with(Vec::new).push(tx_id.clone());
        }
    }

    // Find bilateral pairs and calculate net flows
    let mut processed_pairs: HashSet<(String, String)> = HashSet::new();

    for ((sender_a, receiver_b), txs_ab) in bilateral_map.iter() {
        // Check for reverse flow B→A
        let reverse_key = (receiver_b.clone(), sender_a.clone());

        if bilateral_map.contains_key(&reverse_key) && !processed_pairs.contains(&reverse_key) {
            // Found bilateral pair A↔B
            pairs_found += 1;
            processed_pairs.insert((sender_a.clone(), receiver_b.clone()));
            processed_pairs.insert(reverse_key.clone());

            // Calculate totals in each direction
            let sum_ab: i64 = txs_ab
                .iter()
                .filter_map(|id| state.get_transaction(id))
                .map(|tx| tx.remaining_amount())
                .sum();

            let txs_ba = bilateral_map.get(&reverse_key).unwrap();
            let sum_ba: i64 = txs_ba
                .iter()
                .filter_map(|id| state.get_transaction(id))
                .map(|tx| tx.remaining_amount())
                .sum();

            // Offset the minimum
            let offset_amount = sum_ab.min(sum_ba);
            offset_value += offset_amount;

            // Settle in both directions up to offset amount
            if offset_amount > 0 {
                settlements_count += settle_bilateral_pair(
                    state,
                    txs_ab,
                    txs_ba,
                    offset_amount,
                    tick,
                );
            }
        }
    }

    BilateralOffsetResult {
        pairs_found,
        offset_value,
        settlements_count,
    }
}

/// Helper: Settle bilateral pair up to offset amount
///
/// CRITICAL: Bilateral offsetting works by settling ALL transactions in BOTH directions,
/// but the offset amount represents how much is mutually cancelled out.
///
/// Example: A→B 500k, B→A 300k, offset=300k
/// - Settle B→A fully (300k): B-=300k, A+=300k
/// - Settle A→B fully (500k): A-=500k, B+=500k
/// - Net: A=-500k+300k=-200k, B=+500k-300k=+200k (net 200k flow A→B)
/// - Liquidity requirement: Only 200k net (not 500k + 300k = 800k gross)
fn settle_bilateral_pair(
    state: &mut SimulationState,
    txs_ab: &[String],
    txs_ba: &[String],
    _offset_amount: i64,  // Unused: we calculate net flows ourselves
    tick: usize,
) -> usize {
    let mut settlements = 0;

    // Calculate total amounts in each direction
    let sum_ab: i64 = txs_ab
        .iter()
        .filter_map(|id| state.get_transaction(id))
        .map(|tx| tx.remaining_amount())
        .sum();

    let sum_ba: i64 = txs_ba
        .iter()
        .filter_map(|id| state.get_transaction(id))
        .map(|tx| tx.remaining_amount())
        .sum();

    // Determine net direction and required liquidity
    let net_amount = (sum_ab - sum_ba).abs();

    // For bilateral offsetting, we need to check if the net flow can be covered
    // But we use adjust_balance which bypasses liquidity checks, so we need to
    // verify the agent won't violate credit limits AFTER the settlement
    let (net_sender, _net_receiver) = if sum_ab > sum_ba {
        // Net flow is A→B (A will have net negative balance)
        let tx_sample = state.get_transaction(&txs_ab[0]).unwrap();
        (tx_sample.sender_id().to_string(), tx_sample.receiver_id().to_string())
    } else {
        // Net flow is B→A (B will have net negative balance)
        let tx_sample = state.get_transaction(&txs_ba[0]).unwrap();
        (tx_sample.sender_id().to_string(), tx_sample.receiver_id().to_string())
    };

    // Check if net sender can handle the net negative balance (within credit limits)
    if let Some(sender) = state.get_agent(&net_sender) {
        let projected_balance = sender.balance() - net_amount;
        if projected_balance < -(sender.credit_limit() as i64) {
            // Would exceed credit limit even with offsetting
            return 0;
        }
    }

    // Settle ALL transactions in A→B direction
    for tx_id in txs_ab {
        if let Some(tx) = state.get_transaction(tx_id) {
            let amount = tx.remaining_amount();
            let sender_id = tx.sender_id().to_string();
            let receiver_id = tx.receiver_id().to_string();

            state.get_agent_mut(&sender_id).unwrap().adjust_balance(-(amount as i64));
            state.get_agent_mut(&receiver_id).unwrap().adjust_balance(amount as i64);
            state.get_transaction_mut(tx_id).unwrap().settle(amount, tick).ok();
            settlements += 1;
        }
    }

    // Settle ALL transactions in B→A direction
    for tx_id in txs_ba {
        if let Some(tx) = state.get_transaction(tx_id) {
            let amount = tx.remaining_amount();
            let sender_id = tx.sender_id().to_string();
            let receiver_id = tx.receiver_id().to_string();

            state.get_agent_mut(&sender_id).unwrap().adjust_balance(-(amount as i64));
            state.get_agent_mut(&receiver_id).unwrap().adjust_balance(amount as i64);
            state.get_transaction_mut(tx_id).unwrap().settle(amount, tick).ok();
            settlements += 1;
        }
    }

    settlements
}

// ============================================================================
// Cycle Detection
// ============================================================================

/// Detect payment cycles in the queue
///
/// Finds simple cycles (no repeated nodes except start/end) in the payment graph
/// represented by queued transactions.
///
/// # Algorithm
///
/// Uses DFS with path tracking to find cycles. Limits cycle length to prevent
/// exponential explosion.
///
/// # Example
///
/// ```rust
/// // Queue contains: A→B (500k), B→C (500k), C→A (500k)
/// // detect_cycles will find: Cycle([A,B,C,A], min=500k)
/// ```
pub fn detect_cycles(
    state: &SimulationState,
    max_cycle_length: usize,
) -> Vec<Cycle> {
    // Build payment graph: agent -> [(neighbor, tx_id, amount)]
    let mut graph: HashMap<String, Vec<(String, String, i64)>> = HashMap::new();

    for tx_id in state.rtgs_queue() {
        if let Some(tx) = state.get_transaction(tx_id) {
            let sender = tx.sender_id().to_string();
            let receiver = tx.receiver_id().to_string();
            let amount = tx.remaining_amount();

            graph
                .entry(sender)
                .or_insert_with(Vec::new)
                .push((receiver, tx_id.clone(), amount));
        }
    }

    let mut cycles = Vec::new();
    let mut visited_global: HashSet<String> = HashSet::new();

    // Try DFS from each node to find cycles starting at that node
    for start_node in graph.keys() {
        if visited_global.contains(start_node) {
            continue;
        }

        find_cycles_from_start(
            start_node,
            start_node,
            &graph,
            &mut Vec::new(), // path of (node, tx_id, amount) tuples
            &mut HashSet::new(),
            &mut cycles,
            max_cycle_length,
        );

        visited_global.insert(start_node.clone());
    }

    // Sort cycles by total value (descending)
    cycles.sort_by(|a, b| b.total_value.cmp(&a.total_value));

    cycles
}

/// DFS helper to find cycles starting from start_node, currently at current_node
fn find_cycles_from_start(
    start_node: &str,
    current_node: &str,
    graph: &HashMap<String, Vec<(String, String, i64)>>,
    path: &mut Vec<(String, String, i64)>, // edges taken so far: (destination_node, tx_id, amount)
    visited: &mut HashSet<String>,
    cycles: &mut Vec<Cycle>,
    max_length: usize,
) {
    // Don't explore paths longer than max_length
    if path.len() >= max_length {
        return;
    }

    // Mark current node as visited
    visited.insert(current_node.to_string());

    // Explore neighbors
    if let Some(neighbors) = graph.get(current_node) {
        for (next_node, tx_id, amount) in neighbors {
            if next_node == start_node && !path.is_empty() {
                // Found a cycle back to start!
                // Build cycle from start_node + path + closing edge
                let mut agents = vec![start_node.to_string()];
                let mut transactions = Vec::new();
                let mut min_amount = *amount;
                let mut total_value = *amount;

                for (node, tx, amt) in path.iter() {
                    agents.push(node.clone());
                    transactions.push(tx.clone());
                    min_amount = min_amount.min(*amt);
                    total_value += amt;
                }

                transactions.push(tx_id.clone());
                agents.push(start_node.to_string()); // Close the cycle

                cycles.push(Cycle {
                    agents,
                    transactions,
                    min_amount,
                    total_value,
                });
            } else if !visited.contains(next_node) {
                // Continue DFS
                path.push((next_node.clone(), tx_id.clone(), *amount));
                find_cycles_from_start(start_node, next_node, graph, path, visited, cycles, max_length);
                path.pop();
            }
        }
    }

    // Unmark current node when backtracking
    visited.remove(current_node);
}

/// Settle a detected cycle
///
/// Settles the minimum amount on the cycle, achieving net-zero balance changes
/// for all participants.
///
/// # Example
///
/// ```rust
/// // Cycle: A→B→C→A, amounts [500k, 600k, 700k]
/// // Settle min (500k) on cycle:
/// //   A: -500k + 500k = 0 (net)
/// //   B: -500k + 500k = 0
/// //   C: -500k + 500k = 0
/// ```
pub fn settle_cycle(
    state: &mut SimulationState,
    cycle: &Cycle,
    tick: usize,
) -> Result<CycleSettlementResult, SettlementError> {
    let settle_amount = cycle.min_amount;
    let mut transactions_affected = 0;

    // Validate all transactions still exist and are queued
    for tx_id in &cycle.transactions {
        if let Some(tx) = state.get_transaction(tx_id) {
            if tx.is_fully_settled() {
                return Err(SettlementError::AlreadySettled);
            }
        } else {
            return Err(SettlementError::AgentError(
                crate::models::agent::AgentError::InsufficientLiquidity {
                    required: 0,
                    available: 0,
                },
            ));
        }
    }

    // Settle each transaction in cycle
    // IMPORTANT: Use adjust_balance instead of debit/credit because cycle settlement
    // is net-zero - each agent sends and receives the same amount around the cycle
    for tx_id in &cycle.transactions {
        let tx = state.get_transaction(tx_id).unwrap();
        let sender_id = tx.sender_id().to_string();
        let receiver_id = tx.receiver_id().to_string();

        // Perform settlement (net-zero for cycle)
        // Use adjust_balance to bypass liquidity checks (flows cancel out)
        state.get_agent_mut(&sender_id).unwrap().adjust_balance(-(settle_amount as i64));
        state.get_agent_mut(&receiver_id).unwrap().adjust_balance(settle_amount as i64);
        state.get_transaction_mut(tx_id).unwrap().settle(settle_amount, tick)?;

        transactions_affected += 1;
    }

    Ok(CycleSettlementResult {
        cycle_length: cycle.agents.len() - 1,
        settled_value: settle_amount,
        transactions_affected,
    })
}

// ============================================================================
// LSM Coordinator
// ============================================================================

/// Run complete LSM optimization pass
///
/// Coordinates bilateral offsetting and cycle detection, with iterative
/// refinement until convergence or max iterations.
///
/// # Algorithm
///
/// 1. Run bilateral offsetting
/// 2. Retry basic queue processing (recycling may enable settlements)
/// 3. Run cycle detection and settlement
/// 4. Retry basic queue processing again
/// 5. Repeat until no progress or max iterations
///
/// # Example
///
/// ```no_run
/// use payment_simulator_core_rs::settlement::lsm::{run_lsm_pass, LsmConfig};
///
/// # let mut state = todo!();
/// # let current_tick = 5;
/// let config = LsmConfig::default();
/// let result = run_lsm_pass(&mut state, &config, current_tick);
///
/// println!("LSM settled {}k, {} iterations", result.total_settled_value / 1000, result.iterations_run);
/// ```
pub fn run_lsm_pass(
    state: &mut SimulationState,
    config: &LsmConfig,
    tick: usize,
) -> LsmPassResult {
    let mut total_settled_value = 0i64;
    let mut iterations = 0;
    let mut bilateral_offsets = 0;
    let mut cycles_settled = 0;
    const MAX_ITERATIONS: usize = 3;

    while iterations < MAX_ITERATIONS && !state.rtgs_queue().is_empty() {
        iterations += 1;
        let settled_this_iteration = total_settled_value;

        // 1. Bilateral offsetting
        if config.enable_bilateral {
            let bilateral_result = bilateral_offset(state, tick);
            bilateral_offsets += bilateral_result.pairs_found;
            total_settled_value += bilateral_result.offset_value;

            // Retry queue processing after bilateral settlements
            if bilateral_result.settlements_count > 0 {
                let queue_result = process_queue(state, tick);
                total_settled_value += queue_result.settled_value;
            }
        }

        // 2. Cycle detection and settlement
        if config.enable_cycles && !state.rtgs_queue().is_empty() {
            let cycles = detect_cycles(state, config.max_cycle_length);

            for cycle in cycles.iter().take(config.max_cycles_per_tick) {
                if let Ok(result) = settle_cycle(state, cycle, tick) {
                    total_settled_value += result.settled_value;
                    cycles_settled += 1;
                }
            }

            // Retry queue processing after cycle settlements
            if !cycles.is_empty() {
                let queue_result = process_queue(state, tick);
                total_settled_value += queue_result.settled_value;
            }
        }

        // 3. Check for progress
        if total_settled_value == settled_this_iteration {
            break; // No progress, stop iterating
        }
    }

    LsmPassResult {
        iterations_run: iterations,
        total_settled_value,
        final_queue_size: state.queue_size(),
        bilateral_offsets,
        cycles_settled,
    }
}
