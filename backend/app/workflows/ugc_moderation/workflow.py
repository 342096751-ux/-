from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
import sys

from fastapi import HTTPException

from ...schemas import (
    AgentDefinition,
    RunArtifacts,
    TraceEvent,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowGraph,
    WorkflowNode,
    WorkflowRunResponse,
)
from ...store import InMemoryPlaygroundStore

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from audit_system.orchestrator import run_audit_stream  # noqa: E402
from audit_system.work_units_loader import list_work_unit_graph_rows  # noqa: E402

WORKFLOW_NODE_INTENT = "intent_analyst"
WORKFLOW_NODE_VERIFIER = "verifier"
WORKFLOW_NODE_ARBITER = "arbiter"


def event(
    event_type: str,
    title: str,
    detail: str,
    **payload: object,
) -> TraceEvent:
    return TraceEvent(type=event_type, title=title, detail=detail, payload=payload)


def build_ugc_moderation_graph(
    workflow: WorkflowDefinition,
    _agents: list[AgentDefinition],
) -> WorkflowGraph:
    """与 work_units_config.yaml 中的工作单元一致，节点 id 为 audit_{domain}。"""
    unit_rows = list_work_unit_graph_rows()
    wu_ids: list[str] = []
    wu_nodes: list[WorkflowNode] = []
    for row in unit_rows:
        wu_ids.append(row["node_id"])
        wu_nodes.append(
            WorkflowNode(
                id=row["node_id"],
                label=row["name"],
                kind="agent",
                caption="工作单元",
            )
        )
    if not wu_ids:
        wu_ids = ["audit_politics", "audit_sexual"]
        wu_nodes = [
            WorkflowNode(id="audit_politics", label="政治审核员", kind="agent", caption="工作单元"),
            WorkflowNode(id="audit_sexual", label="色情审核员", kind="agent", caption="工作单元"),
        ]
    nodes: list[WorkflowNode] = [
        WorkflowNode(id="start", label="开始", kind="start"),
        WorkflowNode(
            id=WORKFLOW_NODE_INTENT,
            label="意图分析",
            kind="logic",
            caption="分析意图与风险",
        ),
        *wu_nodes,
        WorkflowNode(
            id=WORKFLOW_NODE_VERIFIER,
            label="验证器",
            kind="logic",
            caption="质询与挑错",
        ),
        WorkflowNode(
            id=WORKFLOW_NODE_ARBITER,
            label="仲裁者",
            kind="final",
            caption="拦截 / 放行 / 记录",
        ),
        WorkflowNode(id="end", label="结束", kind="end"),
    ]
    edges: list[WorkflowEdge] = [WorkflowEdge(source="start", target=WORKFLOW_NODE_INTENT)]
    for wid in wu_ids:
        edges.append(WorkflowEdge(source=WORKFLOW_NODE_INTENT, target=wid))
    for wid in wu_ids:
        edges.append(WorkflowEdge(source=wid, target=WORKFLOW_NODE_VERIFIER))
    edges.extend(
        [
            WorkflowEdge(source=WORKFLOW_NODE_VERIFIER, target=WORKFLOW_NODE_ARBITER),
            WorkflowEdge(source=WORKFLOW_NODE_ARBITER, target="end"),
        ]
    )
    return WorkflowGraph(nodes=nodes, edges=edges)


def run_ugc_moderation(
    _store: InMemoryPlaygroundStore,
    workflow: WorkflowDefinition,
    user_input: str,
    history: list[dict[str, str]] | None = None,
    on_event: Callable[[TraceEvent], None] | None = None,
) -> WorkflowRunResponse:
    del history
    trace: list[TraceEvent] = []
    final_payload: dict | None = None

    def push(item: TraceEvent) -> None:
        trace.append(item)
        if on_event is not None:
            on_event(item)

    unit_rows = list_work_unit_graph_rows()

    def resolve_node(stage_name: str) -> str:
        s = str(stage_name)
        if s in {"启动", "开始"} or s.startswith("启动"):
            return "start"
        if s.startswith("意图分析"):
            return WORKFLOW_NODE_INTENT
        if "工作单元激活" in s or s == "工作单元激活":
            return WORKFLOW_NODE_INTENT
        if s.startswith("工作单元-"):
            for r in unit_rows:
                if r["domain"] in s:
                    return r["node_id"]
            return unit_rows[0]["node_id"] if unit_rows else "audit_politics"
        if s.startswith("验证器"):
            return WORKFLOW_NODE_VERIFIER
        if s.startswith("回应-"):
            for r in unit_rows:
                if r["domain"] in s:
                    return r["node_id"]
            return WORKFLOW_NODE_VERIFIER
        if s.startswith("仲裁") or s.startswith("完成"):
            return WORKFLOW_NODE_ARBITER
        return WORKFLOW_NODE_INTENT

    push(event("run_started", "Run Started", "UGC 审核流程开始。", workflow_id=workflow.id))
    try:
        for update in run_audit_stream(user_input):
            stage_name = str(update.get("阶段名") or "处理中")
            detail = str(update.get("内容") or "")
            payload = update.get("数据") or {}
            node_id = resolve_node(stage_name)
            push(
                event(
                    "state_updated",
                    stage_name,
                    detail[:260],
                    node_id=node_id,
                    stage=stage_name,
                    stage_data=payload,
                    at=update.get("时间戳"),
                )
            )
            if stage_name == "完成" and isinstance(payload, dict):
                final_payload = payload
    except Exception as error:  # noqa: BLE001
        message = str(error) or "UGC 审核流程执行失败"
        raise HTTPException(status_code=400, detail=message) from error

    final_payload = final_payload or {}
    intent_result = final_payload.get("intent") or {}
    findings = final_payload.get("findings") or {}
    final_decisions = final_payload.get("final_decisions") or []
    final_action = "放行"
    final_judgement = "安全"
    if isinstance(final_decisions, list) and final_decisions:
        first = final_decisions[0] if isinstance(final_decisions[0], dict) else {}
        final_action = str(first.get("执行动作") or final_action)
        final_judgement = str(first.get("最终判定") or final_judgement)
    et = final_payload.get("execution_trace") if isinstance(final_payload, dict) else None
    ms = (final_payload.get("mermaid_sequential") or "") if isinstance(final_payload, dict) else ""
    mp = (final_payload.get("mermaid_pipeline") or "") if isinstance(final_payload, dict) else ""
    final_report = {
        "意图标签": intent_result.get("意图标签", []),
        "工作单元结果": findings,
        "仲裁结果": final_decisions,
        "最终执行动作": final_action,
        "最终判定": final_judgement,
        "执行轨迹": et if et is not None else [],
        "流程图Mermaid_管线": mp,
        "流程图Mermaid_顺序": ms,
    }
    final_text = json.dumps(final_report, ensure_ascii=False, indent=2)
    push(event("run_finished", "Run Finished", "UGC 审核流程已完成。", final_report=final_report))

    return WorkflowRunResponse(
        workflow_id=workflow.id,
        user_input=user_input,
        assistant_message=final_text,
        trace=trace,
        graph=build_ugc_moderation_graph(workflow, []),
        artifacts=RunArtifacts(
            route_agent_id=None,
            route_agent_name="UGC Moderation",
            route_reason="intent -> work_unit -> verifier -> arbiter",
            specialist_answer=json.dumps(findings, ensure_ascii=False)[:800],
            final_answer=final_action,
        ),
    )
