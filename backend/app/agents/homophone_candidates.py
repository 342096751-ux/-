from __future__ import annotations

import re
from typing import Any

# 谐音词候选表：只做弱语义映射，不做强制还原
HOMOPHONE_CANDIDATES: dict[str, list[str]] = {
    "sha": ["杀", "傻", "沙"],
    "si": ["死", "四", "私"],
    "cao": ["草", "操", "槽"],
    "ni": ["你", "尼", "泥"],
    "ma": ["妈", "吗", "马"],
    "la": ["了", "拉", "辣"],
    "wan": ["玩", "完", "弯"],
    "ban": ["办", "板", "半"],
    "zhong": ["中", "种", "忠"],
    "guo": ["国", "过", "果"],
}

# 汉字谐音规避表达：用于高风险规避表达识别，不做日常宽松映射
PHRASE_HOMOPHONE_MAP: dict[str, list[str]] = {
    "拔韭留丝": ["八九六四", "8964"],
    "八九六四": ["拔韭留丝"],
}

PUNCT_RE = re.compile(r"[，。！？,.!?；;：:、\s]+")


def tokenize_context(text: str) -> list[str]:
    return [tok for tok in PUNCT_RE.split(text or "") if tok]


def has_context_support(text: str) -> bool:
    t = text or ""
    return any(k in t for k in ["威胁", "攻击", "暴力", "杀", "死", "违法", "违规", "敏感", "煽动", "分裂", "对抗"])


def score_candidate(candidate: str, context: str) -> float:
    score = 0.0
    if candidate in context:
        score += 0.55
    if any(k in context for k in [candidate, candidate[:1]]):
        score += 0.15
    if has_context_support(context):
        score += 0.2
    if len(tokenize_context(context)) > 1:
        score += 0.1
    return min(score, 1.0)


def build_homophone_candidates(token: str, context: str) -> list[dict[str, Any]]:
    key = (token or "").strip().lower()
    cands = HOMOPHONE_CANDIDATES.get(key, [])
    scored = []
    for cand in cands:
        scored.append({"token": token, "candidate": cand, "score": score_candidate(cand, context)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def build_phrase_homophone_candidates(text: str, context: str) -> list[dict[str, Any]]:
    raw = text or ""
    out: list[dict[str, Any]] = []
    for phrase, cands in PHRASE_HOMOPHONE_MAP.items():
        if phrase in raw:
            scored = []
            for cand in cands:
                scored.append({"token": phrase, "candidate": cand, "score": score_candidate(cand, context)})
            scored.sort(key=lambda x: x["score"], reverse=True)
            out.append({"phrase": phrase, "candidates": scored})
    return out


def should_participate_for_homophone(token: str, context: str) -> tuple[bool, float, str, list[dict[str, Any]]]:
    candidates = build_homophone_candidates(token, context)
    if not candidates:
        return False, 0.0, "无候选映射", []
    top = candidates[0]
    if len(candidates) >= 2 and abs(top["score"] - candidates[1]["score"]) < 0.12:
        return False, top["score"], "多个候选竞争接近，歧义过高", candidates
    if top["score"] < 0.35:
        return False, top["score"], "缺乏上下文支撑", candidates
    return True, top["score"], "候选语义稳定且上下文支持", candidates
