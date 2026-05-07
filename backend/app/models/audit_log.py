from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentDecision(BaseModel):
    agent: str
    verdict: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""


class AuditRequest(BaseModel):
    content: str
    metadata: dict = Field(default_factory=dict)


class AuditLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    decisions: list[AgentDecision] = Field(default_factory=list)
    final_verdict: str = "pending"
    final_reason: str = ""

