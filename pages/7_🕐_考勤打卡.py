"""Attendance page — check-in/out, monthly view, stats."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

if "user" not in st.session_state:
    st.warning("请先在首页登录")
    st.stop()

from utils import inject_css, badge
inject_css()

from attendance import (
    check_in, check_out, get_today_record,
    get_monthly_records, get_attendance_stats, get_all_today,
)

user = st.session_state["user"]
today = date.today()

st.title("🕐 考勤打卡")

# ── Today's Status ──
st.subheader("📍 今日打卡")
record = get_today_record(user["id"])
now = datetime.now()

col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    st.metric("当前时间", now.strftime("%H:%M:%S"))
with col2:
    if record and record.get("check_in"):
        st.success(f"签到：{record['check_in'][11:19]}")
    else:
        st.info("未签到")
with col3:
    if record and record.get("check_out"):
        st.success(f"签退：{record['check_out'][11:19]}")
    else:
        st.info("未签退")

status_text = {"normal": "✅ 正常", "late": "⚠️ 迟到", "early": "⚠️ 早退", "absent": "❌ 缺勤"}
if record:
    st.caption(f"状态：{status_text.get(record.get('status','normal'), record.get('status',''))}")

c1, c2 = st.columns(2)
with c1:
    if st.button("✅ 签到", type="primary", use_container_width=True, disabled=bool(record and record.get("check_in"))):
        ok, msg = check_in(user["id"])
        if ok:
            st.success(msg)
        else:
            st.warning(msg)
        st.rerun()
with c2:
    if st.button("👋 签退", type="primary", use_container_width=True, disabled=not record or bool(record and record.get("check_out"))):
        ok, msg = check_out(user["id"])
        if ok:
            st.success(msg)
        else:
            st.warning(msg)
        st.rerun()

# ── Monthly View ──
st.divider()
st.subheader("📊 月考勤记录")

c1, c2 = st.columns(2)
with c1:
    view_year = st.selectbox("年", range(today.year - 1, today.year + 2), index=1)
with c2:
    view_month = st.selectbox("月", range(1, 13), index=today.month - 1)

records = get_monthly_records(user["id"], view_year, view_month)
stats = get_attendance_stats(user["id"], view_year, view_month)

# Stats
cols = st.columns(4)
cols[0].metric("✅ 正常", stats["normal"])
cols[1].metric("⚠️ 迟到", stats["late"])
cols[2].metric("⏰ 早退", stats["early"])
cols[3].metric("❌ 缺勤", stats["absent"])

# Table
if records:
    lines = "| 日期 | 签到 | 签退 | 状态 |\n|------|------|------|------|\n"
    for r in records:
        ci = r["check_in"][11:19] if r.get("check_in") else "-"
        co = r["check_out"][11:19] if r.get("check_out") else "-"
        st_text = status_text.get(r.get("status", "normal"), r.get("status", ""))
        lines += f"| {r['date']} | {ci} | {co} | {st_text} |\n"
    st.markdown(lines)
else:
    st.info("该月暂无考勤记录")

# ── Admin: All Today ──
if user.get("role") == "admin":
    st.divider()
    st.subheader("👥 今日全员考勤")
    all_records = get_all_today()
    if all_records:
        for r in all_records:
            st_text = status_text.get(r.get("status", "normal"), r.get("status", ""))
            ci = r["check_in"][11:19] if r.get("check_in") else "未签到"
            co = r["check_out"][11:19] if r.get("check_out") else "未签退"
            st.caption(f"{st_text} | {r['display_name']} ({r.get('department','')}) | 签到:{ci} | 签退:{co}")
    else:
        st.caption("今日暂无打卡记录")
