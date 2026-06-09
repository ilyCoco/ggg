"""知识库浏览与管理页面"""

from __future__ import annotations

import streamlit as st

if "user" not in st.session_state:
    st.warning("请先在首页登录")
    st.stop()

from utils import inject_css, badge, ai_insight
inject_css()

from knowledge_base import (
    get_categories, create_category, update_category, delete_category,
    get_tags, create_tag, delete_tag,
    list_entries, search_entries, get_entry, update_entry, delete_entry,
    KnowledgeIntelligenceAgent,
)
from summary_system.llm_client import LLMClient

user = st.session_state["user"]
is_admin = user.get("role") == "admin"
llm = LLMClient.from_env()
kb_agent = KnowledgeIntelligenceAgent(llm)

st.title("📚 知识库")

# ── Sidebar ──
with st.sidebar:
    st.subheader("知识库管理")
    if is_admin:
        tab = st.radio("操作", ["浏览搜索", "AI 智能问答", "分类管理", "标签管理"], label_visibility="collapsed")
    else:
        tab = st.radio("操作", ["浏览搜索", "AI 智能问答"], label_visibility="collapsed")

# ── Browse & Search ──
if tab == "浏览搜索":
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_query = st.text_input("搜索知识库", placeholder="输入关键词搜索...")
    with col2:
        cats = get_categories()
        cat_options = {"全部": None}
        cat_options.update({c["name"]: c["id"] for c in cats})
        selected_cat = st.selectbox("分类筛选", list(cat_options.keys()), key="cat_filter")
    with col3:
        sort_options = {"最新": "created_at", "最近更新": "updated_at", "最热门": "view_count"}
        selected_sort = st.selectbox("排序方式", list(sort_options.keys()))

    if search_query.strip():
        result = search_entries(search_query.strip())
    else:
        result = list_entries(
            category_id=cat_options[selected_cat],
            sort_by=sort_options[selected_sort],
            only_public=False if is_admin else True,
            viewer_id=None if is_admin else user["id"],
        )

    st.caption(f"共 {result['total']} 条结果，第 {result['page']}/{result['total_pages']} 页")

    if not result["entries"]:
        st.info("暂无知识条目。从语音总结页面生成总结后可导入知识库。")
    else:
        for entry in result["entries"]:
            cat_icon = ""
            cat_name = ""
            for c in cats:
                if c["id"] == entry.get("category_id"):
                    cat_icon = c.get("icon", "")
                    cat_name = c["name"]
                    break
            with st.expander(f"{cat_icon} {entry['title']} — {entry.get('author_name', '')} · {entry['created_at'][:10]}"):
                st.caption(f"分类：{cat_name or '未分类'} | 场景：{entry['scene_type']} | 浏览：{entry['view_count']}")
                if entry.get("tags"):
                    tag_names = [t["name"] for t in entry["tags"]]
                    st.caption(f"标签：{', '.join(tag_names)}")
                st.markdown(entry["content"][:3000] + ("..." if len(entry.get("content", "")) > 3000 else ""))

                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("查看详情", key=f"view_{entry['id']}"):
                        st.session_state["view_entry"] = entry["id"]
                        st.rerun()
                with c2:
                    if user.get("role") == "admin" or entry.get("created_by") == user["id"]:
                        if st.button("编辑", key=f"edit_{entry['id']}"):
                            st.session_state["edit_entry"] = entry["id"]
                            st.rerun()
                with c3:
                    if user.get("role") == "admin" or entry.get("created_by") == user["id"]:
                        if st.button("删除", key=f"del_{entry['id']}"):
                            delete_entry(entry["id"])
                            st.success("已删除")
                            st.rerun()

    # ── Entry detail view (AI-enhanced) ──
    if st.session_state.get("view_entry"):
        entry = get_entry(st.session_state["view_entry"])
        if entry:
            st.divider()
            st.subheader(f"📄 {entry['title']}")
            st.caption(f"作者：{entry.get('author_name', '')} | 创建：{entry['created_at']} | 浏览：{entry['view_count']}")
            st.markdown(entry["content"])

            # AI features for this entry
            st.divider()
            ai_col1, ai_col2, ai_col3 = st.columns(3)
            with ai_col1:
                if st.button("🤖 AI 建议分类", key=f"ai_cat_{entry['id']}"):
                    suggestion = kb_agent.suggest_category(entry["title"], entry.get("content", ""))
                    if suggestion.get("category_name"):
                        st.success(f"建议分类：**{suggestion['category_name']}**（置信度 {suggestion['confidence']}）")
                        if suggestion.get("suggested_tags"):
                            st.caption(f"建议标签：{', '.join(suggestion['suggested_tags'])}")
                        st.caption(f"理由：{suggestion.get('reason','')}")
                        if st.button("✅ 应用分类", key=f"apply_cat_{entry['id']}"):
                            update_entry(entry["id"], category_id=suggestion.get("category_id"))
                            st.success("已更新分类")
                            st.rerun()
                    else:
                        st.info("AI 无法确定分类，请手动选择")
            with ai_col2:
                if st.button("🔗 AI 关联发现", key=f"ai_rel_{entry['id']}"):
                    rel_result = kb_agent.find_related_with_llm(entry["id"])
                    if rel_result["related"]:
                        st.caption(f"发现 {len(rel_result['related'])} 条可能相关")
                        if rel_result.get("ai_analysis"):
                            st.info(rel_result["ai_analysis"])
                        for rel in rel_result["related"][:5]:
                            if st.button(f"📄 {rel['title']}", key=f"rel_{rel['id']}"):
                                st.session_state["view_entry"] = rel["id"]
                                st.rerun()
                    else:
                        st.info("暂未发现关联条目")
            with ai_col3:
                if st.button("📝 AI 摘要", key=f"ai_summ_{entry['id']}"):
                    summary = kb_agent.summarize(entry["id"])
                    st.info(f"AI 摘要：{summary}")

            if st.button("关闭详情"):
                st.session_state.pop("view_entry")
                st.rerun()

    # ── Edit entry dialog ──
    if st.session_state.get("edit_entry"):
        entry = get_entry(st.session_state["edit_entry"])
        if entry:
            st.divider()
            st.subheader("✏️ 编辑知识条目")
            new_title = st.text_input("标题", value=entry["title"])
            new_content = st.text_area("内容（Markdown）", value=entry["content"], height=400)
            new_scene = st.selectbox(
                "场景类型",
                ["meeting", "classroom", "mixed", "general"],
                index=["meeting", "classroom", "mixed", "general"].index(entry.get("scene_type", "general")),
            )
            cat_sel = {c["name"]: c["id"] for c in cats}
            cat_sel["（不分类）"] = None
            current_cat = next((k for k, v in cat_sel.items() if v == entry.get("category_id")), "（不分类）")
            new_cat = st.selectbox("分类", list(cat_sel.keys()), index=list(cat_sel.keys()).index(current_cat))
            new_public = st.checkbox("公开", value=bool(entry.get("is_public")))

            # Tags
            all_tags = get_tags()
            current_tag_ids = {t["id"] for t in entry.get("tags", [])}
            selected_tags = st.multiselect(
                "标签",
                options=[t["name"] for t in all_tags],
                default=[t["name"] for t in all_tags if t["id"] in current_tag_ids],
            )
            selected_tag_ids = [t["id"] for t in all_tags if t["name"] in selected_tags]

            c1, c2 = st.columns(2)
            with c1:
                if st.button("保存修改", type="primary", use_container_width=True):
                    update_entry(
                        entry["id"],
                        title=new_title,
                        content=new_content,
                        scene_type=new_scene,
                        category_id=cat_sel[new_cat],
                        tag_ids=selected_tag_ids,
                        is_public=new_public,
                    )
                    st.success("已更新")
                    st.session_state.pop("edit_entry")
                    st.rerun()
            with c2:
                if st.button("取消", use_container_width=True):
                    st.session_state.pop("edit_entry")
                    st.rerun()

# ── AI Q&A Tab ──
elif tab == "AI 智能问答":
    st.subheader("🤖 AI 知识库问答")
    st.caption("基于知识库实际内容回答，不只搜标题")

    q_col1, q_col2, q_col3 = st.columns([2.5, 0.7, 0.8])
    with q_col1:
        kb_question = st.text_input(
            "输入问题",
            placeholder="例：最近的会议讨论了什么？/ 有哪些课堂知识？/ Q2项目的决策是什么？",
            label_visibility="collapsed",
        )
    with q_col2:
        deep_mode = st.checkbox("🔬 深度模式", value=False,
                                help="加载更多内容到 AI，回答更详细")
    with q_col3:
        ask = st.button("🤖 提问", type="primary", use_container_width=True)

    if ask and kb_question.strip():
        with st.spinner(f"AI 正在{'深度' if deep_mode else ''}搜索知识库..."):
            answer = kb_agent.answer_question(kb_question.strip(), deep=deep_mode)
            st.session_state["kb_answer"] = answer

    if st.session_state.get("kb_answer"):
        ans = st.session_state["kb_answer"]

        # ── Answer card ──
        st.markdown("---")
        st.markdown(f"**💬 {ans['question']}**")
        st.markdown(
            f'<div class="geshi-ai-box" style="font-size:1.02em;line-height:1.7">{ans.get("answer", "")}</div>',
            unsafe_allow_html=True,
        )

        # ── Source entries with preview ──
        if ans.get("results"):
            st.caption(f"🔍 搜索到 {len(ans['results'])} 条相关内容")
            for i, r in enumerate(ans["results"][:8]):
                method_badge = {"fts": "🔎 全文匹配", "like": "📝 关键词命中",
                                "scene": "🏷️ 场景匹配"}.get(r.get("search_method", ""), "")
                preview = r.get("content_preview", "")
                snippet = r.get("snippet", "")
                snippet_html = snippet.replace("<b>", "**").replace("</b>", "**") if snippet else ""

                with st.expander(
                    f"{r['title']} · {r.get('scene_type', '')} · {r.get('created_at', '')[:10]} "
                    f"· {method_badge}"
                ):
                    if snippet_html:
                        st.markdown(f"> {snippet_html}")
                    elif preview:
                        st.text(preview[:300])
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("📄 查看完整", key=f"kbans_{r['id']}"):
                            st.session_state["view_entry"] = r["id"]
                            st.rerun()
                    with c2:
                        # Quick AI summary for this single entry
                        if st.button("🤖 AI 摘要", key=f"kbss_{r['id']}"):
                            summary = kb_agent.summarize(r["id"])
                            st.info(summary)

        if st.button("✕ 清除结果", key="clear_kb_ans"):
            st.session_state.pop("kb_answer", None)
            st.rerun()

    # ── Sample questions + Search tips ──
    st.divider()
    st.caption("💡 试试这些（点击直接提问）：")
    samples = [
        ("最近的会议讨论了什么？", "meeting"),
        ("有哪些课堂知识点？", "classroom"),
        ("项目中有什么决策或风险？", "decision"),
        ("关于 Q2 的计划是什么？", "plan"),
    ]
    sc1, sc2, sc3, sc4 = st.columns(4)
    for idx, (sq, _) in enumerate(samples):
        col = [sc1, sc2, sc3, sc4][idx]
        with col:
            if st.button(sq, key=f"kbsq_{idx}", use_container_width=True):
                with st.spinner("AI 正在搜索..."):
                    answer = kb_agent.answer_question(sq)
                    st.session_state["kb_answer"] = answer
                    st.rerun()

    with st.expander("🔍 搜索技巧"):
        st.markdown("""
        - **具体问题**：问「Q2 上线日期是什么？」比「Q2」效果好
        - **使用关键词**：会议/课堂/项目/决策/风险 等词帮助定位场景
        - **深度模式**：加载更多内容到 AI，回答更详细（需配置 LLM API）
        - **无 LLM 时**：系统会展示每条相关内容的摘要，可手动阅读
        """)

# ── Category Management ──
elif tab == "分类管理":
    st.subheader("📁 分类管理")

    with st.form("new_cat_form"):
        cols = st.columns([3, 2, 1])
        cat_name = cols[0].text_input("分类名称", placeholder="新分类名称")
        cat_icon = cols[1].text_input("图标 Emoji", value="📁", placeholder="📁")
        cat_desc = st.text_input("描述", placeholder="分类描述（可选）")
        if st.form_submit_button("创建分类", type="primary"):
            if cat_name:
                ok, msg = create_category(cat_name, cat_desc, cat_icon)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    cats = get_categories()
    for c in cats:
        col1, col2, col3, col4 = st.columns([1, 3, 1, 1])
        col1.write(c["icon"])
        col2.write(f"**{c['name']}** — {c.get('description', '')} ({c['entry_count']} 条目)")
        with col3:
            new_icon = st.text_input("图标", value=c["icon"], key=f"icon_{c['id']}", label_visibility="collapsed")
        with col4:
            if st.button("删除", key=f"delcat_{c['id']}"):
                delete_category(c["id"])
                st.rerun()
        if new_icon != c["icon"]:
            update_category(c["id"], icon=new_icon)

# ── Tag Management ──
elif tab == "标签管理":
    st.subheader("🏷️ 标签管理")

    with st.form("new_tag_form"):
        cols = st.columns([3, 1, 1])
        tag_name = cols[0].text_input("标签名称", placeholder="新标签名称")
        tag_color = cols[1].color_picker("颜色", value="#6B7280")
        if st.form_submit_button("创建标签", type="primary"):
            if tag_name:
                ok, msg = create_tag(tag_name, tag_color)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    tags = get_tags()
    if tags:
        cols_per_row = 4
        for i in range(0, len(tags), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, tag in enumerate(tags[i : i + cols_per_row]):
                with cols[j]:
                    st.markdown(
                        f"<span style='background:{tag['color']}20;color:{tag['color']};"
                        f"padding:2px 10px;border-radius:12px;font-size:0.85em'>"
                        f"{tag['name']} ({tag['entry_count']})</span>",
                        unsafe_allow_html=True,
                    )
                    if st.button("删除", key=f"deltag_{tag['id']}"):
                        delete_tag(tag["id"])
                        st.rerun()
    else:
        st.info("暂无标签")
