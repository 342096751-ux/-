"""
RAG 多路召回：规则 / 判例 / 知识库；所有检索入口均假设入参已为清洗后文本（不再做 clean）。
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

from app.services.rag_service import RAGService


def score_from_distance(row: dict[str, Any]) -> float:
    d = row.get("distance")
    if d is None:
        return 0.75
    try:
        dv = float(d)
        if math.isnan(dv) or dv < 0:
            return 0.75
        return max(0.0, min(1.0, 1.0 / (1.0 + dv)))
    except (TypeError, ValueError):
        return 0.75


def _meta_category(meta: dict[str, Any]) -> str:
    return str(meta.get("分类") or meta.get("category") or "").strip()


_CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    "porn": ("色情", "淫秽", "低俗", "成人", "性"),
    "abuse": ("辱骂", "攻击", "暴力", "仇恨", "歧视"),
    "ad": ("广告", "营销", "导流", "诈骗", "交易"),
    "politics": ("政治", "主权", "国家", "党", "政府"),
}


def _category_match_score(meta_category: str, category: str | None) -> float:
    """category 为英文枚举，meta 往往是中文标签，做软匹配映射。"""
    if not category:
        return 0.0
    cat = str(category).strip().lower()
    mc = str(meta_category or "").strip().lower()
    if not mc:
        return 0.0
    if mc == cat:
        return 1.0
    hints = _CATEGORY_HINTS.get(cat, ())
    for h in hints:
        if h in mc:
            return 0.7
    return 0.0


def _text_has_category_cue(text: str, category: str | None) -> bool:
    if not category:
        return False
    cues = _CATEGORY_HINTS.get(str(category).strip().lower(), ())
    t = str(text or "")
    return any(c in t for c in cues)


def _meta_keywords(meta: dict[str, Any]) -> list[str]:
    raw = meta.get("keywords")
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        return [x.strip() for x in raw.split(",") if x.strip()]
    return []


def _meta_regexes(meta: dict[str, Any]) -> list[str]:
    raw = meta.get("regex_patterns")
    if isinstance(raw, list):
        return [str(x) for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


_PINYIN_MAP: dict[str, str] = {
    "tw": "台湾",
    "zf": "政府",
    "d": "党",
    "zg": "中国",
    "mg": "美国",
    "rb": "日本",
    "hg": "韩国",
    "hs": "黄色",
    "sq": "色情",
    "xp": "性爱",
    "sb": "傻逼",
    "cnm": "草泥马",
    "nm": "尼玛",
    "djb": "大鸡巴",
    "nt": "脑瘫",
    "zz": "智障",
}

_STOP = {
    "一个",
    "今天",
    "非常",
    "真的",
    "然后",
    "什么",
    "怎么",
    "这个",
    "那个",
    "这样",
    "那么",
    "就是",
    "不是",
    "没有",
    "可以",
    "进行",
    "完成",
    "开始",
    "已经",
    "因为",
    "所以",
}


class EnhancedRetriever:
    def __init__(self, rag: RAGService) -> None:
        self._rag = rag

    @staticmethod
    def extract_keywords(text: str) -> str:
        words = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z]{2,}", text or "")
        filtered = [w for w in words if w not in _STOP]
        return " ".join(filtered[:5])

    @staticmethod
    def expand_query(text: str, category: str) -> list[str]:
        expanded: set[str] = set()
        t = text or ""
        cat = (category or "general").strip().lower()

        for abbr, full in _PINYIN_MAP.items():
            if abbr in t:
                expanded.add(t.replace(abbr, full))
                expanded.add(full)

        if cat == "politics":
            if any(w in t for w in ["台湾", "tw", "臺灣", "台独"]):
                expanded.update(["分裂主义", "国家主权", "领土完整", "一中一台"])
            if any(w in t for w in ["政府", "zf", "官员", "领导"]):
                expanded.update(["攻击政府", "诋毁官员", "煽动对立", "公共机构"])
        elif cat == "porn":
            if any(w in t for w in ["色情", "hs", "sq", "黄", "淫秽"]):
                expanded.update(["淫秽内容", "成人内容", "性暗示", "低俗内容", "露骨描述"])
        elif cat == "abuse":
            if any(w in t for w in ["傻逼", "sb", "去死", "废物", "垃圾"]):
                expanded.update(["人身攻击", "辱骂言论", "恶意贬低", "歧视言论", "网络暴力"])
        elif cat == "ad":
            if any(w in t for w in ["微信", "扫码", "免费", "转账", "加我"]):
                expanded.update(["诈骗诱导", "虚假广告", "违禁品交易", "垃圾信息", "诱导分享"])

        return list(expanded)[:3]

    def get_all_rules(self, category: str | None = None) -> list[dict[str, Any]]:
        rows = self._rag.get_all("rule_base")
        out: list[dict[str, Any]] = []
        for r in rows:
            meta = dict(r.get("metadata") or {})
            if category and _category_match_score(_meta_category(meta), category) <= 0.0:
                continue
            rid = str(r.get("id", "") or "")
            doc = str(r.get("document", "") or meta.get("内容", "") or "")
            out.append(
                {
                    "id": rid,
                    "content": doc,
                    "keywords": _meta_keywords(meta),
                    "regex_patterns": _meta_regexes(meta),
                    "severity": str(meta.get("严重度", meta.get("severity", "中")) or "中"),
                    "meta": meta,
                }
            )
        return out

    def _hard_match_vector_rows(self, text: str, category: str | None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        t = text or ""
        text_terms = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z]{2,}", t.lower())
        has_cat_cue = _text_has_category_cue(t, category)
        for rule in self.get_all_rules(category):
            score = 0.0
            mc = _meta_category(rule.get("meta") or {})
            if has_cat_cue and _category_match_score(mc, category) > 0.0:
                score = max(score, 0.91)
            for kw in rule.get("keywords") or []:
                if kw and kw in t:
                    score = max(score, 0.92)
            for pat in rule.get("regex_patterns") or []:
                try:
                    if re.search(pat, t):
                        score = max(score, 0.95)
                except re.error:
                    continue
            if not score and rule.get("content"):
                c = str(rule["content"])
                head = c[: min(48, len(c))]
                if len(head) >= 4 and head in t:
                    score = max(score, 0.88)
                if text_terms and any(term in c.lower() for term in text_terms):
                    score = max(score, 0.90)
            if score > 0:
                out.append(
                    {
                        "id": rule["id"],
                        "document": rule["content"],
                        "metadata": rule.get("meta") or {},
                        "distance": (1.0 / max(score, 1e-6)) - 1.0,
                        "match_type": "keyword_fallback",
                        "score": score,
                    }
                )
        return out

    @staticmethod
    def deduplicate_rule_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: dict[str, dict[str, Any]] = {}
        for r in rows:
            rid = str(r.get("id", "") or "")
            if not rid:
                continue
            base = float(r.get("score", 0.0) or 0.0)
            if not base:
                base = score_from_distance(r) if "distance" in r else 0.7
            mt = str(r.get("match_type", "") or "")
            if mt in ("keyword", "keyword_fallback"):
                final = max(base, 0.92)
            else:
                final = base
            if rid not in seen or final > float(seen[rid].get("_final_score", 0.0)):
                r = dict(r)
                r["_final_score"] = final
                seen[rid] = r
        return sorted(seen.values(), key=lambda x: float(x.get("_final_score", 0.0)), reverse=True)

    def _collect_rule_queries(
        self,
        cleaned_text: str,
        category: str | None,
        *,
        top_k: int,
        expand_n: int,
        extra_expanded: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        cat = category
        all_raw: list[dict[str, Any]] = []

        def qcall(query: str, k: int) -> None:
            if not (query or "").strip():
                return
            for row in self._rag.retrieve_rules(query.strip(), top_k=k):
                row = dict(row)
                row.setdefault("match_type", "vector")
                base = score_from_distance(row)
                mc = _meta_category(dict(row.get("metadata") or {}))
                # 同类目条目轻度提权，避免被无关规则淹没
                if category:
                    base = min(1.0, base + 0.08 * _category_match_score(mc, category))
                row["score"] = base
                all_raw.append(row)

        qcall(cleaned_text, top_k)
        kw = self.extract_keywords(cleaned_text)
        if kw and kw.strip() != cleaned_text.strip():
            qcall(kw, top_k)
        expanded = self.expand_query(cleaned_text, cat or "general")
        if extra_expanded:
            expanded = list(expanded) + list(extra_expanded)
        for q in expanded[:expand_n]:
            if q and q.strip() not in {cleaned_text.strip(), kw.strip()}:
                qcall(q, max(3, top_k - 2))

        deduped = self.deduplicate_rule_rows(all_raw)
        if len(deduped) < 2:
            deduped = self.deduplicate_rule_rows(
                deduped + self._hard_match_vector_rows(cleaned_text, cat)
            )

        return deduped[: max(8, top_k + 3)]

    def retrieve_rules_for_executor(self, cleaned_text: str, category: str | None) -> list[dict[str, Any]]:
        return self._collect_rule_queries(
            cleaned_text, category, top_k=5, expand_n=3, extra_expanded=None
        )

    def retrieve_rules_for_detective(self, cleaned_text: str, category: str | None) -> list[dict[str, Any]]:
        # 与规则执行员保持同标准：top_k=5，扩展查询=3
        return self._collect_rule_queries(
            cleaned_text, category, top_k=5, expand_n=3, extra_expanded=None
        )[:8]

    def retrieve_cases_filtered(
        self,
        cleaned_text: str,
        category: str | None,
        *,
        top_k: int = 5,
        min_similarity: float = 0.55,
        expand_queries: int = 3,
    ) -> list[dict[str, Any]]:
        all_c: list[dict[str, Any]] = []

        def take(query: str, k: int) -> None:
            for row in self._rag.retrieve_cases(query, top_k=k):
                sim = score_from_distance(row)
                meta = dict(row.get("metadata") or {})
                if category and _category_match_score(_meta_category(meta), category) <= 0.0:
                    continue
                if sim + 1e-9 >= min_similarity:
                    rc = dict(row)
                    rc["_sim"] = sim * 0.85
                    all_c.append(rc)

        cat = category
        take(cleaned_text, top_k)
        kw = self.extract_keywords(cleaned_text)
        if kw and kw != cleaned_text.strip():
            take(kw, top_k)
        for q in self.expand_query(cleaned_text, cat or "general")[:expand_queries]:
            if q.strip() not in {cleaned_text.strip(), kw.strip()}:
                take(q, max(3, top_k - 2))

        seen: dict[str, dict[str, Any]] = {}
        for r in all_c:
            rid = str(r.get("id", "") or "")
            if not rid:
                continue
            s = float(r.get("_sim", score_from_distance(r)))
            if rid not in seen or s > float(seen[rid].get("_sim", 0.0)):
                seen[rid] = r
        return sorted(seen.values(), key=lambda x: float(x.get("_sim", 0.0)), reverse=True)[:8]

    def comprehensive_retrieve(
        self,
        cleaned_text: str,
        focus_category: str | None,
        *,
        rules_top_k: int = 10,
        kb_top_k: int = 5,
        cases_top_k: int = 5,
    ) -> dict[str, Any]:
        """大法官：不限制品类时跳过 category 过滤案例/规则 meta。"""
        rules: list[dict[str, Any]] = []
        knowledge: list[dict[str, Any]] = []
        cases: list[dict[str, Any]] = []

        def qr(q: str, k: int) -> None:
            if not q.strip():
                return
            for row in self._rag.retrieve_rules(q, top_k=k):
                rules.append(dict(row))

        def qk(q: str, k: int) -> None:
            if not q.strip():
                return
            for row in self._rag.retrieve_knowledge(q, top_k=k):
                knowledge.append(dict(row))

        def qc(q: str, k: int) -> None:
            if not q.strip():
                return
            for row in self._rag.retrieve_cases(q, top_k=k):
                cases.append(dict(row))

        base = cleaned_text.strip()
        kw = self.extract_keywords(cleaned_text)
        expanded = self.expand_query(cleaned_text, focus_category or "general")

        for q in [base, kw] + expanded[:5]:
            qr(q, rules_top_k)
            qk(q, kb_top_k)
            qc(q, cases_top_k)

        def dedup(lst: list[dict[str, Any]]) -> list[dict[str, Any]]:
            seen: dict[str, dict[str, Any]] = {}
            for item in lst:
                iid = str(item.get("id", "") or "")
                if not iid:
                    continue
                d = item.get("distance")
                try:
                    dist = float(d) if d is not None else 999.0
                except (TypeError, ValueError):
                    dist = 999.0
                if iid not in seen or dist < float(seen[iid].get("distance", 999.0)):
                    it = dict(item)
                    it["distance"] = dist
                    seen[iid] = it
            return sorted(seen.values(), key=lambda x: float(x.get("distance", 999.0)))

        return {
            "rules": dedup(rules)[:rules_top_k],
            "knowledge": dedup(knowledge)[:kb_top_k],
            "cases": dedup(cases)[:cases_top_k],
            "recall_detail": {"keywords": kw, "expanded": expanded[:5]},
        }


def rules_to_compact_text(rules: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for r in rules or []:
        rid = r.get("id") or (r.get("metadata") or {}).get("id") or ""
        doc = r.get("document") or r.get("content") or ""
        lines.append(f"- {rid}: {doc}" if rid else f"- {doc}")
    return "\n".join(lines) or "无匹配规则"


def rows_to_prompt_block(label: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return f"（无{label}）"
    lines: list[str] = []
    for r in rows:
        rid = str(r.get("id", "") or "")
        doc = str(r.get("document", "") or "")
        mt = dict(r.get("metadata") or {})
        meta_s = ""
        if mt:
            meta_s = f" meta={json.dumps(mt, ensure_ascii=False)[:200]}"
        lines.append(f"[{rid}] sim≈{score_from_distance(r):.2f}{meta_s}\n{doc}")
    return "\n\n".join(lines)


def retrieve_bundle_enhanced(
    rag: RAGService,
    restored: str,
    *,
    category: str | None = None,
) -> dict[str, Any]:
    """对抗 Detective：多路召回（规则+案例+知识）。"""
    er = EnhancedRetriever(rag)
    rule_rows = er.retrieve_rules_for_detective(restored, category)
    cases_m = er.retrieve_cases_filtered(
        restored, category, top_k=3, min_similarity=0.60, expand_queries=3
    )
    kb_rows: list[dict[str, Any]] = []
    for row in rag.retrieve_knowledge(restored, top_k=5):
        kb_rows.append(dict(row))
    if len(kb_rows) < 3:
        kw = er.extract_keywords(restored)
        if kw:
            for row in rag.retrieve_knowledge(kw, top_k=5):
                kb_rows.append(dict(row))

    return {
        "rules_rows": rule_rows,
        "cases_rows": cases_m,
        "kb_rows": kb_rows[:10],
        "rules_text": rules_to_compact_text(rule_rows),
        "cases_text": rows_to_prompt_block("案例片段", cases_m),
        "kb_text": rows_to_prompt_block("知识库片段", kb_rows),
    }
