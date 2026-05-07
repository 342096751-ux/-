# -*- coding: utf-8 -*-
"""
Streamlit 部署入口：Multi-Agent 审核新界面
- 只保留审核中心，不再显示旧的管理页
- 采用更现代的单页仪表盘式布局
- 便于直接部署到 Streamlit Cloud / deploy
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from audit_system.orchestrator import run_audit_stream

st.set_page_config(page_title="Multi-Agent 审核中心", page_icon="🛡️", layout="wide", initial_sidebar_state="collapsed")

CSS = """
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
.hero {
  border-radius: 24px;
  padding: 24px 24px 18px;
  background: linear-gradient(135deg, rgba(15,23,42,1) 0%, rgba(30,41,59,1) 55%, rgba(15,118,110,1) 100%);
  color: white;
  box-shadow: 0 20px 50px rgba(15,23,42,.18);
}
.hero h1 { font-size: 2rem; margin: 0 0 .25rem 0; }
.hero p { margin: .35rem 0 0 0; opacity: .9; }
.card {
  border-radius: 20px;
  padding: 18px 18px 12px;
  background: white;
  border: 1px solid rgba(148,163,184,.22);
  box-shadow: 0 10px 30px rgba(15,23,42,.06);
}
.small-muted { color: #64748b; font-size: .92rem; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

if "audit_history" not in st.session_state:
    st.session_state.audit_history: list[dict[str, Any]] = []


def render_step_badge(stage: str, detail: str) -> str:
    return f"<div class='card'><b>{stage}</b><div class='small-muted'>{detail}</div></div>"


def run_audit(text: str) -> dict[str, Any]:
    trace_lines: list[str] = []
    final_data: dict[str, Any] | None = None
    for item in run_audit_stream(text):
        stage = str(item.get("阶段名") or "")
        detail = str(item.get("内容") or "")
        trace_lines.append(render_step_badge(stage, detail[:220]))
        if stage == "完成" and isinstance(item.get("数据"), dict):
            final_data = item["数据"]
    return {"trace_html": "".join(trace_lines), "data": final_data}


def page_audit() -> None:
    st.markdown(
        """
        <div class="hero">
          <h1>Multi-Agent 审核中心</h1>
          <p>意图分析 → 工作单元 → 验证器 → 置信度评估 → 仲裁/终审</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([1.35, 0.9])
    with col_left:
        text = st.text_area("待审核内容", height=220, placeholder="在此输入待审文本…")
    with col_right:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("说明")
        st.write("• 只保留新审核中心")
        st.write("• 不再显示旧管理页")
        st.write("• 适合部署展示")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("流程")
        st.write("1. 提交文本")
        st.write("2. 串行跑审核链")
        st.write("3. 展示轨迹与结构化结果")
        st.markdown("</div>", unsafe_allow_html=True)

    run_col, clear_col = st.columns([1, 4])
    with run_col:
        run_clicked = st.button("开始审核", type="primary", use_container_width=True)
    with clear_col:
        if st.button("清空结果", use_container_width=True):
            st.session_state.audit_history = []
            st.rerun()

    if run_clicked:
        if not text.strip():
            st.warning("请输入内容后再审核。")
        else:
            with st.spinner("审核进行中…"):
                result = run_audit(text.strip())
                st.session_state.audit_history.append({"text": text.strip(), **result})

    if st.session_state.audit_history:
        latest = st.session_state.audit_history[-1]
        data = latest.get("data") or {}
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            final_verdict = "-"
            if isinstance(data, dict):
                if data.get("final_decisions"):
                    last = data["final_decisions"][-1]
                    final_verdict = str(last.get("最终判定") or last.get("判定") or last)
                else:
                    final_verdict = str(data.get("intent", {}).get("结论", "-"))
            st.metric("最终裁决", final_verdict)
        with col_b:
            st.metric("审核步骤", len((data.get("execution_trace") or []) if isinstance(data, dict) else []))
        with col_c:
            st.metric("工作单元", len((data.get("findings") or {}) if isinstance(data, dict) else {}))
        with col_d:
            st.metric("仲裁建议", "有" if isinstance(data, dict) and data.get("final_decisions") else "无")

        tab1, tab2, tab3 = st.tabs(["流程轨迹", "结构化结果", "历史记录"])
        with tab1:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown(latest.get("trace_html") or "_无轨迹_", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with tab2:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.json(data)
            st.markdown("</div>", unsafe_allow_html=True)
        with tab3:
            for idx, item in enumerate(reversed(st.session_state.audit_history[-5:]), 1):
                st.write(f"{idx}. {item.get('text','')[:60]}")
                if isinstance(item.get("data"), dict):
                    st.caption(f"裁决: {item['data'].get('final_decisions', [])}")


page_audit()
