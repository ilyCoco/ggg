"""Task CRUD operations and kanban grouping."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from database import get_connection


def create_task(
    title: str,
    creator_id: int,
    *,
    description: str = "",
    assignee_id: int | None = None,
    status: str = "pending",
    priority: str = "medium",
    deadline: str = "",
    risk_tags: list[str] | None = None,
    source_type: str = "manual",
    source_summary_id: int | None = None,
) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO tasks (title, description, assignee_id, creator_id,
           status, priority, deadline, risk_tags, source_type, source_summary_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            title, description, assignee_id, creator_id,
            status, priority, deadline,
            json.dumps(risk_tags or [], ensure_ascii=False),
            source_type, source_summary_id,
        ),
    )
    task_id = cur.lastrowid
    # Notify assignee
    if assignee_id:
        conn.execute(
            "INSERT INTO notifications (user_id, type, title, message, link) VALUES (?, 'task_assigned', ?, ?, ?)",
            (assignee_id, "新任务分配", f"你被分配了新任务：{title}", ""),
        )
    conn.commit()
    conn.close()
    return task_id


def update_task(task_id: int, **fields: Any) -> bool:
    conn = get_connection()
    old = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not old:
        conn.close()
        return False

    allowed = {"title", "description", "assignee_id", "status", "priority", "deadline", "risk_tags"}
    updates = []
    vals: list[Any] = []
    for k, v in fields.items():
        if k in allowed:
            updates.append(f"{k} = ?")
            vals.append(json.dumps(v, ensure_ascii=False) if k == "risk_tags" and isinstance(v, list) else v)

    if not updates:
        conn.close()
        return False

    vals.append(task_id)
    conn.execute(f"UPDATE tasks SET {', '.join(updates)}, updated_at = ? WHERE id = ?",
                 vals[:-1] + [datetime.now().isoformat(timespec="seconds"), task_id])

    # Notify on assignee change
    new_assignee = fields.get("assignee_id")
    if new_assignee and new_assignee != old["assignee_id"]:
        conn.execute(
            "INSERT INTO notifications (user_id, type, title, message) VALUES (?, 'task_assigned', ?, ?)",
            (new_assignee, "任务分配变更", f"你被分配了任务：{old['title']}"),
        )
    # Notify on completion
    if fields.get("status") == "completed" and old["status"] != "completed" and old["creator_id"]:
        conn.execute(
            "INSERT INTO notifications (user_id, type, title, message) VALUES (?, 'task_completed', ?, ?)",
            (old["creator_id"], "任务已完成", f"任务「{old['title']}」已完成"),
        )

    conn.commit()
    conn.close()
    return True


def delete_task(task_id: int) -> bool:
    conn = get_connection()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return True


def get_task(task_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    row = conn.execute(
        """SELECT t.*, a.display_name AS assignee_name, c.display_name AS creator_name
           FROM tasks t
           LEFT JOIN users a ON t.assignee_id = a.id
           LEFT JOIN users c ON t.creator_id = c.id
           WHERE t.id = ?""",
        (task_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["risk_tags"] = json.loads(d.get("risk_tags", "[]"))
    except (json.JSONDecodeError, TypeError):
        d["risk_tags"] = []
    return d


def list_tasks(
    *,
    page: int = 1,
    page_size: int = 20,
    status: str = "",
    priority: str = "",
    assignee_id: int | None = None,
    creator_id: int | None = None,
    my_tasks: int | None = None,
    sort_by: str = "created_at",
) -> dict[str, Any]:
    conn = get_connection()
    where = []
    params: list[Any] = []

    if my_tasks is not None:
        where.append("(t.assignee_id = ? OR t.creator_id = ?)")
        params.extend([my_tasks, my_tasks])
    if status:
        where.append("t.status = ?")
        params.append(status)
    if priority:
        where.append("t.priority = ?")
        params.append(priority)
    if assignee_id is not None:
        where.append("t.assignee_id = ?")
        params.append(assignee_id)
    if creator_id is not None:
        where.append("t.creator_id = ?")
        params.append(creator_id)

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""
    sort_map = {"created_at": "t.created_at", "deadline": "t.deadline", "priority": "CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END"}
    sort_col = sort_map.get(sort_by, "t.created_at")

    count = conn.execute(f"SELECT COUNT(*) FROM tasks t {where_clause}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""SELECT t.*, a.display_name AS assignee_name, c.display_name AS creator_name
            FROM tasks t
            LEFT JOIN users a ON t.assignee_id = a.id
            LEFT JOIN users c ON t.creator_id = c.id
            {where_clause} ORDER BY {sort_col} DESC LIMIT ? OFFSET ?""",
        params + [page_size, offset],
    ).fetchall()
    conn.close()

    tasks = []
    for r in rows:
        d = dict(r)
        try:
            d["risk_tags"] = json.loads(d.get("risk_tags", "[]"))
        except (json.JSONDecodeError, TypeError):
            d["risk_tags"] = []
        tasks.append(d)

    return {
        "tasks": tasks,
        "total": count,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (count + page_size - 1) // page_size),
    }


def get_tasks_by_status(user_id: int | None = None) -> dict[str, list[dict[str, Any]]]:
    conn = get_connection()
    result: dict[str, list[dict[str, Any]]] = {"pending": [], "in_progress": [], "completed": []}
    for status_key in result:
        if user_id:
            rows = conn.execute(
                """SELECT t.*, a.display_name AS assignee_name
                   FROM tasks t LEFT JOIN users a ON t.assignee_id = a.id
                   WHERE t.status = ? AND (t.assignee_id = ? OR t.creator_id = ?)
                   ORDER BY CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, t.deadline""",
                (status_key, user_id, user_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT t.*, a.display_name AS assignee_name
                   FROM tasks t LEFT JOIN users a ON t.assignee_id = a.id
                   WHERE t.status = ?
                   ORDER BY CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, t.deadline""",
                (status_key,),
            ).fetchall()
        result[status_key] = [dict(r) for r in rows]
    conn.close()
    return result


def create_tasks_from_summary(summary_json: str, creator_id: int) -> list[int]:
    """Parse action items from meeting/classroom summary and create tasks."""
    data = json.loads(summary_json)
    content = data.get("content", {})
    scene_type = data.get("scene", {}).get("scene_type", "")

    if scene_type not in ("meeting", "mixed"):
        return []

    action_items: list[dict[str, Any]] = []
    if scene_type == "meeting":
        action_items = content.get("待办事项", [])
    elif scene_type == "mixed":
        meeting_part = content.get("会议部分", {})
        action_items = meeting_part.get("待办事项", [])

    task_ids: list[int] = []
    conn = get_connection()
    for item in action_items:
        if not isinstance(item, dict):
            continue
        task_name = item.get("任务", "").strip()
        if not task_name or task_name in ("待人工确认", "未识别到明确工作部署"):
            continue

        owner = item.get("责任人", "待确认")
        deadline = item.get("截止时间", "").strip()
        if deadline == "待确认":
            deadline = ""
        priority_map = {"高": "high", "中": "medium", "低": "low"}
        priority = priority_map.get(item.get("优先级", "中"), "medium")

        assignee_id = None
        if owner and owner != "待确认":
            row = conn.execute(
                "SELECT id FROM users WHERE display_name = ? OR username = ?",
                (owner, owner),
            ).fetchone()
            if row:
                assignee_id = row["id"]

        cur = conn.execute(
            """INSERT INTO tasks (title, description, assignee_id, creator_id,
               status, priority, deadline, source_type)
               VALUES (?, ?, ?, ?, 'pending', ?, ?, 'meeting')""",
            (task_name, item.get("备注", ""), assignee_id, creator_id, priority, deadline),
        )
        task_ids.append(cur.lastrowid)

        if assignee_id:
            conn.execute(
                "INSERT INTO notifications (user_id, type, title, message) VALUES (?, 'task_assigned', ?, ?)",
                (assignee_id, "会议待办任务", f"来自会议总结：{task_name}"),
            )

    conn.commit()
    conn.close()
    return task_ids
