"""LLM result wrapper with reasoning support.

This module provides the LLMResult dataclass that wraps parsed LLM
responses together with optional reasoning summaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class LLMResult(Generic[T]):
    """Result from LLM call with optional reasoning summary.

    Wraps the parsed response data together with any reasoning/thinking
    content extracted from the LLM response. This enables the audit
    wrapper to capture reasoning for persistence without changing the
    core API contract.

    Type Parameters:
        T: The type of the parsed response data (typically a Pydantic model).

    Example:
        >>> from pydantic import BaseModel
        >>> class Policy(BaseModel):
        ...     name: str
        >>> result = LLMResult(
        ...     data=Policy(name="fifo"),
        ...     reasoning_summary="Selected FIFO because...",
        ... )
        >>> result.data.name
        'fifo'
        >>> result.reasoning_summary
        'Selected FIFO because...'

    Attributes:
        data: The parsed response from the LLM (e.g., a Pydantic model).
        reasoning_summary: Optional reasoning/thinking summary from the LLM.
            None if reasoning was not requested or not available.
    """

    data: T
    reasoning_summary: str | None
