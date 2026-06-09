"""Shared theme — premium CSS + reusable UI components."""

from __future__ import annotations

import streamlit as st


CSS = """
<style>
/* ═══════════════════════════════════════════════════════════════
   GESHI DESIGN SYSTEM
   ═══════════════════════════════════════════════════════════════ */

/* ── Root ── */
:root {
  --geshi-bg:        #F0F2F8;
  --geshi-surface:   #FFFFFF;
  --geshi-primary:   #4F46E5;
  --geshi-primary-l: #818CF8;
  --geshi-accent:    #0EA5E9;
  --geshi-success:   #10B981;
  --geshi-warning:   #F59E0B;
  --geshi-danger:    #EF4444;
  --geshi-text:      #1E293B;
  --geshi-text-dim:  #64748B;
  --geshi-border:    #E2E8F0;
  --geshi-shadow:    0 1px 2px rgba(0,0,0,.04), 0 2px 8px rgba(0,0,0,.04);
  --geshi-shadow-lg: 0 4px 16px rgba(0,0,0,.06), 0 1px 4px rgba(0,0,0,.04);
}

/* ── Global background ── */
.main {
    background: linear-gradient(180deg, #EEF2FF 0%, #F0F2F8 30%, #F8FAFC 100%) !important;
    background-attachment: fixed;
}
.stApp {
    color: #1E293B;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; background: transparent !important; }

/* ═══════════════════════════════════════════════════════════════
   SIDEBAR
   ═══════════════════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1E1B4B 0%, #312E81 40%, #3730A3 100%) !important;
    border-right: none !important;
}
[data-testid="stSidebar"] * {
    color: #E0E7FF !important;
}
[data-testid="stSidebar"] button {
    background: rgba(255,255,255,.08) !important;
    border: 1px solid rgba(255,255,255,.12) !important;
    color: #E0E7FF !important;
    border-radius: 10px !important;
}
[data-testid="stSidebar"] button:hover {
    background: rgba(255,255,255,.16) !important;
    border-color: rgba(255,255,255,.24) !important;
}
[data-testid="stSidebar"] button[kind="primary"] {
    background: linear-gradient(135deg, #818CF8, #6366F1) !important;
    border: none !important;
    color: #FFF !important;
}
[data-testid="stSidebar"] .stRadio label {
    background: rgba(255,255,255,.06);
    border-radius: 8px;
    padding: 6px 12px;
    margin: 2px 0;
}
[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,.1) !important;
}
[data-testid="stSidebar"] input {
    background: rgba(255,255,255,.1) !important;
    border: 1px solid rgba(255,255,255,.2) !important;
    color: #FFF !important;
    border-radius: 10px !important;
}
[data-testid="stSidebar"] input::placeholder {
    color: rgba(255,255,255,.4) !important;
}
[data-testid="stSidebar"] .st-caption {
    color: rgba(255,255,255,.5) !important;
}

/* ═══════════════════════════════════════════════════════════════
   CARDS
   ═══════════════════════════════════════════════════════════════ */
.geshi-card {
    background: linear-gradient(135deg, #FFFFFF 0%, #FAFBFF 100%);
    border-radius: 14px;
    padding: 20px 22px;
    margin: 8px 0;
    box-shadow: var(--geshi-shadow);
    border: 1px solid #EDEFF5;
    transition: all .18s;
}
.geshi-card:hover {
    box-shadow: var(--geshi-shadow-lg);
    transform: translateY(-1px);
}
.geshi-card-accent  {
    border-left: 4px solid var(--geshi-primary);
    background: linear-gradient(135deg, #EEF2FF 0%, #FFFFFF 60%);
}
.geshi-card-warning {
    border-left: 4px solid var(--geshi-warning);
    background: linear-gradient(135deg, #FFFBEB 0%, #FFFFFF 60%);
}
.geshi-card-success {
    border-left: 4px solid var(--geshi-success);
    background: linear-gradient(135deg, #ECFDF5 0%, #FFFFFF 60%);
}
.geshi-card-danger  {
    border-left: 4px solid var(--geshi-danger);
    background: linear-gradient(135deg, #FEF2F2 0%, #FFFFFF 60%);
}

/* ═══════════════════════════════════════════════════════════════
   METRIC CARDS (glass-morphism)
   ═══════════════════════════════════════════════════════════════ */
.geshi-metric-card {
    background: linear-gradient(135deg, #FFFFFF 0%, #FAFBFF 100%);
    border-radius: 14px;
    padding: 16px 14px;
    text-align: center;
    box-shadow: 0 1px 2px rgba(0,0,0,.03), 0 4px 12px rgba(79,70,229,.06);
    border: 1px solid #EEF0F8;
    transition: all .15s;
}
.geshi-metric-card:hover {
    box-shadow: 0 2px 4px rgba(0,0,0,.04), 0 8px 20px rgba(79,70,229,.08);
    transform: translateY(-2px);
}
.geshi-metric-value {
    font-size: 2em;
    font-weight: 800;
    background: linear-gradient(135deg, #4F46E5, #6366F1);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}
.geshi-metric-label {
    font-size: .8em;
    color: #94A3B8;
    font-weight: 600;
    letter-spacing: .5px;
    margin-top: 2px;
}

/* ═══════════════════════════════════════════════════════════════
   BADGES
   ═══════════════════════════════════════════════════════════════ */
.geshi-badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 14px;
    font-size: .76em;
    font-weight: 600;
    letter-spacing: .3px;
}
.geshi-badge-high       { background: #FEE2E2; color: #991B1B; }
.geshi-badge-medium     { background: #FEF3C7; color: #92400E; }
.geshi-badge-low        { background: #DBEAFE; color: #1E40AF; }
.geshi-badge-pending    { background: #FEF3C7; color: #92400E; }
.geshi-badge-in_progress{ background: #DBEAFE; color: #1E40AF; }
.geshi-badge-completed  { background: #D1FAE5; color: #065F46; }
.geshi-badge-cancelled  { background: #F1F5F9; color: #64748B; }
.geshi-badge-approved   { background: #D1FAE5; color: #065F46; }
.geshi-badge-rejected   { background: #FEE2E2; color: #991B1B; }
.geshi-badge-normal     { background: #D1FAE5; color: #065F46; }
.geshi-badge-late       { background: #FEF3C7; color: #92400E; }
.geshi-badge-early      { background: #DBEAFE; color: #1E40AF; }
.geshi-badge-absent     { background: #FEE2E2; color: #991B1B; }
.geshi-badge-admin      { background: linear-gradient(135deg, #C7D2FE, #A5B4FC); color: #3730A3; }

/* ═══════════════════════════════════════════════════════════════
   AI BOX
   ═══════════════════════════════════════════════════════════════ */
.geshi-ai-box {
    background: linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%);
    border-radius: 14px;
    padding: 16px 20px;
    margin: 10px 0;
    border: 1px solid #C7D2FE;
    box-shadow: 0 2px 8px rgba(79,70,229,.06);
    line-height: 1.6;
}
.geshi-ai-box strong { color: #3730A3; }

/* ═══════════════════════════════════════════════════════════════
   SECTION HEADERS
   ═══════════════════════════════════════════════════════════════ */
.geshi-section {
    font-size: .95em;
    font-weight: 700;
    color: #4F46E5;
    margin: 18px 0 10px 0;
    padding: 6px 0;
    border-bottom: 2px solid;
    border-image: linear-gradient(90deg, #6366F1, #C7D2FE) 1;
}

/* ═══════════════════════════════════════════════════════════════
   BUTTONS
   ═══════════════════════════════════════════════════════════════ */
.stButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: .9em !important;
    transition: all .15s !important;
    border: 1px solid #E2E8F0 !important;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(0,0,0,.06);
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #6366F1 0%, #4F46E5 100%) !important;
    border: none !important;
    color: #FFF !important;
    box-shadow: 0 2px 8px rgba(79,70,229,.25);
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 4px 16px rgba(79,70,229,.35);
    transform: translateY(-2px);
}

/* ═══════════════════════════════════════════════════════════════
   TABS
   ═══════════════════════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: transparent;
    padding: 0;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px 10px 0 0 !important;
    padding: 10px 20px !important;
    font-weight: 600 !important;
    font-size: .88em !important;
    margin-right: 2px;
    border: 1px solid transparent !important;
    color: #64748B !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: #FFFFFF !important;
    color: #4F46E5 !important;
    border-color: #E2E8F0 #E2E8F0 #FFF !important;
    box-shadow: 0 -2px 6px rgba(0,0,0,.03);
}

/* ═══════════════════════════════════════════════════════════════
   EXPANDERS
   ═══════════════════════════════════════════════════════════════ */
.streamlit-expanderHeader {
    font-weight: 600 !important;
    font-size: .92em !important;
    border-radius: 10px !important;
    background: linear-gradient(135deg, #F8FAFC, #FFFFFF) !important;
    border: 1px solid #F1F5F9 !important;
}
.streamlit-expanderHeader:hover {
    background: linear-gradient(135deg, #EEF2FF, #F8FAFC) !important;
}

/* ═══════════════════════════════════════════════════════════════
   INPUTS & SELECTBOXES
   ═══════════════════════════════════════════════════════════════ */
.stTextInput input, .stSelectbox [data-baseweb="select"] > div {
    border-radius: 10px !important;
    border-color: #E2E8F0 !important;
}
.stTextInput input:focus, .stSelectbox [data-baseweb="select"] > div:focus-within {
    border-color: #818CF8 !important;
    box-shadow: 0 0 0 3px rgba(79,70,229,.1) !important;
}

/* ═══════════════════════════════════════════════════════════════
   SPINNER
   ═══════════════════════════════════════════════════════════════ */
.stSpinner > div { border-top-color: #6366F1 !important; }

/* ═══════════════════════════════════════════════════════════════
   HR DIVIDER
   ═══════════════════════════════════════════════════════════════ */
hr {
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent, #E2E8F0, transparent) !important;
    margin: 18px 0 !important;
}

/* ═══════════════════════════════════════════════════════════════
   WELCOME HERO (login page)
   ═══════════════════════════════════════════════════════════════ */
.geshi-hero {
    text-align: center;
    padding: 30px 0 10px 0;
}
.geshi-hero h1 {
    font-size: 2em !important;
    background: linear-gradient(135deg, #4F46E5, #0EA5E9);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
}

/* ═══════════════════════════════════════════════════════════════
   CHAT BUBBLES
   ═══════════════════════════════════════════════════════════════ */
.geshi-chat-bubble-me {
    background: linear-gradient(135deg, #6366F1, #4F46E5);
    color: #FFF;
    display: inline-block;
    max-width: 80%;
    padding: 10px 16px;
    border-radius: 16px 16px 4px 16px;
    font-size: .92em;
}
.geshi-chat-bubble-them {
    background: #F1F5F9;
    color: #1E293B;
    display: inline-block;
    max-width: 80%;
    padding: 10px 16px;
    border-radius: 16px 16px 16px 4px;
    font-size: .92em;
}

/* ═══════════════════════════════════════════════════════════════
   STATUSBAR / NOTIFICATIONS
   ═══════════════════════════════════════════════════════════════ */
.geshi-dot-red    { display:inline-block;width:8px;height:8px;border-radius:50%;background:#EF4444;margin-right:4px; }
.geshi-dot-blue   { display:inline-block;width:8px;height:8px;border-radius:50%;background:#3B82F6;margin-right:4px; }
.geshi-dot-green  { display:inline-block;width:8px;height:8px;border-radius:50%;background:#10B981;margin-right:4px; }

/* ═══════════════════════════════════════════════════════════════
   CALENDAR
   ═══════════════════════════════════════════════════════════════ */
.geshi-cal-day {
    text-align: center;
    padding: 7px 4px;
    border-radius: 10px;
    font-size: .85em;
    min-height: 50px;
}
.geshi-cal-today {
    background: linear-gradient(135deg, #EEF2FF, #E0E7FF);
    font-weight: 700;
    border: 2px solid #818CF8;
    box-shadow: 0 0 0 3px rgba(79,70,229,.1);
}
.geshi-cal-other-month { color: #CBD5E1; }
.geshi-cal-dot {
    display: inline-block; width: 5px; height: 5px;
    border-radius: 50%; margin: 1px;
}

/* ═══════════════════════════════════════════════════════════════
   FEATURE CARDS (quick-entry links)
   ═══════════════════════════════════════════════════════════════ */
.geshi-link-card {
    display: block;
    padding: 10px 14px;
    border-radius: 10px;
    margin: 3px 0;
    background: linear-gradient(135deg, #F8FAFC, #FFFFFF);
    border: 1px solid #F1F5F9;
    color: #334155 !important;
    text-decoration: none !important;
    font-weight: 500;
    font-size: .9em;
    transition: all .12s;
}
.geshi-link-card:hover {
    background: linear-gradient(135deg, #EEF2FF, #F8FAFC);
    border-color: #C7D2FE;
    transform: translateX(3px);
}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


# ── Reusable components ──

def metric_card(label: str, value, delta: str = "", color: str = "#6366F1") -> None:
    """Render a styled metric card."""
    delta_html = f'<br><small style="color:#64748B">{delta}</small>' if delta else ""
    st.markdown(
        f'<div class="geshi-metric-card">'
        f'<div style="font-size:.78em;color:#94A3B8;font-weight:600;letter-spacing:.5px">{label}</div>'
        f'<div style="font-size:2em;font-weight:800;background:linear-gradient(135deg,{color},#6366F1);'
        f'-webkit-background-clip:text;-webkit-text-fill-color:transparent">{value}</div>'
        f'{delta_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def badge(label: str, kind: str = "medium") -> str:
    cls_map = {
        "high": "geshi-badge-high", "medium": "geshi-badge-medium", "low": "geshi-badge-low",
        "pending": "geshi-badge-pending", "in_progress": "geshi-badge-in_progress",
        "completed": "geshi-badge-completed", "cancelled": "geshi-badge-cancelled",
        "approved": "geshi-badge-approved", "rejected": "geshi-badge-rejected",
        "normal": "geshi-badge-normal", "late": "geshi-badge-late",
        "early": "geshi-badge-early", "absent": "geshi-badge-absent",
        "admin": "geshi-badge-admin",
    }
    cls = cls_map.get(kind, "geshi-badge-medium")
    return f'<span class="geshi-badge {cls}">{label}</span>'


def ai_insight(icon: str, title: str, message: str) -> None:
    st.markdown(
        f'<div class="geshi-ai-box">'
        f'<span style="font-size:1.3em;margin-right:6px">{icon}</span>'
        f'<strong>{title}</strong><br>'
        f'<span style="color:#475569;font-size:.9em">{message}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def section_header(title: str) -> None:
    st.markdown(f'<div class="geshi-section">{title}</div>', unsafe_allow_html=True)


def user_role_badge(user: dict) -> str:
    return badge("管理员", "admin") if user.get("role") == "admin" else badge("用户", "low")


def nav_links(user: dict) -> None:
    is_admin = user.get("role") == "admin"
    st.markdown('<div style="font-size:.8em;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">功能导航</div>', unsafe_allow_html=True)
    links = [
        ("📝  语音总结", "pages/1_📝_语音总结.py", True),
        ("📚  知识库", "pages/2_📚_知识库.py", True),
        ("✅  任务管理", "pages/4_✅_任务管理.py", True),
        ("📋  审批管理", "pages/5_📋_审批管理.py", True),
        ("📅  日程管理", "pages/6_📅_日程管理.py", True),
        ("🕐  考勤打卡", "pages/7_🕐_考勤打卡.py", True),
        ("📢  公告通知", "pages/8_📢_公告通知.py", True),
        ("💬  站内消息", "pages/9_💬_站内消息.py", True),
        ("👥  用户管理", "pages/3_👥_用户管理.py", is_admin),
    ]
    for label, page, visible in links:
        if visible:
            st.page_link(page, label=label)
    if not is_admin:
        st.caption("🔒 管理功能仅管理员可见")
