from __future__ import annotations

from typing import Any

from .base_agent import AgentResult, BaseAgent
from .blackboard import Blackboard
from .tool import ToolRegistry


class ConfidenceAssessorAgent(BaseAgent):
    def __init__(self, llm_client: Any, tool_registry: ToolRegistry | None = None) -> None:
        super().__init__(
            agent_id="confidence_assessor",
            system_prompt="你是置信度评估员，负责检测冲突并决定是否仲裁。",
            tool_registry=tool_registry or ToolRegistry(),
            llm_client=llm_client,
            max_rounds=3,
            min_tool_rounds=1,
        )

    async def run(self, blackboard: Blackboard) -> AgentResult:
        verdicts = blackboard.get_agent_verdicts()
        conflict = blackboard.detect_conflict()
        uncertain_items = {
            agent_id: data
            for agent_id, data in verdicts.items()
            if str(data.get("verdict") or "").lower() in {"uncertain", "review"}
        }

        should_arbitrate = bool(conflict or uncertain_items)
        supplement_requests: list[dict[str, str]] = []
        reason = "no conflict"
        verdict = "pass"
        confidence = 0.9

        if conflict:
            reason = f"conflict detected: {conflict['agents']}"
            verdict = "review"
            confidence = 0.5
            for agent_id, data in verdicts.items():
                if data.get("verdict") == "clean":
                    supplement_requests.append({"target_agent": agent_id, "message": "请基于黑板重新审查。"})
            blackboard.write_final(self.agent_id, "phase_change", "大法官仲裁")
            blackboard.send_message("confidence_assessor", "chief_judge", "检测到冲突，请启动大法官仲裁。")
        elif uncertain_items:
            reason = f"uncertain evidence detected: {list(uncertain_items.keys())}"
            verdict = "review"
            confidence = 0.55
            blackboard.write_final(self.agent_id, "phase_change", "大法官二次审核")
            blackboard.send_message("confidence_assessor", "chief_judge", "发现疑似证据，请启动大法官二次审核。")
            supplement_requests.append({"target_agent": "chief_judge", "message": "发现疑似证据，请启动大法官二次审核。"})

        blackboard.write_final(self.agent_id, "a_verdict", verdict)
        blackboard.write_final(self.agent_id, f"{self.agent_id}_confidence", confidence)
        blackboard.write_final(self.agent_id, f"{self.agent_id}_reason", reason)
        return AgentResult(agent=self.agent_id, verdict=verdict, confidence=confidence, reason=reason, metadata={"suggest_arbitration": should_arbitrate, "conflict": conflict, "supplement_requests": supplement_requests, "verdicts": verdicts, "uncertain_items": uncertain_items})
