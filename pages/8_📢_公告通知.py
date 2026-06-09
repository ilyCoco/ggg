"""Announcements page."""

from __future__ import annotations

import streamlit as st

if "user" not in st.session_state:
    st.warning("请先在首页登录")
    st.stop()

from utils import inject_css
inject_css()

from announcements import (
    create_announcement, update_announcement, delete_announcement,
    list_announcements, toggle_pin, toggle_publish,
)

user = st.session_state["user"]
is_admin = user.get("role") == "admin"

st.title("📢 公告通知")

# ── Admin: Publish form ──
if is_admin:
    with st.sidebar:
        st.subheader("📝 发布公告")
        with st.form("new_ann_form"):
            ann_title = st.text_input("标题")
            ann_content = st.text_area("内容（支持 Markdown）", height=200)
            ann_pinned = st.checkbox("置顶")
            if st.form_submit_button("发布公告", type="primary", use_container_width=True):
                if not ann_title.strip():
                    st.error("请输入标题")
                else:
                    create_announcement(ann_title, ann_content, user["id"], is_pinned=ann_pinned)
                    st.success("公告已发布")
                    st.rerun()

# ── Main: List announcements ──
result = list_announcements(include_unpublished=is_admin)
st.caption(f"共 {result['total']} 条公告")

for ann in result["announcements"]:
    pin_badge = "📌 " if ann["is_pinned"] else ""
    unpub_badge = " [未发布]" if not ann["is_published"] else ""
    with st.expander(f"{pin_badge}{ann['title']}{unpub_badge} — {ann.get('author_name','')} · {ann['created_at'][:10]}"):
        st.markdown(ann["content"])

        if is_admin:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("📌 切换置顶" if not ann["is_pinned"] else "解除置顶", key=f"pin_{ann['id']}"):
                    toggle_pin(ann["id"])
                    st.rerun()
            with c2:
                lbl = "发布" if not ann["is_published"] else "撤回"
                if st.button(lbl, key=f"pub_{ann['id']}"):
                    toggle_publish(ann["id"])
                    st.rerun()
            with c3:
                if st.button("✏️ 编辑", key=f"editann_{ann['id']}"):
                    st.session_state["edit_ann"] = ann["id"]
                    st.rerun()
            with c4:
                if st.button("🗑️ 删除", key=f"delann_{ann['id']}"):
                    delete_announcement(ann["id"])
                    st.rerun()

# ── Edit modal ──
if is_admin and st.session_state.get("edit_ann"):
    from announcements import get_announcement
    ann = get_announcement(st.session_state["edit_ann"])
    if ann:
        st.divider()
        st.subheader("✏️ 编辑公告")
        new_title = st.text_input("标题", value=ann["title"], key="edit_title")
        new_content = st.text_area("内容", value=ann["content"], height=200, key="edit_content")
        if st.button("保存修改", type="primary"):
            update_announcement(ann["id"], title=new_title, content=new_content)
            st.session_state.pop("edit_ann")
            st.success("已更新")
            st.rerun()
        if st.button("取消"):
            st.session_state.pop("edit_ann")
            st.rerun()
