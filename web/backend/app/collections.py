"""Library curation: collections, visibility defaults, and Firestore persistence."""
from __future__ import annotations

import logging
from typing import Any

from . import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

COLLECTIONS: list[dict[str, Any]] = [
    {
        "id": "paper_experiments",
        "name": "Paper Experiments",
        "icon": "📄",
        "description": "Scenarios that replicate experiments from the SimCash/BIS papers.",
        "scenario_ids": [
            "bis_liquidity_delay_tradeoff",
            "preset_2bank_12tick",
            "suboptimal_policies_10day",
        ],
    },
    {
        "id": "getting_started",
        "name": "Getting Started",
        "icon": "🚀",
        "description": "Simple scenarios to learn the basics of payment simulation.",
        "scenario_ids": [
            "preset_2bank_2tick",
            "preset_2bank_3tick",
            "preset_2bank_12tick",
        ],
    },
    {
        "id": "network_effects",
        "name": "Network Effects",
        "icon": "🌐",
        "description": "Explore how adding more banks changes system dynamics.",
        "scenario_ids": [
            "preset_3bank_6tick",
            "preset_4bank_8tick",
            "preset_5bank_12tick",
        ],
    },
    {
        "id": "crisis_stress",
        "name": "Crisis & Stress",
        "icon": "⚡",
        "description": "Stress-test policies under crisis conditions and liquidity shocks.",
        "scenario_ids": [
            "preset_2bank_stress",
            "advanced_policy_crisis",
            "crisis_resolution_10day",
        ],
    },
    {
        "id": "lsm_exploration",
        "name": "LSM Exploration",
        "icon": "🔄",
        "description": "Scenarios showcasing Liquidity Saving Mechanism features.",
        "scenario_ids": [
            "target2_lsm_features_test",
        ],
    },
]

# ---------------------------------------------------------------------------
# Default visibility
# ---------------------------------------------------------------------------

_VISIBLE_SCENARIOS = {
    "preset_2bank_2tick",
    "preset_2bank_12tick",
    "preset_2bank_3tick",
    "preset_3bank_6tick",
    "preset_4bank_8tick",
    "preset_2bank_stress",
    "preset_5bank_12tick",
    "bis_liquidity_delay_tradeoff",
    "advanced_policy_crisis",
    "crisis_resolution_10day",
}

_ALL_SCENARIOS = {
    "advanced_policy_crisis",
    "bis_liquidity_delay_tradeoff",
    "crisis_resolution_10day",
    "suboptimal_policies_10day",
    "suboptimal_policies_25day",
    "target2_crisis_25day",
    "target2_crisis_25day_bad_policy",
    "target2_lsm_features_test",
    "test_minimal_eod",
    "test_near_deadline",
    "test_priority_escalation",
    "preset_2bank_2tick",
    "preset_2bank_12tick",
    "preset_2bank_3tick",
    "preset_3bank_6tick",
    "preset_4bank_8tick",
    "preset_2bank_stress",
    "preset_5bank_12tick",
}

DEFAULT_SCENARIO_VISIBILITY: dict[str, bool] = {
    sid: sid in _VISIBLE_SCENARIOS for sid in _ALL_SCENARIOS
}

_VISIBLE_POLICIES = {
    "fifo",
    "aggressive_market_maker",
    "balanced_cost_optimizer",
    "cautious_liquidity_preserver",
    "deadline_driven_trader",
    "efficient_proactive",
    "goliath_national_bank",
    "momentum_investment_bank",
    "adaptive_liquidity_manager",
    "smart_splitter",
    "sophisticated_adaptive_bank",
    "target2_aggressive_settler",
    "target2_conservative_offsetter",
    "target2_crisis_proactive_manager",
    "target2_priority_escalator",
}

_ALL_POLICIES = {
    "adaptive_liquidity_manager",
    "aggressive_market_maker",
    "agile_regional_bank",
    "balanced_cost_optimizer",
    "cautious_liquidity_preserver",
    "cost_aware_test",
    "deadline",
    "deadline_driven_trader",
    "efficient_memory_adaptive",
    "efficient_proactive",
    "efficient_splitting",
    "fifo",
    "goliath_national_bank",
    "liquidity_aware",
    "liquidity_splitting",
    "memory_driven_strategist",
    "mock_splitting",
    "momentum_investment_bank",
    "smart_budget_manager",
    "smart_splitter",
    "sophisticated_adaptive_bank",
    "target2_aggressive_settler",
    "target2_conservative_offsetter",
    "target2_crisis_proactive_manager",
    "target2_crisis_risk_denier",
    "target2_limit_aware",
    "target2_priority_aware",
    "target2_priority_escalator",
    "time_aware_test",
}

DEFAULT_POLICY_VISIBILITY: dict[str, bool] = {
    pid: pid in _VISIBLE_POLICIES for pid in _ALL_POLICIES
}

# ---------------------------------------------------------------------------
# Firestore helpers
# ---------------------------------------------------------------------------

_fs_db = None


def _get_fs_db():
    global _fs_db
    if _fs_db is not None:
        return _fs_db
    try:
        from firebase_admin import firestore  # type: ignore[import-untyped]
        db_id = config.FIRESTORE_DATABASE
        _fs_db = firestore.client(database_id=db_id)
        return _fs_db
    except Exception:
        return None


def get_visibility(item_type: str) -> dict[str, bool]:
    """Return visibility map for 'scenario' or 'policy'.

    Tries Firestore first; falls back to built-in defaults.
    """
    defaults = (
        DEFAULT_SCENARIO_VISIBILITY if item_type == "scenario"
        else DEFAULT_POLICY_VISIBILITY
    )
    try:
        db = _get_fs_db()
        if db is None:
            return dict(defaults)
        doc_id = f"{item_type}_visibility"
        doc = db.collection("library_settings").document(doc_id).get()
        if doc.exists:
            stored = doc.to_dict() or {}
            # Merge: defaults for any new items not yet in Firestore
            merged = dict(defaults)
            merged.update(stored)
            return merged
        return dict(defaults)
    except Exception:
        logger.debug("Firestore unavailable for visibility; using defaults")
        return dict(defaults)


def set_visibility(item_type: str, item_id: str, visible: bool) -> None:
    """Persist a single item's visibility to Firestore."""
    db = _get_fs_db()
    if db is None:
        raise RuntimeError("Firestore unavailable")
    doc_id = f"{item_type}_visibility"
    db.collection("library_settings").document(doc_id).set(
        {item_id: visible}, merge=True
    )


def _load_custom_collections() -> list[dict[str, Any]]:
    """Load custom collections from Firestore."""
    try:
        db = _get_fs_db()
        if db is None:
            return []
        doc = db.collection("library_settings").document("custom_collections").get()
        if doc.exists:
            data = doc.to_dict() or {}
            return data.get("collections", [])
        return []
    except Exception:
        logger.debug("Failed to load custom collections from Firestore")
        return []


def _save_custom_collections(custom: list[dict[str, Any]]) -> None:
    """Save custom collections to Firestore."""
    db = _get_fs_db()
    if db is None:
        raise RuntimeError("Firestore unavailable")
    db.collection("library_settings").document("custom_collections").set(
        {"collections": custom}
    )


def _merged_collections() -> list[dict[str, Any]]:
    """Return hardcoded + custom collections merged.

    Custom collections with the same id as hardcoded ones override scenario_ids.
    """
    custom = _load_custom_collections()
    custom_by_id = {c["id"]: c for c in custom}

    result = []
    for c in COLLECTIONS:
        if c["id"] in custom_by_id:
            merged = dict(c)
            merged.update(custom_by_id.pop(c["id"]))
            result.append(merged)
        else:
            result.append(dict(c))

    # Append purely custom collections
    for c in custom_by_id.values():
        result.append(c)

    return result


def get_collections() -> list[dict[str, Any]]:
    """Return collection metadata (hardcoded + custom merged)."""
    return _merged_collections()


def get_collection(collection_id: str) -> dict[str, Any] | None:
    """Return a single collection by id."""
    for c in _merged_collections():
        if c["id"] == collection_id:
            return dict(c)
    return None


def update_collection_scenarios(collection_id: str, scenario_ids: list[str]) -> dict[str, Any]:
    """Update scenario_ids for a collection. Persists to Firestore."""
    custom = _load_custom_collections()
    custom_by_id = {c["id"]: c for c in custom}

    if collection_id in custom_by_id:
        custom_by_id[collection_id]["scenario_ids"] = scenario_ids
    else:
        # Check if it's a hardcoded one — create override
        hardcoded = {c["id"]: c for c in COLLECTIONS}
        if collection_id in hardcoded:
            override = dict(hardcoded[collection_id])
            override["scenario_ids"] = scenario_ids
            custom_by_id[collection_id] = override
        else:
            raise ValueError(f"Collection {collection_id!r} not found")

    _save_custom_collections(list(custom_by_id.values()))
    return get_collection(collection_id)  # type: ignore[return-value]


def create_collection(
    collection_id: str,
    name: str,
    icon: str = "📁",
    description: str = "",
    scenario_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new custom collection."""
    # Check for id conflicts
    existing_ids = {c["id"] for c in COLLECTIONS}
    custom = _load_custom_collections()
    existing_ids.update(c["id"] for c in custom)
    if collection_id in existing_ids:
        raise ValueError(f"Collection {collection_id!r} already exists")

    new_coll = {
        "id": collection_id,
        "name": name,
        "icon": icon,
        "description": description,
        "scenario_ids": scenario_ids or [],
    }
    custom.append(new_coll)
    _save_custom_collections(custom)
    return new_coll


def delete_collection(collection_id: str) -> None:
    """Delete a custom collection. Cannot delete hardcoded ones."""
    hardcoded_ids = {c["id"] for c in COLLECTIONS}
    if collection_id in hardcoded_ids:
        raise ValueError(f"Cannot delete built-in collection {collection_id!r}")

    custom = _load_custom_collections()
    new_custom = [c for c in custom if c["id"] != collection_id]
    if len(new_custom) == len(custom):
        raise ValueError(f"Collection {collection_id!r} not found")
    _save_custom_collections(new_custom)


def _scenario_collections_map() -> dict[str, list[str]]:
    """Build scenario_id -> [collection_id, ...] mapping."""
    mapping: dict[str, list[str]] = {}
    for c in _merged_collections():
        for sid in c["scenario_ids"]:
            mapping.setdefault(sid, []).append(c["id"])
    return mapping
