"""Attendance: check-in, check-out, monthly records and stats."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from database import get_connection


CHECK_IN_DEADLINE = "09:00"
CHECK_OUT_DEADLINE = "17:00"


def check_in(user_id: int, ip_address: str = "") -> tuple[bool, str]:
    today = date.today().isoformat()
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    status = "normal" if current_time <= CHECK_IN_DEADLINE + ":00" else "late"

    conn = get_connection()
    existing = conn.execute(
        "SELECT id, check_in FROM attendance WHERE user_id = ? AND date = ?",
        (user_id, today),
    ).fetchone()
    if existing and existing["check_in"]:
        conn.close()
        return False, "今日已签到"

    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    if existing:
        conn.execute(
            "UPDATE attendance SET check_in = ?, status = ?, ip_address = ? WHERE id = ?",
            (time_str, status, ip_address, existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO attendance (user_id, date, check_in, status, ip_address) VALUES (?, ?, ?, ?, ?)",
            (user_id, today, time_str, status, ip_address),
        )
    conn.commit()
    conn.close()
    msg = "签到成功" + ("（已迟到）" if status == "late" else "")
    return True, msg


def check_out(user_id: int, ip_address: str = "") -> tuple[bool, str]:
    today = date.today().isoformat()
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")

    conn = get_connection()
    row = conn.execute(
        "SELECT id, check_in, check_out, status FROM attendance WHERE user_id = ? AND date = ?",
        (user_id, today),
    ).fetchone()
    if not row or not row["check_in"]:
        conn.close()
        return False, "今日尚未签到，无法签退"
    if row["check_out"]:
        conn.close()
        return False, "今日已签退"

    if current_time < CHECK_OUT_DEADLINE + ":00":
        status = "early"
    else:
        status = row["status"]  # keep original or normal

    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE attendance SET check_out = ?, status = ?, ip_address = ? WHERE id = ?",
        (time_str, status, ip_address, row["id"]),
    )
    conn.commit()
    conn.close()
    msg = "签退成功" + ("（早退）" if status == "early" else "")
    return True, msg


def get_today_record(user_id: int) -> dict[str, Any] | None:
    today = date.today().isoformat()
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM attendance WHERE user_id = ? AND date = ?",
        (user_id, today),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_monthly_records(user_id: int, year: int, month: int) -> list[dict[str, Any]]:
    conn = get_connection()
    start = f"{year}-{month:02d}-01"
    if month == 12:
        end = f"{year + 1}-01-01"
    else:
        end = f"{year}-{month + 1:02d}-01"
    rows = conn.execute(
        "SELECT * FROM attendance WHERE user_id = ? AND date >= ? AND date < ? ORDER BY date",
        (user_id, start, end),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_attendance_stats(user_id: int, year: int, month: int) -> dict[str, int]:
    records = get_monthly_records(user_id, year, month)
    stats = {"normal": 0, "late": 0, "early": 0, "absent": 0}
    for r in records:
        s = r.get("status", "normal")
        if s in stats:
            stats[s] += 1
        else:
            stats["normal"] += 1
    return stats


def get_all_today() -> list[dict[str, Any]]:
    today = date.today().isoformat()
    conn = get_connection()
    rows = conn.execute(
        """SELECT a.*, u.display_name, u.department
           FROM attendance a JOIN users u ON a.user_id = u.id
           WHERE a.date = ? ORDER BY u.department, u.display_name""",
        (today,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_attendance(
    *,
    page: int = 1,
    page_size: int = 20,
    user_id: int | None = None,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    conn = get_connection()
    where = []
    params: list[Any] = []
    if user_id is not None:
        where.append("a.user_id = ?")
        params.append(user_id)
    if year and month:
        start = f"{year}-{month:02d}-01"
        if month == 12:
            end = f"{year + 1}-01-01"
        else:
            end = f"{year}-{month + 1:02d}-01"
        where.append("a.date >= ? AND a.date < ?")
        params.extend([start, end])

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""
    count = conn.execute(f"SELECT COUNT(*) FROM attendance a {where_clause}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""SELECT a.*, u.display_name, u.department
            FROM attendance a JOIN users u ON a.user_id = u.id
            {where_clause} ORDER BY a.date DESC LIMIT ? OFFSET ?""",
        params + [page_size, offset],
    ).fetchall()
    conn.close()
    return {
        "records": [dict(r) for r in rows],
        "total": count,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (count + page_size - 1) // page_size),
    }
