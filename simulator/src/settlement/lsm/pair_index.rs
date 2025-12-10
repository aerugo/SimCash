//! Incremental Pair Index for Fast Bilateral Offsetting
//!
//! Phase 1 optimization: Maintains an incremental index of bilateral payment pairs
//! to eliminate O(N) queue rescans on every tick.
//!
//! Key features:
//! - Deterministic priority ordering via ReadyKey
//! - Incremental updates (O(1) per transaction add/remove)
//! - BTreeMap/BTreeSet for sorted iteration
//! - Single source of truth for bilateral pair state

use crate::models::state::SimulationState;
use std::collections::BTreeMap;
use std::collections::BTreeSet;

// ============================================================================
// ReadyKey - Deterministic Priority for Bilateral Pairs
// ============================================================================

/// Key for ready bilateral pairs with deterministic priority ordering
///
/// Priority order:
/// 1. Higher liquidity release first (min(sum_ab, sum_ba))
/// 2. Tie-break by agent IDs lexicographically (agent_a, agent_b) where a < b
///
/// # Example
///
/// ```
/// use payment_simulator_core_rs::settlement::lsm::pair_index::ReadyKey;
///
/// let key1 = ReadyKey::new(1000, "BANK_A", "BANK_B");  // release=1000
/// let key2 = ReadyKey::new(500, "BANK_A", "BANK_C");   // release=500
///
/// assert!(key1 < key2, "Higher release has higher priority");
/// ```
#[derive(Debug, Clone, Eq, PartialEq)]
pub struct ReadyKey {
    /// Negative liquidity release for max-heap behavior in BTreeSet
    /// (BTreeSet is min-heap, so we negate to get max-heap)
    neg_liquidity: i64,

    /// First agent (lexicographically smaller)
    agent_a: String,

    /// Second agent (lexicographically larger)
    agent_b: String,
}

impl ReadyKey {
    /// Create new ReadyKey with automatic canonicalization (agent_a < agent_b)
    pub fn new(liquidity_release: i64, agent_x: &str, agent_y: &str) -> Self {
        let (agent_a, agent_b) = if agent_x < agent_y {
            (agent_x.to_string(), agent_y.to_string())
        } else {
            (agent_y.to_string(), agent_x.to_string())
        };

        Self {
            neg_liquidity: -liquidity_release,
            agent_a,
            agent_b,
        }
    }

    pub fn agent_a(&self) -> &str {
        &self.agent_a
    }

    pub fn agent_b(&self) -> &str {
        &self.agent_b
    }

    pub fn liquidity_release(&self) -> i64 {
        -self.neg_liquidity
    }
}

impl Ord for ReadyKey {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        // Primary: neg_liquidity (lower = higher priority due to negation)
        self.neg_liquidity
            .cmp(&other.neg_liquidity)
            // Secondary: agent_a lexicographic
            .then(self.agent_a.cmp(&other.agent_a))
            // Tertiary: agent_b lexicographic
            .then(self.agent_b.cmp(&other.agent_b))
    }
}

impl PartialOrd for ReadyKey {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

// ============================================================================
// PairBucket - Transactions in One Direction
// ============================================================================

/// Bucket of transactions flowing in one direction (sender → receiver)
#[derive(Debug, Clone)]
struct PairBucket {
    /// Sum of all transaction amounts in this direction
    sum: i64,

    /// Transaction IDs in enqueue order
    tx_ids: Vec<String>,
}

impl PairBucket {
    fn new() -> Self {
        Self {
            sum: 0,
            tx_ids: Vec::new(),
        }
    }

    fn add(&mut self, tx_id: &str, amount: i64) {
        self.sum = self.sum.saturating_add(amount);
        self.tx_ids.push(tx_id.to_string());
    }

    fn remove(&mut self, tx_id: &str, amount: i64) {
        self.sum = self.sum.saturating_sub(amount);
        self.tx_ids.retain(|id| id != tx_id);
    }

    #[allow(dead_code)] // Utility method for future use
    fn clear(&mut self) {
        self.sum = 0;
        self.tx_ids.clear();
    }

    fn is_empty(&self) -> bool {
        self.sum == 0 && self.tx_ids.is_empty()
    }
}

// ============================================================================
// PairIndex - Incremental Bilateral Pair Index
// ============================================================================

/// Incremental index for bilateral payment pairs
///
/// Maintains:
/// - Flow sums and transaction lists for each (sender, receiver) pair
/// - Ready set of bilateral pairs (both directions have flow)
/// - Deterministic priority ordering for pair selection
///
/// # Performance
///
/// - add_transaction: O(log N) for BTreeMap update
/// - remove_transaction: O(log N)
/// - pop_ready: O(log N)
/// - No O(queue_size) scans required
///
/// # Example
///
/// ```
/// use payment_simulator_core_rs::settlement::lsm::pair_index::PairIndex;
///
/// let mut index = PairIndex::new();
///
/// // Add unilateral flow A→B
/// index.add_transaction("tx1", "BANK_A", "BANK_B", 100_000);
/// assert_eq!(index.ready_count(), 0); // Not ready yet
///
/// // Add reverse flow B→A (creates bilateral pair)
/// index.add_transaction("tx2", "BANK_B", "BANK_A", 50_000);
/// assert_eq!(index.ready_count(), 1); // Now ready!
///
/// // Pop highest priority pair
/// let key = index.pop_ready().unwrap();
/// assert_eq!(key.liquidity_release(), 50_000); // min(100k, 50k)
/// ```
#[derive(Debug)]
pub struct PairIndex {
    /// Adjacency: sender → receiver → bucket
    /// Uses BTreeMap for deterministic iteration
    adj: BTreeMap<String, BTreeMap<String, PairBucket>>,

    /// Ready pairs (both directions have flow), sorted by priority
    /// Uses BTreeSet for deterministic pop order
    ready: BTreeSet<ReadyKey>,
}

impl PairIndex {
    /// Create new empty index
    pub fn new() -> Self {
        Self {
            adj: BTreeMap::new(),
            ready: BTreeSet::new(),
        }
    }

    /// Build index from current queue state
    pub fn from_queue(state: &SimulationState) -> Self {
        let mut index = Self::new();

        for tx_id in state.rtgs_queue() {
            if let Some(tx) = state.get_transaction(tx_id) {
                let sender = tx.sender_id();
                let receiver = tx.receiver_id();
                let amount = tx.remaining_amount();

                index.add_transaction(tx_id, sender, receiver, amount);
            }
        }

        index
    }

    /// Add transaction to index, updating ready set if needed
    pub fn add_transaction(&mut self, tx_id: &str, sender: &str, receiver: &str, amount: i64) {
        // Get or create bucket for this direction
        let bucket = self
            .adj
            .entry(sender.to_string())
            .or_insert_with(BTreeMap::new)
            .entry(receiver.to_string())
            .or_insert_with(PairBucket::new);

        bucket.add(tx_id, amount);

        // Check if this creates/updates a ready pair
        self.update_ready(sender, receiver);
    }

    /// Remove transaction from index, updating ready set if needed
    pub fn remove_transaction(&mut self, tx_id: &str, sender: &str, receiver: &str, amount: i64) {
        if let Some(receivers) = self.adj.get_mut(sender) {
            if let Some(bucket) = receivers.get_mut(receiver) {
                bucket.remove(tx_id, amount);

                // Clean up empty buckets
                if bucket.is_empty() {
                    receivers.remove(receiver);
                }
            }

            // Clean up empty sender entries
            if receivers.is_empty() {
                self.adj.remove(sender);
            }
        }

        // Update ready set (may remove the pair if one direction is now empty)
        self.update_ready(sender, receiver);
    }

    /// Pop highest priority ready pair
    pub fn pop_ready(&mut self) -> Option<ReadyKey> {
        // BTreeSet::pop_first would be ideal, but it's nightly-only
        // Use iter().next() + remove instead
        let key = self.ready.iter().next().cloned()?;
        self.ready.remove(&key);
        Some(key)
    }

    /// Get sum of flows in one direction
    pub fn flow_sum(&self, sender: &str, receiver: &str) -> i64 {
        self.adj
            .get(sender)
            .and_then(|receivers| receivers.get(receiver))
            .map(|bucket| bucket.sum)
            .unwrap_or(0)
    }

    /// Get number of transactions in one direction
    pub fn transaction_count(&self, sender: &str, receiver: &str) -> usize {
        self.adj
            .get(sender)
            .and_then(|receivers| receivers.get(receiver))
            .map(|bucket| bucket.tx_ids.len())
            .unwrap_or(0)
    }

    /// Get transaction IDs for a ready pair (both directions)
    pub fn get_transactions(&self, key: &ReadyKey) -> (Vec<String>, Vec<String>) {
        let agent_a = key.agent_a();
        let agent_b = key.agent_b();

        let txs_ab = self
            .adj
            .get(agent_a)
            .and_then(|r| r.get(agent_b))
            .map(|b| b.tx_ids.clone())
            .unwrap_or_default();

        let txs_ba = self
            .adj
            .get(agent_b)
            .and_then(|r| r.get(agent_a))
            .map(|b| b.tx_ids.clone())
            .unwrap_or_default();

        (txs_ab, txs_ba)
    }

    /// Number of ready pairs
    pub fn ready_count(&self) -> usize {
        self.ready.len()
    }

    /// Check if there are any ready pairs
    pub fn has_ready_pairs(&self) -> bool {
        !self.ready.is_empty()
    }

    /// Update ready set for a pair (may add, update, or remove)
    fn update_ready(&mut self, agent_x: &str, agent_y: &str) {
        let sum_xy = self.flow_sum(agent_x, agent_y);
        let sum_yx = self.flow_sum(agent_y, agent_x);

        // Canonicalize agent order
        let (agent_a, agent_b) = if agent_x < agent_y {
            (agent_x, agent_y)
        } else {
            (agent_y, agent_x)
        };

        // Check if currently in ready set (need to remove old key first)
        // Create a temporary key to search
        if sum_xy > 0 && sum_yx > 0 {
            // Both directions have flow → should be in ready set

            // Remove old key with old priority (if exists)
            // We don't know the old priority, so we need to find and remove
            self.ready.retain(|k| {
                !(k.agent_a() == agent_a && k.agent_b() == agent_b)
            });

            // Add new key with current priority
            let liquidity_release = sum_xy.min(sum_yx);
            let new_key = ReadyKey::new(liquidity_release, agent_a, agent_b);
            self.ready.insert(new_key);
        } else {
            // One or both directions empty → remove from ready set
            self.ready.retain(|k| {
                !(k.agent_a() == agent_a && k.agent_b() == agent_b)
            });
        }
    }
}

impl Default for PairIndex {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Tests (module-level)
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ready_key_new_canonicalizes() {
        let key1 = ReadyKey::new(1000, "B", "A");
        let key2 = ReadyKey::new(1000, "A", "B");

        assert_eq!(key1.agent_a(), "A");
        assert_eq!(key1.agent_b(), "B");
        assert_eq!(key1, key2);
    }

    #[test]
    fn test_pair_bucket_add_remove() {
        let mut bucket = PairBucket::new();

        bucket.add("tx1", 1000);
        bucket.add("tx2", 2000);

        assert_eq!(bucket.sum, 3000);
        assert_eq!(bucket.tx_ids.len(), 2);

        bucket.remove("tx1", 1000);
        assert_eq!(bucket.sum, 2000);
        assert_eq!(bucket.tx_ids.len(), 1);
    }
}
