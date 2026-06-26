"""Request schema with strict validation."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import Channel, Language, TxnStatus, TxnType, UserType


class TransactionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transaction_id: str = Field(..., min_length=1, max_length=128)
    timestamp: str = Field(..., min_length=1)
    type: TxnType
    amount: float = Field(..., ge=0)
    counterparty: str = Field(..., min_length=1, max_length=256)
    status: TxnStatus


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_id: str = Field(..., min_length=1, max_length=128)
    complaint: str = Field(..., max_length=8000)
    language: Optional[Language] = None
    channel: Optional[Channel] = None
    user_type: Optional[UserType] = None
    campaign_context: Optional[str] = Field(default=None, max_length=256)
    transaction_history: list[TransactionEntry] = Field(default_factory=list)
    metadata: Optional[dict[str, Any]] = None
