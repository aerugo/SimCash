"""Local feature toggles for schema generation.

This module provides a PolicyFeatureToggles class that can work independently
or integrate with the main payment_simulator.config.schemas.PolicyFeatureToggles.
"""

from __future__ import annotations

from typing import ClassVar
from pydantic import BaseModel, Field


# Valid policy categories (from payment_simulator/config/schemas.py)
VALID_POLICY_CATEGORIES: frozenset[str] = frozenset([
    # Action categories
    "PaymentAction",
    "BankAction",
    "CollateralAction",
    "RtgsAction",
    # Field categories
    "TransactionField",
    "AgentField",
    "QueueField",
    "CollateralField",
    "CostField",
    "TimeField",
    "LsmField",
    "ThroughputField",
    "StateRegisterField",
    # Other categories
    "SplittingFeature",
    "CollateralFeature",
    "LsmFeature",
])


class PolicyFeatureToggles(BaseModel):
    """Feature toggles for policy DSL.

    Controls which categories of features are allowed in policy generation.
    Uses include/exclude semantics:
    - If include is set, only those categories are allowed
    - If exclude is set, those categories are excluded
    - Both can be set (include takes precedence for whitelist)

    This is a standalone version that doesn't require the main payment_simulator
    package. It mirrors the interface of payment_simulator.config.schemas.PolicyFeatureToggles.
    """

    VALID_CATEGORIES: ClassVar[frozenset[str]] = VALID_POLICY_CATEGORIES

    include: list[str] = Field(
        default_factory=list,
        description="Whitelist of allowed categories (empty = all allowed)",
    )
    exclude: list[str] = Field(
        default_factory=list,
        description="Blacklist of excluded categories",
    )

    def is_category_allowed(self, category: str) -> bool:
        """Check if a category is allowed by the toggles.

        Args:
            category: The category name to check

        Returns:
            True if the category is allowed, False otherwise
        """
        # If include list is specified, category must be in it
        if self.include:
            if category not in self.include:
                return False

        # If exclude list is specified, category must not be in it
        if self.exclude:
            if category in self.exclude:
                return False

        return True


def get_feature_toggles(config: object | None = None) -> PolicyFeatureToggles:
    """Get feature toggles from a config object or return defaults.

    This function tries to extract PolicyFeatureToggles from various config
    types, falling back to defaults if not found.

    Args:
        config: Optional config object that may have policy_feature_toggles

    Returns:
        PolicyFeatureToggles instance
    """
    if config is None:
        return PolicyFeatureToggles()

    # Try to get from attribute
    if hasattr(config, "policy_feature_toggles"):
        toggles = config.policy_feature_toggles
        if isinstance(toggles, PolicyFeatureToggles):
            return toggles
        # Try to construct from dict
        if isinstance(toggles, dict):
            return PolicyFeatureToggles(**toggles)

    return PolicyFeatureToggles()
