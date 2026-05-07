from __future__ import annotations

from typing import Any

from .base_agent import AgentResult, BaseAgent
from .blackboard import Blackboard
from .tool import ToolRegistry


class JudgeAgent(BaseAgent):
    def __init__(self, llm_client: Any, tool_registry: ToolRegistry | None = None) -> None:
        super().__init__(
            agent_id="judge",
            system_prompt="你是大法官，使用最强模型进行终审裁决。",
            tool_registry=tool_registry or ToolRegistry(),
            llm_client=llm_client,
            max_rounds=10,
            min_tool_rounds=1,
        )

    async def run(self, blackboard: Blackboard) -> AgentResult:
        verdicts = blackboard.get_agent_verdicts()
        if not verdicts:
            result = AgentResult(agent=self.agent_id, verdict="review", confidence=0.4, reason="no evidence", metadata={})
        else:
            violations = [item for item in verdicts.values() if item.get("verdict") == "violation"]
            uncertain_items = [item for item in verdicts.values() if str(item.get("verdict") or "").lower() in {"uncertain", "review"}]
            if violations:
                strongest = max(violations, key=lambda x: float(x.get("confidence") or 0.0))
                result = AgentResult(agent=self.agent_id, verdict="reject", confidence=float(strongest.get("confidence") or 0.8), reason="终审采信违规判定", metadata={"verdicts": verdicts})
            elif uncertain_items:
                strongest = max(uncertain_items, key=lambda x: float(x.get("confidence") or 0.0))
                result = AgentResult(
                    agent=self.agent_id,
                    verdict="review",
                    confidence=max(0.45, float(strongest.get("confidence") or 0.5)),
                    reason="存在疑似证据，保留复审",
                    metadata={"verdicts": verdicts, "uncertain_items": uncertain_items},
                )
            else:
                result = AgentResult(agent=self.agent_id, verdict="pass", confidence=0.9, reason="终审未发现违规", metadata={"verdicts": verdicts})
        blackboard.write_final(self.agent_id, "j_verdict", result.verdict)
        blackboard.write_final(self.agent_id, f"{self.agent_id}_confidence", result.confidence)
        blackboard.write_final(self.agent_id, f"{self.agent_id}_reason", result.reason)
        return result
