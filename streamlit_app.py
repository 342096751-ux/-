# -*- coding: utf-8 -*-
"""
UGC 审核 + Agent 工作单元管理（Streamlit）

运行: 在项目根目录执行
  streamlit run streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from audit_system import agent_manager
from audit_system.orchestrator import run_audit_stream


st.set_page_config(page_title="UGC 内容审核", layout="wide", initial_sidebar_state="expanded")

if "last_audit_result" not in st.session_state:
    st.session_state.last_audit_result = None


def page_audit():
    st.title("UGC 内容审核")
    st.caption("基于 audit_system 编排，工作单元自 work_units_config.yaml 加载。")
    text = st.text_area("待审核内容", height=220, placeholder="在此输入待审文本…")
    if st.button("开始审核", type="primary", use_container_width=True) and text.strip():
        with st.spinner("审核进行中…"):
            trace_lines = []
            final_data = None
            for item in run_audit_stream(text.strip()):
                stage = str(item.get("阶段名") or "")
                detail = str(item.get("内容") or "")
                trace_lines.append(f"**{stage}**  {detail[:200]}")
                if stage == "完成" and isinstance(item.get("数据"), dict):
                    final_data = item["数据"]
            st.session_state.last_audit_result = {
                "trace_md": "\n\n".join(trace_lines),
                "data": final_data,
            }
    if st.session_state.last_audit_result:
        res = st.session_state.last_audit_result
        st.subheader("阶段输出")
        st.markdown(res.get("trace_md") or "_无_")
        d = res.get("data")
        if isinstance(d, dict):
            st.subheader("最终结果摘要")
            intent = d.get("intent") or {}
            st.write("**意图**", intent)
            st.write("**工作单元发现**", d.get("findings"))
            st.write("**mermaid_管线**（若有）", d.get("mermaid_pipeline", "")[:80], "…")
    st.info("在侧边栏可切换到 **Agent 管理** 以维护工作单元，无需手改 YAML。")


def page_agents():
    st.title("Agent 工作单元管理")
    st.caption("已注册的工作单元会写入项目根目录的 work_units_config.yaml，提示词文件在 audit_system/prompts/ 下。")

    agent_manager.ensure_default_config()
    cfg = agent_manager.load_units_config()
    units: list = list(cfg.get("units", []))

    st.subheader("已注册的工作单元")
    for i, u in enumerate(units):
        if not isinstance(u, dict):
            continue
        name = u.get("name", "")
        domain = u.get("domain", "")
        pf = u.get("prompt_file", "")
        en = u.get("enabled", True) is not False
        c1, c2, c3, c4, c5, c6 = st.columns([2, 2, 2, 1, 1, 1])
        with c1:
            st.write(f"**{name}**")
        with c2:
            st.code(domain or "—", language=None)
        with c3:
            st.text(pf or "—")
        with c4:
            ne = st.checkbox("启用", value=en, key=f"en_{i}", help="仅启用的单元会参与运行与出现在意图可选项中")
            if ne != en:
                try:
                    agent_manager.set_agent_enabled(i, ne)
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(str(e))
        with c5:
            if st.button("删除", key=f"rm_{i}"):
                try:
                    agent_manager.remove_agent(i)
                    st.success("已删除")
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(str(e))
        with c6:
            if st.button("编辑提示词", key=f"ed_{i}"):
                st.session_state[f"editing_{i}"] = True
        if st.session_state.get(f"editing_{i}"):
            bn = agent_manager.basename_from_prompt_file(str(pf))
            cur = agent_manager.read_prompt_file(bn)
            new_text = st.text_area(f"提示词：{name}", value=cur, height=300, key=f"ta_{i}")
            b1, b2 = st.columns(2)
            with b1:
                if st.button("保存提示词", key=f"sv_{i}"):
                    try:
                        agent_manager.write_prompt_file(bn, new_text)
                        st.session_state[f"editing_{i}"] = False
                        st.success("已保存")
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        st.error(str(e))
            with b2:
                if st.button("取消", key=f"cl_{i}"):
                    st.session_state[f"editing_{i}"] = False
                    st.rerun()
        st.divider()

    st.subheader("新增工作单元")
    with st.form("add_unit"):
        n_name = st.text_input("显示名称 *", placeholder="如：广告审核员")
        n_domain = st.text_input("领域代号 * (小写英文)", placeholder="如：ads")
        n_pf = st.text_input("提示词文件名 *", value="work_unit_custom.txt", help="仅文件名，会保存到 prompts/ 目录")
        n_en = st.checkbox("新建后立即启用", value=True)
        n_body = st.text_area("提示词内容（可选）", height=200, help="若填写，将自动创建/覆盖该 txt 文件")
        submitted = st.form_submit_button("添加工作单元")
        if submitted:
            try:
                agent_manager.add_agent(
                    n_name,
                    n_domain,
                    n_pf,
                    prompt_text=n_body if n_body and n_body.strip() else None,
                    enabled=n_en,
                )
                st.success("已添加并写入配置")
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(str(e))

    st.subheader("导入 / 导出")
    ec1, ec2 = st.columns(2)
    with ec1:
        st.download_button(
            "下载当前配置 (YAML)",
            data=agent_manager.export_config_yaml_string().encode("utf-8"),
            file_name="work_units_export.yaml",
            mime="text/yaml",
        )
    with ec2:
        up = st.file_uploader("上传 YAML 替换当前配置", type=["yaml", "yml"], key="yaml_up")
        if up is not None:
            if st.button("确认导入并覆盖", type="primary"):
                try:
                    raw = up.getvalue().decode("utf-8")
                    agent_manager.import_config_replace(raw)
                    st.success("导入成功")
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(str(e))


st.sidebar.title("导航")
pg = st.sidebar.radio("页面", ("UGC 审核", "Agent 管理"), key="nav_page")
st.sidebar.divider()
st.sidebar.caption("配置路径：" + str(agent_manager.get_config_path()))
st.sidebar.caption("提示词目录：" + str(agent_manager.PROMPTS_DIR))

if pg == "UGC 审核":
    page_audit()
else:
    page_agents()
