"""Notification CRUD — used by all other modules."""

from __future__ import annotations

from typing import Any

from database import get_connection


def create_notification(
    user_id: int, type: str, title: str, *, message: str = "", link: str = ""
) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO notifications (user_id, type, title, message, link) VALUES (?, ?, ?, ?, ?)",
        (user_id, type, title, message, link),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def mark_read(notification_id: int) -> bool:
    conn = get_connection()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
    conn.commit()
    conn.close()
    return True


def mark_all_read(user_id: int) -> bool:
    conn = get_connection()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True


def mark_read_by_type(user_id: int, type: str) -> bool:
    conn = get_connection()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND type = ? AND is_read = 0",
        (user_id, type),
    )
    conn.commit()
    conn.close()
    return True


def get_unread_count(user_id: int) -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,),
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def list_notifications(
    user_id: int, *, limit: int = 50, unread_only: bool = False
) -> list[dict[str, Any]]:
    conn = get_connection()
    where = "WHERE user_id = ?"
    params: list[Any] = [user_id]
    if unread_only:
        where += " AND is_read = 0"
    rows = conn.execute(
        f"SELECT * FROM notifications {where} ORDER BY created_at DESC LIMIT ?",
        params + [limit],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_notification(notification_id: int) -> bool:
    conn = get_connection()
    conn.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
    conn.commit()
    conn.close()
    return True


def delete_old_notifications(days: int = 30) -> int:
    conn = get_connection()
    cur = conn.execute(
        "DELETE FROM notifications WHERE created_at < datetime('now', ?)",
        (f"-{days} days",),
    )
    conn.commit()
    conn.close()
    return cur.rowcount
