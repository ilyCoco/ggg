"""Approval workflow engine — chain-based multi-step approvals."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from database import get_connection


def create_approval(
    title: str,
    applicant_id: int,
    approval_type: str = "other",
    *,
    description: str = "",
    approval_chain: list[int] | None = None,
) -> int:
    chain = approval_chain or []
    first_approver = chain[0] if chain else None
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO approvals (type, title, description, applicant_id, current_approver_id,
           status, approval_chain, current_step)
           VALUES (?, ?, ?, ?, ?, 'pending', ?, 0)""",
        (approval_type, title, description, applicant_id, first_approver, json.dumps(chain)),
    )
    approval_id = cur.lastrowid
    if first_approver:
        conn.execute(
            "INSERT INTO notifications (user_id, type, title, message) VALUES (?, 'approval_request', ?, ?)",
            (first_approver, "新的审批请求", f"申请人提交了{approval_type}审批：{title}"),
        )
    conn.commit()
    conn.close()
    return approval_id


def approve(approval_id: int, approver_id: int) -> tuple[bool, str]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
    if not row:
        conn.close()
        return False, "审批不存在"
    if row["status"] != "pending":
        conn.close()
        return False, "该审批已完成或已取消"
    if row["current_approver_id"] != approver_id:
        conn.close()
        return False, "你不是当前审批人"

    chain = json.loads(row["approval_chain"])
    step = row["current_step"] + 1
    if step >= len(chain):
        # Last approver — mark as approved
        conn.execute(
            "UPDATE approvals SET status = 'approved', current_approver_id = NULL, current_step = ?, updated_at = ? WHERE id = ?",
            (step, datetime.now().isoformat(timespec="seconds"), approval_id),
        )
        conn.execute(
            "INSERT INTO notifications (user_id, type, title, message) VALUES (?, 'approval_result', ?, ?)",
            (row["applicant_id"], "审批已通过", f"你的{row['type']}审批「{row['title']}」已通过"),
        )
        conn.commit()
        conn.close()
        return True, "审批已通过"
    else:
        next_approver = chain[step]
        conn.execute(
            "UPDATE approvals SET current_approver_id = ?, current_step = ?, updated_at = ? WHERE id = ?",
            (next_approver, step, datetime.now().isoformat(timespec="seconds"), approval_id),
        )
        conn.execute(
            "INSERT INTO notifications (user_id, type, title, message) VALUES (?, 'approval_request', ?, ?)",
            (next_approver, "新的审批请求", f"申请人提交了{row['type']}审批：{row['title']}"),
        )
        conn.execute(
            "INSERT INTO notifications (user_id, type, title, message) VALUES (?, 'approval_result', ?, ?)",
            (row["applicant_id"], "审批进度更新", f"你的{row['type']}审批已进入下一级审批"),
        )
        conn.commit()
        conn.close()
        return True, "已批准，流转至下一审批人"


def reject(approval_id: int, approver_id: int) -> tuple[bool, str]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
    if not row:
        conn.close()
        return False, "审批不存在"
    if row["status"] != "pending":
        conn.close()
        return False, "该审批已完成或已取消"
    if row["current_approver_id"] != approver_id:
        conn.close()
        return False, "你不是当前审批人"

    conn.execute(
        "UPDATE approvals SET status = 'rejected', current_approver_id = NULL, updated_at = ? WHERE id = ?",
        (datetime.now().isoformat(timespec="seconds"), approval_id),
    )
    conn.execute(
        "INSERT INTO notifications (user_id, type, title, message) VALUES (?, 'approval_result', ?, ?)",
        (row["applicant_id"], "审批被驳回", f"你的{row['type']}审批「{row['title']}」被驳回"),
    )
    conn.commit()
    conn.close()
    return True, "审批已驳回"


def cancel(approval_id: int, user_id: int) -> bool:
    conn = get_connection()
    row = conn.execute("SELECT * FROM approvals WHERE id = ? AND applicant_id = ?", (approval_id, user_id)).fetchone()
    if not row:
        conn.close()
        return False
    conn.execute("UPDATE approvals SET status = 'cancelled', updated_at = ? WHERE id = ?",
                 (datetime.now().isoformat(timespec="seconds"), approval_id))
    conn.commit()
    conn.close()
    return True


def get_approval(approval_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    row = conn.execute(
        """SELECT a.*, u.display_name AS applicant_name, c.display_name AS approver_name
           FROM approvals a
           LEFT JOIN users u ON a.applicant_id = u.id
           LEFT JOIN users c ON a.current_approver_id = c.id
           WHERE a.id = ?""",
        (approval_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        chain_ids = json.loads(d.get("approval_chain", "[]"))
    except (json.JSONDecodeError, TypeError):
        chain_ids = []
    d["chain_resolved"] = parse_approval_chain(d["approval_chain"], d.get("current_step", 0), d.get("status", ""))
    return d


def list_approvals(
    *,
    page: int = 1,
    page_size: int = 20,
    applicant_id: int | None = None,
    approver_id: int | None = None,
    status: str = "",
    approval_type: str = "",
) -> dict[str, Any]:
    conn = get_connection()
    where = []
    params: list[Any] = []

    if applicant_id is not None:
        where.append("a.applicant_id = ?")
        params.append(applicant_id)
    if approver_id is not None:
        where.append("a.current_approver_id = ?")
        params.append(approver_id)
    if status:
        where.append("a.status = ?")
        params.append(status)
    if approval_type:
        where.append("a.type = ?")
        params.append(approval_type)

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""
    count = conn.execute(f"SELECT COUNT(*) FROM approvals a {where_clause}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""SELECT a.*, u.display_name AS applicant_name, c.display_name AS approver_name
            FROM approvals a
            LEFT JOIN users u ON a.applicant_id = u.id
            LEFT JOIN users c ON a.current_approver_id = c.id
            {where_clause} ORDER BY a.created_at DESC LIMIT ? OFFSET ?""",
        params + [page_size, offset],
    ).fetchall()
    conn.close()
    return {
        "approvals": [dict(r) for r in rows],
        "total": count,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (count + page_size - 1) // page_size),
    }


def parse_approval_chain(chain_str: str, current_step: int = 0, status: str = "pending") -> list[dict[str, Any]]:
    try:
        ids = json.loads(chain_str) if isinstance(chain_str, str) else chain_str
    except (json.JSONDecodeError, TypeError):
        return []
    conn = get_connection()
    result = []
    for i, uid in enumerate(ids):
        row = conn.execute("SELECT id, display_name FROM users WHERE id = ?", (uid,)).fetchone()
        name = row["display_name"] if row else f"用户{uid}"
        if status == "approved":
            step_status = "approved"
        elif status == "rejected":
            step_status = "approved" if i < current_step else "rejected" if i == current_step else "waiting"
        else:
            step_status = "approved" if i < current_step else "pending" if i == current_step else "waiting"
        result.append({"id": uid, "name": name, "status": step_status})
    conn.close()
    return result
