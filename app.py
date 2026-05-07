# -*- coding: utf-8 -*-
"""
Streamlit 部署入口：Multi-Agent 审核新界面
- 保留现有可运行的 audit_system 审核逻辑
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

from audit_system import agent_manager
from audit_system.orchestrator import run_audit_stream

st.set_page_config(page_title="Multi-Agent 审核中心", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")

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

    top1, top2, top3 = st.columns([1.3, 1, 1])
    with top1:
        text = st.text_area("待审核内容", height=220, placeholder="在此输入待审文本…")
    with top2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("快速说明")
        st.write("• 保留当前可运行逻辑")
        st.write("• 使用单页仪表盘展示")
        st.write("• 适合直接部署到 Streamlit Cloud")
        st.markdown("</div>", unsafe_allow_html=True)
    with top3:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("当前配置")
        st.write("配置文件", agent_manager.get_config_path().name)
        st.write("提示词目录", agent_manager.PROMPTS_DIR.name)
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
            st.metric("最终裁决", str((data.get("final_decisions") or ["-"])[-1] if isinstance(data, dict) else "-"))
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


def page_agents() -> None:
    st.markdown(
        """
        <div class="hero">
          <h1>Agent 工作单元管理</h1>
          <p>维护 work_units_config.yaml 与 prompts/ 下的提示词文件</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    agent_manager.ensure_default_config()
    cfg = agent_manager.load_units_config()
    units: list = list(cfg.get("units", []))

    st.subheader("已注册的工作单元")
    for i, u in enumerate(units):
        if not isinstance(u, dict):
            continue
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([2.2, 1.4, 2.2, 1, 1])
            with c1:
                st.write(f"**{u.get('name','')}**")
                st.caption(u.get("prompt_file", ""))
            with c2:
                st.code(u.get("domain", "—"), language=None)
            with c3:
                st.write("启用状态", "是" if u.get("enabled", True) else "否")
            with c4:
                if st.button("编辑", key=f"ed_{i}"):
                    st.session_state[f"editing_{i}"] = True
            with c5:
                if st.button("删除", key=f"rm_{i}"):
                    agent_manager.remove_agent(i)
                    st.rerun()

            if st.session_state.get(f"editing_{i}"):
                bn = agent_manager.basename_from_prompt_file(str(u.get("prompt_file", "")))
                cur = agent_manager.read_prompt_file(bn)
                new_text = st.text_area(f"提示词：{u.get('name','')}", value=cur, height=260, key=f"ta_{i}")
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("保存", key=f"sv_{i}"):
                        agent_manager.write_prompt_file(bn, new_text)
                        st.session_state[f"editing_{i}"] = False
                        st.rerun()
                with b2:
                    if st.button("取消", key=f"cl_{i}"):
                        st.session_state[f"editing_{i}"] = False
                        st.rerun()

    st.divider()
    st.subheader("新增工作单元")
    with st.form("add_unit"):
        n_name = st.text_input("显示名称 *", placeholder="如：广告审核员")
        n_domain = st.text_input("领域代号 * (小写英文)", placeholder="如：ads")
        n_pf = st.text_input("提示词文件名 *", value="work_unit_custom.txt")
        n_en = st.checkbox("新建后立即启用", value=True)
        n_body = st.text_area("提示词内容（可选）", height=180)
        submitted = st.form_submit_button("添加工作单元")
        if submitted:
            agent_manager.add_agent(
                n_name,
                n_domain,
                n_pf,
                prompt_text=n_body if n_body and n_body.strip() else None,
                enabled=n_en,
            )
            st.success("已添加并写入配置")
            st.rerun()


st.sidebar.title("导航")
pg = st.sidebar.radio("页面", ("审核中心", "Agent 管理"), key="nav_page")
st.sidebar.divider()
st.sidebar.caption("配置路径：" + str(agent_manager.get_config_path()))
st.sidebar.caption("提示词目录：" + str(agent_manager.PROMPTS_DIR))

if pg == "审核中心":
    page_audit()
else:
    page_agents()
