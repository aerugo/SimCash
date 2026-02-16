"""LLM Agent for SimCash interactive sandbox.

Uses OpenAI GPT-5.2 with high reasoning to make bank decisions:
1. Initial liquidity allocation (what fraction of pool to commit)
2. Per-tick payment decisions (Release/Hold)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

MODEL = "gpt-5.2"
REASONING_EFFORT = "high"


def _get_client() -> AsyncOpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")
    return AsyncOpenAI(api_key=api_key)


def _format_scenario_context(scenario: dict[str, Any], agent_id: str) -> str:
    """Format scenario into a readable context for the LLM."""
    cost_rates = scenario.get("cost_rates", {})
    agents = scenario.get("agents", [])
    agent_info = next((a for a in agents if a["id"] == agent_id), {})
    
    # Format payment schedule
    events = scenario.get("scenario_events", [])
    payment_schedule = []
    for ev in events:
        if ev.get("from_agent") == agent_id:
            payment_schedule.append(
                f"  - Send ${ev['amount']/100:.2f} to {ev['to_agent']} at tick {ev['schedule']['tick']}, deadline {ev['deadline']}"
            )
    
    incoming = []
    for ev in events:
        if ev.get("to_agent") == agent_id:
            incoming.append(
                f"  - Receive ${ev['amount']/100:.2f} from {ev['from_agent']} at tick {ev['schedule']['tick']}"
            )
    
    # Arrival config (for stochastic scenarios)
    arrival_info = ""
    if "arrival_config" in agent_info:
        ac = agent_info["arrival_config"]
        arrival_info = f"""
Stochastic Arrivals:
  Rate: {ac['rate_per_tick']} payments/tick (Poisson)
  Amount distribution: {ac['amount_distribution']['type']} (mean={ac['amount_distribution'].get('mean', 'N/A')})
  Deadline range: {ac.get('deadline_range', 'N/A')} ticks"""
    
    return f"""
=== SCENARIO CONTEXT FOR {agent_id} ===

Simulation: {scenario['ticks_per_day']} ticks per day, {scenario['num_days']} day(s)

Your Bank ({agent_id}):
  Liquidity Pool: ${agent_info.get('liquidity_pool', 0)/100:.2f}
  Opening Balance: ${agent_info.get('opening_balance', 0)/100:.2f}
  Unsecured Credit Cap: ${agent_info.get('unsecured_cap', 0)/100:.2f}

Cost Rates:
  Liquidity cost: {cost_rates.get('liquidity_cost_per_tick_bps', 0)} bps/tick
  Delay cost: {cost_rates.get('delay_cost_per_tick_per_cent', 0)} per cent per tick
  Overdraft: {cost_rates.get('overdraft_bps_per_tick', 0)} bps/tick
  EOD penalty: ${cost_rates.get('eod_penalty_per_transaction', 0)/100:.2f} per transaction
  Deadline penalty: ${cost_rates.get('deadline_penalty', 0)/100:.2f}

Outgoing Payments:
{chr(10).join(payment_schedule) if payment_schedule else '  (stochastic - see arrival config)'}

Expected Incoming:
{chr(10).join(incoming) if incoming else '  (stochastic - see arrival config)'}
{arrival_info}

Other Banks: {', '.join(a['id'] for a in agents if a['id'] != agent_id)}

Deferred Crediting: {scenario.get('deferred_crediting', False)}
LSM: bilateral={scenario.get('lsm_config', {}).get('enable_bilateral', False)}, cycles={scenario.get('lsm_config', {}).get('enable_cycles', False)}
"""


async def get_initial_decisions(
    agent_ids: list[str],
    scenario: dict[str, Any],
    llm_prompt: str = "",
) -> dict[str, dict[str, Any]]:
    """Ask GPT-5.2 for initial liquidity allocation decisions for all agents.
    
    Returns dict mapping agent_id -> {"initial_liquidity_fraction": float, "reasoning": str}
    """
    client = _get_client()
    decisions: dict[str, dict[str, Any]] = {}
    
    for agent_id in agent_ids:
        context = _format_scenario_context(scenario, agent_id)
        
        system_prompt = f"""You are an expert cash manager at {agent_id}, a bank in an RTGS payment system.
Your goal is to minimize total costs (liquidity costs + delay penalties + EOD penalties).

{llm_prompt}

You must decide what fraction of your liquidity pool to allocate at the start of the day.
- Allocating more = more capacity to settle payments, but higher opportunity cost
- Allocating less = lower cost, but risk of payment failures/delays

Respond with ONLY a JSON object:
{{"initial_liquidity_fraction": <float 0.0-1.0>, "reasoning": "<brief explanation>"}}"""

        try:
            response = await client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context},
                ],
                temperature=0.5,
                reasoning={
                    "effort": REASONING_EFFORT,
                    "summary": "detailed",
                },
                response_format={"type": "json_object"},
                timeout=120,
            )
            
            content = response.choices[0].message.content or "{}"
            decision = json.loads(content)
            
            # Extract reasoning summary if available
            reasoning_summary = ""
            if hasattr(response.choices[0].message, 'reasoning') and response.choices[0].message.reasoning:
                reasoning_summary = str(response.choices[0].message.reasoning)
            
            # Validate fraction
            frac = float(decision.get("initial_liquidity_fraction", 0.3))
            frac = max(0.0, min(1.0, frac))
            
            decisions[agent_id] = {
                "initial_liquidity_fraction": frac,
                "reasoning": decision.get("reasoning", ""),
                "reasoning_summary": reasoning_summary,
                "model": MODEL,
            }
            
            logger.info(f"LLM decision for {agent_id}: fraction={frac:.2f}, reasoning={decision.get('reasoning', '')[:100]}")
            
        except Exception as e:
            logger.error(f"LLM call failed for {agent_id}: {e}")
            decisions[agent_id] = {
                "initial_liquidity_fraction": 0.3,
                "reasoning": f"Fallback (LLM error: {str(e)[:100]})",
                "model": "fallback",
            }
    
    return decisions


async def get_tick_decision(
    agent_id: str,
    scenario: dict[str, Any],
    tick_state: dict[str, Any],
    pending_payments: list[dict[str, Any]],
    llm_prompt: str = "",
) -> dict[str, Any]:
    """Ask GPT-5.2 for per-tick payment decisions (Release/Hold).
    
    This is for future use — currently the Fifo policy handles tick decisions.
    """
    client = _get_client()
    
    payments_text = "\n".join(
        f"  - TX {p.get('tx_id', '?')}: ${p.get('amount', 0)/100:.2f} to {p.get('receiver', '?')}, "
        f"deadline in {p.get('ticks_to_deadline', '?')} ticks"
        for p in pending_payments
    )
    
    system_prompt = f"""You are {agent_id}'s cash manager. Decide Release or Hold for each pending payment.
Current balance: ${tick_state.get('balance', 0)/100:.2f}
Tick: {tick_state.get('current_tick', 0)}/{tick_state.get('total_ticks', 0)}

{llm_prompt}

Respond with JSON: {{"decisions": [{{"tx_id": "...", "action": "Release"|"Hold"}}]}}"""

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Pending payments:\n{payments_text}"},
            ],
            temperature=0.3,
            reasoning={"effort": REASONING_EFFORT, "summary": "detailed"},
            response_format={"type": "json_object"},
            timeout=60,
        )
        
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception as e:
        logger.error(f"Tick decision failed for {agent_id}: {e}")
        return {"decisions": [{"tx_id": p.get("tx_id", ""), "action": "Release"} for p in pending_payments]}
