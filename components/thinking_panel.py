"""Thinking panel — visualizes the agent's reasoning chain in Streamlit.

V2: timeline design, timing badges, token labels, live-updating container.
"""

from __future__ import annotations

import time
import streamlit as st

from agent_core.models import AgentStep


STEP_ICONS = {
    "thought":      "💭",
    "tool_call":    "🔧",
    "observation":  "📋",
    "final_answer": "✅",
    "error":        "❌",
}

STEP_COLORS = {
    "thought":      "#6366F1",
    "tool_call":    "#0EA5E9",
    "observation":  "#10B981",
    "final_answer": "#059669",
    "error":        "#EF4444",
}

STEP_BG = {
    "thought":      "#F5F3FF",
    "tool_call":    "#F0F9FF",
    "observation":  "#ECFDF5",
    "final_answer": "#D1FAE5",
    "error":        "#FEF2F2",
}

STEP_BORDER = {
    "thought":      "#C4B5FD",
    "tool_call":    "#BAE6FD",
    "observation":  "#A7F3D0",
    "final_answer": "#6EE7B7",
    "error":        "#FECACA",
}


def _fmt_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    return f"{seconds:.1f}s"


def _format_args(v) -> str:
    if isinstance(v, str):
        s = str(v)
        return f'"{s[:24]}..."' if len(s) > 24 else f'"{s}"'
    return str(v)


# ═══════════════════════════════════════════════════════════════
#  Main render function (collapsible, for completed chains)
# ═══════════════════════════════════════════════════════════════

def render_thinking_panel(
    steps: list[AgentStep],
    timings: list[float] | None = None,
    token_counts: list[int] | None = None,
    expanded: bool = False,
) -> None:
    """Render the full reasoning chain as an expandable timeline panel.

    Args:
        steps: List of agent reasoning steps.
        timings: Optional per-step durations in seconds.
        token_counts: Optional per-step token estimates.
        expanded: Whether the expander starts open.
    """
    if not steps:
        return

    tool_count = sum(1 for s in steps if s.step_type == "tool_call")
    agents_used = list(dict.fromkeys(s.agent_name for s in steps if s.agent_name))
    total_time = sum(timings) if timings else None

    label_parts = [f"🧠 推理过程 — {tool_count} 次工具调用"]
    if len(agents_used) > 1:
        label_parts.append(f"{len(agents_used)} 个智能体协作")
    if total_time is not None and total_time > 0:
        label_parts.append(f"总耗时 {_fmt_duration(total_time)}")

    with st.expander(" · ".join(label_parts), expanded=expanded):
        _render_timeline(steps, timings, token_counts)


def render_thinking_panel_live(
    steps: list[AgentStep],
    container,
    timings: list[float] | None = None,
    token_counts: list[int] | None = None,
) -> None:
    """Render reasoning steps into a live-updating container (no expander).

    Call this inside `with container:` block after each on_step callback.
    """
    _render_timeline(steps, timings, token_counts)


# ═══════════════════════════════════════════════════════════════
#  Agent status bar
# ═══════════════════════════════════════════════════════════════

def render_agent_status(
    agents_active: list[str],
    tool_count: int,
    total_tokens: int = 0,
    elapsed: float = 0,
) -> None:
    """Render the top agent status bar with live metrics."""
    agents_text = ""
    if agents_active:
        parts = []
        for a in agents_active:
            color = {"协调智能体": "#A5B4FC", "任务智能体": "#FBBF24", "日程智能体": "#38BDF8",
                     "知识库智能体": "#34D399", "审批智能体": "#22D3EE", "通用办公助理": "#CBD5E1",
                     "总结智能体": "#F472B6"}.get(a, "#E2E8F0")
            parts.append(f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;'
                         f'background:{color};margin-right:3px;box-shadow:0 0 6px {color}"></span>'
                         f'<span style="color:{color};font-weight:600">{a}</span>')
        agents_text = "&nbsp;&nbsp;".join(parts)
    else:
        agents_text = "🤖 待命中"

    elapsed_str = _fmt_duration(elapsed) if elapsed > 0 else "—"
    st.markdown(
        f'<div style="padding:10px 18px;background:linear-gradient(90deg,#0F172A,#1E1B4B,#0F172A);'
        f'border-radius:12px;margin-bottom:14px;border:1px solid rgba(99,102,241,0.2);'
        f'box-shadow:0 4px 20px rgba(0,0,0,0.3)">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">'
        f'<span style="font-size:.82em;color:#818CF8;font-weight:700;letter-spacing:1px">'
        f'⚡ AGENT STATUS</span>'
        f'<span style="font-size:.78em;color:#94A3B8">'
        f'<span style="color:#10B981">⬤</span> 工具调用 {tool_count}'
        f'&nbsp;&nbsp;💰 Token {total_tokens}'
        f'&nbsp;&nbsp;⏱ {elapsed_str}'
        f'</span>'
        f'</div>'
        f'<div style="margin-top:8px;font-size:.82em;line-height:1.8;color:#E2E8F0">{agents_text}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════
#  Internal: timeline render
# ═══════════════════════════════════════════════════════════════

def _render_timeline(
    steps: list[AgentStep],
    timings: list[float] | None = None,
    token_counts: list[int] | None = None,
) -> None:
    """Render steps as timeline items with connecting line."""

    ofs = "<span style='margin-left:26px'>"

    for i, step in enumerate(steps):
        icon = STEP_ICONS.get(step.step_type, "•")
        color = STEP_COLORS.get(step.step_type, "#64748B")
        bg = STEP_BG.get(step.step_type, "#F8FAFC")
        border = STEP_BORDER.get(step.step_type, "#E2E8F0")

        # Timing badge
        timing_html = ""
        if timings and i < len(timings) and timings[i] > 0:
            timing_html = (
                f'<span style="float:right;font-size:.72em;color:#94A3B8;'
                f'background:#F1F5F9;padding:1px 7px;border-radius:8px">'
                f'⏱ {_fmt_duration(timings[i])}</span>'
            )

        # Token badge
        token_html = ""
        if token_counts and i < len(token_counts) and token_counts[i] > 0:
            token_html = (
                f'<span style="float:right;font-size:.72em;color:#6366F1;'
                f'background:#EEF2FF;padding:1px 7px;border-radius:8px;margin-right:4px">'
                f'💰 {token_counts[i]}tk</span>'
            )

        if step.step_type == "thought":
            st.markdown(
                f'<div style="position:relative;padding:8px 14px;margin:0 0 0 14px;'
                f'border-left:2px solid {color};background:{bg};'
                f'border-radius:0 8px 8px 0;margin-bottom:2px">'
                f'{timing_html}{token_html}'
                f'<span style="color:{color};font-weight:600;font-size:.82em">'
                f'{icon} {step.agent_name or "思考"}</span>'
                f'<div style="font-size:.85em;color:#374151;margin-top:2px">{step.content}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        elif step.step_type == "tool_call":
            args_display = ""
            if step.tool_args:
                args_display = ", ".join(f"{k}={_format_args(v)}" for k, v in step.tool_args.items() if k != "user_id")
            st.markdown(
                f'<div style="position:relative;padding:8px 14px;margin:0 0 0 14px;'
                f'border-left:2px solid {color};background:{bg};'
                f'border-radius:0 8px 8px 0;margin-bottom:2px">'
                f'{timing_html}{token_html}'
                f'<span style="color:{color};font-weight:600;font-size:.82em">'
                f'{icon} {step.tool_name}</span>'
                f'<span style="color:#64748B;font-size:.76em;margin-left:6px">'
                f'({args_display})</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        elif step.step_type == "observation":
            display_text = step.content[:350]
            st.markdown(
                f'<div style="position:relative;padding:8px 14px;margin:0 0 2px 30px;'
                f'background:{bg};border-radius:8px;border:1px solid {border}">'
                f'{timing_html}'
                f'<span style="color:#065F46;font-size:.78em;font-weight:600">'
                f'{icon} 返回结果</span>'
                f'<div style="font-size:.8em;color:#374151;margin-top:3px;'
                f'max-height:120px;overflow-y:auto;white-space:pre-wrap;'
                f'font-family:Consolas,Monaco,monospace;background:#F8FAFC;'
                f'padding:4px 8px;border-radius:4px">{display_text}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        elif step.step_type == "final_answer":
            st.markdown(
                f'<div style="padding:10px 14px;margin:6px 0 0 14px;'
                f'background:linear-gradient(135deg,#ECFDF5,#D1FAE5);'
                f'border-radius:10px;border:2px solid #6EE7B7;'
                f'box-shadow:0 2px 8px rgba(16,185,129,0.1)">'
                f'{timing_html}{token_html}'
                f'<span style="color:{color};font-weight:700;font-size:.85em">'
                f'{icon} 最终回答</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        elif step.step_type == "error":
            st.markdown(
                f'<div style="padding:8px 14px;margin:0 0 0 14px;'
                f'background:{bg};border-radius:8px;border:1px solid {border};'
                f'animation:pulse 1s ease-in-out 2">'
                f'<span style="color:#DC2626;font-size:.82em;font-weight:600">{icon} {step.content}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Legend ──
    if len(steps) >= 3:
        total_steps = len(steps)
        n_thought = sum(1 for s in steps if s.step_type == "thought")
        n_tool = sum(1 for s in steps if s.step_type == "tool_call")
        n_obs = sum(1 for s in steps if s.step_type == "observation")
        st.caption(
            f"共 {total_steps} 步推理 · {n_thought} 次思考 · {n_tool} 次工具调用 · {n_obs} 次结果观察"
        )
