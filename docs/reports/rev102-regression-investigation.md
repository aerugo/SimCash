# Rev 102 Regression Investigation: exp2 v2 Game Stuck at 0.5

**Date:** 2026-02-21  
**Investigator:** Nash (subagent)  
**Symptom:** Both agents stuck at initial_liquidity_fraction=0.5 for all 25 rounds; many `accepted=False`  
**Working rev:** 101 (BANK_A moved 0.5→0.25)  
**Broken rev:** 102

---

## Root Cause

**Phase 2 Prompt Anatomy (commit `c8b2424f`) introduced an unconditional prompt rebuild that corrupts the user prompt sent to the LLM.**

### What Changed Between Rev 101 and Rev 102

Commits beyond rev 101's `406e127c`:

| Commit | Description |
|--------|-------------|
| `c8b2424f` | **Phase 2: Prompt Profiles** — added prompt rebuild logic ⚠️ ROOT CAUSE |
| `10bc5eb9` | Phase 3: Prompt Explorer UI (frontend only, harmless) |
| `b57ddad2` | Phase 4: Smart default suggestions (frontend only, harmless) |
| `728a69ad` | Wire `_store_prompt` into /auto path (2-line fix, harmless) |

Phase 1 (`ba1be0d5`, already in both revs) only added data collection — it stored the original prompts without modifying them.

### The Bug: Unconditional Prompt Rebuild

In `web/backend/app/streaming_optimizer.py`, Phase 2 added a "rebuild prompts from enabled blocks" section (around line 286) that runs **unconditionally** — even when no prompt profile is configured:

```python
# Rebuild prompts from enabled blocks only
enabled_system_blocks = [b for b in blocks if b.category == "system" and b.enabled]
enabled_user_blocks = [b for b in blocks if b.category == "user" and b.enabled]

if enabled_system_blocks:
    system_prompt = "\n\n".join(b.content for b in enabled_system_blocks)

if enabled_user_blocks:
    user_prompt_parts = [b.content for b in enabled_user_blocks]
    user_prompt_parts.append(f"\nCurrent policy:\n{json.dumps(current_policy, indent=2)}")
    user_prompt_parts.append("\nGenerate an improved policy...\nOutput ONLY the JSON policy, no explanation.")
    user_prompt = "\n\n".join(user_prompt_parts)
```

Since all blocks are enabled by default and no prompt profile disables any, `enabled_user_blocks` is always non-empty, so the prompt is **always rebuilt**.

### How the Rebuilt Prompt Differs

**Original prompt (rev 101):**
```
{build_single_agent_context() → SingleAgentContextBuilder.build()}
{UserPromptBuilder policy_section}
Current policy: {json}
Generate an improved policy...Output ONLY the JSON policy, no explanation.
```

**Rebuilt prompt (rev 102):**
```
{block: usr_header}
{block: usr_current_state}
{block: usr_cost_analysis}
{block: usr_optimization_guidance}
{block: usr_simulation_trace}
{block: usr_iteration_history}
{block: usr_parameter_trajectories}
{block: usr_final_instructions}        ← Detailed output requirements
{block: usr_policy_section}            ← Policy section from UserPromptBuilder
Current policy: {json}                 ← DUPLICATE policy info
Output ONLY the JSON policy...         ← CONFLICTING with usr_final_instructions
```

**Two problems:**

1. **Duplicate policy information** — The policy JSON appears in the `usr_policy_section` block AND is appended again by the rebuild. The `usr_current_state` block also includes parameter values.

2. **Conflicting output instructions** — The `usr_final_instructions` block gives detailed instructions ("Generate a complete, valid policy JSON that defines all parameters, uses only allowed fields, includes unique node_id, wraps arithmetic in compute blocks...") while the appended instruction tersely says "Output ONLY the JSON policy, no explanation." The GLM-4.7-maas model, which is less robust than GPT/Claude, may get confused by contradictory directives.

### Why This Causes 100% Failure

The conflicting/duplicate prompt structure causes GLM-4.7-maas to produce responses that fail JSON parsing or constraint validation. When validation fails for all retries (MAX_VALIDATION_RETRIES), the optimizer yields `accepted=False` and `new_fraction=None`, keeping the old fraction.

Additionally, the `was_accepted` inference in the iteration history builder (line 139-148) marks rounds where fraction didn't change as "rejected". This feeds back into subsequent prompts as increasingly alarming warnings ("N previous policy attempts were REJECTED"), creating a **cascade effect** where the LLM becomes ultra-conservative and keeps proposing 0.5.

### Why Cloud Run Logs Don't Show Errors

The parse/validation failures are handled within the retry loop in `stream_optimize()`. Failures are logged at WARNING level with `logger.warning("Parse error for %s...")` but the Cloud Run log query didn't surface them (possibly due to log retention or query timing). The final `accepted=False` result is returned as a normal "result" event, not an "error" event.

---

## Fix

**Option A (minimal, recommended):** Guard the rebuild to only run when a prompt profile is active:

```python
# Only rebuild if a profile was explicitly applied
if prompt_profile:
    # Rebuild prompts from enabled blocks only
    enabled_system_blocks = [b for b in blocks if b.category == "system" and b.enabled]
    enabled_user_blocks = [b for b in blocks if b.category == "user" and b.enabled]
    
    if enabled_system_blocks:
        system_prompt = "\n\n".join(b.content for b in enabled_system_blocks)
    
    if enabled_user_blocks:
        user_prompt_parts = [b.content for b in enabled_user_blocks]
        # Don't append duplicate policy/instructions — they're already in blocks
        user_prompt = "\n\n".join(user_prompt_parts)
```

**Option B (thorough):** Even when rebuilding with a profile, don't append the duplicate policy JSON and conflicting instruction — the `usr_policy_section` and `usr_final_instructions` blocks already cover this.

---

## Verification Plan

1. Apply fix
2. Run exp2 v2 locally with GLM-4.7-maas
3. Verify BANK_A fraction changes from 0.5 within first few rounds
4. Deploy as rev 103 and re-run exp2 on Cloud Run
