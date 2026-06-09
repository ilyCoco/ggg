from __future__ import annotations

import streamlit as st
from database import init_db
from utils import inject_css, metric_card, badge, ai_insight, section_header, nav_links, user_role_badge

st.set_page_config(page_title="Geshi 智能办公", page_icon="🏢", layout="wide")
init_db()
inject_css()


def login_page() -> None:
    from auth import authenticate

    _, center, _ = st.columns([1, 0.8, 1])
    with center:
        st.markdown(
            '<div class="geshi-hero">'
            '<div style="font-size:3em;margin-bottom:8px">🏢</div>'
            '<h1 style="font-size:2em">Geshi 智能办公</h1>'
            '<p style="color:#64748B;font-size:.95em;margin:4px 0 28px 0">'
            '多智能体协同工作平台</p>'
            '</div>',
            unsafe_allow_html=True,
        )

        # ── Role quick-switch chips ──
        st.markdown(
            '<div style="text-align:center;margin-bottom:16px">'
            '<span style="background:#EEF2FF;color:#4F46E5;padding:4px 14px;border-radius:14px;font-size:.78em;font-weight:600;margin:0 4px">'
            '管理员 admin / admin123</span>'
            '<span style="color:#94A3B8;font-size:.78em">或</span>'
            '<span style="background:#F0FDF4;color:#065F46;padding:4px 14px;border-radius:14px;font-size:.78em;font-weight:600;margin:0 4px">'
            '注册新用户</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        tab_login, tab_register = st.tabs(["🔑 登录", "✨ 注册"])

        with tab_login:
            with st.form("login_form"):
                username = st.text_input("用户名", placeholder="请输入用户名")
                password = st.text_input("密码", type="password", placeholder="请输入密码")
                submitted = st.form_submit_button("登    录", type="primary", use_container_width=True)
                if submitted:
                    if not username or not password:
                        st.error("请输入用户名和密码")
                    else:
                        user = authenticate(username, password)
                        if user:
                            st.session_state["user"] = user
                            st.rerun()
                        else:
                            st.error("用户名或密码错误")

        with tab_register:
            from auth import register_user

            with st.form("register_form"):
                r1, r2 = st.columns(2)
                new_username = r1.text_input("用户名 *", placeholder="2-30 位字母或中文", key="reg_user")
                display_name = r2.text_input("显示名称", placeholder="您的姓名")
                new_password = st.text_input("密码 *", type="password", placeholder="至少 6 位", key="reg_pw")
                new_password2 = st.text_input("确认密码 *", type="password", placeholder="再次输入密码", key="reg_pw2")
                r3, r4 = st.columns(2)
                email = r3.text_input("邮箱", placeholder="可选", key="reg_email")
                department = r4.text_input("部门", placeholder="可选", key="reg_dept")
                if st.form_submit_button("注    册", type="primary", use_container_width=True):
                    if not new_username or not new_password:
                        st.error("用户名和密码为必填项")
                    elif new_password != new_password2:
                        st.error("两次密码不一致")
                    else:
                        ok, msg = register_user(new_username, new_password, display_name, email, department)
                        if ok:
                            st.success("注册成功！请登录")
                        else:
                            st.error(msg)


def dashboard_page() -> None:
    user = st.session_state["user"]

    from knowledge_base import get_recent_entries, get_categories
    from tasks import get_tasks_by_status
    from notifications import get_unread_count as get_unread_notif_count, list_notifications
    from messages import get_unread_count as get_unread_msg_count
    from scheduler import get_upcoming_events
    from assistant import PersonalAssistantAgent, NaturalQueryAgent
    from summary_system.llm_client import LLMClient

    llm = LLMClient.from_env()
    pa_agent = PersonalAssistantAgent(llm)
    nq_agent = NaturalQueryAgent(llm)

    # ═══════════════════════════ Header ═══════════════════════════
    h1, h2 = st.columns([4, 1])
    with h1:
        st.markdown(
            f'<div style="padding:6px 0">'
            f'<h2 style="margin:0;font-weight:700;letter-spacing:-.5px">'
            f'👋 {pa_agent._greeting()}，{user.get("display_name") or user["username"]}</h2>'
            f'<div style="margin-top:4px">{user_role_badge(user)} '
            f'<small style="color:#94A3B8;font-size:.85em">{user.get("department") or ""}</small></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with h2:
        st.markdown('<div style="padding-top:12px;text-align:right">', unsafe_allow_html=True)
        if st.button("🚪 切换用户", key="header_logout"):
            st.session_state.clear()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

    # ═══════════════════════════ AI Briefing ═══════════════════════════
    if st.session_state.get("show_briefing", True):
        with st.spinner("🤖 AI 正在分析您的今日工作..."):
            briefing = pa_agent.daily_briefing(user["id"])
        td = briefing["task_summary"]

        # Briefing metric cards
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        with mc1:
            metric_card("待办任务", td["total_pending"],
                        delta=f"🔴 {td['urgent_count']} 紧急" if td["urgent_count"] else "暂无紧急",
                        color="#4F46E5")
        with mc2:
            metric_card("今日日程", len(briefing["meetings_today"]), color="#0EA5E9")
        with mc3:
            metric_card("未读通知", briefing["notifications"]["unread_count"], color="#F59E0B")
            if briefing["notifications"]["unread_count"] > 0:
                if st.button("查看", key="view_notifs_top", use_container_width=True):
                    st.session_state["show_notif_panel"] = True
                    st.rerun()
        with mc4:
            metric_card("待审批", briefing["pending_approvals"], color="#10B981")
        with mc5:
            att = briefing.get("attendance")
            label = "已签到" if att and att.get("check_in") else "未签到"
            metric_card("今日考勤", label, color="#8B5CF6")

        st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

        # ── Notification panel (shown when user clicks "查看") ──
        if st.session_state.get("show_notif_panel"):
            section_header("🔔 未读通知")
            notif_list = list_notifications(user["id"], limit=10, unread_only=True)
            if notif_list:
                notif_type_page = {
                    "task_assigned": "pages/4_✅_任务管理.py",
                    "task_deadline": "pages/4_✅_任务管理.py",
                    "task_completed": "pages/4_✅_任务管理.py",
                    "approval_request": "pages/5_📋_审批管理.py",
                    "approval_result": "pages/5_📋_审批管理.py",
                    "message_new": "pages/9_💬_站内消息.py",
                    "meeting_reminder": "pages/6_📅_日程管理.py",
                    "system": None,
                }
                from notifications import mark_read as _mark_read
                for n in notif_list:
                    nc1, nc2 = st.columns([5, 1])
                    with nc1:
                        page = notif_type_page.get(n["type"])
                        if page:
                            if st.button(f"🔴 {n['title']}", key=f"notif_go_{n['id']}",
                                         use_container_width=True):
                                _mark_read(n["id"])
                                st.switch_page(page)
                        else:
                            st.markdown(f"🔴 {n['title']}", unsafe_allow_html=True)
                    with nc2:
                        st.caption(n["created_at"][5:16])
                from notifications import mark_all_read as _mark_all
                bc1, bc2, _ = st.columns([1, 1, 4])
                with bc1:
                    if st.button("全部已读", key="notif_panel_mark"):
                        _mark_all(user["id"])
                        st.session_state["show_notif_panel"] = False
                        st.rerun()
                with bc2:
                    if st.button("收起", key="notif_panel_hide"):
                        st.session_state["show_notif_panel"] = False
                        st.rerun()
            else:
                st.success("暂无未读通知")
                if st.button("收起", key="notif_panel_hide_empty"):
                    st.session_state["show_notif_panel"] = False
                    st.rerun()
            st.markdown('<hr>', unsafe_allow_html=True)

        # AI insights
        i1, i2 = st.columns([1, 1])
        with i1:
            ai_insight("🧠", "今日洞察", briefing.get("ai_insight", ""))
        with i2:
            ai_insight("💡", "行动建议", briefing.get("ai_suggestion", ""))

        # Alerts
        if td["overdue"]:
            st.error("⚠️ 逾期任务：" + "、".join(t["title"] for t in td["overdue"][:3]))
        if td["due_today"]:
            st.warning("📌 今日截止：" + "、".join(t["title"] for t in td["due_today"][:3]))
        if briefing["conflicts"]:
            for c in briefing["conflicts"]:
                st.warning(f"⚠️ {c['message']}")

        c1, _ = st.columns([1, 10])
        with c1:
            if st.button("收起简报", key="hide_briefing", use_container_width=True):
                st.session_state["show_briefing"] = False
                st.rerun()
    else:
        if st.button("🤖 展开 AI 简报", key="show_briefing_btn"):
            st.session_state["show_briefing"] = True
            st.rerun()

    st.markdown('<hr>', unsafe_allow_html=True)

    # ═══════════════════════════ Main Content ═══════════════════════════
    left, right = st.columns([1.4, 0.6])

    with left:
        section_header("📊 我的工作台")
        tasks_map = get_tasks_by_status(user["id"])

        w1, w2, w3, w4 = st.columns(4)
        with w1:
            metric_card("待办", len(tasks_map.get("pending", [])), color="#F59E0B")
        with w2:
            metric_card("进行中", len(tasks_map.get("in_progress", [])), color="#3B82F6")
        with w3:
            metric_card("已完成", len(tasks_map.get("completed", [])), color="#10B981")
        with w4:
            metric_card("未读消息", get_unread_msg_count(user["id"]), color="#8B5CF6")

        # ── Urgent task previews ──
        urgent_tasks = [t for t in tasks_map.get("pending", []) if t.get("priority") == "high"]
        active_high = [t for t in tasks_map.get("in_progress", []) if t.get("priority") == "high"]
        if urgent_tasks or active_high:
            st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
            if urgent_tasks:
                st.markdown(
                    '<div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:10px;padding:10px 14px;margin:4px 0">'
                    f'<strong style="color:#C2410C">🔴 {len(urgent_tasks)} 个紧急待办</strong><br>'
                    + "<br>".join(f'<span style="color:#9A3412;font-size:.9em">• {t["title"]}</span>' for t in urgent_tasks[:3])
                    + '</div>',
                    unsafe_allow_html=True,
                )
            if active_high:
                for t in active_high[:2]:
                    st.markdown(
                        f'<div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:10px;padding:10px 14px;margin:4px 0">'
                        f'<span style="color:#1E40AF;font-size:.9em">🔄 {t["title"]}</span></div>',
                        unsafe_allow_html=True,
                    )

        # ── Knowledge Base Feed ──
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
        section_header("📚 知识库动态")
        entries = get_recent_entries(5)
        if entries:
            cats = get_categories()
            cat_map = {c["id"]: c for c in cats}
            for entry in entries:
                cat = cat_map.get(entry.get("category_id"), {})
                st.markdown(
                    f'<div style="padding:8px 0;border-bottom:1px solid #F1F5F9">'
                    f'<span style="font-size:.9em">{cat.get("icon", "📄")} '
                    f'<strong>{entry["title"]}</strong></span>'
                    f'<span style="color:#94A3B8;font-size:.8em;float:right">'
                    f'{entry.get("author_name", "")} · {entry["created_at"][:10]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("暂无知识条目，从语音总结导入吧 →")

        # ── Upcoming Events ──
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        section_header("📅 近期日程")
        events = get_upcoming_events(user["id"], limit=4)
        if events:
            for ev in events:
                st.markdown(
                    f'<div style="padding:4px 0">'
                    f'<span style="color:#6366F1;font-weight:600;font-size:.85em">{ev["start_time"][5:16]}</span>'
                    f'<span style="margin-left:8px;font-size:.9em">{ev["title"]}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("暂无近期日程")

    with right:
        # ── AI Smart Query ──
        section_header("🤖 AI 智能查询")
        nl_query = st.text_input(
            "问我任何问题...",
            placeholder="例：我这周完成了什么？",
            key="nl_input",
            label_visibility="collapsed",
        )
        q1, q2 = st.columns([0.55, 0.45])
        with q1:
            if st.button("🔍 查询", key="nl_go", use_container_width=True) and nl_query.strip():
                with st.spinner("AI 分析中..."):
                    st.session_state["nl_result"] = nq_agent.query(
                        nl_query.strip(), user["id"], user.get("display_name", ""))
        with q2:
            if st.button("💬 快捷提问", key="nl_faq", use_container_width=True):
                st.session_state["show_faq"] = not st.session_state.get("show_faq", False)

        if st.session_state.get("show_faq"):
            for q in ["我这周完成了什么？", "考勤怎么样？", "有哪些公告？"]:
                if st.button(q, key=f"faq_{hash(q) % 10000}"):
                    with st.spinner("..."):
                        st.session_state["nl_result"] = nq_agent.query(q, user["id"], "")

        if st.session_state.get("nl_result"):
            r = st.session_state["nl_result"]
            with st.container():
                st.success(r.get("summary", ""))
                rtype = r.get("type", "")
                if rtype == "work_summary":
                    if r.get("completed"):
                        st.caption("✅ " + "、".join(r["completed"][:4]))
                    if r.get("active"):
                        st.caption("🔄 " + "、".join(t["title"] for t in r["active"][:4]))
                elif rtype == "attendance":
                    st.caption(f"正常 {r['stats']['normal']}d · 迟到 {r['stats']['late']}次")
                elif rtype == "project_progress":
                    for t in r.get("tasks", [])[:3]:
                        st.caption(f"• {t['title']}")
                if st.button("✕ 清除", key="nl_clear"):
                    st.session_state.pop("nl_result", None)
                    st.rerun()

        # ── Quick Nav ──
        st.markdown('<hr>', unsafe_allow_html=True)
        section_header("🚀 快捷入口")
        nav_links(user)

        # ── Notifications ──
        st.markdown('<hr>', unsafe_allow_html=True)
        section_header("🔔 最近通知")
        notifs = list_notifications(user["id"], limit=8, unread_only=True)
        if notifs:
            from notifications import mark_read as _sidebar_mark_read
            sidebar_type_page = {
                "task_assigned": "pages/4_✅_任务管理.py",
                "task_deadline": "pages/4_✅_任务管理.py",
                "task_completed": "pages/4_✅_任务管理.py",
                "approval_request": "pages/5_📋_审批管理.py",
                "approval_result": "pages/5_📋_审批管理.py",
                "message_new": "pages/9_💬_站内消息.py",
                "meeting_reminder": "pages/6_📅_日程管理.py",
                "system": None,
            }
            for n in notifs:
                page = sidebar_type_page.get(n["type"])
                if page:
                    if st.button(f"🔴 {n['title']}", key=f"sb_notif_{n['id']}",
                                 use_container_width=True):
                        _sidebar_mark_read(n["id"])
                        st.switch_page(page)
                else:
                    st.markdown(
                        f'<div style="padding:5px 0;border-bottom:1px solid #F8FAFC">'
                        f'<span class="geshi-dot-blue"></span>'
                        f'<span style="font-size:.85em">{n["title"]}</span>'
                        f'<span style="color:#94A3B8;font-size:.75em;float:right">{n["created_at"][5:16]}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            if st.button("全部标为已读", key="mark_all"):
                from notifications import mark_all_read
                mark_all_read(user["id"])
                st.rerun()
        else:
            st.caption("暂无未读通知 ✓")

        # ── Account ──
        st.markdown('<hr>', unsafe_allow_html=True)
        section_header("👤 账户")
        st.markdown(
            f'<div style="padding:4px 0;font-size:.9em"><strong>{user.get("display_name") or user["username"]}</strong></div>'
            f'<div style="font-size:.82em;color:#94A3B8">{user_role_badge(user)}  ·  {user.get("department") or "未设置部门"}</div>',
            unsafe_allow_html=True,
        )
        with st.expander("⚙️ 修改密码"):
            from auth import verify_password, update_user
            with st.form("change_pw"):
                old = st.text_input("当前密码", type="password")
                new = st.text_input("新密码", type="password")
                new2 = st.text_input("确认新密码", type="password")
                if st.form_submit_button("确认修改", use_container_width=True):
                    if not verify_password(old, user["password_hash"]):
                        st.error("当前密码错误")
                    elif new != new2:
                        st.error("两次密码不一致")
                    elif len(new) < 6:
                        st.error("密码至少 6 位")
                    else:
                        update_user(user["id"], password=new)
                        st.success("密码已修改")
                        st.session_state["user"]["password_hash"] = ""


if "user" not in st.session_state:
    login_page()
else:
    dashboard_page()
