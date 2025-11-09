//! LSM (Liquidity-Saving Mechanisms) Module
//!
//! Implements T2 RTGS-compliant liquidity optimization through:
//! - Bilateral offsetting (A↔B payment netting with unequal amounts)
//! - Multilateral cycle settlement (A→B→C→A with unequal payment values)
//! - Two-phase atomic settlement ensuring all-or-nothing execution
//!
//! # Overview
//!
//! LSMs reduce liquidity requirements by settling net positions instead of gross flows.
//! From game_concept_doc.md Section 4.3:
//! > "LSM/optimisation tries offsetting and multilateral cycles/batches to release
//! > queued items with minimal net liquidity."
//!
//! # T2-Compliant Behavior
//!
//! This implementation follows T2 RTGS specifications:
//! - Supports **unequal payment values** in cycles (partial netting)
//! - Each payment settles at **full value** or not at all (no transaction splitting)
//! - Each participant must cover their **net position** (not the minimum amount)
//! - Uses **two-phase commit** for atomic all-or-nothing execution
//!
//! # Example: Bilateral Offsetting
//!
//! ```rust
//! // A owes B 500k, B owes A 300k
//! // Without LSM: Need 800k total liquidity
//! // With LSM: Net 200k (A→B), settles BOTH transactions simultaneously
//! //   - A needs 200k to cover net outflow
//! //   - B needs 0 (net inflow)
//! ```
//!
//! # Example: Cycle Settlement (Equal Amounts)
//!
//! ```rust
//! // A→B→C→A cycle, each 500k
//! // Net positions: A: 0, B: 0, C: 0 (all net zero)
//! // With LSM: Settles all 3 transactions (total value: 1.5M)
//! // Each bank needs 0 liquidity (net zero)
//! ```
//!
//! # Example: Cycle Settlement (Unequal Amounts - T2-Compliant)
//!
//! ```rust
//! // A→B (500k), B→C (800k), C→A (700k)
//! // Net positions:
//! //   A: -500k + 700k = +200k (net inflow)
//! //   B: +500k - 800k = -300k (net outflow, needs 300k liquidity)
//! //   C: +800k - 700k = +100k (net inflow)
//! // With LSM: If B has 300k available, settles ALL 3 transactions at full value
//! // Total settled value: 2M (not 500k minimum)
//! ```
//!
//! # Two-Phase Settlement Protocol
//!
//! 1. **Phase 1: Feasibility Check** (read-only, no state changes)
//!    - Calculate net positions for all participants
//!    - Verify conservation (sum of net positions = 0)
//!    - Check each net payer can cover their net outflow
//!
//! 2. **Phase 2: Atomic Settlement** (all-or-nothing)
//!    - Settle ALL transactions at FULL value
//!    - Update all agent balances atomically
//!    - If any step fails, entire cycle fails (rollback not needed due to Phase 1 check)

use crate::models::event::Event;
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

/// Information about a bilateral offset pair
#[derive(Debug, Clone, PartialEq)]
pub struct BilateralPair {
    pub agent_a: String,
    pub agent_b: String,
    pub txs_a_to_b: Vec<String>,
    pub txs_b_to_a: Vec<String>,
    pub amount_a_to_b: i64,
    pub amount_b_to_a: i64,
}

/// Result of bilateral offsetting pass
#[derive(Debug, Clone, PartialEq)]
pub struct BilateralOffsetResult {
    /// Number of bilateral pairs found
    pub pairs_found: usize,

    /// Total value offset (gross, not net)
    pub offset_value: i64,

    /// Number of transactions settled
    pub settlements_count: usize,

    /// Details of bilateral pairs that were offset
    pub offset_pairs: Vec<BilateralPair>,
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

    /// Value settled on cycle (T2-compliant: sum of all transaction values)
    pub settled_value: i64,

    /// Number of transactions affected
    pub transactions_affected: usize,

    /// Net positions for each agent in cycle (T2-compliant)
    /// Positive = net inflow, Negative = net outflow
    pub net_positions: HashMap<String, i64>,
}

/// LSM cycle event for persistence (Phase 4)
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct LsmCycleEvent {
    /// Tick when cycle was settled
    pub tick: usize,

    /// Day when cycle was settled
    pub day: usize,

    /// Type of cycle: "bilateral" or "multilateral"
    pub cycle_type: String,

    /// Number of agents in cycle (2 for bilateral, 3+ for multilateral)
    pub cycle_length: usize,

    /// Agent IDs in cycle order (e.g., [A, B, C, A])
    pub agents: Vec<String>,

    /// Transaction IDs in cycle order
    pub transactions: Vec<String>,

    /// Net value settled (after netting)
    pub settled_value: i64,

    /// Gross value (sum of all transaction amounts)
    pub total_value: i64,

    /// Individual transaction amounts in cycle order
    /// Used for detailed display of each payment in the cycle
    pub tx_amounts: Vec<i64>,

    /// Net positions for each agent in cycle
    /// Positive = net inflow, Negative = net outflow (used liquidity)
    /// Example: {"BANK_A": -200000, "BANK_B": 100000, "BANK_C": 100000}
    pub net_positions: HashMap<String, i64>,

    /// Maximum net outflow in cycle (largest liquidity requirement)
    /// This is the actual liquidity used to settle the cycle
    pub max_net_outflow: i64,

    /// Agent ID that had the maximum net outflow
    /// This agent required the most liquidity to participate in the cycle
    pub max_net_outflow_agent: String,
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

    /// Detailed cycle events for persistence (Phase 4)
    pub cycle_events: Vec<LsmCycleEvent>,

    /// Events to be logged for replay (Event::LsmBilateralOffset, Event::LsmCycleSettlement)
    /// These are returned to the orchestrator which logs them to the event log
    pub replay_events: Vec<Event>,
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
pub fn bilateral_offset(state: &mut SimulationState, tick: usize) -> BilateralOffsetResult {
    let mut pairs_found = 0;
    let mut offset_value = 0i64;
    let mut settlements_count = 0;
    let mut offset_pairs = Vec::new();

    let lsm_debug = std::env::var("LSM_DEBUG").is_ok();

    // Build bilateral payment matrix: (sender, receiver) -> [tx_ids]
    // LSM operates ONLY on Queue 2 (RTGS central queue), not Queue 1 (banks' internal queues)
    let mut bilateral_map: HashMap<(String, String), Vec<String>> = HashMap::new();

    for tx_id in state.rtgs_queue() {
        if let Some(tx) = state.get_transaction(tx_id) {
            let sender = tx.sender_id().to_string();
            let receiver = tx.receiver_id().to_string();
            let key = (sender.clone(), receiver.clone());

            bilateral_map
                .entry(key)
                .or_insert_with(Vec::new)
                .push(tx_id.clone());
        }
    }

    // Find bilateral pairs and calculate net flows
    let mut processed_pairs: HashSet<(String, String)> = HashSet::new();

    for ((sender_a, receiver_b), txs_ab) in bilateral_map.iter() {
        // Check for reverse flow B→A
        let reverse_key = (receiver_b.clone(), sender_a.clone());

        // Skip if we already processed this pair (either direction)
        if processed_pairs.contains(&(sender_a.clone(), receiver_b.clone())) {
            if lsm_debug {
                eprintln!("[LSM DEBUG] Skipping already processed pair: {} ⇄ {}", sender_a, receiver_b);
            }
            continue;
        }

        if bilateral_map.contains_key(&reverse_key) && !processed_pairs.contains(&reverse_key) {
            // Found bilateral pair A↔B
            pairs_found += 1;
            processed_pairs.insert((sender_a.clone(), receiver_b.clone()));
            processed_pairs.insert(reverse_key.clone());

            if lsm_debug {
                eprintln!("[LSM DEBUG] Found bilateral pair: {} ⇄ {} ({} txs A→B, {} txs B→A)",
                    sender_a, receiver_b, txs_ab.len(), bilateral_map.get(&reverse_key).unwrap().len());
            }

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
                settlements_count +=
                    settle_bilateral_pair(state, txs_ab, txs_ba, offset_amount, tick);

                // Track this bilateral pair for event emission
                offset_pairs.push(BilateralPair {
                    agent_a: sender_a.clone(),
                    agent_b: receiver_b.clone(),
                    txs_a_to_b: txs_ab.clone(),
                    txs_b_to_a: txs_ba.clone(),
                    amount_a_to_b: sum_ab,
                    amount_b_to_a: sum_ba,
                });
            }
        }
    }

    BilateralOffsetResult {
        pairs_found,
        offset_value,
        settlements_count,
        offset_pairs,
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
    _offset_amount: i64, // Unused: we calculate net flows ourselves
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
        (
            tx_sample.sender_id().to_string(),
            tx_sample.receiver_id().to_string(),
        )
    } else {
        // Net flow is B→A (B will have net negative balance)
        let tx_sample = state.get_transaction(&txs_ba[0]).unwrap();
        (
            tx_sample.sender_id().to_string(),
            tx_sample.receiver_id().to_string(),
        )
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

            state
                .get_agent_mut(&sender_id)
                .unwrap()
                .adjust_balance(-(amount as i64));
            state
                .get_agent_mut(&receiver_id)
                .unwrap()
                .adjust_balance(amount as i64);
            state
                .get_transaction_mut(tx_id)
                .unwrap()
                .settle(amount, tick)
                .ok();

            // Remove from Queue 2 (RTGS queue)
            let lsm_debug = std::env::var("LSM_DEBUG").is_ok();
            if lsm_debug {
                eprintln!("[LSM DEBUG] Removing {} from queue", &tx_id[..8]);
            }
            state.rtgs_queue_mut().retain(|id| id != tx_id);

            settlements += 1;
        }
    }

    // Settle ALL transactions in B→A direction
    for tx_id in txs_ba {
        if let Some(tx) = state.get_transaction(tx_id) {
            let amount = tx.remaining_amount();
            let sender_id = tx.sender_id().to_string();
            let receiver_id = tx.receiver_id().to_string();

            state
                .get_agent_mut(&sender_id)
                .unwrap()
                .adjust_balance(-(amount as i64));
            state
                .get_agent_mut(&receiver_id)
                .unwrap()
                .adjust_balance(amount as i64);
            state
                .get_transaction_mut(tx_id)
                .unwrap()
                .settle(amount, tick)
                .ok();

            // Remove from Queue 2 (RTGS queue)
            let lsm_debug = std::env::var("LSM_DEBUG").is_ok();
            if lsm_debug {
                eprintln!("[LSM DEBUG] Removing {} from queue", &tx_id[..8]);
            }
            state.rtgs_queue_mut().retain(|id| id != tx_id);

            settlements += 1;
        }
    }

    settlements
}

// ============================================================================
// T2-Compliant LSM Helpers (Phase 1 & 2)
// ============================================================================

/// Calculate net position for each agent in a cycle (T2-compliant)
///
/// Net position = sum(incoming) - sum(outgoing) for each agent
/// - Positive = net inflow (agent receives more than sends)
/// - Negative = net outflow (agent sends more than receives, needs liquidity)
///
/// # Conservation Invariant
///
/// The sum of all net positions MUST equal zero (what flows out must flow in).
/// This is validated in `check_cycle_feasibility()`.
///
/// # Example
///
/// ```rust
/// // Cycle: A→B (500k), B→C (800k), C→A (700k)
/// // Net positions:
/// //   A: -500k + 700k = +200k (net inflow)
/// //   B: -800k + 500k = -300k (net outflow, needs 300k liquidity)
/// //   C: -700k + 800k = +100k (net inflow)
/// // Sum: +200k - 300k + 100k = 0 ✓
/// ```
fn calculate_cycle_net_positions(
    state: &SimulationState,
    cycle: &Cycle,
) -> HashMap<String, i64> {
    let mut net_positions: HashMap<String, i64> = HashMap::new();

    // Build flows from cycle transactions
    for tx_id in &cycle.transactions {
        if let Some(tx) = state.get_transaction(tx_id) {
            let sender = tx.sender_id();
            let receiver = tx.receiver_id();
            let amount = tx.remaining_amount();

            // Sender has outflow (negative)
            *net_positions.entry(sender.to_string()).or_insert(0) -= amount;
            // Receiver has inflow (positive)
            *net_positions.entry(receiver.to_string()).or_insert(0) += amount;
        }
    }

    net_positions
}

/// Error type for cycle feasibility checks
#[derive(Debug)]
enum CycleFeasibilityError {
    /// Sum of net positions doesn't equal zero (conservation violated)
    ConservationViolated { sum: i64 },
    /// Agent not found in state
    AgentNotFound { agent_id: String },
    /// Agent lacks liquidity to cover net outflow
    InsufficientLiquidity {
        agent_id: String,
        required: i64,
        available: i64,
    },
}

/// Check if cycle can settle given agent liquidity constraints (T2-compliant)
///
/// Returns Ok(()) if all agents with net outflow can cover it with balance + credit.
/// Returns Err with first blocking agent if any agent lacks sufficient liquidity.
///
/// # T2 Principle
///
/// "If any participant lacks liquidity for their net position, the entire cycle fails
/// and all transactions remain queued" - All-or-nothing atomicity
///
/// # Example
///
/// ```rust
/// // Agent B has net -300k outflow, 200k balance, 100k credit
/// // Available: 200k + 100k = 300k ✓ Can cover
/// //
/// // If B only had 250k available → Err(InsufficientLiquidity)
/// ```
fn check_cycle_feasibility(
    state: &SimulationState,
    _cycle: &Cycle,
    net_positions: &HashMap<String, i64>,
) -> Result<(), CycleFeasibilityError> {
    // Validate conservation (sum of net positions must be zero)
    let sum: i64 = net_positions.values().sum();
    if sum != 0 {
        return Err(CycleFeasibilityError::ConservationViolated { sum });
    }

    // Check each agent with net outflow can cover it
    for (agent_id, net_position) in net_positions {
        if *net_position < 0 {
            // Agent has net outflow - check liquidity
            let agent = state.get_agent(agent_id).ok_or_else(|| {
                CycleFeasibilityError::AgentNotFound {
                    agent_id: agent_id.clone(),
                }
            })?;

            let available_liquidity = agent.balance() + agent.credit_limit();
            let required_liquidity = net_position.abs();

            if available_liquidity < required_liquidity {
                return Err(CycleFeasibilityError::InsufficientLiquidity {
                    agent_id: agent_id.clone(),
                    required: required_liquidity,
                    available: available_liquidity,
                });
            }
        }
    }

    Ok(())
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
pub fn detect_cycles(state: &SimulationState, max_cycle_length: usize) -> Vec<Cycle> {
    // Build payment graph: agent -> [(neighbor, tx_id, amount)]
    // LSM operates ONLY on Queue 2 (RTGS central queue), not Queue 1 (banks' internal queues)
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
                find_cycles_from_start(
                    start_node, next_node, graph, path, visited, cycles, max_length,
                );
                path.pop();
            }
        }
    }

    // Unmark current node when backtracking
    visited.remove(current_node);
}

/// Settle a detected cycle (T2-compliant)
///
/// Implements T2 RTGS multilateral cycle settlement with unequal payment values.
/// Uses two-phase commit for atomic all-or-nothing execution.
///
/// # T2 Principles
///
/// 1. **No Partial Settlement**: Each payment settles in full or not at all
/// 2. **Unequal Values Supported**: Payments can have different amounts
/// 3. **Net Position Coverage**: Each agent must cover their net outflow with balance + credit
/// 4. **All-or-Nothing**: If any agent can't cover net, entire cycle fails
///
/// # Two-Phase Commit
///
/// **Phase 1 (Check)**: Calculate net positions and verify feasibility WITHOUT changing state
/// **Phase 2 (Execute)**: Settle ALL transactions at full value atomically
///
/// # Example
///
/// ```rust
/// // Cycle: A→B (500k), B→C (800k), C→A (700k)
/// // Net positions:
/// //   A: -500k + 700k = +200k (inflow)
/// //   B: -800k + 500k = -300k (outflow, needs 300k liquidity)
/// //   C: -700k + 800k = +100k (inflow)
/// //
/// // Phase 1: Check B has 300k available → ✓
/// // Phase 2: Settle ALL THREE at full value
/// //   Total settled: 2M (not 500k min)
/// //   Final balances: A=+200k, B=-300k, C=+100k
/// ```
pub fn settle_cycle(
    state: &mut SimulationState,
    cycle: &Cycle,
    tick: usize,
) -> Result<CycleSettlementResult, SettlementError> {
    // ========== PHASE 1: FEASIBILITY CHECK (No State Changes) ==========

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

    // Calculate net positions for all agents in cycle
    let net_positions = calculate_cycle_net_positions(state, cycle);

    // Check if cycle is feasible (all net outflows can be covered)
    match check_cycle_feasibility(state, cycle, &net_positions) {
        Err(CycleFeasibilityError::InsufficientLiquidity {
            agent_id: _,
            required,
            available,
        }) => {
            return Err(SettlementError::AgentError(
                crate::models::agent::AgentError::InsufficientLiquidity {
                    required,
                    available,
                },
            ));
        }
        Err(CycleFeasibilityError::ConservationViolated { sum }) => {
            return Err(SettlementError::AgentError(
                crate::models::agent::AgentError::InsufficientLiquidity {
                    required: sum.abs(),
                    available: 0,
                },
            ));
        }
        Err(CycleFeasibilityError::AgentNotFound { .. }) => {
            return Err(SettlementError::AgentError(
                crate::models::agent::AgentError::InsufficientLiquidity {
                    required: 0,
                    available: 0,
                },
            ));
        }
        Ok(()) => {
            // Feasibility check passed, proceed to Phase 2
        }
    }

    // ========== PHASE 2: ATOMIC SETTLEMENT (All or Nothing) ==========

    let mut transactions_affected = 0;
    let mut total_value = 0i64;

    // Settle EACH transaction at its FULL value (T2-compliant)
    for tx_id in &cycle.transactions {
        let tx = state.get_transaction(tx_id).unwrap();
        let sender_id = tx.sender_id().to_string();
        let receiver_id = tx.receiver_id().to_string();
        let amount = tx.remaining_amount(); // FULL amount, not min

        // Settle full transaction amount
        // Use adjust_balance to bypass liquidity checks (net positions already verified)
        state
            .get_agent_mut(&sender_id)
            .unwrap()
            .adjust_balance(-(amount as i64));
        state
            .get_agent_mut(&receiver_id)
            .unwrap()
            .adjust_balance(amount as i64);
        state
            .get_transaction_mut(tx_id)
            .unwrap()
            .settle(amount, tick)?;

        // Remove from Queue 2 (RTGS queue)
        state.rtgs_queue_mut().retain(|id| id != tx_id);

        transactions_affected += 1;
        total_value += amount;
    }

    Ok(CycleSettlementResult {
        cycle_length: cycle.agents.len() - 1,
        settled_value: total_value, // Sum of ALL transaction values (T2-compliant)
        transactions_affected,
        net_positions, // Include net positions for analysis
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
/// # let ticks_per_day = 100;
/// let config = LsmConfig::default();
/// let result = run_lsm_pass(&mut state, &config, current_tick, ticks_per_day);
///
/// println!("LSM settled {}k, {} iterations", result.total_settled_value / 1000, result.iterations_run);
/// ```
pub fn run_lsm_pass(
    state: &mut SimulationState,
    config: &LsmConfig,
    tick: usize,
    ticks_per_day: usize,
) -> LsmPassResult {
    let mut total_settled_value = 0i64;
    let mut iterations = 0;
    let mut bilateral_offsets = 0;
    let mut cycles_settled = 0;
    let mut cycle_events = Vec::new();
    let mut replay_events = Vec::new(); // Events to be logged by orchestrator
    const MAX_ITERATIONS: usize = 3;

    let lsm_debug = std::env::var("LSM_DEBUG").is_ok();

    // LSM operates ONLY on Queue 2 (RTGS central queue)
    // Track settled transactions to prevent duplicate cycle events across iterations
    let mut settled_tx_pairs: HashSet<(String, String)> = HashSet::new();

    while iterations < MAX_ITERATIONS && !state.rtgs_queue().is_empty() {
        iterations += 1;
        let settled_this_iteration = total_settled_value;

        // 1. Bilateral offsetting
        if config.enable_bilateral {
            let bilateral_result = bilateral_offset(state, tick);
            bilateral_offsets += bilateral_result.pairs_found;
            total_settled_value += bilateral_result.offset_value;

            // Create cycle events for each bilateral offset
            // BUT: Only create events for NEW pairs, not ones we've already processed in previous iterations
            let day = tick / ticks_per_day;
            if lsm_debug {
                eprintln!("[LSM DEBUG] Iteration {}: bilateral_offset returned {} pairs",
                    iterations, bilateral_result.offset_pairs.len());
            }
            for pair in &bilateral_result.offset_pairs {
                // Create a unique key for this bilateral pair (sorted to handle both directions)
                let pair_key = if pair.agent_a < pair.agent_b {
                    (pair.agent_a.clone(), pair.agent_b.clone())
                } else {
                    (pair.agent_b.clone(), pair.agent_a.clone())
                };

                // Skip if we've already created an event for this pair in a previous iteration
                if settled_tx_pairs.contains(&pair_key) {
                    if lsm_debug {
                        eprintln!("[LSM DEBUG] Skipping duplicate cycle event for {} ⇄ {} (already processed)",
                            pair.agent_a, pair.agent_b);
                    }
                    continue;
                }

                settled_tx_pairs.insert(pair_key);

                if lsm_debug {
                    eprintln!("[LSM DEBUG] Tick {}: Creating bilateral cycle event for {} ⇄ {}",
                        tick, pair.agent_a, pair.agent_b);
                }
                if lsm_debug {
                    eprintln!("[LSM DEBUG] Cycle event for: {} ⇄ {}", pair.agent_a, pair.agent_b);
                }
                let mut transactions = Vec::new();
                let mut tx_amounts = Vec::new();

                // Collect individual transaction amounts for A→B
                for tx_id in &pair.txs_a_to_b {
                    if let Some(tx) = state.get_transaction(tx_id) {
                        transactions.push(tx_id.clone());
                        tx_amounts.push(tx.amount());
                    }
                }

                // Collect individual transaction amounts for B→A
                for tx_id in &pair.txs_b_to_a {
                    if let Some(tx) = state.get_transaction(tx_id) {
                        transactions.push(tx_id.clone());
                        tx_amounts.push(tx.amount());
                    }
                }

                let agents = vec![pair.agent_a.clone(), pair.agent_b.clone(), pair.agent_a.clone()];
                let offset_amount = pair.amount_a_to_b.min(pair.amount_b_to_a);

                // Calculate net positions for bilateral offset
                let mut net_positions = HashMap::new();
                let net_a = pair.amount_b_to_a as i64 - pair.amount_a_to_b as i64;
                let net_b = pair.amount_a_to_b as i64 - pair.amount_b_to_a as i64;
                net_positions.insert(pair.agent_a.clone(), net_a);
                net_positions.insert(pair.agent_b.clone(), net_b);

                // Calculate max net outflow and identify agent
                let (max_net_outflow, max_net_outflow_agent) = if net_a.abs() >= net_b.abs() {
                    (net_a.abs(), pair.agent_a.clone())
                } else {
                    (net_b.abs(), pair.agent_b.clone())
                };

                // Collect Event::LsmBilateralOffset for replay with ALL enriched fields
                // This enables replay to reconstruct LSM activity from persisted events
                replay_events.push(Event::LsmBilateralOffset {
                    tick,
                    agent_a: pair.agent_a.clone(),
                    agent_b: pair.agent_b.clone(),
                    amount_a: pair.amount_a_to_b,
                    amount_b: pair.amount_b_to_a,
                    tx_ids: transactions.clone(),  // Use full transaction list
                });

                cycle_events.push(LsmCycleEvent {
                    tick,
                    day,
                    cycle_type: "bilateral".to_string(),
                    cycle_length: 2,
                    agents,
                    transactions,  // Can move now since we cloned for replay_events above
                    settled_value: offset_amount,
                    total_value: pair.amount_a_to_b + pair.amount_b_to_a,
                    tx_amounts,
                    net_positions,
                    max_net_outflow,
                    max_net_outflow_agent,
                });
            }

            // Retry queue processing after bilateral settlements
            if bilateral_result.settlements_count > 0 {
                let queue_result = process_queue(state, tick);
                total_settled_value += queue_result.settled_value;
            }
        }

        // 2. Cycle detection and settlement
        if config.enable_cycles && !state.rtgs_queue().is_empty() {
            let cycles = detect_cycles(state, config.max_cycle_length);

            if lsm_debug && !cycles.is_empty() {
                eprintln!("[LSM DEBUG] Tick {}: Detected {} cycles (before filtering)", tick, cycles.len());
            }

            // Filter out 2-agent "cycles" which are actually bilateral pairs
            // These should be handled by bilateral offset, not multilateral cycle detection
            let cycles: Vec<_> = cycles.into_iter()
                .filter(|cycle| {
                    // A true cycle has at least 3 unique agents
                    // (agents vec has duplicate of first agent at end, so length > 3 means 3+ unique agents)
                    let is_multilateral = cycle.agents.len() > 3;
                    if !is_multilateral && lsm_debug {
                        eprintln!("[LSM DEBUG] Filtering out 2-agent cycle {} ⇄ {} (should be handled by bilateral offset)",
                            cycle.agents.get(0).unwrap_or(&"?".to_string()),
                            cycle.agents.get(1).unwrap_or(&"?".to_string()));
                    }
                    is_multilateral
                })
                .collect();

            if lsm_debug && !cycles.is_empty() {
                eprintln!("[LSM DEBUG] Tick {}: Processing {} cycles (after filtering 2-agent pairs)", tick, cycles.len());
            }

            for cycle in cycles.iter().take(config.max_cycles_per_tick) {
                if let Ok(result) = settle_cycle(state, cycle, tick) {
                    total_settled_value += result.settled_value;
                    cycles_settled += 1;

                    // Capture cycle event for persistence (Phase 4.2)
                    let day = tick / ticks_per_day;
                    let cycle_length = cycle.agents.len().saturating_sub(1); // Exclude duplicate agent
                    let cycle_type = if cycle_length == 2 {
                        "bilateral".to_string()
                    } else {
                        "multilateral".to_string()
                    };

                    // Build tx_amounts vector from cycle transactions
                    let tx_amounts: Vec<i64> = cycle.transactions.iter()
                        .filter_map(|tx_id| state.get_transaction(tx_id))
                        .map(|tx| tx.amount())
                        .collect();

                    // Calculate max net outflow from net_positions
                    let max_net_outflow = result.net_positions.values()
                        .filter(|&&v| v < 0)
                        .map(|v| v.abs())
                        .max()
                        .unwrap_or(0);

                    // Find agent with max net outflow
                    let max_net_outflow_agent = result.net_positions.iter()
                        .filter(|(_, &v)| v < 0)
                        .max_by_key(|(_, v)| v.abs())
                        .map(|(agent, _)| agent.clone())
                        .unwrap_or_default();

                    // Convert net_positions HashMap to Vec in agent order
                    let net_positions_vec: Vec<i64> = cycle.agents.iter()
                        .filter_map(|agent| result.net_positions.get(agent).copied())
                        .collect();

                    // Collect Event::LsmCycleSettlement for replay with ALL enriched fields first
                    // This enables replay to reconstruct LSM cycle activity from persisted events
                    replay_events.push(Event::LsmCycleSettlement {
                        tick,
                        agents: cycle.agents.clone(),
                        tx_amounts: tx_amounts.clone(),
                        total_value: cycle.total_value,
                        net_positions: net_positions_vec,
                        max_net_outflow,
                        max_net_outflow_agent: max_net_outflow_agent.clone(),
                        tx_ids: cycle.transactions.clone(),
                    });

                    let event = LsmCycleEvent {
                        tick,
                        day,
                        cycle_type,
                        cycle_length,
                        agents: cycle.agents.clone(),
                        transactions: cycle.transactions.clone(),
                        settled_value: result.settled_value,
                        total_value: cycle.total_value,
                        tx_amounts,  // Can move now since we cloned for replay_events above
                        net_positions: result.net_positions.clone(),
                        max_net_outflow,
                        max_net_outflow_agent,
                    };

                    if lsm_debug {
                        eprintln!("[LSM DEBUG] Tick {}: Creating multilateral cycle event with {} agents",
                            tick, cycle_length);
                    }

                    cycle_events.push(event);
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
        cycle_events,
        replay_events,
    }
}
