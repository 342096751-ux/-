from __future__ import annotations

from typing import Any

from .adversarial_detective import AdversarialDetectiveAgent
from .blackboard import Blackboard
from .confidence_assessor import ConfidenceAssessorAgent
from .cluster import AgentCluster
from .judge import JudgeAgent
from .rule_enforcer import RuleEnforcerAgent


async def run_multiaudit(user_text: str, llm_client: Any) -> dict[str, Any]:
    blackboard = Blackboard()
    blackboard.write_input("user_text", user_text)
    blackboard.write_input("cleaned_text", user_text)

    adversarial_cluster = AgentCluster(
        role="adversarial_detective",
        agents=[AdversarialDetectiveAgent(llm_client, model_size="small"), AdversarialDetectiveAgent(llm_client, model_size="large")],
    )
    rule_cluster = AgentCluster(
        role="rule_enforcer",
        agents=[RuleEnforcerAgent(llm_client, model_size="small"), RuleEnforcerAgent(llm_client, model_size="medium"), RuleEnforcerAgent(llm_client, model_size="large")],
    )

    adv_results = await adversarial_cluster.run(blackboard, strategy="auto")
    rule_results = await rule_cluster.run(blackboard, strategy="cost_sensitive")

    assessor = ConfidenceAssessorAgent(llm_client)
    assess_result = await assessor.run(blackboard)

    # 由置信度评估员统一决定是否需要启动大法官；编排器只负责执行这个决定
    should_escalate = bool(assess_result.metadata.get("suggest_arbitration"))

    if should_escalate:
        blackboard.write_intermediate("system", "phase_change", "进入大法官二次审核")
        judge = JudgeAgent(llm_client)
        judge_result = await judge.run(blackboard)
        verdict = judge_result.verdict
        confidence = judge_result.confidence
        reason = judge_result.reason
    else:
        verdict = assess_result.verdict if assess_result.verdict != "pass" else "pass"
        confidence = assess_result.confidence
        reason = assess_result.reason

    return {
        "verdict": verdict,
        "confidence": confidence,
        "reason": reason,
        "logs": blackboard.to_audit_log(),
        "agent_results": {
            "adversarial_detective": [r.__dict__ for r in adv_results],
            "rule_enforcer": [r.__dict__ for r in rule_results],
            "confidence_assessor": assess_result.__dict__,
        },
    }
