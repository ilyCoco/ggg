"""AI Assistant — multi-agent chat with streaming output & live reasoning panel."""

from __future__ import annotations

import time
import streamlit as st

from database import init_db
from utils import inject_css

st.set_page_config(page_title="AI 智能助手", page_icon="🤖", layout="wide")
init_db()
inject_css()

if "user" not in st.session_state:
    st.warning("请先登录")
    st.stop()

user = st.session_state["user"]

from agent_core.llm_client import AgentLLMClient
from agent_core.coordinator import CoordinatorAgent, build_registry
from agent_core.memory import MemoryManager, init_memory_tables, log_agent_activity
from agent_core.models import AgentStep
from components import render_thinking_panel, render_agent_status
from components.thinking_panel import STEP_ICONS

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

chat_key = f"chat_history_{user['id']}"
if chat_key not in st.session_state:
    st.session_state[chat_key] = []
if "memory_mgr" not in st.session_state:
    st.session_state["memory_mgr"] = MemoryManager(user["id"])
token_key = f"total_tokens_{user['id']}"
if token_key not in st.session_state:
    st.session_state[token_key] = 0

memory = st.session_state["memory_mgr"]

# ═══════════════════════════════════════════════════════════
#  Header
# ═══════════════════════════════════════════════════════════
st.markdown(
    '<div style="padding:4px 0 8px 0">'
    '<h2 style="margin:0;font-weight:700;letter-spacing:-.5px">🤖 AI 智能助手</h2>'
    '<p style="color:#98A2B3;font-size:.85em;margin:4px 0 0 0">'
    '多智能体协同 · 流式推理 · 思维链可视化</p>'
    '</div>',
    unsafe_allow_html=True,
)

# ── Agent status bar ──
total_tools = sum(
    sum(1 for s in msg.get("steps", []) if s.step_type == "tool_call")
    for msg in st.session_state[chat_key] if msg["role"] == "assistant"
)
recent_agents = []
if st.session_state[chat_key]:
    for msg in reversed(st.session_state[chat_key]):
        if msg["role"] == "assistant" and msg.get("steps"):
            recent_agents = list(dict.fromkeys(s.agent_name for s in msg["steps"] if s.agent_name))
            break

last_elapsed = 0
if st.session_state[chat_key]:
    for msg in reversed(st.session_state[chat_key]):
        if msg["role"] == "assistant" and msg.get("elapsed"):
            last_elapsed = msg["elapsed"]
            break

render_agent_status(recent_agents, total_tools, st.session_state[token_key], last_elapsed)

# ── Quick actions ──
qa_cols = st.columns(6)
quick_actions = [
    ("📋 本周任务", "列出我本周的所有任务"),
    ("📅 今日日程", "我今天有什么安排？"),
    ("🔍 搜知识库", "搜索知识库中关于项目管理的内容"),
    ("📊 工作总结", "帮我总结本周工作进展"),
    ("🕐 考勤查询", "查看我本月的考勤统计"),
    ("📝 创建任务", "帮我创建一个明天的任务：准备项目答辩PPT，高优先级"),
]
for i, (label, prompt) in enumerate(quick_actions):
    with qa_cols[i]:
        if st.button(label, key=f"qa_{hash(prompt) % 100000}", use_container_width=True):
            st.session_state["pending_input"] = prompt
            st.rerun()

st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

# ── Chat history ──
for msg in st.session_state[chat_key]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("steps"):
            timings = msg.get("timings")
            tokens = msg.get("step_tokens")
            render_thinking_panel(msg["steps"], timings=timings, token_counts=tokens)

# ── Chat input ──
pending = st.session_state.pop("pending_input", None)
user_input = st.chat_input("输入指令，让 AI 帮你处理办公事务...")

if pending:
    user_input = pending

if user_input:
    st.session_state[chat_key].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        status = st.status("🤖 智能体正在推理...", expanded=True)
        steps_collected: list[AgentStep] = []
        step_timings: list[float] = []
        current_step_start = [time.time()]

        def on_step(step: AgentStep):
            now = time.time()
            step_timings.append(now - current_step_start[0])
            current_step_start[0] = now
            steps_collected.append(step)
            with status:
                icon = STEP_ICONS.get(step.step_type, "•")
                dur = step_timings[-1] if step_timings else 0
                dur_str = f"({dur:.1f}s)" if dur > 0.05 else ""
                if step.step_type == "tool_call":
                    st.write(f"{icon} 调用工具: **{step.tool_name}** {dur_str}")
                elif step.step_type == "thought":
                    st.write(f"{icon} {step.content[:120]}{'...' if len(step.content) > 120 else ''} {dur_str}")
                elif step.step_type == "observation":
                    st.caption(f"{icon} 返回: {step.content[:100]}...")
                elif step.step_type == "error":
                    st.error(f"{icon} {step.content[:100]}")

        context = {
            "user_id": user["id"],
            "display_name": user.get("display_name") or user["username"],
            "department": user.get("department", ""),
            "role": user.get("role", "user"),
            "chat_history": [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state[chat_key][-7:-1]
            ],
        }

        t_start = time.time()
        try:
            answer, steps = coordinator.handle_request(
                user_input, context, memory=memory, on_step=on_step
            )
        except Exception as exc:
            answer = f"处理请求时出错: {exc}"
            steps = steps_collected

        total_elapsed = time.time() - t_start
        status.update(label=f"✅ 推理完成 · 耗时 {total_elapsed:.1f}s", state="complete", expanded=False)

        # Streaming typing effect
        answer_placeholder = st.empty()
        streamed = ""
        words = answer.replace("\n", " \n ").split(" ")
        for word in words:
            if word == "\n":
                streamed += "\n\n"
            elif word:
                streamed += word + " "
            answer_placeholder.markdown(streamed + "▌")
            delay = min(0.025, max(0.008, 0.5 / max(len(word), 1)))
            time.sleep(delay)
        answer_placeholder.markdown(answer)

        if steps:
            step_tokens_est = []
            for s in steps:
                if s.step_type == "tool_call":
                    step_tokens_est.append(80)
                elif s.step_type == "observation":
                    step_tokens_est.append(len(s.content) // 3)
                elif s.step_type == "thought":
                    step_tokens_est.append(len(s.content) // 2)
                else:
                    step_tokens_est.append(len(s.content) // 3)
            render_thinking_panel(steps, timings=step_timings, token_counts=step_tokens_est)

        total_tokens_est = sum(step_tokens_est) if step_tokens_est else 0
        st.session_state[token_key] += total_tokens_est

        log_agent_activity("协调智能体", "handle_request",
                           user_input[:80], int(total_elapsed * 1000), total_tokens_est,
                           user_id=user["id"])

    st.session_state[chat_key].append({
        "role": "assistant",
        "content": answer,
        "steps": steps,
        "timings": step_timings,
        "step_tokens": step_tokens_est,
        "elapsed": total_elapsed,
    })

if st.session_state[chat_key]:
    c1, _ = st.columns([1, 10])
    with c1:
        if st.button("🗑️ 清空对话", key="clear_chat_main", use_container_width=True):
            st.session_state[chat_key] = []
            st.session_state[token_key] = 0
            memory.clear_session()
            st.rerun()

# ── Sidebar ──
with st.sidebar:
    st.markdown("---")
    st.markdown("**🤖 智能体系统**")
    st.caption(f"已注册工具: {len(coordinator.registry.list_tools())}")
    st.caption(f"对话轮数: {len(st.session_state[chat_key]) // 2}")
    st.caption(f"累计 Token: {st.session_state[token_key]:,}")

    if st.button("🗑️ 清空对话", key="clear_sidebar", use_container_width=True):
        st.session_state[chat_key] = []
        st.session_state[token_key] = 0
        memory.clear_session()
        st.rerun()

    with st.expander("📝 已注册工具列表"):
        for tool in coordinator.registry.list_tools():
            st.caption(f"• **{tool.name}** [{tool.domain}]")
            st.caption(f"  {tool.description[:40]}...")

    with st.expander("📊 系统信息"):
        st.caption("Agent 数量: 7")
        st.caption("数据库: SQLite + FTS5")
        st.caption("框架: Streamlit + ReAct")
