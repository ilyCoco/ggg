"""Tasks page — Kanban, list, and create with AI intelligence."""

from __future__ import annotations

import streamlit as st

if "user" not in st.session_state:
    st.warning("请先在首页登录")
    st.stop()

from utils import inject_css
inject_css()

from tasks import (
    create_task, update_task, delete_task, get_task,
    list_tasks, get_tasks_by_status,
    TaskIntelligenceAgent,
)
from notifications import get_unread_count
from notifications import mark_read_by_type
from summary_system.llm_client import LLMClient

user = st.session_state["user"]
mark_read_by_type(user["id"], "task_assigned")
mark_read_by_type(user["id"], "task_deadline")
mark_read_by_type(user["id"], "task_completed")
llm = LLMClient.from_env()
agent = TaskIntelligenceAgent(llm)

st.title("✅ 任务管理")

tab1, tab2, tab3 = st.tabs(["📋 看板视图", "📃 列表筛选", "➕ 创建任务"])

# ── Kanban ──
with tab1:
    tasks_map = get_tasks_by_status(user["id"])
    cols = st.columns(3)
    status_config = [
        ("pending", "📌 待办", "#FEF3C7"),
        ("in_progress", "🔄 进行中", "#DBEAFE"),
        ("completed", "✅ 已完成", "#D1FAE5"),
    ]

    for idx, (status_key, label, color) in enumerate(status_config):
        with cols[idx]:
            st.markdown(f"### {label} ({len(tasks_map[status_key])})")
            for t in tasks_map[status_key]:
                priority_badge = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t["priority"], "")
                deadline_str = f"📅 {t['deadline']}" if t.get("deadline") else ""
                with st.container():
                    st.markdown(
                        f"""<div style="border-left:3px solid {color};padding:8px;margin:4px 0;background:#F9FAFB;border-radius:4px;">
                        <strong>{priority_badge} {t['title']}</strong><br>
                        <small>👤 {t.get('assignee_name') or '未分配'} {deadline_str}</small>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    new_status = st.selectbox(
                        "状态",
                        ["pending", "in_progress", "completed", "cancelled"],
                        index=["pending", "in_progress", "completed", "cancelled"].index(t["status"]),
                        key=f"kanban_{t['id']}",
                        label_visibility="collapsed",
                    )
                    if new_status != t["status"]:
                        update_task(t["id"], status=new_status)
                        st.rerun()

# ── List view ──
with tab2:
    c1, c2, c3 = st.columns(3)
    with c1:
        filter_status = st.selectbox("状态筛选", ["全部", "pending", "in_progress", "completed", "cancelled"], format_func=lambda x: {"全部":"全部","pending":"待办","in_progress":"进行中","completed":"已完成","cancelled":"已取消"}[x])
    with c2:
        filter_priority = st.selectbox("优先级筛选", ["全部", "high", "medium", "low"], format_func=lambda x: {"全部":"全部","high":"高","medium":"中","low":"低"}[x])
    with c3:
        sort = st.selectbox("排序", ["创建时间", "截止时间", "优先级"], key="list_sort")

    sort_map = {"创建时间": "created_at", "截止时间": "deadline", "优先级": "priority"}
    result = list_tasks(
        my_tasks=None if user["role"] == "admin" else user["id"],
        status=filter_status if filter_status != "全部" else "",
        priority=filter_priority if filter_priority != "全部" else "",
        sort_by=sort_map[sort],
    )

    st.caption(f"共 {result['total']} 个任务")
    for t in result["tasks"]:
        with st.expander(f"{t['title']} — {t.get('assignee_name') or '未分配'} · {t['status']}"):
            c1, c2, c3, c4 = st.columns(4)
            c1.caption(f"优先级：{t['priority']}")
            c2.caption(f"截止：{t.get('deadline') or '无'}")
            c3.caption(f"创建者：{t.get('creator_name', '')}")
            c4.caption(f"创建：{t['created_at'][:10]}")
            if t.get("description"):
                st.text(t["description"])
            if t.get("risk_tags"):
                st.caption(f"风险标签：{', '.join(t['risk_tags'])}")

            ce1, ce2 = st.columns(2)
            with ce1:
                if st.button("完成", key=f"done_{t['id']}"):
                    update_task(t["id"], status="completed")
                    st.rerun()
            with ce2:
                if st.button("删除", key=f"del_{t['id']}"):
                    delete_task(t["id"])
                    st.rerun()

# ── Create ──
with tab3:
    with st.form("create_task_form"):
        st.subheader("创建新任务")
        title = st.text_input("任务标题 *", placeholder="输入任务标题")
        description = st.text_area("任务描述", placeholder="详细描述任务内容...", height=120)

        from auth import get_all_users
        users = get_all_users()
        user_options = {f"{u['display_name']} (@{u['username']})": u["id"] for u in users}
        user_options["（不分配）"] = None
        assignee = st.selectbox("分配给", list(user_options.keys()))

        col1, col2 = st.columns(2)
        with col1:
            priority = st.selectbox("优先级", ["medium", "high", "low"], format_func=lambda x: {"high":"🔴 高","medium":"🟡 中","low":"🟢 低"}[x])
        with col2:
            deadline = st.date_input("截止日期", value=None)

        use_ai = st.checkbox("AI 智能分析（需要 LLM API）", value=bool(llm))
        submitted = st.form_submit_button("创建任务", type="primary", use_container_width=True)

        if submitted:
            if not title.strip():
                st.error("请输入任务标题")
            else:
                ai_result = {}
                if use_ai or llm:
                    with st.spinner("AI 正在分析任务..."):
                        ai_result = agent.analyze(title, description, str(deadline) if deadline else "")
                        if not ai_result.get("priority"):
                            ai_result["priority"] = priority
                        st.info(f"AI 建议：{ai_result.get('suggestion', '')}")

                task_id = create_task(
                    title=title,
                    description=description,
                    creator_id=user["id"],
                    assignee_id=user_options[assignee],
                    priority=ai_result.get("priority") or priority,
                    deadline=str(deadline) if deadline else ai_result.get("deadline_norm") or "",
                    risk_tags=ai_result.get("risks") or [],
                )
                st.success(f"任务已创建（ID: {task_id}）")
                if ai_result.get("risks"):
                    st.warning("风险提醒：" + "；".join(ai_result["risks"]))
