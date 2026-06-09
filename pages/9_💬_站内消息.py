"""Internal messages page — chat UI."""

from __future__ import annotations

import streamlit as st

if "user" not in st.session_state:
    st.warning("请先在首页登录")
    st.stop()

from utils import inject_css
inject_css()

from messages import (
    send_message, get_conversation, get_inbox, get_recent_contacts,
    get_unread_count,
)
from auth import get_all_users
from notifications import mark_read_by_type

user = st.session_state["user"]

# 进入消息页面时，自动将所有 message_new 通知标为已读
mark_read_by_type(user["id"], "message_new")

st.title("💬 站内消息")

# Initialize selected contact
if "chat_with" not in st.session_state:
    st.session_state["chat_with"] = None

left, right = st.columns([0.35, 0.65])

# ── Left: Contacts ──
with left:
    st.subheader("📋 联系人")
    unread_total = get_unread_count(user["id"])
    if unread_total:
        st.caption(f"🔵 {unread_total} 条未读")

    # Recent contacts
    contacts = get_recent_contacts(user["id"], limit=30)
    for c in contacts:
        if c["id"] == user["id"]:
            continue
        unread_badge = f" 🔵{c.get('unread',0)}" if c.get("unread") else ""
        last_msg = (c.get("last_message") or "")[:30]
        is_selected = st.session_state["chat_with"] == c["id"]
        bg = "#E5F0FF" if is_selected else "transparent"
        st.markdown(
            f"""<div style='background:{bg};padding:6px;border-radius:4px;cursor:pointer;margin:2px 0'>
            <strong>{c['display_name']}</strong>{unread_badge}<br>
            <small style='color:#888'>{last_msg}</small></div>""",
            unsafe_allow_html=True,
        )
        if st.button("💬", key=f"contact_{c['id']}"):
            st.session_state["chat_with"] = c["id"]
            st.rerun()

    # Search all users
    with st.expander("搜索其他用户"):
        all_users = get_all_users()
        for u in all_users:
            if u["id"] != user["id"]:
                if st.button(f"{u['display_name']} (@{u['username']})", key=f"search_{u['id']}"):
                    st.session_state["chat_with"] = u["id"]
                    st.rerun()

# ── Right: Chat area ──
with right:
    if st.session_state["chat_with"]:
        chat_user_id = st.session_state["chat_with"]
        # Get chat user name
        chat_users = get_all_users()
        chat_name = next((f"{u['display_name']}" for u in chat_users if u["id"] == chat_user_id), f"用户{chat_user_id}")

        st.subheader(f"💬 {chat_name}")

        # Messages
        conv = get_conversation(user["id"], chat_user_id)
        chat_container = st.container()
        with chat_container:
            for msg in conv["messages"]:
                is_me = msg["sender_id"] == user["id"]
                align = "right" if is_me else "left"
                bg_color = "#DBEAFE" if is_me else "#F3F4F6"
                st.markdown(
                    f"""<div style='text-align:{align};margin:4px 0'>
                    <div style='display:inline-block;background:{bg_color};padding:8px 14px;
                    border-radius:12px;max-width:80%;text-align:left'>
                    <small style='color:#666'>{msg.get('sender_name','')}</small><br>
                    {msg['content']}<br>
                    <small style='color:#999'>{msg['created_at'][11:19]}</small>
                    </div></div>""",
                    unsafe_allow_html=True,
                )

        # Input
        st.divider()
        with st.form("send_msg_form", clear_on_submit=True):
            msg_text = st.text_area("输入消息", placeholder=f"发送给 {chat_name}...", key="msg_input", label_visibility="collapsed")
            if st.form_submit_button("发送 📤", use_container_width=True):
                if msg_text.strip():
                    send_message(user["id"], chat_user_id, msg_text.strip())
                    st.rerun()
    else:
        st.info("👈 选择左侧联系人开始聊天")
