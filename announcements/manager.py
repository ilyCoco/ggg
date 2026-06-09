"""Announcements CRUD — admin publish, all users read."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from database import get_connection


def create_announcement(title: str, content: str, author_id: int, *, is_pinned: bool = False) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO announcements (title, content, author_id, is_pinned) VALUES (?, ?, ?, ?)",
        (title, content, author_id, 1 if is_pinned else 0),
    )
    conn.commit()
    conn.close()
    return cur.lastrowid


def update_announcement(ann_id: int, **fields: Any) -> bool:
    allowed = {"title", "content", "is_pinned", "is_published"}
    updates = []
    vals: list[Any] = []
    for k, v in fields.items():
        if k in allowed:
            updates.append(f"{k} = ?")
            vals.append(v)
    if not updates:
        return False
    conn = get_connection()
    vals.append(ann_id)
    conn.execute(f"UPDATE announcements SET {', '.join(updates)} WHERE id = ?", vals)
    conn.commit()
    conn.close()
    return True


def delete_announcement(ann_id: int) -> bool:
    conn = get_connection()
    conn.execute("DELETE FROM announcements WHERE id = ?", (ann_id,))
    conn.commit()
    conn.close()
    return True


def get_announcement(ann_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    row = conn.execute(
        """SELECT a.*, u.display_name AS author_name
           FROM announcements a LEFT JOIN users u ON a.author_id = u.id
           WHERE a.id = ?""",
        (ann_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_announcements(*, page: int = 1, page_size: int = 20,
                       pinned_first: bool = True, include_unpublished: bool = False) -> dict[str, Any]:
    conn = get_connection()
    where = ""
    if not include_unpublished:
        where = "WHERE a.is_published = 1"
    order = "ORDER BY a.is_pinned DESC, a.created_at DESC" if pinned_first else "ORDER BY a.created_at DESC"
    count = conn.execute(f"SELECT COUNT(*) FROM announcements a {where}").fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""SELECT a.*, u.display_name AS author_name
            FROM announcements a LEFT JOIN users u ON a.author_id = u.id
            {where} {order} LIMIT ? OFFSET ?""",
        (page_size, offset),
    ).fetchall()
    conn.close()
    return {
        "announcements": [dict(r) for r in rows],
        "total": count,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (count + page_size - 1) // page_size),
    }


def toggle_pin(ann_id: int) -> bool:
    conn = get_connection()
    conn.execute("UPDATE announcements SET is_pinned = NOT is_pinned WHERE id = ?", (ann_id,))
    conn.commit()
    conn.close()
    return True


def toggle_publish(ann_id: int) -> bool:
    conn = get_connection()
    conn.execute("UPDATE announcements SET is_published = NOT is_published WHERE id = ?", (ann_id,))
    conn.commit()
    conn.close()
    return True
