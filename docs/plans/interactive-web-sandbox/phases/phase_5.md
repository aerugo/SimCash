# Phase 5: LLM Agent Integration

**Status**: Pending
**Started**: —

## Objective

Wire GPT-5.2 into the simulation as an opt-in AI agent mode.

## Implementation Steps

### Step 5.1: Backend — LLM Toggle
- Add `use_llm_agents: bool` to ScenarioConfig
- When true, call `get_initial_decisions()` before first tick
- Apply returned `initial_liquidity_fraction` to each agent's opening balance
- Store LLM reasoning in SimulationInstance for display

### Step 5.2: Backend — LLM Decision Display
- Include LLM decisions in tick results: `llm_decisions` field
- Include reasoning text for display in frontend

### Step 5.3: Frontend — AI Toggle
- Checkbox on Home view: "Use AI Agents (GPT-5.2)"
- When enabled, show loading spinner during LLM calls
- Display reasoning in agent cards (expandable)

### Step 5.4: Error Handling
- Graceful fallback to FIFO on LLM errors
- Display warning when fallback is used
- Timeout after 120s

## Files

| File | Action |
|------|--------|
| `web/backend/app/simulation.py` | MODIFY — add LLM call before first tick |
| `web/backend/app/main.py` | MODIFY — async endpoint for LLM sims |
| `web/backend/app/models.py` | MODIFY — add use_llm_agents field |
| `src/views/HomeView.tsx` | MODIFY — add AI toggle |
| `src/components/AgentCards.tsx` | MODIFY — show LLM reasoning |

## Completion Criteria
- [ ] Can toggle AI agents on/off
- [ ] LLM makes liquidity decisions displayed in UI
- [ ] Graceful fallback on API errors
- [ ] Reasoning text shown in agent cards
