# Bootstrap Rejection Retry: Implementation Plan

**Date:** 2026-02-25  
**Status:** Plan  
**Context:** Currently, when bootstrap rejects a proposed policy, the agent doesn't get a second chance until the next day. This feature adds configurable multi-turn retries after bootstrap rejection.

---

## Design

### User-Facing Behavior

1. Agent proposes policy → passes validation → bootstrap evaluates
2. **If bootstrap rejects:** Agent sees full bootstrap results + rejection reason, is asked to revise
3. Agent responds with either:
   - A new policy JSON → goes back to bootstrap evaluation
   - The literal text `"False"` (or no JSON found) → agent declines to retry, day ends with old policy
4. Repeat up to `max_policy_proposals - 1` retries (default: 2 total proposals, so 1 retry)
5. **If bootstrap accepts:** Normal flow, day proceeds

### Configuration

New field in game settings:

```yaml
max_policy_proposals: 2  # default, means 1 initial + 1 retry
```

Valid range: 1-5. Setting to 1 = current behavior (no retries).

Exposed in:
- `GameSettingsPanel.tsx` (frontend)
- Game creation API / checkpoint
- Passed through to `_optimize_one` in `game.py`

### Key Constraint: True Multi-Turn Conversation

This is NOT "append error text to user prompt and re-run from scratch" (which is what validation retries currently do). The agent must see:

1. Its original reasoning + proposal (its own prior output)
2. The bootstrap evaluation results
3. A follow-up prompt asking it to revise

This requires **pydantic-ai's `message_history`** to maintain a real conversation.

---

## Implementation

### Layer 1: `streaming_optimizer.py` — New Retry-After-Bootstrap Flow

The current `stream_optimize()` yields `{"type": "result", "data": {...}}` as its final event. Bootstrap evaluation happens *outside* in `game.py`. This means the optimizer doesn't currently know about bootstrap outcomes.

**Change:** Add a new generator function that wraps `stream_optimize` and handles bootstrap retries:

```python
async def stream_optimize_with_retries(
    agent_id: str,
    current_policy: dict,
    last_day: GameDay,
    all_days: list,
    raw_yaml: dict,
    bootstrap_gate: BootstrapGate,
    max_proposals: int = 2,
    # ... existing kwargs
) -> AsyncIterator[dict]:
```

**Flow:**

```
proposal_num = 0
message_history = None

while proposal_num < max_proposals:
    proposal_num += 1
    
    if proposal_num == 1:
        # First proposal: normal stream_optimize
        async for event in stream_optimize(...):
            if event["type"] == "result":
                result = event["data"]
            else:
                yield event
    else:
        # Retry: multi-turn with bootstrap feedback
        async for event in _stream_retry_proposal(
            agent, retry_prompt, message_history, model_settings, agent_id
        ):
            if event["type"] == "result":
                result = event["data"]
            else:
                yield event
    
    # No policy proposed (parse failure, gave up, etc.)
    if not result.get("new_policy"):
        yield {"type": "result", "data": result}
        return
    
    # Run bootstrap
    bootstrap_result = bootstrap_gate.evaluate(agent_id, last_day, result)
    
    if bootstrap_result.get("accepted", True):
        # Accepted! Done.
        yield {"type": "result", "data": bootstrap_result}
        return
    
    # Rejected — can we retry?
    if proposal_num >= max_proposals:
        yield {"type": "bootstrap_rejected", ...}
        yield {"type": "result", "data": bootstrap_result}
        return
    
    # Build retry prompt with bootstrap feedback
    retry_prompt = _build_bootstrap_retry_prompt(bootstrap_result)
    # Capture message_history from the pydantic-ai run for multi-turn
    message_history = <from first run>
    
    yield {"type": "bootstrap_retry", "proposal": proposal_num, "max": max_proposals, ...}
```

### Layer 2: Multi-Turn via pydantic-ai `message_history`

pydantic-ai's `Agent.run()` and `Agent.run_stream()` both accept `message_history` and return it on the result. This gives us true multi-turn:

```python
# First call
async with agent.run_stream(user_prompt, model_settings=...) as stream:
    # ... collect response
    pass
first_messages = stream.all_messages()  # includes system, user, assistant

# Retry call — agent sees the full conversation
retry_result = await agent.run(
    retry_prompt,  # new user message with bootstrap feedback  
    message_history=first_messages,
    model_settings=...,
)
retry_messages = retry_result.all_messages()
```

The agent now sees:
1. **Turn 1 (user):** Original optimization prompt with simulation data
2. **Turn 1 (assistant):** Its own reasoning + policy proposal
3. **Turn 2 (user):** Bootstrap results + rejection reason + retry request
4. **Turn 2 (assistant):** Revised proposal (or "False")

This is a real conversation, not prompt-stuffing.

### Layer 3: The Retry Prompt

```python
def _build_bootstrap_retry_prompt(bootstrap_result: dict) -> str:
    """Build the follow-up prompt after bootstrap rejection."""
    bs = bootstrap_result["bootstrap"]
    reason = bootstrap_result["rejection_reason"]
    
    prompt = f"""--- BOOTSTRAP EVALUATION RESULTS ---

Your proposed policy was evaluated against your current policy using {bs['num_samples']} paired bootstrap samples.

**Result: REJECTED**
**Reason:** {reason}

### Evaluation Statistics
- Current policy mean cost: {bs['old_mean_cost']:,}
- Proposed policy mean cost: {bs['new_mean_cost']:,}  
- Mean cost delta: {bs['mean_delta']:,} (positive = proposed is cheaper)
- 95% CI: [{bs['ci_lower']:,}, {bs['ci_upper']:,}]
- Coefficient of variation: {bs['cv']:.4f}
"""
    
    # Add settlement info if available
    if 'mean_settlement' in bs:
        prompt += f"- Mean settlement rate: {bs['mean_settlement']:.1%}\n"
    
    prompt += f"""
### What This Means
{_explain_rejection(reason, bs)}

### Your Options
You may propose a revised policy that addresses the rejection reason above. 
Respond with either:
1. A new policy JSON block (will be evaluated again)
2. The word "False" if you prefer to keep your current policy

If proposing a new policy, consider what the evaluation statistics tell you about 
the direction and magnitude of change needed.
"""
    return prompt
```

### Layer 4: `game.py` Changes

In `_optimize_one()`, replace:

```python
# Current:
result = <from stream_optimize>
if result.get("new_policy"):
    result = self._run_real_bootstrap(aid, last_day, result)
```

With:

```python
# New:
async for event in stream_optimize_with_retries(
    aid, self.policies[aid], last_day, self.days, self.raw_yaml,
    bootstrap_gate=self.bootstrap_gate,
    max_proposals=self.max_policy_proposals,
    ...
):
    if event["type"] == "result":
        result = event["data"]
    elif event["type"] == "bootstrap_retry":
        await _send({"type": "bootstrap_retry", ...})
    else:
        # chunk, model_info, etc — forward as before
        await _send(event)
```

Bootstrap evaluation moves *inside* the optimizer loop instead of happening after.

### Layer 5: Frontend

New WebSocket event types to handle:

- `bootstrap_retry` — show "Policy rejected, agent retrying (2/2)..." in the optimization stream
- `bootstrap_rejected` — show final rejection with stats

The reasoning panel already shows rejection reasons. The main UI change is showing retry progress inline in the streaming output.

### Layer 6: Experiment Runner (`optimization.py`)

The experiment runner in `api/` has its own optimization loop. Add the same retry logic there for CLI experiments:

```python
# In OptimizationLoop._optimize_agent()
for proposal_num in range(max_proposals):
    if proposal_num == 0:
        response = await self.llm_client.optimize(...)
    else:
        response = await self.llm_client.retry_with_feedback(
            feedback_prompt, message_history=prev_messages
        )
    # ... parse, validate, bootstrap
    if accepted:
        break
    # Build feedback for next attempt
```

---

## What NOT to Change

- **Bootstrap gate logic** — untouched, it still returns accept/reject
- **Validation retries** — these stay as-is (prompt-stuffing is fine for "you wrote invalid JSON")
- **System prompt** — no changes needed, the retry prompt is a user-turn follow-up
- **Policy parsing** — reuse `_parse_policy_response()`, also handle `"False"` as decline

---

## Testing

1. **Unit test:** Mock bootstrap gate to reject first proposal, verify retry prompt is sent, verify "False" response is handled
2. **Unit test:** Verify `max_policy_proposals=1` gives current behavior
3. **Integration test:** Full flow with mock LLM — reject → retry → accept
4. **Integration test:** Full flow — reject → retry → reject → give up (max=2)
5. **Edge case:** Agent responds with "False" on first retry
6. **Edge case:** Agent's retry proposal also fails validation (validation retry + bootstrap retry interact)

---

## Migration

- Default `max_policy_proposals=2` for new games
- Existing games/checkpoints without the field default to `1` (backward compatible, no behavior change)
- Checkpoint serialization: add `max_policy_proposals` to game settings

---

## Cost Implications

Each retry = 1 additional LLM call per rejected agent per day. With `max_proposals=2`:
- Best case: 0 extra calls (all accepted on first try)
- Worst case: N_agents extra calls per day
- The retry call is cheaper than the original (shorter prompt — just bootstrap stats, no full simulation trace; conversation history handles context)

---

## Sequence Diagram

```
Agent          Optimizer           Bootstrap Gate       Frontend
  |                |                     |                  |
  |  proposal 1    |                     |                  |
  |<---------------|                     |                  |
  |  policy JSON   |                     |                  |
  |--------------->|                     |                  |
  |                |--- evaluate ------->|                  |
  |                |<-- REJECTED --------|                  |
  |                |                     |    "retry 1/1"   |
  |                |------------------------------------>---|
  |                |                     |                  |
  |  retry prompt  |                     |                  |
  |  (w/ history)  |                     |                  |
  |<---------------|                     |                  |
  |  revised JSON  |                     |                  |
  |  (or "False")  |                     |                  |
  |--------------->|                     |                  |
  |                |--- evaluate ------->|                  |
  |                |<-- ACCEPTED --------|                  |
  |                |                     |   "accepted"     |
  |                |------------------------------------>---|
```

---

## Files to Modify

| File | Change |
|------|--------|
| `web/backend/app/streaming_optimizer.py` | Add `stream_optimize_with_retries()`, `_build_bootstrap_retry_prompt()`, capture `message_history` from pydantic-ai |
| `web/backend/app/game.py` | Use `stream_optimize_with_retries()` instead of `stream_optimize()` + separate bootstrap; add `max_policy_proposals` to GameSession |
| `web/backend/app/bootstrap_gate.py` | No changes (used as-is) |
| `web/frontend/src/components/GameView.tsx` | Handle `bootstrap_retry` WS event |
| `web/frontend/src/components/GameSettingsPanel.tsx` | Add `max_policy_proposals` slider (1-5, default 2) |
| `api/payment_simulator/experiments/runner/optimization.py` | Add retry loop with `message_history` for CLI experiments |
| `api/payment_simulator/experiments/runner/llm_client.py` | Add `retry_with_feedback(prompt, message_history)` method |
