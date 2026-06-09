"""Calendar event CRUD — month/week views and upcoming events."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from database import get_connection


def create_event(
    title: str,
    creator_id: int,
    start_time: str,
    *,
    description: str = "",
    event_type: str = "personal",
    end_time: str = "",
    all_day: bool = False,
    location: str = "",
    attendees: list[int] | None = None,
) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO calendar_events (title, description, creator_id, event_type,
           start_time, end_time, all_day, location, attendees)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, description, creator_id, event_type, start_time, end_time or start_time,
         1 if all_day else 0, location, json.dumps(attendees or [])),
    )
    ev_id = cur.lastrowid
    # Notify attendees
    for uid in (attendees or []):
        conn.execute(
            "INSERT INTO notifications (user_id, type, title, message) VALUES (?, 'meeting_reminder', ?, ?)",
            (uid, "新的日程邀请", f"你被邀请参加：{title} ({start_time[:16]})"),
        )
    conn.commit()
    conn.close()
    return ev_id


def update_event(event_id: int, **fields: Any) -> bool:
    allowed = {"title", "description", "event_type", "start_time", "end_time", "all_day", "location", "attendees"}
    updates = []
    vals: list[Any] = []
    for k, v in fields.items():
        if k in allowed:
            updates.append(f"{k} = ?")
            vals.append(json.dumps(v) if k == "attendees" and isinstance(v, list) else v)
    if not updates:
        return False
    conn = get_connection()
    vals.append(event_id)
    conn.execute(f"UPDATE calendar_events SET {', '.join(updates)} WHERE id = ?", vals)
    conn.commit()
    conn.close()
    return True


def delete_event(event_id: int) -> bool:
    conn = get_connection()
    conn.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    return True


def get_event(event_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    row = conn.execute(
        """SELECT e.*, u.display_name AS creator_name
           FROM calendar_events e LEFT JOIN users u ON e.creator_id = u.id
           WHERE e.id = ?""",
        (event_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["attendees_list"] = resolve_attendees(d.get("attendees", "[]"))
    except (json.JSONDecodeError, TypeError):
        d["attendees_list"] = []
    return d


def get_events_by_date_range(
    start_date: str, end_date: str,
    *,
    creator_id: int | None = None,
    event_type: str = "",
) -> list[dict[str, Any]]:
    conn = get_connection()
    where = ["e.start_time >= ? AND e.start_time <= ?"]
    params: list[Any] = [start_date, end_date]
    if creator_id is not None:
        where.append("(e.creator_id = ? OR e.attendees LIKE ?)")
        params.extend([creator_id, f"%{creator_id}%"])
    if event_type:
        where.append("e.event_type = ?")
        params.append(event_type)
    rows = conn.execute(
        f"""SELECT e.*, u.display_name AS creator_name
            FROM calendar_events e LEFT JOIN users u ON e.creator_id = u.id
            WHERE {' AND '.join(where)} ORDER BY e.start_time""",
        params,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_upcoming_events(user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    conn = get_connection()
    now = datetime.now().isoformat(timespec="seconds")
    rows = conn.execute(
        """SELECT e.*, u.display_name AS creator_name
           FROM calendar_events e LEFT JOIN users u ON e.creator_id = u.id
           WHERE e.start_time >= ? AND (e.creator_id = ? OR e.attendees LIKE ?)
           ORDER BY e.start_time LIMIT ?""",
        (now, user_id, f"%{user_id}%", limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_events_for_month(year: int, month: int, user_id: int | None = None) -> dict[int, list[dict[str, Any]]]:
    """Return events grouped by day of month."""
    start = f"{year}-{month:02d}-01"
    if month == 12:
        end = f"{year + 1}-01-01"
    else:
        end = f"{year}-{month + 1:02d}-01"
    events = get_events_by_date_range(start, end, creator_id=user_id)
    grouped: dict[int, list[dict[str, Any]]] = {}
    for ev in events:
        day = int(ev["start_time"][8:10])
        grouped.setdefault(day, []).append(ev)
    return grouped


def list_events(
    *,
    page: int = 1,
    page_size: int = 20,
    creator_id: int | None = None,
    event_type: str = "",
) -> dict[str, Any]:
    conn = get_connection()
    where = []
    params: list[Any] = []
    if creator_id is not None:
        where.append("e.creator_id = ?")
        params.append(creator_id)
    if event_type:
        where.append("e.event_type = ?")
        params.append(event_type)
    where_clause = ("WHERE " + " AND ".join(where)) if where else ""
    count = conn.execute(f"SELECT COUNT(*) FROM calendar_events e {where_clause}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""SELECT e.*, u.display_name AS creator_name
            FROM calendar_events e LEFT JOIN users u ON e.creator_id = u.id
            {where_clause} ORDER BY e.start_time DESC LIMIT ? OFFSET ?""",
        params + [page_size, offset],
    ).fetchall()
    conn.close()
    return {
        "events": [dict(r) for r in rows],
        "total": count,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (count + page_size - 1) // page_size),
    }


def resolve_attendees(attendees_json: str) -> list[dict[str, Any]]:
    try:
        ids = json.loads(attendees_json) if isinstance(attendees_json, str) else attendees_json
    except (json.JSONDecodeError, TypeError):
        return []
    conn = get_connection()
    result = []
    for uid in ids:
        row = conn.execute("SELECT id, display_name FROM users WHERE id = ?", (uid,)).fetchone()
        if row:
            result.append({"id": row["id"], "name": row["display_name"]})
        else:
            result.append({"id": uid, "name": f"用户{uid}"})
    conn.close()
    return result
