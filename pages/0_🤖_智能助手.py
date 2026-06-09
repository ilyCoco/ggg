"""Unified AI Assistant chat page — the main agentic interface."""

from __future__ import annotations

import streamlit as st

from database import init_db
from utils import inject_css

st.set_page_config(page_title="AI 智能助手", page_icon="🤖", layout="wide")
init_db()
inject_css()

# ── Auth check ──
if "user" not in st.session_state:
    st.warning("请先登录")
    st.stop()

user = st.session_state["user"]

# ── Initialize agent system ──
from agent_core.llm_client import AgentLLMClient
from agent_core.coordinator import CoordinatorAgent, build_registry
from agent_core.memory import MemoryManager, init_memory_tables
from agent_core.models import AgentStep
from components.thinking_panel import render_thinking_panel, render_agent_status

init_memory_tables()


@st.cache_resource
def get_coordinator():
    llm = AgentLLMClient.from_env()
    if not llm:
        return None
    registry = build_registry()
    return CoordinatorAgent(llm, registry)


coordinator = get_coordinator()

if not coordinator:
    st.error("未配置 LLM API Key，请在 .env 中设置 DEEPSEEK_API_KEY")
    st.stop()

# ── Session state ──
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "memory_mgr" not in st.session_state:
    st.session_state["memory_mgr"] = MemoryManager(user["id"])

memory = st.session_state["memory_mgr"]

# ── Page header ──
st.markdown(
    '<div style="padding:4px 0 12px 0">'
    '<h2 style="margin:0;font-weight:700;letter-spacing:-.5px">🤖 AI 智能助手</h2>'
    '<p style="color:#64748B;font-size:.88em;margin:4px 0 0 0">'
    '多智能体协同 · ReAct 推理 · 自然语言操控办公系统</p>'
    '</div>',
    unsafe_allow_html=True,
)

# ── Agent status bar ──
total_tools = sum(
    sum(1 for s in msg.get("steps", []) if s.step_type == "tool_call")
    for msg in st.session_state["chat_history"]
    if msg["role"] == "assistant"
)
recent_agents = []
if st.session_state["chat_history"]:
    for msg in reversed(st.session_state["chat_history"]):
        if msg["role"] == "assistant" and msg.get("steps"):
            recent_agents = list({s.agent_name for s in msg["steps"] if s.agent_name})[:3]
            break
render_agent_status(recent_agents, total_tools)

# ── Quick actions ──
st.markdown('<div style="margin-bottom:12px">', unsafe_allow_html=True)
qa_cols = st.columns(5)
quick_actions = [
    ("📋 本周任务", "列出我本周的所有任务"),
    ("📅 今日日程", "我今天有什么安排？"),
    ("🔍 搜知识库", "搜索知识库中关于项目管理的内容"),
    ("📊 工作总结", "帮我总结本周工作进展"),
    ("🕐 考勤查询", "查看我本月的考勤统计"),
]
for i, (label, prompt) in enumerate(quick_actions):
    with qa_cols[i]:
        if st.button(label, key=f"qa_{i}", use_container_width=True):
            st.session_state["pending_input"] = prompt
            st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# ── Chat history display ──
for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("steps"):
            render_thinking_panel(msg["steps"])

# ── Chat input ──
pending = st.session_state.pop("pending_input", None)
user_input = st.chat_input("输入指令，让 AI 帮你处理办公事务...")

if pending:
    user_input = pending

if user_input:
    # Display user message
    st.session_state["chat_history"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Run agent
    with st.chat_message("assistant"):
        status = st.status("🤖 智能体正在推理...", expanded=True)
        steps_collected: list[AgentStep] = []

        def on_step(step: AgentStep):
            steps_collected.append(step)
            with status:
                icon = {"thought": "💭", "tool_call": "🔧", "observation": "📋",
                        "final_answer": "✅", "error": "❌"}.get(step.step_type, "•")
                if step.step_type == "tool_call":
                    st.write(f"{icon} 调用工具: **{step.tool_name}**")
                elif step.step_type == "thought":
                    st.write(f"{icon} {step.content[:100]}")
                elif step.step_type == "observation":
                    st.caption(f"{icon} 返回: {step.content[:80]}...")

        context = {
            "user_id": user["id"],
            "display_name": user.get("display_name") or user["username"],
            "department": user.get("department", ""),
            "role": user.get("role", "user"),
            "chat_history": [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state["chat_history"][-7:-1]  # exclude current message, last 3 rounds
            ],
        }

        try:
            answer, steps = coordinator.handle_request(
                user_input, context, memory=memory, on_step=on_step
            )
        except Exception as exc:
            answer = f"处理请求时出错: {exc}"
            steps = steps_collected

        status.update(label="✅ 推理完成", state="complete", expanded=False)

        st.markdown(answer)
        if steps:
            render_thinking_panel(steps)

    st.session_state["chat_history"].append({
        "role": "assistant",
        "content": answer,
        "steps": steps,
    })

# ── Sidebar controls ──
with st.sidebar:
    st.markdown("---")
    st.markdown("**🤖 智能体系统**")
    st.caption(f"已注册工具: {len(coordinator.registry.list_tools())}")
    st.caption(f"对话轮数: {len(st.session_state['chat_history']) // 2}")

    if st.button("🗑️ 清空对话", use_container_width=True):
        st.session_state["chat_history"] = []
        memory.clear_session()
        st.rerun()

    with st.expander("📝 已注册工具列表"):
        for tool in coordinator.registry.list_tools():
            st.caption(f"• **{tool.name}** [{tool.domain}]")
            st.caption(f"  {tool.description[:40]}...")
