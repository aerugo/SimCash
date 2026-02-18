"""Scenario Library — loads, validates, and serves all example configs + preset scenarios."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from payment_simulator.config.schemas import SimulationConfig  # type: ignore[import-untyped]

from .scenario_pack import SCENARIO_PACK

# Paths
EXAMPLES_DIR = Path(__file__).resolve().parents[3] / "examples" / "configs"

# Fields accepted by SimulationConfig
_SIM_CONFIG_FIELDS = {
    "simulation", "agents", "cost_rates", "lsm_config", "scenario_events",
    "policy_feature_toggles", "cost_feature_toggles", "deferred_crediting",
    "deadline_cap_at_eod",
}


def _slugify(name: str) -> str:
    """Convert filename (without extension) to a slug id."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _extract_comments(filepath: Path) -> tuple[str, str]:
    """Extract name and description from YAML header comments."""
    lines: list[str] = []
    with open(filepath) as f:
        for line in f:
            if line.startswith("#"):
                lines.append(line.lstrip("#").strip())
            elif line.strip() == "":
                lines.append("")
            else:
                break

    # Filter out separator lines (===, ---)
    lines = [l for l in lines if not re.match(r"^[=\-]+$", l)]

    # First non-empty line is usually the name/title
    name = ""
    description_lines: list[str] = []
    found_name = False
    for line in lines:
        if not found_name and line:
            name = line
            found_name = True
        elif found_name:
            description_lines.append(line)

    # Clean up description
    desc = " ".join(l for l in description_lines if l).strip()
    # Truncate if very long
    if len(desc) > 500:
        desc = desc[:497] + "..."

    return name, desc


def _name_from_slug(slug: str) -> str:
    """Generate human-readable name from slug."""
    return slug.replace("_", " ").title()


def _categorize(slug: str, raw: dict) -> str:
    """Assign category based on content."""
    if any(kw in slug for kw in ("crisis", "stress", "bad_policy")):
        return "Crisis & Stress"
    if any(k in raw for k in ("algorithm_sequencing", "entry_disposition_offsetting")) or \
       "lsm" in slug:
        return "LSM Exploration"
    if any(kw in slug for kw in ("test_", "minimal", "near_deadline", "priority_escalation")):
        return "Custom"
    if "bis" in slug or "suboptimal" in slug:
        return "Paper Experiments"
    return "Custom"


def _detect_features(raw: dict) -> list[str]:
    """Detect features used in the config."""
    features: list[str] = []
    lsm = raw.get("lsm_config", {})
    if isinstance(lsm, dict):
        if lsm.get("enable_bilateral"):
            features.append("bilateral_limits")
        if lsm.get("enable_cycles"):
            features.append("lsm")
    if raw.get("algorithm_sequencing"):
        features.append("algorithm_sequencing")
    if raw.get("entry_disposition_offsetting"):
        features.append("entry_disposition_offsetting")
    if raw.get("priority_escalation"):
        features.append("priority_escalation")
    if raw.get("scenario_events"):
        features.append("custom_events")
    if raw.get("deferred_crediting"):
        features.append("deferred_crediting")
    if raw.get("deadline_cap_at_eod"):
        features.append("deadline_cap_at_eod")
    return sorted(features)


def _detect_tags(slug: str, raw: dict, features: list[str]) -> list[str]:
    """Generate tags."""
    tags: list[str] = []
    if "crisis" in slug or "stress" in slug:
        tags.append("crisis")
    if "lsm" in slug or "bilateral_limits" in features or "lsm" in features:
        tags.append("lsm")
    if "priority" in slug or "priority_escalation" in features:
        tags.append("priority")
    sim = raw.get("simulation", {})
    num_days = sim.get("num_days", 1)
    if num_days > 1:
        tags.append("multi-day")
    # Stochastic if agents have arrival_config with rate_per_tick
    agents = raw.get("agents", [])
    has_stochastic = any(
        a.get("arrival_config", {}).get("rate_per_tick", 0) > 0
        for a in agents if isinstance(a.get("arrival_config"), dict)
    )
    tags.append("stochastic" if has_stochastic else "deterministic")
    return sorted(set(tags))


def _difficulty(features: list[str], num_agents: int, num_days: int) -> str:
    """Estimate difficulty."""
    score = len(features) + (1 if num_agents > 3 else 0) + (1 if num_days > 5 else 0)
    if score <= 1:
        return "beginner"
    elif score <= 3:
        return "intermediate"
    return "advanced"


def _build_metadata(scenario_id: str, name: str, description: str,
                    category: str, raw: dict) -> dict[str, Any]:
    """Build full metadata dict for a scenario."""
    sim = raw.get("simulation", {})
    agents = raw.get("agents", [])
    num_agents = len(agents)
    ticks_per_day = sim.get("ticks_per_day", 0)
    num_days = sim.get("num_days", 1)
    features = _detect_features(raw)
    tags = _detect_tags(scenario_id, raw, features)
    cost_config = raw.get("cost_rates", {})

    return {
        "id": scenario_id,
        "name": name,
        "description": description,
        "category": category,
        "tags": tags,
        "num_agents": num_agents,
        "ticks_per_day": ticks_per_day,
        "num_days": num_days,
        "difficulty": _difficulty(features, num_agents, num_days),
        "features_used": features,
        "cost_config": cost_config if isinstance(cost_config, dict) else {},
    }


def _validate_config(raw: dict) -> SimulationConfig:
    """Validate raw config dict via SimulationConfig."""
    filtered = {k: v for k, v in raw.items() if k in _SIM_CONFIG_FIELDS}
    return SimulationConfig(**filtered)


def _load_example_configs() -> list[dict[str, Any]]:
    """Load all YAML configs from examples/configs/."""
    scenarios: list[dict[str, Any]] = []
    if not EXAMPLES_DIR.exists():
        return scenarios

    for filepath in sorted(EXAMPLES_DIR.glob("*.yaml")):
        with open(filepath) as f:
            raw = yaml.safe_load(f)
        if not isinstance(raw, dict) or "agents" not in raw:
            continue

        slug = _slugify(filepath.stem)
        comment_name, comment_desc = _extract_comments(filepath)
        name = comment_name or _name_from_slug(slug)
        description = comment_desc or f"Example scenario: {name}"
        category = _categorize(slug, raw)

        # Validate
        _validate_config(raw)

        metadata = _build_metadata(slug, name, description, category, raw)
        scenarios.append({**metadata, "raw_config": raw})

    return scenarios


def _load_preset_scenarios() -> list[dict[str, Any]]:
    """Load preset scenarios from scenario_pack.py as library entries."""
    scenarios: list[dict[str, Any]] = []
    for entry in SCENARIO_PACK:
        raw = entry["scenario"]
        scenario_id = f"preset_{entry['id']}"
        name = entry["name"]
        description = entry["description"]
        category = "Paper Experiments"

        # Validate
        _validate_config(raw)

        metadata = _build_metadata(scenario_id, name, description, category, raw)
        scenarios.append({**metadata, "raw_config": raw})

    return scenarios


# Module-level cache
_LIBRARY_CACHE: list[dict[str, Any]] | None = None


def get_library(include_archived: bool = False) -> list[dict[str, Any]]:
    """Get all scenarios (cached). Returns list of metadata dicts (without raw_config).

    If *include_archived* is False (default), only visible scenarios are returned.
    Each entry includes ``visible`` (bool) and ``collections`` (list of collection ids).
    """
    global _LIBRARY_CACHE
    if _LIBRARY_CACHE is None:
        _LIBRARY_CACHE = _load_example_configs() + _load_preset_scenarios()

    from .collections import get_visibility, _scenario_collections_map
    visibility = get_visibility("scenario")
    col_map = _scenario_collections_map()

    results = []
    for s in _LIBRARY_CACHE:
        entry = {k: v for k, v in s.items() if k != "raw_config"}
        entry["visible"] = visibility.get(s["id"], True)
        entry["collections"] = col_map.get(s["id"], [])
        if include_archived or entry["visible"]:
            results.append(entry)
    return results


def get_scenario_detail(scenario_id: str) -> dict[str, Any] | None:
    """Get full scenario detail including raw_config."""
    global _LIBRARY_CACHE
    if _LIBRARY_CACHE is None:
        _LIBRARY_CACHE = _load_example_configs() + _load_preset_scenarios()
    for s in _LIBRARY_CACHE:
        if s["id"] == scenario_id:
            return s
    return None


def reset_cache() -> None:
    """Clear the library cache (useful for testing)."""
    global _LIBRARY_CACHE
    _LIBRARY_CACHE = None
