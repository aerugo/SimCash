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


def get_collections() -> list[dict[str, Any]]:
    """Return collection metadata."""
    return [dict(c) for c in COLLECTIONS]


def get_collection(collection_id: str) -> dict[str, Any] | None:
    """Return a single collection by id."""
    for c in COLLECTIONS:
        if c["id"] == collection_id:
            return dict(c)
    return None


def _scenario_collections_map() -> dict[str, list[str]]:
    """Build scenario_id -> [collection_id, ...] mapping."""
    mapping: dict[str, list[str]] = {}
    for c in COLLECTIONS:
        for sid in c["scenario_ids"]:
            mapping.setdefault(sid, []).append(c["id"])
    return mapping
