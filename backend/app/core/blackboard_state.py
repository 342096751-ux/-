"""与多 Agent 黑板协作模型对齐的快照视图（便于序列化 / 导出 / 测试）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.blackboard import Blackboard


def _iso_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class BlackboardState:
    """黑板共享状态 — 与各 Agent 读写的运行时 Blackboard 对应（逻辑等价）。"""

    task_id: str
    original_text: str
    category: str
    created_at: str

    cleaned_text: str | None = None
    risk_signals: list[str] = field(default_factory=list)
    was_cleaned: bool = False

    specialist_results: dict[str, Any] = field(default_factory=dict)

    aggregated_verdict: str | None = None
    aggregated_confidence: float = 0.0
    aggregated_reason: str | None = None

    execution_log: list[dict[str, Any]] = field(default_factory=list)
    is_complete: bool = False


def snapshot_from_blackboard(
    blackboard: Blackboard,
    audit_id: str,
    *,
    include_logs: bool = False,
    log_tail: int = 200,
) -> BlackboardState:
    """
    从运行中的 ``Blackboard`` 生成 ``BlackboardState`` 快照。

    - ``cleaned_text`` 优先取自 ``preprocessed_content``，否则 ``content``
    - ``category`` 来自 ``config['category']``，缺省为 ``general``
    - ``aggregated_*``：若流水线已写完 ``final_verdict``，则填入（判词域仍为 violation/normal）
    """
    raw = str(blackboard.get_state(audit_id, "raw_content", "") or "")
    cleaned = str(
        blackboard.get_state(audit_id, "preprocessed_content", "")
        or blackboard.get_state(audit_id, "cleaned_text", "")
        or blackboard.get_state(audit_id, "content", "")
        or ""
    ).strip() or None
    cfg = blackboard.get_state(audit_id, "config", None) or {}
    category = str((cfg.get("category") if isinstance(cfg, dict) else None) or "general")

    risk = blackboard.get_state(audit_id, "risk_signals", [])
    if not isinstance(risk, list):
        risk = []

    fv = blackboard.get_state(audit_id, "final_verdict", None)
    conf = blackboard.get_state(audit_id, "confidence", None)
    state = BlackboardState(
        task_id=audit_id,
        original_text=raw,
        category=category,
        created_at=str(blackboard.get_state(audit_id, "_created_at_iso", _iso_now())),
        cleaned_text=cleaned,
        risk_signals=[str(x) for x in risk],
        was_cleaned=bool(blackboard.get_state(audit_id, "was_cleaned", False)),
        specialist_results=dict(blackboard.get_agent_results(audit_id)),
        aggregated_verdict=str(fv) if fv is not None else None,
        aggregated_confidence=float(conf) if isinstance(conf, (int, float)) else 0.0,
        aggregated_reason=str(blackboard.get_state(audit_id, "final_reason", "") or "") or None,
        is_complete=bool(blackboard.get_state(audit_id, "audit_complete", False)),
    )
    if include_logs:
        logs = blackboard.get_logs(audit_id)[-log_tail:]
        state.execution_log = [
            {
                "timestamp": e.timestamp,
                "agent": e.agent,
                "zone": e.zone,
                "phase": e.phase,
                "content": e.content,
                "data": e.data,
            }
            for e in logs
        ]
    return state
