"""
规则执行员：召回优先 + 初判 + 仅 violation 二次确认。
通过环境变量 RULE_EXECUTOR_PIPELINE=recall_secondary 启用，见 rule_executor.audit_text。
"""

from __future__ import annotations

import json
import math
import os
from typing import Any


def _score_from_distance(row: dict[str, Any]) -> float:
    d = row.get("distance")
    if d is None:
        return 0.75
    try:
        dv = float(d)
        if dv != dv or dv < 0:  # nan
            return 0.75
        return 1.0 / (1.0 + dv)
    except (TypeError, ValueError):
        return 0.75


PRIMARY_JSON_SPEC = """输出必须且只能是合法 JSON，不要用 markdown。
{{
    "verdict": "violation" | "uncertain" | "clean",
    "confidence": 0.0,
    "reason": "简短理由，尽量引用下方资料中的规则 id",
    "matched_rules": [
        {{"rule_id": "规则ID字符串", "matched_text": "与内容相关的简短片段"}}

    ]

}}
"""

PRIMARY_PROMPT = """你是内容安全规则执行员的初筛组件。

【已检索到的资料（规则 + 可选历史案例摘要）】
{items_block}

判定原则：
1. violation：明显违反规则或语义上明确违规。命中规则是充分条件但不是必要条件
2. uncertain：模糊、擦边、无法确认时选此项
3. clean：与本安全域无关、明显正常

约束：
- 参考资料是辅助，你的语义理解也可独立形成违规判断
- 若语义明显违规但资料未覆盖，仍应标 violation（置信度可下调）
- uncertain 只用于“真的不确定”，不能因“未命中规则”而使用
- 尽量引用规则ID；无规则可引时 matched_rules 可为空，但 reason 需引用文本证据片段

""" + PRIMARY_JSON_SPEC


SECONDARY_JSON_SPEC = """输出必须且只能是合法 JSON。
{{
    "verdict": "confirmed" | "overruled" | "uncertain",
    "confidence": 0.0,
    "reason": "复核一句话理由"
}}

"""

SECONDARY_PROMPT = """你是复核审查引擎：防止初筛误判。

初筛结论：violation
初筛置信度：{primary_conf:.2f}
初筛理由：{primary_reason}
命中规则条目：
{matches_text}

参考资料（同初筛）：
{items_block}

复核原则：
1. confirmed：确实违规，无讽刺/引用/科普等豁免语境
2. overruled：字面命中但语境明显不构成违规（反讽、纯引用、中性讨论等）
3. uncertain：仍无法定论

约束：
- 不能因为“资料未覆盖”就推翻明显违规
- uncertain 只能用于复核后仍无法确认

""" + SECONDARY_JSON_SPEC


def _format_materials(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "（未检索到规则或案例。）"
    lines: list[str] = []
    for r in rows:
        kind = str(r.get("kind", "rule")).lower()
        tag = "规则" if kind == "rule" else "案例"
        rid = str(r.get("id", ""))
        sim = float(r.get("relevance_score", 0.0))
        doc = str(r.get("document", "") or "")
        meta = r.get("metadata") or {}
        cat = ""
        if isinstance(meta, dict) and meta.get("category"):
            cat = str(meta.get("category"))
        head = f"【{tag}】 {rid}"
        if cat:
            head += f" [分类:{cat}]"
        lines.append(f"{head} 相关度:{sim:.2f}\n{doc}")
    return "\n\n".join(lines)


def _retrieve_mixed(
    text: str,
    rag_service: Any,
    *,
    rules_k: int,
    cases_k: int,
    case_min_sim: float,
    category: str | None = None,
) -> list[dict[str, Any]]:
    from app.services.enhanced_rag import EnhancedRetriever

    er = EnhancedRetriever(rag_service)
    merged: list[dict[str, Any]] = []

    for r in er.retrieve_rules_for_executor(text, category)[: max(rules_k + 8, 12)]:
        rid = str(r.get("id", "") or "")
        doc = str(r.get("document", "") or "")
        merged.append(
            {
                "id": rid,
                "kind": "rule",
                "document": doc,
                "metadata": dict(r.get("metadata") or {}),
                "relevance_score": float(r.get("_final_score", _score_from_distance(r))),
            }
        )

    for c in er.retrieve_cases_filtered(
        text,
        category,
        top_k=max(cases_k, 5),
        min_similarity=case_min_sim,
        expand_queries=3,
    ):
        sim = float(c.get("_sim", _score_from_distance(c)))
        if sim + 1e-9 < case_min_sim:
            continue
        rid = str(c.get("id", "") or "")
        doc = str(c.get("document", "") or "")
        merged.append(
            {
                "id": rid,
                "kind": "case",
                "document": doc,
                "metadata": dict(c.get("metadata") or {}),
                "relevance_score": max(0.0, sim * 0.90),
            }
        )

    merged.sort(key=lambda x: float(x.get("relevance_score", 0.0)), reverse=True)
    max_items = int(os.getenv("RULE_RECALL_MERGE_TOP", "8") or "8")
    return merged[: max(3, max_items)]


def _extract_json(raw: str) -> dict[str, Any]:
    r = (raw or "").strip()
    if not r:
        return {}
    if "```" in r:
        if "```json" in r:
            r = r.split("```json", 1)[1]
        elif "```" in r:
            r = r.split("```", 1)[1]
        r = r.split("```", 1)[0] if "```" in r else r
        r = r.strip()
    try:
        o = json.loads(r)
        return o if isinstance(o, dict) else {}
    except json.JSONDecodeError:
        return {}


def _flatten_matched_for_evidence(matched: Any) -> list[str]:
    out: list[str] = []
    if not matched:
        return out
    for x in matched:
        if isinstance(x, dict):
            rid = x.get("rule_id") or x.get("id")
            if rid is not None and str(rid).strip():
                out.append(str(rid).strip())
        elif str(x).strip():
            out.append(str(x).strip())
    return out


async def audit_text_recall_secondary(
    text: str,
    *,
    rag_service: Any,
    llm_client: Any,
    rules_top_k: int = 5,
    cases_top_k: int = 3,
    case_min_similarity: float = 0.60,
    category: str | None = None,
    return_trace: bool = True,
) -> dict[str, Any]:
    """
    R1 混合检索 → R2 初判（clean/uncertain/violation）→ 仅 violation 时 R3 复核。
    对外输出与 audit_text 相同字段结构（verdict ∈ violation|normal|uncertain）。
    """
    merged = _retrieve_mixed(
        text,
        rag_service,
        rules_k=rules_top_k,
        cases_k=cases_top_k,
        case_min_sim=case_min_similarity,
        category=category,
    )
    from app.services.enhanced_rag import EnhancedRetriever

    raw_rules_docs = EnhancedRetriever(rag_service).retrieve_rules_for_executor(text, category)[
        :rules_top_k
    ]

    primary_prompt = PRIMARY_PROMPT.format(items_block=_format_materials(merged))
    llm1 = await llm_client.complete(
        system_prompt="你是严格的内容安全审核员，只输出 JSON。",
        user_prompt=f"{primary_prompt}\n\n---\n【待审核内容】\n{text}",
        use_strong_model=False,
        return_trace=return_trace,
        temperature=0.15,
    )
    raw1 = llm1.get("output_text", "") if isinstance(llm1, dict) else str(llm1)
    tr1 = llm1.get("trace", {}) if isinstance(llm1, dict) else {}
    p1 = _extract_json(raw1)

    raw_verdict = str(p1.get("verdict", "uncertain") or "uncertain").lower()
    if raw_verdict == "clean":
        pv = "normal"
    elif raw_verdict in ("violation", "uncertain"):
        pv = raw_verdict if raw_verdict == "violation" else "uncertain"
    else:
        pv = "uncertain"

    conf_primary = float(p1.get("confidence", 0.55) or 0.55)
    if math.isnan(conf_primary):
        conf_primary = 0.55
    conf_primary = max(0.0, min(1.0, conf_primary))

    matched = p1.get("matched_rules", []) or []
    flat_ids = _flatten_matched_for_evidence(matched)
    reason_p = str(p1.get("reason", "") or "初判输出").strip()

    secondary_raw_output = ""
    secondary_trace: dict[str, Any] = {}
    sec_verdict: str | None = None
    pipeline_stage = "primary_only"

    final_verdict = pv if pv != "normal" else "normal"
    final_confidence = conf_primary
    reason_out = reason_p
    need_knowledge = False

    if pv == "violation":
        matches_text = "\n".join(
            f"- {m.get('rule_id','?')}: 「{m.get('matched_text','')}」"
            if isinstance(m, dict)
            else f"- {m}"
            for m in (matched if isinstance(matched, list) else [])
        )
        sp = SECONDARY_PROMPT.format(
            primary_conf=conf_primary,
            primary_reason=reason_p,
            matches_text=matches_text or "（未解析到结构化命中条目）",
            items_block=_format_materials(merged),
        )
        llm2 = await llm_client.complete(
            system_prompt="你是严格的内容安全复核员，只输出 JSON。",
            user_prompt=f"{sp}\n\n---\n【待复核正文】\n{text}",
            use_strong_model=True,
            return_trace=return_trace,
            temperature=0.1,
        )
        secondary_raw_output = llm2.get("output_text", "") if isinstance(llm2, dict) else str(llm2)
        secondary_trace = llm2.get("trace", {}) if isinstance(llm2, dict) else {}
        p2 = _extract_json(secondary_raw_output)
        sv = str(p2.get("verdict", "uncertain") or "uncertain").lower()
        sec_verdict = sv
        conf_s = float(p2.get("confidence", 0.5) or 0.5)
        reason_s = str(p2.get("reason", "") or "").strip()
        pipeline_stage = "full_pipeline"

        if sv == "confirmed":
            final_verdict = "violation"
            final_confidence = (conf_primary + max(0.0, min(1.0, conf_s))) / 2.0
            reason_out = f"初判: {reason_p} | 复核: {reason_s}".strip()
        elif sv == "overruled":
            final_verdict = "normal"
            final_confidence = 0.55
            reason_out = f"初判违规后经复核推翻: {reason_s}".strip()
        else:
            final_verdict = "uncertain"
            final_confidence = max(0.35, min(0.62, (conf_primary + max(0.0, min(1.0, conf_s))) / 2.0))
            reason_out = f"初判违规但复核仍存疑 | 复核: {reason_s}".strip()

    meta = {
        "pipeline": "recall_secondary",
        "pipeline_stage": pipeline_stage,
        "primary_verdict_raw": raw_verdict,
        "secondary_verdict": sec_verdict,
        "merged_retrieval_len": len(merged),
        "matched_rules_detail": matched,
        "trace_primary": tr1,
        "raw_primary": raw1,
        "trace_secondary": secondary_trace,
        "raw_secondary": secondary_raw_output,
    }

    return {
        "verdict": final_verdict,
        "need_knowledge": need_knowledge,
        "matched_rules": flat_ids,
        "reasoning": reason_out[:800],
        "reason": reason_out[:800],
        "confidence": float(final_confidence),
        "kb_results": [],
        "_meta": meta,
        "_rules": raw_rules_docs,
    }


def is_recall_secondary_enabled() -> bool:
    v = (os.getenv("RULE_EXECUTOR_PIPELINE") or "").strip().lower()
    return v in {"recall_secondary", "secondary_v1", "1", "true", "yes"}
