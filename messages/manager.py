"""Internal messaging — 1-to-1 chat."""

from __future__ import annotations

from typing import Any

from database import get_connection


def send_message(sender_id: int, receiver_id: int, content: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
        (sender_id, receiver_id, content),
    )
    msg_id = cur.lastrowid
    conn.execute(
        "INSERT INTO notifications (user_id, type, title, message, link) VALUES (?, 'message_new', ?, ?, ?)",
        (receiver_id, "新消息", content[:50], ""),
    )
    conn.commit()
    conn.close()
    return msg_id


def get_message(msg_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    row = conn.execute(
        """SELECT m.*, s.display_name AS sender_name, r.display_name AS receiver_name
           FROM messages m
           LEFT JOIN users s ON m.sender_id = s.id
           LEFT JOIN users r ON m.receiver_id = r.id
           WHERE m.id = ?""",
        (msg_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_conversation(user_a: int, user_b: int, *, page: int = 1, page_size: int = 30) -> dict[str, Any]:
    conn = get_connection()
    count = conn.execute(
        """SELECT COUNT(*) FROM messages
           WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)""",
        (user_a, user_b, user_b, user_a),
    ).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        """SELECT m.*, s.display_name AS sender_name
           FROM messages m LEFT JOIN users s ON m.sender_id = s.id
           WHERE (m.sender_id = ? AND m.receiver_id = ?) OR (m.sender_id = ? AND m.receiver_id = ?)
           ORDER BY m.created_at ASC LIMIT ? OFFSET ?""",
        (user_a, user_b, user_b, user_a, page_size, offset),
    ).fetchall()
    # Mark as read
    conn.execute(
        "UPDATE messages SET is_read = 1 WHERE sender_id = ? AND receiver_id = ? AND is_read = 0",
        (user_b, user_a),
    )
    conn.commit()
    conn.close()
    return {
        "messages": [dict(r) for r in rows],
        "total": count,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (count + page_size - 1) // page_size),
    }


def get_inbox(user_id: int, *, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    conn = get_connection()
    # Group by sender — show latest message from each
    count = conn.execute(
        """SELECT COUNT(DISTINCT sender_id) FROM messages WHERE receiver_id = ?""",
        (user_id,),
    ).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        """SELECT m.*, s.display_name AS sender_name,
           (SELECT COUNT(*) FROM messages WHERE sender_id = m.sender_id AND receiver_id = ? AND is_read = 0) AS unread
           FROM messages m
           LEFT JOIN users s ON m.sender_id = s.id
           WHERE m.id IN (
               SELECT MAX(id) FROM messages WHERE receiver_id = ? GROUP BY sender_id
           )
           ORDER BY m.created_at DESC LIMIT ? OFFSET ?""",
        (user_id, user_id, page_size, offset),
    ).fetchall()
    conn.close()
    return {
        "conversations": [dict(r) for r in rows],
        "total": count,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (count + page_size - 1) // page_size),
    }


def get_sent(user_id: int, *, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM messages WHERE sender_id = ?", (user_id,)).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        """SELECT m.*, r.display_name AS receiver_name
           FROM messages m LEFT JOIN users r ON m.receiver_id = r.id
           WHERE m.sender_id = ? ORDER BY m.created_at DESC LIMIT ? OFFSET ?""",
        (user_id, page_size, offset),
    ).fetchall()
    conn.close()
    return {
        "messages": [dict(r) for r in rows],
        "total": count,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (count + page_size - 1) // page_size),
    }


def get_unread_count(user_id: int) -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE receiver_id = ? AND is_read = 0",
        (user_id,),
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def get_recent_contacts(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT DISTINCT u.id, u.display_name,
           (SELECT content FROM messages
            WHERE (sender_id = u.id AND receiver_id = ?) OR (sender_id = ? AND receiver_id = u.id)
            ORDER BY created_at DESC LIMIT 1) AS last_message,
           (SELECT COUNT(*) FROM messages WHERE sender_id = u.id AND receiver_id = ? AND is_read = 0) AS unread
           FROM messages m
           JOIN users u ON (u.id = m.sender_id OR u.id = m.receiver_id)
           WHERE (m.sender_id = ? OR m.receiver_id = ?) AND u.id != ?
           ORDER BY unread DESC, last_message DESC LIMIT ?""",
        (user_id, user_id, user_id, user_id, user_id, user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_message(msg_id: int) -> bool:
    conn = get_connection()
    conn.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()
    return True
