from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class BlackboardEntry:
    timestamp: str
    agent_id: str
    key: str
    value: Any
    entry_type: str
    version: int = 1


@dataclass
class AgentMessage:
    from_agent: str
    to_agent: str
    content: str
    read: bool = False
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class Blackboard:
    def __init__(self) -> None:
        self._store: dict[str, list[BlackboardEntry]] = defaultdict(list)
        self._messages: dict[str, list[AgentMessage]] = defaultdict(list)

    def write(self, agent_id: str, key: str, value: Any, entry_type: str = "intermediate") -> BlackboardEntry:
        version = len(self._store[key]) + 1
        entry = BlackboardEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            agent_id=agent_id,
            key=key,
            value=value,
            entry_type=entry_type,
            version=version,
        )
        self._store[key].append(entry)
        return entry

    def write_input(self, key: str, value: Any) -> BlackboardEntry:
        return self.write("system", key, value, "input")

    def write_final(self, agent_id: str, key: str, value: Any) -> BlackboardEntry:
        return self.write(agent_id, key, value, "final")

    def write_intermediate(self, agent_id: str, key: str, value: Any) -> BlackboardEntry:
        return self.write(agent_id, key, value, "intermediate")

    def read(self, key: str) -> BlackboardEntry | None:
        entries = self._store.get(key, [])
        return entries[-1] if entries else None

    def read_value(self, key: str, default: Any = None) -> Any:
        entry = self.read(key)
        return default if entry is None else entry.value

    def read_all(self, agent_id: str | None = None, entry_type: str | None = None) -> list[BlackboardEntry]:
        entries: list[BlackboardEntry] = []
        for records in self._store.values():
            for record in records:
                if agent_id and record.agent_id != agent_id:
                    continue
                if entry_type and record.entry_type != entry_type:
                    continue
                entries.append(record)
        return entries

    def send_message(self, from_agent: str, to_agent: str, content: str) -> None:
        if to_agent == "*":
            for agent_id in list(self._messages.keys()) or ["broadcast"]:
                self._messages[agent_id].append(AgentMessage(from_agent, agent_id, content))
            return
        self._messages[to_agent].append(AgentMessage(from_agent, to_agent, content))

    def get_messages(self, agent_id: str, unread_only: bool = True, mark_read: bool = True) -> list[AgentMessage]:
        messages = self._messages.get(agent_id, [])
        selected = [message for message in messages if (not unread_only or not message.read)]
        if mark_read:
            for message in selected:
                message.read = True
        return selected

    def get_agent_verdicts(self) -> dict[str, dict[str, Any]]:
        verdicts: dict[str, dict[str, Any]] = {}
        for entry in self.read_all(entry_type="final"):
            if "verdict" in entry.key:
                verdicts[entry.agent_id] = {
                    "key": entry.key,
                    "verdict": entry.value,
                    "confidence": self.read_value(f"{entry.agent_id}_confidence"),
                    "reason": self.read_value(f"{entry.agent_id}_reason"),
                }
        return verdicts

    def detect_conflict(self) -> dict[str, Any] | None:
        verdicts = self.get_agent_verdicts()
        labels = {data.get("verdict") for data in verdicts.values() if data.get("verdict")}
        if len(labels) > 1:
            return {"type": "verdict_conflict", "agents": verdicts, "severity": "high"}
        return None

    def to_audit_log(self) -> list[dict[str, Any]]:
        return [asdict(entry) for entries in self._store.values() for entry in entries]
