"""Prompt block registry and structured prompt builder."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class PromptBlock:
    """A named section of the optimization prompt."""
    id: str
    name: str
    category: str          # "system" | "user"
    source: str            # "static" | "dynamic"
    content: str
    token_estimate: int
    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_summary_dict(self) -> dict[str, Any]:
        """Compact form for storage — truncate large content."""
        d = asdict(self)
        if len(self.content) > 50_000:
            d["content_hash"] = hashlib.sha256(self.content.encode()).hexdigest()
            d["content_length"] = len(self.content)
            d["content"] = self.content[:1000] + f"\n\n... [{len(self.content) - 1000} chars truncated] ..."
            d["truncated"] = True
        return d


@dataclass
class StructuredPrompt:
    """Complete prompt with named blocks + assembled text."""
    blocks: list[PromptBlock]
    system_prompt: str
    user_prompt: str
    total_tokens: int
    profile_hash: str
    llm_response: str | None = None
    llm_response_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocks": [b.to_dict() for b in self.blocks],
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "total_tokens": self.total_tokens,
            "profile_hash": self.profile_hash,
            "llm_response": self.llm_response,
            "llm_response_tokens": self.llm_response_tokens,
        }

    def to_summary_dict(self) -> dict[str, Any]:
        """Compact form — truncates large block content."""
        return {
            "blocks": [b.to_summary_dict() for b in self.blocks],
            "total_tokens": self.total_tokens,
            "profile_hash": self.profile_hash,
            "llm_response_tokens": self.llm_response_tokens,
        }

    @staticmethod
    def compute_profile_hash(blocks: list[PromptBlock]) -> str:
        """Hash of block IDs + enabled states for reproducibility."""
        config = {b.id: {"enabled": b.enabled, "options": b.options} for b in blocks}
        return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class PromptProfile:
    """Saved profile for prompt block configuration."""
    id: str
    name: str
    description: str = ""
    blocks: dict[str, dict[str, Any]] = field(default_factory=dict)  # block_id → {enabled, options}
    created_at: str = ""
    hash: str = ""
