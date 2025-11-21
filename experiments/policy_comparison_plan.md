# Agent Policy Simulation Experiment Plan

## Research Question
How do different individual agent policies perform in a multi-agent payment system when all other agents maintain a cautious liquidity preservation strategy?

## Experimental Design

### Baseline Scenario
- **Config**: `examples/configs/suboptimal_policies_25day.yaml`
- **Duration**: 25 days (2,500 ticks @ 100 ticks/day)
- **Agents**: 4 banks with varying sizes and transaction patterns
- **Stress Events**: Multiple liquidity shocks with recovery mechanisms
- **Cost Structure**: High delay costs (0.00022 per tick per cent), moderate overdraft (0.5 bps/tick), cheap collateral (0.0005 bps/tick)

### Experimental Variables

#### Control Group (Baseline)
- BIG_BANK_A: cautious_liquidity_preserver
- BIG_BANK_B: cautious_liquidity_preserver
- SMALL_BANK_A: efficient_memory_adaptive
- SMALL_BANK_B: cautious_liquidity_preserver

#### Test Policies
1. **cautious_liquidity_preserver** - Ultra-conservative baseline (2.5x buffer)
2. **efficient_memory_adaptive** - Adaptive with stress memory
3. **efficient_proactive** - Modest buffer (1.2x) + strategic collateral
4. **aggressive_market_maker** - High-velocity + liberal credit
5. **balanced_cost_optimizer** - Balanced approach
6. **adaptive_liquidity_manager** - Sophisticated adaptive

### Experiment Matrix

We will run 4 agents × 6 policies = 24 simulation runs:

| Run ID | BIG_BANK_A | BIG_BANK_B | SMALL_BANK_A | SMALL_BANK_B | Description |
|--------|------------|------------|--------------|--------------|-------------|
| baseline | cautious | cautious | efficient_memory | cautious | Original config |
| A_cautious | cautious | cautious | efficient_memory | cautious | Control (same as baseline) |
| A_efficient_mem | efficient_memory | cautious | efficient_memory | cautious | Test memory-adaptive |
| A_efficient_pro | efficient_proactive | cautious | efficient_memory | cautious | Test proactive strategy |
| A_aggressive | aggressive_market_maker | cautious | efficient_memory | cautious | Test aggressive strategy |
| A_balanced | balanced_cost_optimizer | cautious | efficient_memory | cautious | Test balanced approach |
| A_adaptive | adaptive_liquidity_manager | cautious | efficient_memory | cautious | Test sophisticated adaptive |
| B_cautious | cautious | cautious | efficient_memory | cautious | Control |
| B_efficient_mem | cautious | efficient_memory | efficient_memory | cautious | Test memory-adaptive |
| B_efficient_pro | cautious | efficient_proactive | efficient_memory | cautious | Test proactive strategy |
| B_aggressive | cautious | aggressive_market_maker | efficient_memory | cautious | Test aggressive strategy |
| B_balanced | cautious | balanced_cost_optimizer | efficient_memory | cautious | Test balanced approach |
| B_adaptive | cautious | adaptive_liquidity_manager | efficient_memory | cautious | Test sophisticated adaptive |
| SA_cautious | cautious | cautious | cautious | cautious | All cautious baseline |
| SA_efficient_mem | cautious | cautious | efficient_memory | cautious | Baseline (same as original) |
| SA_efficient_pro | cautious | cautious | efficient_proactive | cautious | Test proactive on SMALL_BANK_A |
| SA_aggressive | cautious | cautious | aggressive_market_maker | cautious | Test aggressive on SMALL_BANK_A |
| SA_balanced | cautious | cautious | balanced_cost_optimizer | cautious | Test balanced on SMALL_BANK_A |
| SA_adaptive | cautious | cautious | adaptive_liquidity_manager | cautious | Test adaptive on SMALL_BANK_A |
| SB_cautious | cautious | cautious | efficient_memory | cautious | Baseline |
| SB_efficient_mem | cautious | cautious | efficient_memory | efficient_memory | Test memory-adaptive |
| SB_efficient_pro | cautious | cautious | efficient_memory | efficient_proactive | Test proactive strategy |
| SB_aggressive | cautious | cautious | efficient_memory | aggressive_market_maker | Test aggressive strategy |
| SB_balanced | cautious | cautious | efficient_memory | balanced_cost_optimizer | Test balanced approach |
| SB_adaptive | cautious | cautious | efficient_memory | adaptive_liquidity_manager | Test sophisticated adaptive |

### Metrics to Collect

For each simulation run, collect:

#### Per-Agent Metrics
1. **Total accumulated costs** (sum of all cost components)
2. **Cost breakdown**:
   - Delay costs
   - Overdraft costs
   - Collateral costs
   - Deadline penalty costs
   - Split friction costs
   - EOD penalties
3. **Operational metrics**:
   - Total transactions sent
   - Total transactions received
   - Settlement rate (%)
   - Average queue wait time
   - Max queue depth
   - Collateral usage (peak, average)
   - Credit usage (peak, average)
4. **Time-series data**:
   - Costs per tick
   - Balance over time
   - Queue depth over time

#### System-Wide Metrics
1. Overall settlement rate
2. Total system costs
3. LSM efficiency (bilateral vs cycle settlements)
4. Gridlock incidents

### Data Collection Strategy

1. Run each simulation with `--persist` flag to save to DuckDB
2. Extract per-tick cost data from `agent_tick_snapshots` table
3. Extract final metrics from `agent_final_states` table
4. Save summary statistics to scratchpad document
5. Generate comparative visualizations

### Analysis Plan

1. **Within-Agent Analysis**: Compare how each policy performs when used by each specific agent
2. **Cross-Agent Analysis**: Identify which agents benefit most from policy changes
3. **Cost Component Analysis**: Decompose which cost types dominate for each policy
4. **Temporal Analysis**: Identify how policies perform during stress vs normal periods
5. **Strategic Interaction**: Analyze if policy effectiveness depends on what other agents do

### Success Criteria

A policy is considered "better" if it achieves:
- Lower total accumulated costs (primary metric)
- Higher settlement rate (secondary metric)
- Lower variance in costs (stability metric)

### Deliverables

1. **Scratchpad document** with raw results and intermediate analysis
2. **Research report** with:
   - Executive summary
   - Methodology
   - Results and visualizations
   - Discussion of findings
   - Recommendations
   - Future research directions
