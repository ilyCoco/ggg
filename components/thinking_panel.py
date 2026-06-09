"""Thinking panel — visualizes the agent's reasoning chain in Streamlit."""

from __future__ import annotations

import streamlit as st

from agent_core.models import AgentStep


STEP_ICONS = {
    "thought": "💭",
    "tool_call": "🔧",
    "observation": "📋",
    "final_answer": "✅",
    "error": "❌",
}

STEP_COLORS = {
    "thought": "#6366F1",
    "tool_call": "#0EA5E9",
    "observation": "#10B981",
    "final_answer": "#059669",
    "error": "#EF4444",
}


def render_thinking_panel(steps: list[AgentStep], expanded: bool = False) -> None:
    """Render the full reasoning chain as an expandable panel."""
    if not steps:
        return

    tool_count = sum(1 for s in steps if s.step_type == "tool_call")
    agents_used = list({s.agent_name for s in steps if s.agent_name})

    label = f"🧠 推理过程 — {tool_count} 次工具调用"
    if len(agents_used) > 1:
        label += f" · {len(agents_used)} 个智能体协作"

    with st.expander(label, expanded=expanded):
        for i, step in enumerate(steps):
            _render_step(step, i)


def render_step_live(step: AgentStep, container) -> None:
    """Render a single step into a Streamlit container (for real-time updates)."""
    with container:
        _render_step(step, 0)


def _render_step(step: AgentStep, index: int) -> None:
    """Render a single reasoning step."""
    icon = STEP_ICONS.get(step.step_type, "•")
    color = STEP_COLORS.get(step.step_type, "#64748B")

    if step.step_type == "thought":
        st.markdown(
            f'<div style="padding:6px 12px;margin:4px 0;border-left:3px solid {color};'
            f'background:#F8FAFC;border-radius:0 6px 6px 0">'
            f'<span style="color:{color};font-weight:600;font-size:.85em">'
            f'{icon} {step.agent_name or "思考"}</span><br>'
            f'<span style="font-size:.9em;color:#374151">{step.content}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    elif step.step_type == "tool_call":
        args_display = ""
        if step.tool_args:
            args_display = ", ".join(f"{k}={_format_val(v)}" for k, v in step.tool_args.items())
        st.markdown(
            f'<div style="padding:6px 12px;margin:4px 0;border-left:3px solid {color};'
            f'background:#F0F9FF;border-radius:0 6px 6px 0">'
            f'<span style="color:{color};font-weight:600;font-size:.85em">'
            f'{icon} {step.tool_name}</span>'
            f'<span style="color:#64748B;font-size:.8em;margin-left:8px">'
            f'({args_display})</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    elif step.step_type == "observation":
        display_text = step.content[:300]
        st.markdown(
            f'<div style="padding:6px 12px;margin:4px 0 8px 20px;'
            f'background:#F0FDF4;border-radius:6px;border:1px solid #BBF7D0">'
            f'<span style="color:#065F46;font-size:.82em">'
            f'{icon} 返回结果</span><br>'
            f'<span style="font-size:.82em;color:#374151">{display_text}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    elif step.step_type == "final_answer":
        st.markdown(
            f'<div style="padding:8px 12px;margin:6px 0;'
            f'background:#ECFDF5;border-radius:8px;border:1px solid #6EE7B7">'
            f'<span style="color:{color};font-weight:600;font-size:.85em">'
            f'{icon} 最终回答</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    elif step.step_type == "error":
        st.markdown(
            f'<div style="padding:6px 12px;margin:4px 0;'
            f'background:#FEF2F2;border-radius:6px;border:1px solid #FECACA">'
            f'<span style="color:#DC2626;font-size:.85em">{icon} {step.content}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_agent_status(agents_active: list[str], tool_count: int) -> None:
    """Render agent status bar at the top of the chat page."""
    agents_text = " → ".join(f"🤖 {a}" for a in agents_active) if agents_active else "🤖 待命"
    st.markdown(
        f'<div style="padding:8px 16px;background:linear-gradient(90deg,#EEF2FF,#F8FAFC);'
        f'border-radius:8px;margin-bottom:12px;border:1px solid #E0E7FF">'
        f'<span style="font-size:.85em;color:#4338CA;font-weight:600">智能体状态</span>'
        f'<span style="float:right;font-size:.8em;color:#64748B">'
        f'工具调用: {tool_count}</span><br>'
        f'<span style="font-size:.82em;color:#6366F1">{agents_text}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _format_val(v) -> str:
    if isinstance(v, str):
        return f'"{v[:20]}"' if len(str(v)) > 20 else f'"{v}"'
    return str(v)
