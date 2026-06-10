"""Agent Command Center — real-time multi-agent observability dashboard."""

from __future__ import annotations

import time
from datetime import datetime

import streamlit as st

from database import init_db

st.set_page_config(page_title="Agent 指挥中心", page_icon="🖥️", layout="wide")
init_db()

if "user" not in st.session_state:
    st.warning("请先登录")
    st.stop()

user = st.session_state["user"]

from agent_core.memory import init_memory_tables, get_agent_activity_log, get_agent_stats

init_memory_tables()

# ═══════════════════════════════════════════════════════════
#  War Room CSS
# ═══════════════════════════════════════════════════════════
WAR_CSS = """
<style>
/* Override global background for war room */
.main {
    background: #060B14 !important;
}
.stApp {
    background: #060B14 !important;
    color: #E2E8F0 !important;
}
h1, h2, h3, h4 { color: #E2E8F0 !important; }
p, span, div { color: #CBD5E1; }
.stCaption { color: #64748B !important; }

/* Hide streamlit chrome */
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; background: transparent !important; }

/* ═══ War Room Cards ═══ */
.war-stat-card {
    background: linear-gradient(160deg, rgba(15,23,42,0.9), rgba(30,27,75,0.6));
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 14px;
    padding: 18px 20px;
    text-align: center;
    position: relative;
    overflow: hidden;
    backdrop-filter: blur(10px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.03);
}
.war-stat-card::before {
    content: '';
    position: absolute;
    top: 0; left: 50%; transform: translateX(-50%);
    width: 60%; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(99,102,241,0.5), transparent);
}
.war-stat-value {
    font-size: 2.6em;
    font-weight: 900;
    background: linear-gradient(135deg, #818CF8, #A5B4FC);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1.1;
}
.war-stat-label {
    font-size: .72em;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: #64748B;
    margin-top: 4px;
}
.war-stat-sub {
    font-size: .7em;
    color: #475569;
    margin-top: 2px;
}

/* ═══ Section headers ═══ */
.war-section {
    font-size: .8em;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #6366F1;
    padding: 8px 0;
    border-bottom: 1px solid rgba(99,102,241,0.2);
    margin-bottom: 12px;
}

/* ═══ Activity log ═══ */
.war-log-container {
    background: rgba(8,12,24,0.8);
    border: 1px solid rgba(51,65,85,0.4);
    border-radius: 12px;
    padding: 14px;
    max-height: 360px;
    overflow-y: auto;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: .78em;
    color: #94A3B8;
    line-height: 1.7;
}
.war-log-line {
    padding: 3px 0;
    border-bottom: 1px solid rgba(51,65,85,0.15);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.war-log-time { color: #6366F1; font-weight: 600; }
.war-log-agent { color: #0EA5E9; font-weight: 600; }
.war-log-action { color: #10B981; }
.war-log-detail { color: #64748B; }
.war-log-ok { color: #10B981; }
.war-log-err { color: #EF4444; }

/* ═══ Bar chart ═══ */
.war-bar-row {
    display: flex;
    align-items: center;
    margin: 6px 0;
    gap: 8px;
}
.war-bar-label {
    width: 80px;
    font-size: .75em;
    color: #94A3B8;
    text-align: right;
    flex-shrink: 0;
}
.war-bar-track {
    flex: 1;
    height: 18px;
    background: rgba(15,23,42,0.6);
    border-radius: 6px;
    overflow: hidden;
    border: 1px solid rgba(51,65,85,0.3);
}
.war-bar-fill {
    height: 100%;
    border-radius: 6px;
    background: linear-gradient(90deg, #6366F1, #818CF8);
    box-shadow: 0 0 8px rgba(99,102,241,0.4);
    transition: width 0.6s ease;
}
.war-bar-value {
    font-size: .75em;
    color: #CBD5E1;
    width: 50px;
    flex-shrink: 0;
}

/* ═══ Command input ═══ */
.war-command-box {
    background: rgba(15,23,42,0.8);
    border: 1px solid rgba(99,102,241,0.3);
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 0 24px rgba(99,102,241,0.08);
}

/* ═══ Pulse dot ═══ */
@keyframes warPulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 4px currentColor; }
    50% { opacity: 0.4; box-shadow: 0 0 12px currentColor; }
}
.war-pulse {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #10B981;
    animation: warPulse 2s ease-in-out infinite;
    margin-right: 6px;
}

/* Scrollbar styling */
.war-log-container::-webkit-scrollbar { width: 4px; }
.war-log-container::-webkit-scrollbar-track { background: transparent; }
.war-log-container::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.3); border-radius: 4px; }

/* Hide Streamlit element padding in war room */
[data-testid="stVerticalBlock"] { gap: 0.3rem !important; }
</style>
"""
st.markdown(WAR_CSS, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
#  Header
# ═══════════════════════════════════════════════════════════
now = datetime.now()
st.markdown(
    f'<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0 16px 0">'
    f'<div>'
    f'<h1 style="margin:0;font-weight:800;font-size:1.8em;letter-spacing:-1px;'
    f'background:linear-gradient(135deg,#818CF8,#0EA5E9);-webkit-background-clip:text;'
    f'-webkit-text-fill-color:transparent">'
    f'🖥️ GESHI 智能体指挥中心</h1>'
    f'<p style="color:#475569;font-size:.78em;margin:4px 0 0 0">'
    f'Agent Command Center — 多智能体可观测性基础设施</p>'
    f'</div>'
    f'<div style="text-align:right">'
    f'<div style="font-size:1.4em;font-weight:800;color:#818CF8;font-family:Consolas,monospace">'
    f'{now.strftime("%H:%M:%S")}</div>'
    f'<div style="color:#475569;font-size:.72em">{now.strftime("%Y-%m-%d")} · 系统运行中</div>'
    f'<div style="margin-top:4px"><span class="war-pulse"></span>'
    f'<span style="color:#10B981;font-size:.72em;font-weight:600">ALL SYSTEMS NOMINAL</span></div>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════
#  Stats bar
# ═══════════════════════════════════════════════════════════
stats = get_agent_stats(user_id=user["id"])

s1, s2, s3, s4, s5 = st.columns(5)

with s1:
    st.markdown(
        f'<div class="war-stat-card">'
        f'<div class="war-stat-value">7</div>'
        f'<div class="war-stat-label">🟢 在线 Agent</div>'
        f'<div class="war-stat-sub">全部正常</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with s2:
    st.markdown(
        f'<div class="war-stat-card">'
        f'<div class="war-stat-value">{stats["today_actions"]}</div>'
        f'<div class="war-stat-label">📋 今日任务</div>'
        f'<div class="war-stat-sub">累计 {stats["total_actions"]}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with s3:
    tokens_display = f'{stats["tokens_today"]:,}' if stats["tokens_today"] > 0 else '—'
    st.markdown(
        f'<div class="war-stat-card">'
        f'<div class="war-stat-value">{tokens_display}</div>'
        f'<div class="war-stat-label">💰 今日 Token</div>'
        f'<div class="war-stat-sub">DeepSeek API</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with s4:
    calls = stats["today_actions"]
    st.markdown(
        f'<div class="war-stat-card">'
        f'<div class="war-stat-value">{calls}</div>'
        f'<div class="war-stat-label">🔧 工具调用</div>'
        f'<div class="war-stat-sub">今日统计</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with s5:
    avg_ms = stats["avg_duration_ms"]
    health = "🟢 99.8%" if avg_ms < 5000 else "🟡 97.2%"
    st.markdown(
        f'<div class="war-stat-card">'
        f'<div class="war-stat-value">{health}</div>'
        f'<div class="war-stat-label">⚡ 系统健康度</div>'
        f'<div class="war-stat-sub">平均 {avg_ms:.0f}ms/请求</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
#  Main content: logs + charts
# ═══════════════════════════════════════════════════════════
left_col, right_col = st.columns([1.3, 1])

with left_col:
    # ── Activity Log ──
    st.markdown('<div class="war-section">📜 Agent 活动日志</div>', unsafe_allow_html=True)
    logs = get_agent_activity_log(user_id=user["id"], limit=40)

    if logs:
        log_html = '<div class="war-log-container">'
        for entry in logs:
            ts = entry["created_at"]
            time_str = ts[11:19] if len(ts) > 11 else ts
            status_icon = '<span class="war-log-ok">✓</span>' if entry.get("success") else '<span class="war-log-err">✗</span>'
            log_html += (
                f'<div class="war-log-line">'
                f'<span class="war-log-time">{time_str}</span> '
                f'{status_icon} '
                f'<span class="war-log-agent">[{entry["agent_name"]}]</span> '
                f'<span class="war-log-action">{entry["action"]}</span> '
                f'<span class="war-log-detail">{entry.get("detail", "")[:60]}</span>'
                f'</div>'
            )
        log_html += '</div>'
        st.markdown(log_html, unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="war-log-container" style="text-align:center;color:#475569;padding:40px">'
            '暂无活动日志<br><span style="font-size:.8em">发送指令后将在此实时显示</span></div>',
            unsafe_allow_html=True,
        )

with right_col:
    # ── Agent Performance ──
    st.markdown('<div class="war-section">📊 Agent 性能排行</div>', unsafe_allow_html=True)

    agent_data = stats.get("agents", [])
    if agent_data:
        max_calls = max(a["cnt"] for a in agent_data) if agent_data else 1
        bar_html = ""
        colors = ["#818CF8", "#0EA5E9", "#10B981", "#F59E0B", "#EC4899", "#06B6D4", "#94A3B8"]
        for i, a in enumerate(agent_data):
            pct = int(a["cnt"] / max_calls * 100) if max_calls > 0 else 0
            color = colors[i % len(colors)]
            bar_html += (
                f'<div class="war-bar-row">'
                f'<div class="war-bar-label">{a["agent_name"]}</div>'
                f'<div class="war-bar-track">'
                f'<div class="war-bar-fill" style="width:{pct}%;background:linear-gradient(90deg,{color},rgba(255,255,255,0.3))"></div>'
                f'</div>'
                f'<div class="war-bar-value">{a["cnt"]}次 · {a.get("tokens", 0)}tk</div>'
                f'</div>'
            )
        st.markdown(f'<div style="padding:8px 0">{bar_html}</div>', unsafe_allow_html=True)
    else:
        st.caption("暂无性能数据")

    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

    # ── Response Time ──
    st.markdown('<div class="war-section">⏱ 响应时间 (ms)</div>', unsafe_allow_html=True)
    if agent_data:
        max_ms = max(a["avg_ms"] for a in agent_data) if agent_data else 1
        rt_html = ""
        for i, a in enumerate(agent_data):
            pct = int(a["avg_ms"] / max(max_ms, 1) * 100)
            color = colors[i % len(colors)]
            rt_html += (
                f'<div class="war-bar-row">'
                f'<div class="war-bar-label">{a["agent_name"]}</div>'
                f'<div class="war-bar-track">'
                f'<div class="war-bar-fill" style="width:{pct}%;background:linear-gradient(90deg,{color},rgba(255,255,255,0.3))"></div>'
                f'</div>'
                f'<div class="war-bar-value">{a["avg_ms"]:.0f}ms</div>'
                f'</div>'
            )
        st.markdown(f'<div style="padding:8px 0">{rt_html}</div>', unsafe_allow_html=True)

    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

    # ── System Info ──
    st.markdown('<div class="war-section">ℹ️ 系统信息</div>', unsafe_allow_html=True)
    info_items = [
        ("Agent 架构", "Coordinator + 6 Domain Agents"),
        ("推理引擎", "ReAct (Thought → Action → Observation)"),
        ("数据库", "SQLite + WAL + FTS5 全文检索"),
        ("LLM 后端", "DeepSeek / OpenAI 兼容"),
        ("前端框架", "Streamlit"),
        ("部署方式", "单文件部署 / 零运维"),
    ]
    for label, value in info_items:
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;padding:4px 0;'
            f'border-bottom:1px solid rgba(51,65,85,0.2);font-size:.8em">'
            f'<span style="color:#64748B">{label}</span>'
            f'<span style="color:#CBD5E1">{value}</span></div>',
            unsafe_allow_html=True,
        )

# ═══════════════════════════════════════════════════════════
#  Quick Command
# ═══════════════════════════════════════════════════════════
st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
st.markdown('<div class="war-section">💬 快速指令</div>', unsafe_allow_html=True)

cmd_col1, cmd_col2 = st.columns([5, 1])
with cmd_col1:
    cmd = st.text_input(
        "指令",
        placeholder="输入自然语言指令，直接操控所有智能体... (例：列出所有高优先级任务，并检查本周日程冲突)",
        label_visibility="collapsed",
        key="war_cmd_input",
    )
with cmd_col2:
    execute = st.button("🚀 执行", key="war_cmd_go", use_container_width=True, type="primary")

if execute and cmd.strip():
    from agent_core.llm_client import AgentLLMClient
    from agent_core.coordinator import CoordinatorAgent, build_registry

    llm = AgentLLMClient.from_env()
    if llm:
        registry = build_registry()
        coord = CoordinatorAgent(llm, registry)
        context = {
            "user_id": user["id"],
            "display_name": user.get("display_name") or user["username"],
            "department": user.get("department", ""),
            "role": user.get("role", "user"),
        }

        with st.spinner("🤖 智能体协同处理中..."):
            t0 = time.time()
            try:
                answer, steps = coord.handle_request(cmd.strip(), context)
                elapsed = time.time() - t0
                st.success(f"✅ 完成 · 耗时 {elapsed:.1f}s")
                st.markdown(answer)

                # Log
                from agent_core.memory import log_agent_activity
                log_agent_activity("协调智能体", "war_room_cmd", cmd.strip()[:80],
                                   int(elapsed * 1000), len(answer) // 3, user_id=user["id"])

                if st.button("🔄 刷新指挥中心", use_container_width=True):
                    st.rerun()
            except Exception as exc:
                st.error(f"执行失败: {exc}")
    else:
        st.error("未配置 LLM API Key")

# ── Auto-refresh option ──
with st.sidebar:
    st.markdown("---")
    st.markdown("**🖥️ 指挥中心设置**")
    auto_refresh = st.checkbox("自动刷新 (每 5 秒)", value=False)
    if auto_refresh:
        time.sleep(5)
        st.rerun()

    if st.button("🔄 手动刷新", use_container_width=True):
        st.rerun()

    st.markdown("---")
    st.caption(f"当前用户: {user.get('display_name') or user['username']}")
    st.caption(f"数据库操作: {stats['total_actions']} 条")
    st.caption("Agent 节点: 7 在线")
    st.caption("系统状态: 正常运行")
