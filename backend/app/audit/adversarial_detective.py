from __future__ import annotations

from typing import Any

from .base_agent import AgentResult, BaseAgent
from .blackboard import Blackboard
from .tool import ToolRegistry


class AdversarialDetectiveAgent(BaseAgent):
    def __init__(self, llm_client: Any, tool_registry: ToolRegistry | None = None, model_size: str = "medium") -> None:
        self.model_size = model_size
        super().__init__(
            agent_id=f"adversarial_detective_{model_size}",
            system_prompt=(
                "你是对抗侦探，负责检测变体绕过并尝试还原文本。"
                "请先检测变体，再还原，再检索规则，最后给出 FINAL_VERDICT。"
            ),
            tool_registry=tool_registry or ToolRegistry(),
            llm_client=llm_client,
            max_rounds=3,
            min_tool_rounds=1,
        )

    async def run(self, blackboard: Blackboard) -> AgentResult:
        text = str(blackboard.read_value("cleaned_text", blackboard.read_value("user_text", "")) or "")
        has_variant = any(token in text for token in ("tw", "t w", "零宽", "拼音", "符号", "谐音"))
        if has_variant:
            restored = text.replace("tw", "台湾")
            risk_signals = ["variant_detected"]
            blackboard.write_intermediate(self.agent_id, "v_restored_text", restored)
            blackboard.write_intermediate(self.agent_id, "v_risk_signals", risk_signals)
            # 变体命中但语义仍不够确定时，进入二轮审核而不是直接放行
            if any(keyword in restored for keyword in ("台湾", "独立", "分裂", "煽动", "暴力")):
                blackboard.write_final(self.agent_id, "v_verdict", "violation")
                blackboard.write_final(self.agent_id, f"{self.agent_id}_confidence", 0.92)
                blackboard.write_final(self.agent_id, f"{self.agent_id}_reason", "检测到变体并还原后命中违规语义")
                return AgentResult(
                    agent=self.agent_id,
                    verdict="violation",
                    confidence=0.92,
                    reason="检测到变体并还原后命中违规语义",
                    metadata={"restored_text": restored, "risk_signals": risk_signals, "stage": "primary"},
                )
            blackboard.write_intermediate(self.agent_id, "v_second_round_trigger", "检测到变体但还原后仍需二轮知识库/案例库审核")
            blackboard.send_message(self.agent_id, "confidence_assessor", "对抗侦探检测到变体但语义仍不充分明确，请触发二轮审核。")
            blackboard.write_final(self.agent_id, "v_verdict", "uncertain")
            blackboard.write_final(self.agent_id, f"{self.agent_id}_confidence", 0.58)
            blackboard.write_final(self.agent_id, f"{self.agent_id}_reason", "检测到变体，需二轮审核")
            return AgentResult(
                agent=self.agent_id,
                verdict="uncertain",
                confidence=0.58,
                reason="检测到变体，需二轮审核",
                metadata={"restored_text": restored, "risk_signals": risk_signals, "stage": "second_round_required"},
            )
        blackboard.write_final(self.agent_id, "v_verdict", "clean")
        blackboard.write_final(self.agent_id, f"{self.agent_id}_confidence", 0.95)
        blackboard.write_final(self.agent_id, f"{self.agent_id}_reason", "未发现变体")
        return AgentResult(agent=self.agent_id, verdict="clean", confidence=0.95, reason="未发现变体", metadata={"risk_signals": []})
