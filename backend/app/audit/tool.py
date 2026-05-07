from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from .blackboard import Blackboard


ToolFn = Callable[..., Any]


@dataclass
class ToolSpec:
    name: str
    description: str
    fn: ToolFn


class VariantDetector:
    @classmethod
    def detect(cls, text: str) -> list[str]:
        signals: list[str] = []
        if re.search(r"[\u200b-\u200f\ufeff]", text):
            signals.append("zero_width_characters")
        if re.search(r"\b[a-z]{1,3}\b", text.lower()):
            signals.append("latin_abbreviation")
        if " " in text and len(text.replace(" ", "")) < len(text):
            signals.append("space_splicing")
        if re.search(r"[·•\-_/\\|]", text):
            signals.append("symbol_splicing")
        return signals

    @classmethod
    def restore(cls, text: str, signals: list[str]) -> str:
        restored = re.sub(r"[\u200b-\u200f\ufeff]", "", text)
        restored = re.sub(r"[·•\-_/\\|]", "", restored)
        restored = re.sub(r"\s+", "", restored)
        if any(sig in signals for sig in ("latin_abbreviation", "space_splicing")) and "tw" in restored:
            restored = restored.replace("tw", "台湾")
        return restored


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self.register("detect_variants", "Detect obfuscation patterns", self._detect_variants)
        self.register("restore_text", "Restore obfuscated text", self._restore_text)
        self.register("search_rules", "Search compliance rules", self._search_rules)
        self.register("search_knowledge", "Search knowledge base", self._search_knowledge)
        self.register("read_blackboard", "Read from blackboard", self._read_blackboard)
        self.register("write_blackboard", "Write to blackboard", self._write_blackboard)

    def register(self, name: str, description: str, fn: ToolFn) -> None:
        self._tools[name] = ToolSpec(name=name, description=description, fn=fn)

    def has(self, name: str) -> bool:
        return name in self._tools

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        if name not in self._tools:
            raise KeyError(f"tool not found: {name}")
        return self._tools[name].fn(*args, **kwargs)

    def parse_final_verdict(self, text: str) -> dict[str, Any] | None:
        match = re.search(r"FINAL_VERDICT:\s*(\{.*\})", text, re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(1))
        except Exception:
            return None
        required = ("verdict", "confidence", "reason")
        if not all(k in data for k in required):
            return None
        return data

    def _detect_variants(self, *, text: str, **_: Any) -> list[str]:
        return VariantDetector.detect(text)

    def _restore_text(self, *, text: str, signals: list[str] | None = None, **_: Any) -> str:
        return VariantDetector.restore(text, signals or [])

    def _search_rules(self, *, query: str, top_k: int = 3, **_: Any) -> list[dict[str, Any]]:
        corpus = [
            {"id": "PA-001", "title": "political separation", "content": "涉及国家分裂、独立表述"},
            {"id": "AD-001", "title": "advertising", "content": "营销推广和广告内容"},
        ]
        hits = [item for item in corpus if any(token in item["content"] or token in item["title"] for token in query.split())]
        return hits[:top_k]

    def _search_knowledge(self, *, query: str, top_k: int = 3, **_: Any) -> list[dict[str, Any]]:
        return [{"query": query, "answer": "knowledge lookup placeholder"}][:top_k]

    def _read_blackboard(self, *, blackboard: Blackboard, key: str, default: Any = None, **_: Any) -> Any:
        return blackboard.read_value(key, default)

    def _write_blackboard(self, *, blackboard: Blackboard, agent_id: str, key: str, value: Any, entry_type: str = "intermediate", **_: Any) -> Any:
        return blackboard.write(agent_id, key, value, entry_type)
