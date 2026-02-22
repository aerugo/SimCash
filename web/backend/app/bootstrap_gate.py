"""Bootstrap evaluation gate for policy acceptance."""
from __future__ import annotations

import json
import math
import statistics
import logging
import time as _time
from typing import Any

from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler  # type: ignore
from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import BootstrapPolicyEvaluator  # type: ignore

logger = logging.getLogger(__name__)

# ── Bootstrap acceptance profiles ────────────────────────────────────
BOOTSTRAP_PROFILES: dict[str, dict[str, Any]] = {
    "conservative": {
        "n_samples": 100,
        "cv_threshold": 0.3,
        "require_significance": True,
        "min_improvement_pct": 0.02,
    },
    "moderate": {
        "n_samples": 50,
        "cv_threshold": 0.5,
        "require_significance": True,
        "min_improvement_pct": 0.0,
    },
    "aggressive": {
        "n_samples": 20,
        "cv_threshold": 1.0,
        "require_significance": False,
        "min_improvement_pct": 0.0,
    },
}
DEFAULT_BOOTSTRAP_PROFILE = "moderate"


def _resolve_bootstrap_thresholds(agent_cfg: dict[str, Any]) -> dict[str, Any]:
    """Resolve bootstrap thresholds for an agent from its scenario config."""
    custom = agent_cfg.get("bootstrap_thresholds")
    if isinstance(custom, dict):
        base = dict(BOOTSTRAP_PROFILES["moderate"])
        base.update(custom)
        return base

    profile_name = agent_cfg.get("bootstrap_profile", DEFAULT_BOOTSTRAP_PROFILE)
    if profile_name in BOOTSTRAP_PROFILES:
        return dict(BOOTSTRAP_PROFILES[profile_name])

    logger.warning("Unknown bootstrap_profile '%s', using moderate", profile_name)
    return dict(BOOTSTRAP_PROFILES["moderate"])


class BootstrapGate:
    """Evaluates proposed policies via bootstrap paired comparison."""

    def __init__(
        self,
        raw_yaml: dict,
        agent_ids: list[str],
        ticks_per_day: int,
        base_seed: int,
        policies: dict[str, dict],
    ):
        self.raw_yaml = raw_yaml
        self.agent_ids = agent_ids
        self.ticks_per_day = ticks_per_day
        self.base_seed = base_seed
        self.policies = policies  # shared reference with Game

    def evaluate(self, aid: str, day: Any, result: dict) -> dict:
        """Run bootstrap evaluation on a proposed policy.

        Args:
            aid: Agent ID.
            day: GameDay with agent_histories.
            result: Optimization result dict with 'new_policy'.

        Returns:
            The result dict, annotated with bootstrap stats and possibly rejected.
        """
        if not result.get("new_policy"):
            return result

        history = day.agent_histories.get(aid)
        if not history or (not history.outgoing and not history.incoming):
            logger.warning("No transaction history for %s on day %d, skipping bootstrap", aid, day.day_num)
            return result

        agent_cfg = next((a for a in self.raw_yaml.get("agents", []) if a.get("id") == aid), None)
        if not agent_cfg:
            logger.warning("Agent %s not found in scenario config, skipping bootstrap", aid)
            return result

        _bs_start = _time.monotonic()

        # Log proposed vs current fraction
        current_fraction = self.policies[aid].get("parameters", {}).get("initial_liquidity_fraction", 1.0)
        proposed_fraction = result["new_policy"].get("parameters", {}).get("initial_liquidity_fraction", 1.0)
        tree_changed = (json.dumps(self.policies[aid].get("payment_tree", {}), sort_keys=True) !=
                        json.dumps(result["new_policy"].get("payment_tree", {}), sort_keys=True))
        logger.info("Bootstrap for %s: fraction %.3f → %.3f (delta=%.3f), tree_changed=%s",
                     aid, current_fraction, proposed_fraction, proposed_fraction - current_fraction, tree_changed)

        thresholds = _resolve_bootstrap_thresholds(agent_cfg)
        n_samples = thresholds["n_samples"]
        cv_threshold = thresholds["cv_threshold"]
        require_significance = thresholds["require_significance"]
        min_improvement_pct = thresholds.get("min_improvement_pct", 0.0)

        # Step 1: Generate bootstrap samples
        sampler = BootstrapSampler(seed=self.base_seed + day.day_num * 100)
        samples = sampler.generate_samples(
            agent_id=aid,
            n_samples=n_samples,
            outgoing_records=history.outgoing,
            incoming_records=history.incoming,
            total_ticks=self.ticks_per_day,
        )

        # Step 2: Paired evaluation
        scenario_cost_rates = self.raw_yaml.get("cost_rates") or None
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=agent_cfg.get("opening_balance", 0),
            credit_limit=agent_cfg.get("unsecured_cap", 0),
            liquidity_pool=agent_cfg.get("liquidity_pool"),
            max_collateral_capacity=agent_cfg.get("max_collateral_capacity"),
            cost_rates=scenario_cost_rates,
        )
        try:
            deltas = evaluator.compute_paired_deltas(
                samples=samples,
                policy_a=self.policies[aid],
                policy_b=result["new_policy"],
            )
        except Exception as e:
            # Proposed policy is structurally invalid (e.g. hallucinated field names)
            error_msg = str(e)
            logger.warning("Bootstrap eval for %s: proposed policy is invalid — %s", aid, error_msg)
            result["accepted"] = False
            result["rejection_reason"] = f"Invalid policy: {error_msg}"
            result["reasoning"] += f" [REJECTED: invalid policy — {error_msg}]"
            rejected_pol = result.get("new_policy")
            result["rejected_policy"] = rejected_pol
            result["rejected_fraction"] = result.get("new_fraction")
            result["new_policy"] = None
            result["new_fraction"] = None
            if rejected_pol:
                day.rejected_policies[aid] = rejected_pol
            return result

        if deltas:
            costs_a = [d.cost_a for d in deltas]
            costs_b = [d.cost_b for d in deltas]
            logger.info("Bootstrap costs for %s: cost_a=[min=%d, max=%d, mean=%d], cost_b=[min=%d, max=%d, mean=%d]",
                        aid, min(costs_a), max(costs_a), sum(costs_a)//len(costs_a),
                        min(costs_b), max(costs_b), sum(costs_b)//len(costs_b))

        # Step 3: Compute statistics
        delta_values = [d.delta for d in deltas]
        n = len(delta_values)
        delta_sum = sum(delta_values)
        mean_delta = delta_sum // n if n else 0

        if n >= 2 and mean_delta != 0:
            std = statistics.stdev(delta_values)
            se = std / math.sqrt(n)
            ci_lower = int(mean_delta - 1.96 * se)
            ci_upper = int(mean_delta + 1.96 * se)
            cv = abs(std / mean_delta)
        else:
            ci_lower = ci_upper = mean_delta
            cv = 0.0

        mean_old = sum(d.cost_a for d in deltas) // n if n else 0
        mean_new = sum(d.cost_b for d in deltas) // n if n else 0

        # Step 4: Acceptance criteria
        accepted = True
        rejection_reason = ""
        profile_name = agent_cfg.get("bootstrap_profile", DEFAULT_BOOTSTRAP_PROFILE)
        if "bootstrap_thresholds" in agent_cfg:
            profile_name = "custom"

        if delta_sum <= 0:
            accepted = False
            rejection_reason = f"No improvement: delta_sum={delta_sum} (old={mean_old:,}, new={mean_new:,})"
        elif min_improvement_pct > 0 and mean_old > 0:
            improvement_pct = delta_sum / (n * mean_old) if n else 0
            if improvement_pct < min_improvement_pct:
                accepted = False
                rejection_reason = f"Improvement too small: {improvement_pct:.1%} < {min_improvement_pct:.0%} threshold"
        if accepted and require_significance and ci_lower <= 0 and n >= 2:
            accepted = False
            rejection_reason = f"Not significant: 95% CI [{ci_lower:,}, {ci_upper:,}] includes zero"

        _bs_elapsed = _time.monotonic() - _bs_start
        logger.warning(
            "Bootstrap eval for %s [%s]: %.1fs, %d samples, delta_sum=%d, accepted=%s%s",
            aid, profile_name, _bs_elapsed, n, delta_sum, accepted,
            f" ({rejection_reason})" if rejection_reason else "",
        )

        result["bootstrap"] = {
            "delta_sum": delta_sum,
            "mean_delta": mean_delta,
            "cv": round(cv, 4),
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "num_samples": n,
            "old_mean_cost": mean_old,
            "new_mean_cost": mean_new,
            "rejection_reason": rejection_reason,
            "profile": profile_name,
            "cv_threshold": cv_threshold,
            "require_significance": require_significance,
        }

        if not accepted:
            result["accepted"] = False
            result["rejection_reason"] = rejection_reason
            result["reasoning"] += f" [REJECTED: {rejection_reason}]"
            rejected_pol = result.get("new_policy")
            result["rejected_policy"] = rejected_pol
            result["rejected_fraction"] = result.get("new_fraction")
            result["new_policy"] = None
            result["new_fraction"] = None
            if rejected_pol:
                day.rejected_policies[aid] = rejected_pol

        return result
