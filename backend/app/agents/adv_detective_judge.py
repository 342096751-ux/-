"""
对抗侦探 V4：V0/V1 后进入完整流程
V2 检索（rule+case+knowledge）→ V3 初判（含 need_knowledge）
→ [V4/V5 知识库补充判定] → 输出。
"""

from __future__ import annotations

import math
from typing import Any

from app.agents.rule_executor import _extract_json
from app.services.enhanced_rag import retrieve_bundle_enhanced

_CATEGORY = "通用"


def _sim(row: dict[str, Any]) -> float:
    d = row.get("distance")
    if d is None:
        return 0.76
    try:
        dv = float(d)
        if math.isnan(dv):
            return 0.76
        return max(0.0, min(1.0, 1.0 / (1.0 + dv)))
    except (TypeError, ValueError):
        return 0.76


def retrieve_bundle(rag_service: Any, restored: str, *, category: str | None = None) -> dict[str, Any]:
    """多路召回（清洗后文本）；category 取自对抗管线或运行时配置。"""
    return retrieve_bundle_enhanced(rag_service, restored, category=category or _CATEGORY)


PRIMARY_PROMPT = """你是「变体检测与合规判定引擎」。

类目（仅标注）: {category}

原始文本：
{original}

还原后文本（预处理引擎产出）：
{restored}

【检索到的规则条文】
{rules_text}

【检索到的相近案例摘要】
{cases_text}

【检索到的相关知识库条目】
{kb_text}

判定（仅用 violation / uncertain / clean）：
- violation：还原后文本语义明确违规。命中规则是充分条件但不是必要条件
- uncertain：还原后文本模糊、擦边、无法确认
- clean：还原后文本明显无关，不构成违规

重要约束：
- 判断基于“还原文本”语义，而不是变体手段本身
- 参考资料是辅助，你的语义理解也是判断依据
- 若语义明显违规但规则未覆盖，仍判 violation（置信度可在 0.70~0.85）
- uncertain 不能用于“我知道违规但规则没命中”
- matched_rules 可为空，但 reason 需引用文本证据片段

知识库需求判断：
- need_knowledge=true：初判依据不足，需知识库背景补充
- need_knowledge=false：已有信息足够判断

仅输出合法 JSON，勿 markdown：
{{
  "verdict": "violation" | "uncertain" | "clean",
  "need_knowledge": true | false,
  "confidence": 0.0,
  "reason": "50字内",
  "matched_rules": [{{ "rule_id": "xxx", "matched_text": "片段" }}]
}}
"""


SECONDARY_PROMPT = """你是知识库补充判定引擎。

类目: {category}
原始：
{original}
还原：
{restored}

初判:
- verdict: {pv}
- confidence: {pc:.2f}
- reason: {pr}
- matched_rules:
{matches}

检索资料：
【规则与案例】
{rules_and_cases}
【知识】
{kb_text}

判定原则：
1) violation：结合知识库后可确认违规
2) uncertain：知识补充后仍无法确认
3) clean：知识补充后可确认不违规

输出 JSON：
{{
  "verdict": "violation" | "uncertain" | "clean",
  "confidence": 0.0,
  "reason": "50字内",
  "knowledge_references": ["KNOW-001"]
}}
"""


async def run_adversarial_judge_rounds(
    *,
    original: str,
    restored: str,
    transformations: list[str],
    rag_service: Any,
    llm: Any,
    category: str | None = None,
) -> dict[str, Any]:
    cat = (category or _CATEGORY).strip() or _CATEGORY
    bundle = retrieve_bundle(rag_service, restored, category=cat)
    u1 = PRIMARY_PROMPT.format(
        category=cat,
        original=original,
        restored=restored,
        rules_text=bundle["rules_text"],
        cases_text=bundle["cases_text"],
        kb_text=bundle["kb_text"],
    )
    r1 = await llm.complete(
        system_prompt="你是严格的安全审核助手，仅输出 JSON。",
        user_prompt=u1,
        use_strong_model=False,
        return_trace=True,
        temperature=0.12,
    )
    raw1 = r1.get("output_text", "") if isinstance(r1, dict) else str(r1)
    p1 = _extract_json(raw1)
    vr = str(p1.get("verdict", "uncertain")).lower()
    pv_map = {"clean": "normal", "violation": "violation", "uncertain": "uncertain"}.get(vr, "uncertain")

    mc = float(p1.get("confidence", 0.55) or 0.55)
    if math.isnan(mc):
        mc = 0.55
    mc = max(0.0, min(1.0, mc))
    mr = p1.get("matched_rules") or []

    need_knowledge = bool(p1.get("need_knowledge", False))
    sec_raw = ""
    sv: str | None = None
    sc = 0.5
    stage = "primary_only"

    if need_knowledge:
        matches = "\n".join(
            f"- {m.get('rule_id', m) if isinstance(m, dict) else m}" for m in (mr if isinstance(mr, list) else [])
        )
        u2 = SECONDARY_PROMPT.format(
            category=cat,
            original=original,
            restored=restored,
            rules_and_cases=f"{bundle['rules_text']}\n\n{bundle['cases_text']}",
            kb_text=bundle["kb_text"],
            pv=vr,
            pc=mc,
            pr=str(p1.get("reason", ""))[:400],
            matches=matches or "（无）",
        )
        r2 = await llm.complete(
            system_prompt="你是严格的安全审核助手，仅输出 JSON。",
            user_prompt=u2,
            use_strong_model=True,
            return_trace=True,
            temperature=0.08,
        )
        sec_raw = r2.get("output_text", "") if isinstance(r2, dict) else str(r2)
        p2 = _extract_json(sec_raw)
        sv = str(p2.get("verdict", "uncertain")).lower()
        sc = float(p2.get("confidence", 0.5) or 0.5)
        stage = "full_pipeline"

        if sv == "violation":
            final_v = "violation"
            final_c = max(0.0, min(1.0, (mc + max(0.0, min(1.0, sc))) / 2.0))
            reason = f"初判后知识库补充确认违规: {p2.get('reason', '')}"[:900]
        elif sv == "clean":
            final_v = "normal"
            final_c = 0.55
            reason = f"初判后知识库补充认为不违规: {p2.get('reason', '')}"[:900]
        else:
            final_v = "uncertain"
            final_c = max(0.35, min(0.70, (mc + max(0.0, min(1.0, sc))) / 2.0))
            reason = f"初判后知识库补充仍存疑: {p2.get('reason', '')}"[:900]
    else:
        final_v = "normal" if pv_map == "normal" else "uncertain"
        final_c = mc
        reason = str(p1.get("reason", ""))[:900]
        sec_raw = ""
        sv = None

    return {
        "verdict": final_v,
        "confidence": float(final_c),
        "reason": reason,
        "primary_verdict": vr,
        "secondary_verdict": sv,
        "need_knowledge": need_knowledge,
        "knowledge_used": stage == "full_pipeline",
        "matched_rules": mr,
        "transformations": transformations,
        "retrieved_count": len(bundle["rules_rows"]) + len(bundle["cases_rows"]) + len(bundle["kb_rows"]),
        "stage": stage,
        "raw_primary": raw1,
        "raw_secondary": sec_raw,
        "bundle_meta": {
            "rules_n": len(bundle["rules_rows"]),
            "cases_n": len(bundle["cases_rows"]),
            "kb_n": len(bundle["kb_rows"]),
        },
    }
