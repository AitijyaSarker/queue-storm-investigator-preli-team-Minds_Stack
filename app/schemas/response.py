"""Response schema. Enum values locked per Section 6/7 of the problem statement."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import CaseType, Department, EvidenceVerdict, Severity


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_id: str
    relevant_transaction_id: Optional[str] = None
    evidence_verdict: EvidenceVerdict
    case_type: CaseType
    severity: Severity
    department: Department
    agent_summary: str = Field(..., min_length=1, max_length=1200)
    recommended_next_action: str = Field(..., min_length=1, max_length=1200)
    customer_reply: str = Field(..., min_length=1, max_length=2000)
    human_review_required: bool
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
