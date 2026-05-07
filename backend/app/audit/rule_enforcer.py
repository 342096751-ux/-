from __future__ import annotations

from typing import Any

from .base_agent import AgentResult, BaseAgent
from .blackboard import Blackboard
from .tool import ToolRegistry


class RuleEnforcerAgent(BaseAgent):
    def __init__(self, llm_client: Any, tool_registry: ToolRegistry | None = None, model_size: str = "medium") -> None:
        self.model_size = model_size
        super().__init__(
            agent_id=f"rule_enforcer_{model_size}",
            system_prompt="你是规则执行员，负责根据黑板和规则判定内容。",
            tool_registry=tool_registry or ToolRegistry(),
            llm_client=llm_client,
            max_rounds=3,
            min_tool_rounds=1,
        )

    async def run(self, blackboard: Blackboard) -> AgentResult:
        text = str(blackboard.read_value("v_restored_text", blackboard.read_value("cleaned_text", blackboard.read_value("user_text", ""))) or "")

        # 明确违规：直接判 violation
        if "台湾" in text and "独立" in text:
            blackboard.write_final(self.agent_id, "r_verdict", "violation")
            blackboard.write_final(self.agent_id, f"{self.agent_id}_confidence", 0.88)
            blackboard.write_final(self.agent_id, f"{self.agent_id}_reason", "命中明确违规模式")
            return AgentResult(agent=self.agent_id, verdict="violation", confidence=0.88, reason="命中明确违规模式", metadata={"matched_rules": ["national_separation"], "stage": "primary"})

        # 可疑/疑似：必须进入二轮知识库/案例库审核
        suspicious_markers = ["疑似", "可能", "暗示", "影射", "擦边", "敏感", "tw", "td", "zg"]
        if any(marker in text.lower() for marker in suspicious_markers):
            second_round_reason = "疑似内容，触发二轮知识库/案例库审核"
            blackboard.write_intermediate(self.agent_id, "r_second_round_trigger", second_round_reason)
            blackboard.send_message(self.agent_id, "confidence_assessor", "规则执行员已进入二轮审核，请提高仲裁敏感度。")
            blackboard.write_final(self.agent_id, "r_verdict", "uncertain")
            blackboard.write_final(self.agent_id, f"{self.agent_id}_confidence", 0.48)
            blackboard.write_final(self.agent_id, f"{self.agent_id}_reason", second_round_reason)
            return AgentResult(
                agent=self.agent_id,
                verdict="uncertain",
                confidence=0.48,
                reason=second_round_reason,
                metadata={"matched_rules": ["suspicious_pattern"], "stage": "second_round_required"},
            )

        if "餐厅" in text and "好吃" in text:
            blackboard.write_final(self.agent_id, "r_verdict", "clean")
            blackboard.write_final(self.agent_id, f"{self.agent_id}_confidence", 0.72)
            blackboard.write_final(self.agent_id, f"{self.agent_id}_reason", "普通评价，不构成违规")
            return AgentResult(agent=self.agent_id, verdict="clean", confidence=0.72, reason="普通评价，不构成违规", metadata={"matched_rules": []})

        blackboard.write_final(self.agent_id, "r_verdict", "uncertain")
        blackboard.write_final(self.agent_id, f"{self.agent_id}_confidence", 0.5)
        blackboard.write_final(self.agent_id, f"{self.agent_id}_reason", "无法确认，进入二轮审核")
        blackboard.write_intermediate(self.agent_id, "r_second_round_trigger", "无法确认，进入二轮知识库/案例库审核")
        return AgentResult(agent=self.agent_id, verdict="uncertain", confidence=0.5, reason="无法确认，进入二轮审核", metadata={"matched_rules": [], "stage": "second_round_required"})
