"""Pydantic models for transaction endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class TransactionSubmission(BaseModel):
    """Request model for submitting a transaction."""

    sender: str = Field(..., description="Sender agent ID")
    receiver: str = Field(..., description="Receiver agent ID")
    amount: int = Field(
        ..., description="Transaction amount in cents"
    )  # Let FFI validate
    deadline_tick: int = Field(..., description="Deadline tick number", gt=0)
    priority: int = Field(5, description="Priority level (0-10)", ge=0, le=10)
    divisible: bool = Field(False, description="Whether transaction can be split")


class TransactionResponse(BaseModel):
    """Response model for transaction submission."""

    transaction_id: str
    message: str = "Transaction submitted successfully"


class TransactionListResponse(BaseModel):
    """Response model for listing transactions."""

    transactions: list[dict[str, Any]]
