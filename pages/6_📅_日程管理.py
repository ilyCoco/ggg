"""Calendar page — month view, event management, AI scheduling, weekly report."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

import streamlit as st

if "user" not in st.session_state:
    st.warning("请先在首页登录")
    st.stop()

from utils import inject_css
inject_css()

from scheduler import (
    create_event, update_event, delete_event, get_event,
    get_events_for_month, get_upcoming_events, resolve_attendees,
    SchedulingAgent, ReportGenerationAgent,
)
from notifications import mark_read_by_type
from summary_system.llm_client import LLMClient

user = st.session_state["user"]
mark_read_by_type(user["id"], "meeting_reminder")
llm = LLMClient.from_env()
sched_agent = SchedulingAgent(llm)
report_agent = ReportGenerationAgent(llm)

st.title("📅 日程管理")

# ── Month navigation ──
today = date.today()
if "cal_year" not in st.session_state:
    st.session_state["cal_year"] = today.year
    st.session_state["cal_month"] = today.month

c1, c2, c3, c4, c5 = st.columns([1, 1, 2, 1, 1])
with c1:
    if st.button("◀ 上月"):
        if st.session_state["cal_month"] == 1:
            st.session_state["cal_month"] = 12
            st.session_state["cal_year"] -= 1
        else:
            st.session_state["cal_month"] -= 1
        st.rerun()
with c2:
    if st.button("本月"):
        st.session_state["cal_year"] = today.year
        st.session_state["cal_month"] = today.month
        st.rerun()
with c3:
    st.markdown(f"### {st.session_state['cal_year']} 年 {st.session_state['cal_month']} 月")
with c4:
    if st.button("下月 ▶"):
        if st.session_state["cal_month"] == 12:
            st.session_state["cal_month"] = 1
            st.session_state["cal_year"] += 1
        else:
            st.session_state["cal_month"] += 1
        st.rerun()

year = st.session_state["cal_year"]
month = st.session_state["cal_month"]

# ── Calendar grid ──
events_by_day = get_events_for_month(year, month, user["id"])
cal = calendar.Calendar(firstweekday=0)
weeks = list(cal.monthdatescalendar(year, month))

# Header
day_names = ["一", "二", "三", "四", "五", "六", "日"]
cols = st.columns(7)
for i, dn in enumerate(day_names):
    cols[i].markdown(f"**{dn}**")

for week in weeks:
    cols = st.columns(7)
    for i, d in enumerate(week):
        with cols[i]:
            if d.month != month:
                st.markdown(f"<span style='color:#ccc'>{d.day}</span>", unsafe_allow_html=True)
            else:
                is_today = d == today
                bg = "#FFF3CD" if is_today else "transparent"
                day_events = events_by_day.get(d.day, [])
                dots = ""
                for ev in day_events:
                    color = {"meeting": "#3B82F6", "task_deadline": "#EF4444", "reminder": "#F59E0B", "personal": "#10B981"}.get(ev.get("event_type", "personal"), "#6B7280")
                    dots += f"<span style='display:inline-block;width:6px;height:6px;border-radius:50%;background:{color};margin:1px'></span>"

                st.markdown(
                    f"""<div style='background:{bg};padding:4px;border-radius:4px;text-align:center;cursor:pointer'
                        onclick=''>
                        <strong>{d.day}</strong><br>{dots}
                        </div>""",
                    unsafe_allow_html=True,
                )
                if day_events:
                    for ev in day_events[:2]:
                        st.caption(f"· {ev['title'][:8]}")

# ── Selected day events + Create ──
st.divider()
left, right = st.columns([1, 1])

with left:
    st.subheader("今日日程")
    today_events = events_by_day.get(today.day, [])
    if today_events:
        for ev in today_events:
            with st.expander(f"{ev['title']} — {ev.get('start_time','')[11:16]}"):
                st.caption(f"类型：{ev['event_type']} | 地点：{ev.get('location') or '-'}")
                if ev.get("description"):
                    st.text(ev["description"])
    else:
        st.caption("今日暂无日程")

    st.subheader("📅 近期日程")
    upcoming = get_upcoming_events(user["id"], limit=10)
    for ev in upcoming:
        st.caption(f"{ev['start_time'][:16]} — {ev['title']}")

with right:
    st.subheader("➕ 创建日程")
    with st.form("create_event_form"):
        ev_title = st.text_input("标题 *")
        ev_desc = st.text_area("描述")
        c1, c2 = st.columns(2)
        with c1:
            ev_date = st.date_input("日期", value=today)
            ev_time = st.time_input("时间", value=datetime.strptime("09:00", "%H:%M").time())
        with c2:
            ev_type = st.selectbox("类型", ["meeting", "task_deadline", "reminder", "personal"],
                                   format_func=lambda x: {"meeting":"会议","task_deadline":"任务截止","reminder":"提醒","personal":"个人"}[x])
            ev_duration = st.number_input("时长(分钟)", min_value=15, value=30, step=15)
        ev_location = st.text_input("地点")
        ev_all_day = st.checkbox("全天")
        from auth import get_all_users
        users = get_all_users()
        user_opts = {f"{u['display_name']}": u["id"] for u in users if u["id"] != user["id"]}
        ev_attendees = st.multiselect("参与人", list(user_opts.keys()))

        use_ai = st.checkbox("AI 智能排期", value=bool(llm))
        submitted = st.form_submit_button("创建日程", type="primary")
        if submitted:
            if not ev_title.strip():
                st.error("请输入标题")
            else:
                start = f"{ev_date}T{ev_time.strftime('%H:%M:%S')}" if not ev_all_day else f"{ev_date}T00:00:00"
                end_dt = datetime.combine(ev_date, ev_time) + timedelta(minutes=ev_duration)
                end = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
                aid_list = [user_opts[n] for n in ev_attendees]

                if use_ai:
                    with st.spinner("AI 正在分析最佳时间..."):
                        suggestion = sched_agent.suggest_time(ev_title, ev_desc, aid_list or [])
                        if suggestion.get("suggestion"):
                            st.info(f"AI 建议：{suggestion['suggestion']}")

                eid = create_event(title=ev_title, creator_id=user["id"], start_time=start,
                                   end_time=end, event_type=ev_type, all_day=ev_all_day,
                                   location=ev_location, description=ev_desc, attendees=aid_list)
                st.success(f"日程已创建（ID: {eid}）")

# ── Weekly Report ──
st.divider()
st.subheader("📊 周报生成")
if st.button("🤖 生成本周周报", type="primary"):
    with st.spinner("AI 正在生成周报..."):
        report = report_agent.generate_weekly_report(user["id"])
        st.markdown(report)
        st.download_button("下载周报", report, file_name=f"weekly_report_{today}.md", mime="text/markdown")
