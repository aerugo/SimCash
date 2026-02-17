"""Simulation manager — wraps the Rust Orchestrator."""
from __future__ import annotations

import asyncio
import random
import sys
import uuid
from pathlib import Path
from typing import Any

import yaml

# Add the SimCash api to path so we can import payment_simulator
API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))

from payment_simulator._core import Orchestrator  # type: ignore[import-untyped]
from payment_simulator.config.schemas import SimulationConfig  # type: ignore[import-untyped]

from .models import AgentSetup, AgentType, PresetScenario, ScenarioConfig
from .llm_agent import get_llm_decision
from .policy_runner import (
    make_default_policy,
    run_with_policy,
    build_simulation_trace,
    optimize_policy_with_llm,
)

CONFIGS_DIR = Path(__file__).resolve().parents[3] / "docs" / "papers" / "simcash-paper" / "paper_generator" / "configs"

PRESET_SCENARIO_MAP: dict[PresetScenario, str] = {
    PresetScenario.EXP1: "exp1_2period.yaml",
    PresetScenario.EXP2: "exp2_12period.yaml",
    PresetScenario.EXP3: "exp3_joint.yaml",
}


def _load_preset_yaml(preset: PresetScenario) -> dict[str, Any]:
    path = CONFIGS_DIR / PRESET_SCENARIO_MAP[preset]
    with open(path) as f:
        return yaml.safe_load(f)


def _config_to_ffi(raw_yaml: dict[str, Any]) -> dict[str, Any]:
    """Use the existing SimulationConfig to produce a proper FFI dict."""
    sc = SimulationConfig(**raw_yaml)
    return sc.to_ffi_dict()


def _build_custom_yaml(config: ScenarioConfig) -> dict[str, Any]:
    """Build a YAML-style dict from custom ScenarioConfig."""
    agents_cfg = config.agents or [
        AgentSetup(id="BANK_A", liquidity_pool=100_000),
        AgentSetup(id="BANK_B", liquidity_pool=100_000),
    ]

    agents = []
    for a in agents_cfg:
        agents.append({
            "id": a.id,
            "opening_balance": a.opening_balance,
            "unsecured_cap": a.unsecured_cap,
            "liquidity_pool": a.liquidity_pool,
        })

    return {
        "simulation": {
            "ticks_per_day": config.ticks_per_day,
            "num_days": config.num_days,
            "rng_seed": config.rng_seed,
        },
        "deferred_crediting": config.deferred_crediting,
        "deadline_cap_at_eod": config.deadline_cap_at_eod,
        "cost_rates": {
            "liquidity_cost_per_tick_bps": config.liquidity_cost_per_tick_bps,
            "delay_cost_per_tick_per_cent": config.delay_cost_per_tick_per_cent,
            "overdraft_bps_per_tick": 0,
            "collateral_cost_per_tick_bps": 0,
            "eod_penalty_per_transaction": config.eod_penalty_per_transaction,
            "deadline_penalty": config.deadline_penalty,
            "split_friction_cost": 0,
        },
        "lsm_config": {
            "enable_bilateral": False,
            "enable_cycles": False,
        },
        "agents": agents,
    }


class SimulationManager:
    def __init__(self) -> None:
        self.simulations: dict[str, SimulationInstance] = {}

    def create(self, config: ScenarioConfig) -> str:
        sim_id = str(uuid.uuid4())[:8]

        if config.preset:
            raw_yaml = _load_preset_yaml(config.preset)
        else:
            raw_yaml = _build_custom_yaml(config)

        ffi_config = _config_to_ffi(raw_yaml)

        # Determine agent types
        agent_types: dict[str, AgentType] = {}
        if config.agents:
            for a in config.agents:
                agent_types[a.id] = a.agent_type
        for ac in ffi_config["agent_configs"]:
            if ac["id"] not in agent_types:
                agent_types[ac["id"]] = AgentType.AI

        orch = Orchestrator.new(ffi_config)
        total_ticks = ffi_config["ticks_per_day"] * ffi_config["num_days"]

        instance = SimulationInstance(
            sim_id=sim_id,
            orchestrator=orch,
            raw_config=raw_yaml,
            ffi_config=ffi_config,
            total_ticks=total_ticks,
            agent_types=agent_types,
            use_llm=config.use_llm,
            mock_reasoning=config.mock_reasoning,
            scenario_config=config,
        )
        self.simulations[sim_id] = instance
        return sim_id

    async def create_async(self, config: ScenarioConfig) -> str:
        """Async creation — same as create but runs in thread for safety."""
        return self.create(config)

    def get(self, sim_id: str) -> SimulationInstance | None:
        return self.simulations.get(sim_id)

    def delete(self, sim_id: str) -> bool:
        return self.simulations.pop(sim_id, None) is not None


class SimulationInstance:
    def __init__(
        self,
        sim_id: str,
        orchestrator: Any,
        raw_config: dict[str, Any],
        ffi_config: dict[str, Any],
        total_ticks: int,
        agent_types: dict[str, AgentType],
        use_llm: bool = False,
        mock_reasoning: bool = True,
        scenario_config: ScenarioConfig | None = None,
    ) -> None:
        self.sim_id = sim_id
        self.orch = orchestrator
        self.raw_config = raw_config
        self.ffi_config = ffi_config
        self.total_ticks = total_ticks
        self.agent_types = agent_types
        self.tick_history: list[dict[str, Any]] = []
        self.balance_history: dict[str, list[int]] = {}
        self.cost_history: dict[str, list[dict[str, float]]] = {}
        self.use_llm = use_llm
        self.mock_reasoning = mock_reasoning
        self.scenario_config = scenario_config
        self.reasoning_history: dict[str, list[dict[str, Any]]] = {}

        # Policy optimization state
        self.policies: dict[str, dict[str, Any]] = {}
        self.iteration: int = 0
        self.optimization_history: list[dict[str, Any]] = []
        self.policy_cost_history: list[dict[str, Any]] = []

    @property
    def is_complete(self) -> bool:
        return self.orch.current_tick() >= self.total_ticks

    def get_agent_ids(self) -> list[str]:
        return list(self.orch.get_agent_ids())

    def _get_agent_data(self, aid: str) -> dict[str, Any]:
        state = self.orch.get_agent_state(aid)
        costs = self.orch.get_agent_accumulated_costs(aid)
        return {
            "balance": state["balance"],
            "available_liquidity": state["available_liquidity"],
            "queue1_size": state["queue1_size"],
            "posted_collateral": state["posted_collateral"],
            "costs": {
                "liquidity_cost": costs.get("liquidity_cost", 0),
                "delay_cost": costs.get("delay_cost", 0),
                "penalty_cost": costs.get("penalty_cost", 0) + costs.get("deadline_penalty_cost", 0),
                "total": costs.get("total", 0),
            },
        }

    def get_state(self) -> dict[str, Any]:
        agents = {aid: self._get_agent_data(aid) for aid in self.get_agent_ids()}
        return {
            "sim_id": self.sim_id,
            "current_tick": self.orch.current_tick(),
            "current_day": self.orch.current_day(),
            "total_ticks": self.total_ticks,
            "is_complete": self.is_complete,
            "agents": agents,
            "balance_history": self.balance_history,
            "cost_history": self.cost_history,
            "policies": self.policies,
            "iteration": self.iteration,
            "optimization_history": self.optimization_history,
            "policy_cost_history": self.policy_cost_history,
        }

    def _get_scenario_context(self) -> dict[str, Any]:
        sc = self.scenario_config
        return {
            "liquidity_cost_bps": sc.liquidity_cost_per_tick_bps if sc else 333,
            "delay_cost": sc.delay_cost_per_tick_per_cent if sc else 0.2,
            "deadline_penalty": sc.deadline_penalty if sc else 50_000,
            "deferred_crediting": sc.deferred_crediting if sc else True,
        }

    async def run_optimization_step(self, agent_id: str | None = None) -> dict[str, Any]:
        """Run one LLM policy optimization iteration.

        1. Build trace from tick history
        2. Ask LLM for improved policy
        3. Re-run sim with new policy
        4. Compare costs, accept if improved
        """
        all_agents = self.get_agent_ids()
        target_agent = agent_id or (all_agents[0] if all_agents else None)
        if not target_agent:
            return {"error": "No agents to optimize"}

        # Get current costs
        old_costs: dict[str, int] = {}
        for aid in all_agents:
            costs = self.orch.get_agent_accumulated_costs(aid)
            old_costs[aid] = int(costs.get("total_cost", costs.get("total", 0)))
        old_total = sum(old_costs.values())

        # Build trace
        trace_lines = []
        for td in self.tick_history:
            tick = td.get("tick", "?")
            trace_lines.append(f"--- Tick {tick} ---")
            for aid, adata in td.get("agents", {}).items():
                c = adata.get("costs", {})
                trace_lines.append(f"  {aid}: balance={adata.get('balance',0)}, queue={adata.get('queue1_size',0)}, total_cost={c.get('total',0)}")
            for ev in td.get("events", [])[:10]:
                trace_lines.append(f"  [{ev.get('event_type','?')}]")
        simulation_trace = "\n".join(trace_lines)

        # Initialize default policies if needed
        if not self.policies:
            for aid in all_agents:
                self.policies[aid] = make_default_policy(aid, 1.0)

        current_agent_cost = old_costs.get(target_agent, 0)
        self.iteration += 1

        if self.mock_reasoning:
            old_policy = self.policies.get(target_agent, make_default_policy(target_agent))
            old_frac = old_policy.get("parameters", {}).get("initial_liquidity_fraction", 0.5)
            new_frac = max(0.05, min(0.95, old_frac + random.uniform(-0.15, 0.15)))
            new_frac = round(new_frac, 3)
            new_policy = {
                **old_policy,
                "policy_id": f"web_opt_{self.iteration}",
                "parameters": {"initial_liquidity_fraction": new_frac},
            }
            reasoning = (
                f"Iteration {self.iteration}: Adjusting initial_liquidity_fraction from "
                f"{old_frac:.3f} to {new_frac:.3f}. "
                f"Current cost is {current_agent_cost}."
            )
            opt_result = {"policy": new_policy, "reasoning": reasoning, "model": "mock"}
        else:
            opt_result = await optimize_policy_with_llm(
                raw_yaml=self.raw_config,
                current_policies=self.policies,
                agent_id=target_agent,
                simulation_trace=simulation_trace,
                current_cost=current_agent_cost,
                iteration=self.iteration,
            )

        new_policy = opt_result.get("policy")
        if not new_policy:
            return {"error": "LLM failed", "reasoning": opt_result.get("reasoning", ""), "iteration": self.iteration}

        # Run sim with new policy
        new_policies = {**self.policies, target_agent: new_policy}
        try:
            new_result = run_with_policy(self.raw_config, new_policies)
            new_total = new_result["total_cost"]
            new_agent_cost = new_result["per_agent_costs"].get(target_agent, {}).get("total", 0)
        except Exception as e:
            return {"error": f"Sim failed: {e}", "reasoning": opt_result.get("reasoning", ""), "iteration": self.iteration, "new_policy": new_policy}

        improved = new_total <= old_total
        accepted = improved or self.iteration <= 2

        old_policy = self.policies.get(target_agent)
        record = {
            "iteration": self.iteration, "agent_id": target_agent,
            "old_cost": old_total, "new_cost": new_total,
            "old_agent_cost": current_agent_cost, "new_agent_cost": new_agent_cost,
            "improved": improved, "accepted": accepted,
            "reasoning": opt_result.get("reasoning", ""), "model": opt_result.get("model", ""),
        }
        self.optimization_history.append(record)
        self.policy_cost_history.append({
            "iteration": self.iteration,
            "total_cost": new_total if accepted else old_total,
            "accepted": accepted,
        })
        if accepted:
            self.policies[target_agent] = new_policy

        return {
            "iteration": self.iteration, "agent_id": target_agent,
            "old_cost": old_total, "new_cost": new_total,
            "old_agent_cost": current_agent_cost, "new_agent_cost": new_agent_cost,
            "improved": improved, "accepted": accepted,
            "new_policy": new_policy, "old_policy": old_policy,
            "reasoning": opt_result.get("reasoning", ""), "model": opt_result.get("model", ""),
            "per_agent_costs": new_result["per_agent_costs"] if accepted else None,
        }

    async def do_tick_async(self) -> dict[str, Any]:
        """Async version that supports LLM reasoning."""
        if self.is_complete:
            return {"error": "Simulation complete"}

        tick_num = self.orch.current_tick()
        reasoning: dict[str, Any] = {}

        if self.use_llm:
            ctx = self._get_scenario_context()
            for aid in self.get_agent_ids():
                agent_state = self._get_agent_data(aid)
                trace = await get_llm_decision(
                    agent_id=aid,
                    tick=tick_num,
                    agent_state=agent_state,
                    scenario_context=ctx,
                    mock=self.mock_reasoning,
                )
                reasoning[aid] = trace
                if aid not in self.reasoning_history:
                    self.reasoning_history[aid] = []
                self.reasoning_history[aid].append(trace)

        result = self._execute_tick(tick_num)
        if reasoning:
            result["reasoning"] = reasoning
        return result

    def do_tick(self) -> dict[str, Any]:
        if self.is_complete:
            return {"error": "Simulation complete"}
        tick_num = self.orch.current_tick()
        return self._execute_tick(tick_num)

    def _execute_tick(self, tick_num: int) -> dict[str, Any]:
        result = self.orch.tick()
        events = self.orch.get_tick_events(tick_num)

        for aid in self.get_agent_ids():
            if aid not in self.balance_history:
                self.balance_history[aid] = []
                self.cost_history[aid] = []
            balance = self.orch.get_agent_balance(aid) or 0
            self.balance_history[aid].append(balance)
            costs = self.orch.get_agent_accumulated_costs(aid)
            self.cost_history[aid].append({
                "liquidity_cost": costs.get("liquidity_cost", 0),
                "delay_cost": costs.get("delay_cost", 0),
                "penalty_cost": costs.get("penalty_cost", 0) + costs.get("deadline_penalty_cost", 0),
                "total": costs.get("total", 0),
            })

        agents = {aid: self._get_agent_data(aid) for aid in self.get_agent_ids()}
        formatted_events = [dict(ev) for ev in events]

        tick_data = {
            "tick": tick_num,
            "num_arrivals": result.get("num_arrivals", 0) if isinstance(result, dict) else 0,
            "num_settlements": result.get("num_settlements", 0) if isinstance(result, dict) else 0,
            "agents": agents,
            "events": formatted_events,
            "is_complete": self.is_complete,
            "balance_history": self.balance_history,
            "cost_history": self.cost_history,
        }
        self.tick_history.append(tick_data)
        return tick_data
