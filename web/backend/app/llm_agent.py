"""LLM-based agent reasoning for SimCash simulations.

Supports real OpenAI calls (GPT-5.2) and mock reasoning mode.
"""
from __future__ import annotations

import random
import time
from typing import Any


def generate_mock_reasoning(
    agent_id: str,
    tick: int,
    agent_state: dict[str, Any],
    scenario_context: dict[str, Any],
) -> dict[str, Any]:
    """Generate realistic mock reasoning traces for demo/testing."""
    if tick == 0:
        return _mock_liquidity_allocation(agent_id, agent_state, scenario_context)
    else:
        return _mock_payment_timing(agent_id, tick, agent_state, scenario_context)


def _mock_liquidity_allocation(
    agent_id: str,
    agent_state: dict[str, Any],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    pool = agent_state.get("available_liquidity", 100_000)
    pool_dollars = pool / 100

    templates = [
        {
            "reasoning": (
                f"As {agent_id}, I need to decide how much of my ${pool_dollars:,.0f} liquidity pool to allocate. "
                f"Looking at the payment schedule, I have outgoing obligations that require careful balancing. "
                f"The liquidity cost is {ctx.get('liquidity_cost_bps', 333)} bps per tick — allocating too much "
                f"wastes capital. But under-allocation risks deadline penalties of ${ctx.get('deadline_penalty', 50000)/100:,.0f} each. "
                f"The bilateral symmetry suggests my counterpart faces identical incentives — this is a coordination game. "
                f"Game-theoretic analysis: in a symmetric 2-player game, the Nash equilibrium allocation is typically "
                f"moderate (40-60%). I'll allocate ~{random.randint(45, 55)}% to balance the liquidity-penalty tradeoff."
            ),
            "reasoning_summary": (
                f"Allocating moderate liquidity ({random.randint(45, 55)}%) based on Nash equilibrium analysis. "
                f"Bilateral symmetry creates coordination incentives — neither player benefits from extreme allocation."
            ),
            "decision": f"Allocate {random.randint(45, 55)}% of liquidity pool",
        },
        {
            "reasoning": (
                f"I'm {agent_id} with a ${pool_dollars:,.0f} pool. The key tension: liquidity cost "
                f"({ctx.get('liquidity_cost_bps', 333)} bps/tick) vs deadline penalties "
                f"(${ctx.get('deadline_penalty', 50000)/100:,.0f}/tx). With deferred crediting active, "
                f"incoming payments won't be immediately available, so I need buffer liquidity. "
                f"My expected outflows exceed inflows in early ticks. Optimal strategy under incomplete "
                f"information: allocate enough to cover first-period obligations plus a safety margin. "
                f"Computing: expected outflow = ~${random.randint(150, 300):,}, so I need at least that much. "
                f"Adding 20% buffer for timing uncertainty. Decision: allocate {random.randint(50, 65)}%."
            ),
            "reasoning_summary": (
                f"Higher allocation ({random.randint(50, 65)}%) due to deferred crediting reducing incoming liquidity. "
                f"Buffer accounts for timing uncertainty in counterpart behavior."
            ),
            "decision": f"Allocate {random.randint(50, 65)}% of liquidity pool",
        },
        {
            "reasoning": (
                f"Strategic analysis for {agent_id}: This is fundamentally a prisoners' dilemma variant. "
                f"If both players allocate conservatively, both face deadline risk. If both allocate generously, "
                f"both pay excess liquidity costs. The dominant strategy depends on the cost ratio: "
                f"r_c={ctx.get('liquidity_cost_bps', 333)}bps vs penalty=${ctx.get('deadline_penalty', 50000)/100:,.0f}. "
                f"Since penalty >> liquidity cost, the risk-adjusted optimal is to slightly over-allocate. "
                f"Expected value calculation favors {random.randint(40, 50)}% allocation — the marginal cost of "
                f"extra liquidity is small compared to the expected penalty savings."
            ),
            "reasoning_summary": (
                f"Cost ratio analysis (penalty >> liquidity cost) favors slight over-allocation at ~{random.randint(40, 50)}%. "
                f"Dominant strategy in this prisoners' dilemma variant."
            ),
            "decision": f"Allocate {random.randint(40, 50)}% of liquidity pool",
        },
    ]

    choice = random.choice(templates)
    tokens_prompt = random.randint(400, 700)
    tokens_completion = random.randint(150, 350)

    return {
        "tick": 0,
        "agent_id": agent_id,
        "phase": "decided",
        "decision_type": "liquidity_allocation",
        "decision": choice["decision"],
        "reasoning": choice["reasoning"],
        "reasoning_summary": choice["reasoning_summary"],
        "prompt_tokens": tokens_prompt,
        "completion_tokens": tokens_completion,
    }


def _mock_payment_timing(
    agent_id: str,
    tick: int,
    agent_state: dict[str, Any],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    balance = agent_state.get("balance", 0)
    balance_dollars = balance / 100
    queue_size = agent_state.get("queue1_size", 0)

    decisions = ["Release", "Hold"]
    decision = random.choice(decisions) if queue_size > 0 else "Release"

    release_templates = [
        {
            "reasoning": (
                f"Tick {tick}: {agent_id} holds ${balance_dollars:,.0f} with {queue_size} payment(s) queued. "
                f"Delay cost accrues at {ctx.get('delay_cost', 0.2)}/cent/tick — holding is expensive. "
                f"My counterpart's behavior is uncertain, but the Nash equilibrium in this simultaneous-move "
                f"game favors releasing when delay costs exceed option value. Current delay cost per tick "
                f"exceeds the expected benefit of waiting for incoming offsets. "
                f"Decision: Release — the marginal delay cost outweighs strategic waiting value."
            ),
            "reasoning_summary": (
                f"Releasing payments — delay cost per tick exceeds option value of waiting. "
                f"Nash equilibrium favors simultaneous release."
            ),
        },
        {
            "reasoning": (
                f"At tick {tick}, I ({agent_id}) have ${balance_dollars:,.0f} available. Queue has {queue_size} pending payment(s). "
                f"Analyzing counterpart incentives: they face symmetric costs, so rational play is to release. "
                f"If I release now and they release simultaneously, both settle optimally. "
                f"If I hold and they release, I benefit from incoming liquidity but they don't — "
                f"this is the temptation payoff, but it's dominated by delay costs accumulating. "
                f"Tit-for-tat reasoning: release to establish cooperation."
            ),
            "reasoning_summary": (
                f"Releasing to establish cooperative equilibrium. Symmetric incentives suggest "
                f"counterpart will also release — mutual benefit from simultaneous settlement."
            ),
        },
    ]

    hold_templates = [
        {
            "reasoning": (
                f"Tick {tick}: {agent_id} evaluating with ${balance_dollars:,.0f} balance, {queue_size} in queue. "
                f"Expected incoming payment could arrive next tick, which would offset my outgoing obligation. "
                f"If I hold one more tick, I preserve optionality: incoming liquidity reduces my net position. "
                f"Risk: additional delay cost of ~${random.randint(5, 20):,}. "
                f"Reward: potential netting saves ~${random.randint(50, 200):,} in liquidity cost. "
                f"Expected value favors holding this tick. Decision: Hold — wait for potential netting opportunity."
            ),
            "reasoning_summary": (
                f"Holding to wait for incoming netting opportunity. "
                f"Expected netting savings (${random.randint(50, 200):,}) exceed delay cost (${random.randint(5, 20):,})."
            ),
        },
        {
            "reasoning": (
                f"Strategic hold at tick {tick} for {agent_id}. My balance is ${balance_dollars:,.0f}. "
                f"Counterpart hasn't released yet (queue size suggests pending). "
                f"In a sequential game, the second mover can condition on observing the first move. "
                f"By holding, I maintain information advantage. The deadline is still "
                f"{random.randint(1, 3)} ticks away — delay cost is manageable. "
                f"Decision: Hold this round, reassess next tick based on counterpart action."
            ),
            "reasoning_summary": (
                f"Holding to maintain strategic optionality. Deadline buffer allows waiting — "
                f"will reassess based on counterpart's next move."
            ),
        },
    ]

    if decision == "Release":
        template = random.choice(release_templates)
    else:
        template = random.choice(hold_templates)

    tokens_prompt = random.randint(350, 600)
    tokens_completion = random.randint(120, 280)

    return {
        "tick": tick,
        "agent_id": agent_id,
        "phase": "decided",
        "decision_type": "payment_timing",
        "decision": decision,
        "reasoning": template["reasoning"],
        "reasoning_summary": template["reasoning_summary"],
        "prompt_tokens": tokens_prompt,
        "completion_tokens": tokens_completion,
    }


async def get_llm_decision(
    agent_id: str,
    tick: int,
    agent_state: dict[str, Any],
    scenario_context: dict[str, Any],
    mock: bool = True,
) -> dict[str, Any]:
    """Get an LLM decision for an agent. Uses mock mode by default."""
    if mock:
        # Add slight delay to simulate API call
        return generate_mock_reasoning(agent_id, tick, agent_state, scenario_context)

    # Real LLM call via pydantic-ai (uses platform settings for model)
    try:
        from .settings import settings_manager
        from .streaming_optimizer import _create_agent
        from dotenv import load_dotenv
        from pathlib import Path
        import os

        load_dotenv(Path(__file__).resolve().parents[3] / ".env")

        llm_config = settings_manager.get_llm_config()
        agent = _create_agent(llm_config, "")
        model_settings = llm_config.to_model_settings()

        # Fix: google-vertex needs thinking_config in model_settings
        if llm_config.provider == "google-vertex" and llm_config.thinking_config:
            model_settings["google_thinking_config"] = llm_config.thinking_config

        decision_type = "liquidity_allocation" if tick == 0 else "payment_timing"

        prompt = _build_prompt(agent_id, tick, agent_state, scenario_context, decision_type)

        result = await agent.run(prompt, model_settings=model_settings)
        content = result.output

        decision = _extract_decision(content, decision_type)

        return {
            "tick": tick,
            "agent_id": agent_id,
            "phase": "decided",
            "decision_type": decision_type,
            "decision": decision,
            "reasoning": content,
            "reasoning_summary": "",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "model": llm_config.model,
        }
    except Exception as e:
        # Fall back to mock on any error
        result = generate_mock_reasoning(agent_id, tick, agent_state, scenario_context)
        result["error"] = str(e)
        result["fallback"] = True
        return result


def _build_prompt(
    agent_id: str,
    tick: int,
    agent_state: dict[str, Any],
    ctx: dict[str, Any],
    decision_type: str,
) -> str:
    if decision_type == "liquidity_allocation":
        return (
            f"You are {agent_id} in a payment system simulation. "
            f"You must decide what fraction of your liquidity pool (${agent_state.get('available_liquidity', 0)/100:,.0f}) to allocate.\n\n"
            f"Parameters:\n"
            f"- Liquidity cost: {ctx.get('liquidity_cost_bps', 333)} bps per tick\n"
            f"- Delay cost: {ctx.get('delay_cost', 0.2)} per cent per tick\n"
            f"- Deadline penalty: ${ctx.get('deadline_penalty', 50000)/100:,.0f}\n"
            f"- Deferred crediting: {ctx.get('deferred_crediting', True)}\n\n"
            f"Think about Nash equilibrium, coordination games, and optimal allocation.\n"
            f"State your decision as a percentage (e.g., 'Allocate 50%')."
        )
    else:
        return (
            f"You are {agent_id} at tick {tick}. "
            f"Balance: ${agent_state.get('balance', 0)/100:,.0f}, "
            f"Queue: {agent_state.get('queue1_size', 0)} pending payments.\n\n"
            f"Should you Release queued payments or Hold?\n"
            f"Consider delay costs, counterpart behavior, netting opportunities.\n"
            f"State: 'Release' or 'Hold' with reasoning."
        )


def _extract_decision(content: str, decision_type: str) -> str:
    content_lower = content.lower()
    if decision_type == "liquidity_allocation":
        import re
        match = re.search(r"allocate\s+(\d+)%", content_lower)
        if match:
            return f"Allocate {match.group(1)}% of liquidity pool"
        return "Allocate 50% of liquidity pool"
    else:
        if "hold" in content_lower and "release" not in content_lower:
            return "Hold"
        return "Release"
