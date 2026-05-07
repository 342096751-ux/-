from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from app.models.audit import AuditResult

RunAudit = Callable[[str, str, str], Awaitable[AuditResult]]


def _verdict_display(v: Any) -> str:
    if v is None:
        return "-"
    s = str(v).strip()
    zh = {
        "violation": "违规",
        "normal": "正常",
        "uncertain": "疑似",
        "not_participate": "不参与",
        "not_participating": "不参与",
    }
    return zh.get(s, s or "-")


def _pack_agent(ar: dict[str, Any], name: str) -> dict[str, Any]:
    x = ar.get(name) or {}
    return {
        "verdict": _verdict_display(x.get("verdict")),
        "confidence": x.get("confidence", "-"),
        "reason": ((x.get("reason") or "") or "")[:500],
    }


def _empty_agents() -> dict[str, dict[str, Any]]:
    empty = {"verdict": "-", "confidence": "-", "reason": ""}
    return {
        "rule_executor": dict(empty),
        "adversarial_detective": dict(empty),
        "case_executor": dict(empty),
        "chief_judge": dict(empty),
    }


class BatchAuditManager:
    """内存批量任务：并发审核 Excel 行，结果按行序占位更新。"""

    def __init__(
        self,
        run_audit: RunAudit,
        *,
        discard_audit: Callable[[str], None] | None = None,
    ) -> None:
        self._run_audit = run_audit
        self._discard_audit = discard_audit
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create_and_start(
        self,
        rows: list[dict[str, str]],
        concurrency: int,
        strategy: str,
    ) -> str:
        task_id = uuid.uuid4().hex[:12]
        n = len(rows)
        results: list[dict[str, Any]] = [
            {"id": r["id"], "content": r["content"], "status": "pending"}
            for r in rows
        ]
        self._tasks[task_id] = {
            "created_at": time.time(),
            "created_at_iso": datetime.now().isoformat(),
            "total": n,
            "task_status": "running",
            "results": results,
            "concurrency": concurrency,
            "strategy": strategy,
        }
        asyncio.create_task(self._run_all(task_id, rows, concurrency, strategy))
        return task_id

    def get_status(self, task_id: str) -> dict[str, Any] | None:
        t = self._tasks.get(task_id)
        if not t:
            return None
        results = t["results"]
        completed = sum(1 for r in results if r.get("status") == "completed")
        failed = sum(1 for r in results if r.get("status") == "failed")
        pending = sum(1 for r in results if r.get("status") == "pending")
        total = t["total"]
        done = completed + failed
        percent = int((done / total) * 100) if total > 0 else 0
        ts = t["task_status"]
        if ts == "completed":
            message = f"审核完成！成功 {completed}，失败 {failed}"
        elif ts == "failed":
            message = "任务执行异常"
        else:
            message = "审核中..."
        return {
            "task_id": task_id,
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "remaining": pending,
            "percent": percent,
            "status": ts,
            "message": message,
            "created_at": t.get("created_at_iso", ""),
            "concurrency": t["concurrency"],
            "strategy": t["strategy"],
        }

    def get_results(self, task_id: str) -> list[dict[str, Any]] | None:
        t = self._tasks.get(task_id)
        if not t:
            return None
        return t["results"]

    def _build_completed(self, row: dict[str, str], audit: AuditResult) -> dict[str, Any]:
        ar = audit.agent_results
        return {
            "id": row["id"],
            "content": row["content"],
            "status": "completed",
            "rule_executor": _pack_agent(ar, "rule_executor"),
            "adversarial_detective": _pack_agent(ar, "adversarial_detective"),
            "case_executor": _pack_agent(ar, "case_executor"),
            "chief_judge": _pack_agent(ar, "chief_judge"),
            "final_result": _verdict_display(audit.final_verdict),
            "final_confidence": audit.confidence,
            "error": "",
        }

    def _build_failed(self, row: dict[str, str], err: str) -> dict[str, Any]:
        agents = _empty_agents()
        return {
            "id": row["id"],
            "content": row["content"],
            "status": "failed",
            **agents,
            "final_result": "-",
            "final_confidence": "-",
            "error": err[:2000],
        }

    async def _run_all(
        self,
        task_id: str,
        rows: list[dict[str, str]],
        concurrency: int,
        strategy: str,
    ) -> None:
        sem = asyncio.Semaphore(concurrency)

        async def one(idx: int, row: dict[str, str]) -> None:
            aid = f"batch-{task_id}-{idx}-{uuid.uuid4().hex[:8]}"
            try:
                async with sem:
                    result = await self._run_audit(aid, row["content"], strategy)
                item = self._build_completed(row, result)
            except Exception as exc:
                item = self._build_failed(row, str(exc))
            finally:
                if self._discard_audit:
                    try:
                        self._discard_audit(aid)
                    except Exception:
                        pass

            async with self._lock:
                tt = self._tasks.get(task_id)
                if not tt:
                    return
                tt["results"][idx] = item
                results = tt["results"]
                if all(r.get("status") != "pending" for r in results):
                    tt["task_status"] = "completed"

        try:
            await asyncio.gather(*[one(i, row) for i, row in enumerate(rows)])
        except Exception:
            async with self._lock:
                tt = self._tasks.get(task_id)
                if tt and tt["task_status"] == "running":
                    tt["task_status"] = "failed"
