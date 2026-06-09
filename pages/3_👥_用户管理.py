"""用户管理页面 - 仅管理员可访问"""

from __future__ import annotations

import streamlit as st

if "user" not in st.session_state:
    st.warning("请先在首页登录")
    st.stop()

from utils import inject_css
inject_css()

user = st.session_state["user"]

if user.get("role") != "admin":
    st.error("仅管理员可访问此页面")
    st.stop()

from auth import get_all_users, register_user, update_user

st.title("👥 用户管理")

tab1, tab2 = st.tabs(["用户列表", "添加用户"])

with tab1:
    users = get_all_users()
    st.caption(f"共 {len(users)} 个用户")

    for u in users:
        with st.expander(f"{'👑' if u['role'] == 'admin' else '👤'} {u['display_name']} (@{u['username']})"):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.caption(f"ID：{u['id']}")
                st.caption(f"角色：{u['role']}")
                st.caption(f"部门：{u.get('department') or '-'}")
            with c2:
                st.caption(f"邮箱：{u.get('email') or '-'}")
                st.caption(f"状态：{'启用' if u['is_active'] else '禁用'}")
                st.caption(f"注册时间：{u['created_at']}")
            with c3:
                if u["id"] != user["id"]:  # Don't allow self-modification
                    new_role = st.selectbox(
                        "角色", ["user", "admin"],
                        index=0 if u["role"] == "user" else 1,
                        key=f"role_{u['id']}",
                    )
                    new_active = st.checkbox("启用", value=bool(u["is_active"]), key=f"active_{u['id']}")
                    new_dept = st.text_input("部门", value=u.get("department", ""), key=f"dept_{u['id']}")
                    if st.button("保存", key=f"save_{u['id']}"):
                        update_user(
                            u["id"],
                            role=new_role,
                            is_active=new_active,
                            department=new_dept,
                        )
                        st.success("已更新")
                        st.rerun()
                else:
                    st.caption("（当前登录用户）")

with tab2:
    st.subheader("添加新用户")
    from auth import register_user

    with st.form("add_user_form"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        password2 = st.text_input("确认密码", type="password")
        display_name = st.text_input("显示名称")
        email = st.text_input("邮箱")
        department = st.text_input("部门")

        if st.form_submit_button("添加用户", type="primary"):
            if not username or not password:
                st.error("用户名和密码为必填项")
            elif password != password2:
                st.error("两次密码不一致")
            else:
                ok, msg = register_user(username, password, display_name, email, department)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
