from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base_agent import AgentResult, BaseAgent
from .blackboard import Blackboard


class LLMRouter:
    def __init__(self, large_model: Any, medium_model: Any, small_model: Any | None = None) -> None:
        self.models = {"large": large_model, "medium": medium_model, "small": small_model or medium_model}

    async def chat(self, messages: list[dict[str, str]], model_preference: str = "auto") -> str:
        if model_preference == "large":
            return await self.models["large"].chat(messages)
        if model_preference == "small":
            return await self.models["small"].chat(messages)
        if messages:
            last = messages[-1].get("content", "")
            if "delegate_to_large" in last or "调用大模型" in last:
                return await self.models["large"].chat(messages)
            if "delegate_to_small" in last or "调用小模型" in last:
                return await self.models["small"].chat(messages)
        return await self.models["medium"].chat(messages)


@dataclass
class ClusterResult:
    role: str
    results: list[AgentResult] = field(default_factory=list)


class AgentCluster:
    def __init__(self, role: str, agents: list[BaseAgent]) -> None:
        self.role = role
        self.agents = agents
        self.shared_memory: list[Any] = []

    async def run(self, blackboard: Blackboard, strategy: str = "auto") -> list[AgentResult]:
        results: list[AgentResult] = []
        if strategy == "parallel":
            for agent in self.agents:
                results.append(await agent.run(blackboard))
            return results
        for agent in self.agents:
            if strategy == "cost_sensitive" and getattr(agent, "model_size", "medium") == "large" and results:
                if all(r.confidence >= 0.9 for r in results):
                    continue
            result = await agent.run(blackboard)
            results.append(result)
            self.shared_memory.extend(agent.memory)
            blackboard.write_final(agent.agent_id, f"{self.role}_{getattr(agent, 'model_size', 'default')}_verdict", result.verdict)
            blackboard.write_final(agent.agent_id, f"{self.role}_{getattr(agent, 'model_size', 'default')}_confidence", result.confidence)
            blackboard.write_final(agent.agent_id, f"{self.role}_{getattr(agent, 'model_size', 'default')}_reason", result.reason)
        return results
