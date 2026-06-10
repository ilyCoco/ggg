"""Memory system — short-term conversation + long-term user preferences."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from database import get_connection


def init_memory_tables() -> None:
    """Create memory tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agent_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            memory_type TEXT NOT NULL CHECK(memory_type IN ('preference','fact','decision')),
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS agent_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tool_calls TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS agent_activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            agent_name TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT DEFAULT '',
            duration_ms INTEGER DEFAULT 0,
            token_count INTEGER DEFAULT 0,
            success INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    # Migration: add user_id column if old table doesn't have it
    try:
        conn.execute("ALTER TABLE agent_activity_log ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
    except Exception:
        pass  # Column already exists
    conn.close()


class MemoryManager:
    """Manages short-term (session) and long-term (persisted) memory."""

    def __init__(self, user_id: int, session_id: str = "") -> None:
        self.user_id = user_id
        self.session_id = session_id or datetime.now().strftime("%Y%m%d%H%M%S")
        self.conversation: list[dict[str, str]] = []

    # ── Short-term: conversation within session ──

    def add_turn(self, role: str, content: str) -> None:
        self.conversation.append({"role": role, "content": content})

    def get_recent_turns(self, n: int = 10) -> list[dict[str, str]]:
        return self.conversation[-n:]

    def clear_session(self) -> None:
        self.conversation.clear()

    # ── Long-term: persisted preferences and facts ──

    def store_memory(self, content: str, memory_type: str = "fact", category: str = "general") -> None:
        conn = get_connection()
        conn.execute(
            "INSERT INTO agent_memory (user_id, memory_type, content, category) VALUES (?, ?, ?, ?)",
            (self.user_id, memory_type, content, category),
        )
        conn.commit()
        conn.close()

    def get_memories(self, memory_type: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        conn = get_connection()
        if memory_type:
            rows = conn.execute(
                "SELECT content, memory_type, category, created_at FROM agent_memory "
                "WHERE user_id = ? AND memory_type = ? ORDER BY created_at DESC LIMIT ?",
                (self.user_id, memory_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT content, memory_type, category, created_at FROM agent_memory "
                "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (self.user_id, limit),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_context_string(self) -> str:
        """Build a memory context string to inject into the system prompt."""
        memories = self.get_memories(limit=5)
        if not memories:
            return ""
        parts = ["以下是关于该用户的历史记忆："]
        for m in memories:
            parts.append(f"- [{m['memory_type']}] {m['content']}")
        return "\n".join(parts)

    def save_conversation(self) -> None:
        """Persist current conversation to database."""
        if not self.conversation:
            return
        conn = get_connection()
        for turn in self.conversation:
            conn.execute(
                "INSERT INTO agent_conversations (user_id, session_id, role, content) VALUES (?, ?, ?, ?)",
                (self.user_id, self.session_id, turn["role"], turn["content"]),
            )
        conn.commit()
        conn.close()


# ═══════════════════════════════════════════════════════════════
#  Agent Activity Log — for War Room / observability
# ═══════════════════════════════════════════════════════════════

def log_agent_activity(
    agent_name: str,
    action: str,
    detail: str = "",
    duration_ms: int = 0,
    token_count: int = 0,
    success: bool = True,
    user_id: int = 1,
) -> None:
    """Write an entry to the agent activity log."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO agent_activity_log (user_id, agent_name, action, detail, duration_ms, token_count, success) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, agent_name, action, detail, duration_ms, token_count, 1 if success else 0),
    )
    conn.commit()
    conn.close()


def get_agent_activity_log(user_id: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve recent agent activity entries, optionally filtered by user."""
    conn = get_connection()
    if user_id is not None:
        rows = conn.execute(
            "SELECT agent_name, action, detail, duration_ms, token_count, success, created_at "
            "FROM agent_activity_log WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT agent_name, action, detail, duration_ms, token_count, success, created_at "
            "FROM agent_activity_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_agent_stats(user_id: int | None = None) -> dict[str, Any]:
    """Get aggregate statistics for the War Room dashboard."""
    conn = get_connection()
    params_all: list = []
    params_today: list = []
    user_clause = ""
    user_clause_today = "WHERE"

    if user_id is not None:
        user_clause = "WHERE user_id = ?"
        user_clause_today = "WHERE user_id = ? AND"
        params_all.append(user_id)
        params_today.append(user_id)

    total = conn.execute(
        f"SELECT COUNT(*) as c FROM agent_activity_log {user_clause}", params_all
    ).fetchone()["c"]
    today = conn.execute(
        f"SELECT COUNT(*) as c FROM agent_activity_log {user_clause_today} "
        f"date(created_at) = date('now', 'localtime')", params_today
    ).fetchone()["c"]
    tokens_today = conn.execute(
        f"SELECT COALESCE(SUM(token_count), 0) as c FROM agent_activity_log "
        f"{user_clause_today} date(created_at) = date('now', 'localtime')", params_today
    ).fetchone()["c"]
    avg_duration = conn.execute(
        f"SELECT COALESCE(AVG(duration_ms), 0) as c FROM agent_activity_log "
        f"{user_clause_today} date(created_at) = date('now', 'localtime')", params_today
    ).fetchone()["c"]

    agent_rows = conn.execute(
        f"SELECT agent_name, COUNT(*) as cnt, COALESCE(SUM(token_count), 0) as tokens, "
        f"COALESCE(AVG(duration_ms), 0) as avg_ms "
        f"FROM agent_activity_log {user_clause} GROUP BY agent_name ORDER BY cnt DESC LIMIT 10",
        params_all,
    ).fetchall()
    agents = [dict(r) for r in agent_rows]
    conn.close()

    return {
        "total_actions": total,
        "today_actions": today,
        "tokens_today": tokens_today,
        "avg_duration_ms": round(avg_duration, 1),
        "agents": agents,
    }
