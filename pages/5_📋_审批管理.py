"""Approval workflow page."""

from __future__ import annotations

import streamlit as st

if "user" not in st.session_state:
    st.warning("请先在首页登录")
    st.stop()

from utils import inject_css
inject_css()

from approvals import (
    create_approval, approve, reject, cancel, get_approval,
    list_approvals, parse_approval_chain, ApprovalReviewAgent,
)
from notifications import mark_read_by_type
from summary_system.llm_client import LLMClient

user = st.session_state["user"]
mark_read_by_type(user["id"], "approval_request")
mark_read_by_type(user["id"], "approval_result")
llm = LLMClient.from_env()
review_agent = ApprovalReviewAgent(llm)

st.title("📋 审批管理")

tab1, tab2, tab3, tab4 = st.tabs(["📝 我的申请", "⏳ 待我审批", "➕ 创建申请", "📜 审批历史"])

# ── My applications ──
with tab1:
    result = list_approvals(applicant_id=user["id"])
    st.caption(f"共 {result['total']} 条")
    for a in result["approvals"]:
        status_badge = {"pending": "⏳", "approved": "✅", "rejected": "❌", "cancelled": "🚫"}.get(a["status"], "")
        with st.expander(f"{status_badge} [{a['type']}] {a['title']} — {a['created_at'][:10]}"):
            st.caption(f"状态：{a['status']} | 当前审批人：{a.get('approver_name') or '-'}")
            if a.get("description"):
                st.text(a["description"])
            chain = parse_approval_chain(a["approval_chain"], a.get("current_step", 0), a["status"])
            if chain:
                st.write("**审批链：**")
                for step in chain:
                    icon = {"approved": "✅", "rejected": "❌", "pending": "⏳", "waiting": "⬜"}.get(step["status"], "")
                    st.caption(f"{icon} {step['name']}")
            if a["status"] == "pending":
                if st.button("取消申请", key=f"cancel_{a['id']}"):
                    cancel(a["id"], user["id"])
                    st.rerun()

# ── Pending my approval ──
with tab2:
    result = list_approvals(approver_id=user["id"], status="pending")
    st.caption(f"共 {result['total']} 条待审批")
    for a in result["approvals"]:
        with st.expander(f"[{a['type']}] {a['title']} — 申请人：{a.get('applicant_name', '')}"):
            st.caption(f"申请时间：{a['created_at'][:16]}")
            if a.get("description"):
                st.text(a["description"])

            chain = parse_approval_chain(a["approval_chain"], a.get("current_step", 0), a["status"])
            if chain:
                chain_text = " → ".join(s["name"] + "(" + s["status"] + ")" for s in chain)
                st.caption(f"审批进度：{chain_text}")

            # AI review
            ai = review_agent.review(a["type"], a["title"], a.get("description", ""), a.get("applicant_name", ""))
            if ai.get("flags"):
                st.warning(f"AI 提示：{ai.get('suggestion', '')} | 风险等级：{ai['risk_level']}")
                for f in ai["flags"]:
                    st.caption(f"⚠️ {f}")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 批准", key=f"appr_{a['id']}", type="primary"):
                    ok, msg = approve(a["id"], user["id"])
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
                    st.rerun()
            with c2:
                if st.button("❌ 驳回", key=f"rej_{a['id']}"):
                    ok, msg = reject(a["id"], user["id"])
                    if ok:
                        st.warning(msg)
                    else:
                        st.error(msg)
                    st.rerun()

# ── Create application ──
with tab3:
    with st.form("create_approval_form"):
        st.subheader("创建审批申请")
        atype = st.selectbox("审批类型", ["leave", "expense", "seal", "other"],
                             format_func=lambda x: {"leave":"请假","expense":"报销","seal":"用章","other":"其他"}[x])
        title = st.text_input("标题 *", placeholder="如：2024年6月差旅报销")
        description = st.text_area("说明", placeholder="详细描述申请内容...", height=120)

        from auth import get_all_users
        users = get_all_users()
        user_opts = {f"{u['display_name']} (@{u['username']})": u["id"] for u in users if u["id"] != user["id"]}
        selected = st.multiselect("审批人（按顺序）", list(user_opts.keys()), help="选择审批人，按选择顺序依次审批")

        if st.form_submit_button("提交申请", type="primary"):
            if not title.strip():
                st.error("请输入标题")
            elif not selected:
                st.error("请至少选择一个审批人")
            else:
                chain = [user_opts[s] for s in selected]
                aid = create_approval(title=title, applicant_id=user["id"], approval_type=atype,
                                      description=description, approval_chain=chain)
                st.success(f"申请已提交（ID: {aid}）")

# ── History ──
with tab4:
    result = list_approvals(status=st.selectbox("状态", ["全部", "approved", "rejected", "cancelled"],
                                                 format_func=lambda x:{"全部":"","approved":"已通过","rejected":"已驳回","cancelled":"已取消"}.get(x,""),
                                                 key="hist_status"))
    st.caption(f"共 {result['total']} 条")
    for a in result["approvals"]:
        st.caption(f"{'✅' if a['status']=='approved' else '❌'} [{a['type']}] {a['title']} — {a.get('applicant_name','')} · {a['created_at'][:10]}")
