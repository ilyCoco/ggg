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
    """)
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
