from fastapi import APIRouter

from app.agents.adversarial_detective import AdversarialDetective
from app.agents.case_executor import CaseExecutor
from app.agents.chief_judge import ChiefJudge
from app.agents.rule_executor import RuleExecutor
from app.api.deps import knowledge_manager
from app.core.blackboard import Blackboard
from app.models.audit_log import AuditLog, AuditRequest
from app.services.rag_service import RAGService

router = APIRouter(prefix="/audit", tags=["audit"])
_audit_logs: list[AuditLog] = []


@router.post("", response_model=AuditLog)
async def run_audit(payload: AuditRequest) -> AuditLog:
    blackboard = Blackboard()
    rag_service = RAGService(knowledge_manager)
    agents = [
        RuleExecutor(),
        AdversarialDetective(),
        CaseExecutor(rag_service),
        ChiefJudge(),
    ]

    decisions = []
    final_verdict = "review"
    final_reason = "No final decision"
    for agent in agents:
        decision = await agent.run(payload.content, blackboard)
        decisions.append(decision)
        if agent.name == "chief_judge":
            final_verdict = decision.verdict
            final_reason = decision.reason

    log = AuditLog(
        content=payload.content,
        decisions=decisions,
        final_verdict=final_verdict,
        final_reason=final_reason,
    )
    _audit_logs.append(log)
    return log


def get_audit_logs() -> list[AuditLog]:
    return _audit_logs

