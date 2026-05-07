from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any

from .blackboard import Blackboard
from .tool import ToolRegistry


@dataclass
class ThoughtRecord:
    round_num: int
    observation: str
    thought: str
    action_type: str
    action_detail: str
    action_result: Any
    timestamp: float = field(default_factory=time)


@dataclass
class AgentResult:
    agent: str
    verdict: str
    confidence: float
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent:
    def __init__(
        self,
        agent_id: str,
        system_prompt: str,
        tool_registry: ToolRegistry,
        llm_client: Any,
        max_rounds: int = 5,
        min_tool_rounds: int = 2,
    ) -> None:
        self.agent_id = agent_id
        self.system_prompt = system_prompt
        self.tool_registry = tool_registry
        self.llm_client = llm_client
        self.max_rounds = max_rounds
        self.min_tool_rounds = min_tool_rounds
        self.memory: list[ThoughtRecord] = []
        self.pending_messages: list[str] = []
        self.run_count = 0
        self.tools_used: list[str] = []

    def receive_message(self, message: str) -> None:
        self.pending_messages.append(message)

    def _observe(self, blackboard: Blackboard) -> str:
        parts: list[str] = []
        for key in ["user_text", "cleaned_text", "v_restored_text", "v_verdict", "r_verdict", "a_verdict", "j_verdict"]:
            value = blackboard.read_value(key)
            if value is not None:
                parts.append(f"{key}: {value}")
        messages = blackboard.get_messages(self.agent_id, unread_only=True, mark_read=True)
        for message in messages:
            self.pending_messages.append(message.content)
        if self.pending_messages:
            parts.append("messages:\n" + "\n".join(self.pending_messages))
        parts.append(f"tools_used: {','.join(self.tools_used) or 'none'}")
        parts.append(f"memory_rounds: {len(self.memory)}")
        return "\n".join(parts)

    def _build_prompt(self, observation: str, round_num: int) -> list[dict[str, str]]:
        history = "\n".join(f"{record.round_num}:{record.thought}" for record in self.memory[-5:])
        tool_names = ", ".join(sorted(self.tool_registry._tools.keys())) if hasattr(self.tool_registry, "_tools") else ""
        return [
            {"role": "system", "content": self.system_prompt + (f"\n可用工具: {tool_names}" if tool_names else "")},
            {"role": "user", "content": f"History:\n{history or 'none'}\n\nRound {round_num}\n{observation}\n\n请输出思考与 FINAL_VERDICT。"},
        ]

    def _extract_action(self, thought_text: str) -> tuple[str, dict[str, Any]] | None:
        for name in ("delegate_to_large", "delegate_to_small", "delegate_to_medium", "detect_variants", "restore_text", "search_rules"):
            if name in thought_text:
                return name, {}
        return None

    def _try_parse_verdict(self, thought_text: str, round_num: int) -> dict[str, Any] | None:
        if self.run_count == 1 and round_num < self.min_tool_rounds:
            return None
        if not self.tools_used and round_num < self.max_rounds - 1:
            return None
        verdict = self.tool_registry.parse_final_verdict(thought_text)
        if not verdict or not all(key in verdict for key in ("verdict", "confidence", "reason")):
            return None
        return verdict

    async def _call_llm(self, messages: list[dict[str, str]]) -> str:
        chat = getattr(self.llm_client, "chat", None)
        if chat is None:
            return "FINAL_VERDICT: {\"verdict\": \"uncertain\", \"confidence\": 0.0, \"reason\": \"no llm\"}"
        result = chat(messages)
        if hasattr(result, "__await__"):
            return await result
        return result

    async def run(self, blackboard: Blackboard) -> AgentResult:
        self.run_count += 1
        observation = self._observe(blackboard)
        final: dict[str, Any] = {"verdict": "uncertain", "confidence": 0.0, "reason": "not run"}
        for round_num in range(self.max_rounds):
            messages = self._build_prompt(observation, round_num)
            thought = await self._call_llm(messages)
            action = self._extract_action(thought)
            action_type = "tool" if action else "thought"
            action_detail = action[0] if action else ""
            action_result: Any = None
            if action:
                tool_name = action[0]
                if self.tool_registry.has(tool_name):
                    action_result = self.tool_registry.call(tool_name, blackboard=blackboard, agent=self, text=blackboard.read_value("user_text", ""), query=blackboard.read_value("user_text", ""))
                    self.tools_used.append(tool_name)
            verdict = self._try_parse_verdict(thought, round_num)
            if verdict:
                final = verdict
                action_type = "verdict"
                action_detail = "FINAL_VERDICT"
                action_result = verdict
                self.memory.append(ThoughtRecord(round_num, observation, thought, action_type, action_detail, action_result))
                break
            self.memory.append(ThoughtRecord(round_num, observation, thought, action_type, action_detail, action_result or thought))
        return AgentResult(
            agent=self.agent_id,
            verdict=str(final.get("verdict", "uncertain")),
            confidence=float(final.get("confidence", 0.0)),
            reason=str(final.get("reason", "")),
            metadata=final,
        )
