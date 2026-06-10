"""Notification, message, attendance, approval, and user tools."""

from __future__ import annotations

import json
from typing import Any

from agent_core.tool_registry import ToolDef


# ── Notification Tools ──

def _list_notifications(user_id: int = 0, limit: int = 10, **_: Any) -> str:
    from notifications import list_notifications
    notifs = list_notifications(user_id, limit=limit, unread_only=True)
    brief = [{"id": n["id"], "title": n["title"], "type": n["type"], "time": n["created_at"][:16]} for n in notifs]
    return json.dumps({"notifications": brief, "count": len(brief)}, ensure_ascii=False)


def _send_notification(target_user_id: int, title: str, message: str = "",
                       notification_type: str = "system", **_: Any) -> str:
    from notifications import create_notification
    create_notification(target_user_id, notification_type, title, message=message)
    return json.dumps({"success": True, "message": f"已向用户 {target_user_id} 发送通知"}, ensure_ascii=False)


# ── Message Tools ──

def _send_message(receiver_id: int, content: str, user_id: int = 0, subject: str = "", **_: Any) -> str:
    from messages import send_message
    msg_id = send_message(user_id, receiver_id, content)
    return json.dumps({"success": True, "message_id": msg_id}, ensure_ascii=False)


def _get_unread_count(user_id: int = 0, **_: Any) -> str:
    from messages import get_unread_count
    count = get_unread_count(user_id)
    return json.dumps({"unread_count": count}, ensure_ascii=False)


# ── Attendance Tools ──

def _get_attendance_stats(user_id: int = 0, **_: Any) -> str:
    from datetime import datetime
    from attendance import get_attendance_stats
    now = datetime.now()
    stats = get_attendance_stats(user_id, now.year, now.month)
    return json.dumps({"month": f"{now.year}-{now.month:02d}", **stats}, ensure_ascii=False, default=str)


def _check_in(user_id: int = 0, **_: Any) -> str:
    from attendance import check_in
    ok, msg = check_in(user_id)
    return json.dumps({"success": ok, "message": msg}, ensure_ascii=False)


# ── Approval Tools ──

def _create_approval(title: str, approval_type: str = "general",
                     description: str = "", user_id: int = 0,
                     approver_ids: list[int] | None = None, **_: Any) -> str:
    from approvals import create_approval
    if not approver_ids:
        return json.dumps({"error": "需要指定审批人"}, ensure_ascii=False)
    appr_id = create_approval(title, user_id, approval_type, description=description, approval_chain=approver_ids)
    return json.dumps({"success": True, "approval_id": appr_id, "message": f"审批'{title}'已提交"}, ensure_ascii=False)


def _list_approvals(user_id: int = 0, role: str = "approver", **_: Any) -> str:
    from approvals import list_approvals
    if role == "approver":
        result = list_approvals(approver_id=user_id, page_size=10)
    else:
        result = list_approvals(applicant_id=user_id, page_size=10)
    approvals = result.get("approvals", [])
    brief = [
        {"id": a["id"], "title": a["title"], "type": a.get("approval_type", ""),
         "status": a["status"], "applicant": a.get("applicant_name", "")}
        for a in approvals[:10]
    ]
    return json.dumps({"approvals": brief, "count": len(brief)}, ensure_ascii=False)


def _delete_approval(approval_id: int, user_id: int = 0, **_: Any) -> str:
    from approvals import delete_approval
    ok = delete_approval(approval_id, user_id)
    return json.dumps({"success": ok, "message": f"审批 {approval_id} 已删除" if ok else "删除失败"}, ensure_ascii=False)


# ── User Tools ──

def _list_users(**_: Any) -> str:
    from database import get_connection
    conn = get_connection()
    rows = conn.execute("SELECT id, username, display_name, department, role FROM users ORDER BY id").fetchall()
    conn.close()
    users = [{"id": r["id"], "name": r["display_name"] or r["username"], "department": r["department"] or "", "role": r["role"]} for r in rows]
    return json.dumps({"users": users}, ensure_ascii=False)


def _get_current_time(**_: Any) -> str:
    from datetime import datetime
    now = datetime.now()
    return json.dumps({
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()],
    }, ensure_ascii=False)


# ── Registration ──

def register_notification_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="list_notifications",
            description="获取当前用户的未读通知列表。",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "返回数量，默认10"},
                },
            },
            handler=_list_notifications,
            domain="notification",
            requires_user_id=True,
        ),
        ToolDef(
            name="send_notification",
            description="向指定用户发送系统通知。",
            parameters={
                "type": "object",
                "properties": {
                    "target_user_id": {"type": "integer", "description": "目标用户ID"},
                    "title": {"type": "string", "description": "通知标题"},
                    "message": {"type": "string", "description": "通知内容"},
                },
                "required": ["target_user_id", "title"],
            },
            handler=_send_notification,
            domain="notification",
        ),
    ]


def register_message_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="send_message",
            description="向指定用户发送站内消息。",
            parameters={
                "type": "object",
                "properties": {
                    "receiver_id": {"type": "integer", "description": "接收人用户ID"},
                    "content": {"type": "string", "description": "消息内容"},
                    "subject": {"type": "string", "description": "消息主题（可选）"},
                },
                "required": ["receiver_id", "content"],
            },
            handler=_send_message,
            domain="message",
            requires_user_id=True,
        ),
        ToolDef(
            name="get_unread_message_count",
            description="获取当前用户的未读消息数。",
            parameters={"type": "object", "properties": {}},
            handler=_get_unread_count,
            domain="message",
            requires_user_id=True,
        ),
    ]


def register_attendance_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="get_attendance_stats",
            description="获取当前用户本月的考勤统计（正常、迟到、早退、缺勤天数）。",
            parameters={"type": "object", "properties": {}},
            handler=_get_attendance_stats,
            domain="attendance",
            requires_user_id=True,
        ),
        ToolDef(
            name="check_in",
            description="为当前用户打卡签到。",
            parameters={"type": "object", "properties": {}},
            handler=_check_in,
            domain="attendance",
            requires_user_id=True,
        ),
    ]


def register_approval_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="create_approval",
            description="提交审批申请。需要指定标题、类型和审批人。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "审批标题"},
                    "approval_type": {"type": "string", "enum": ["leave", "expense", "purchase", "other"], "description": "审批类型：leave(请假)/expense(报销)/purchase(采购)/other(其他)"},
                    "description": {"type": "string", "description": "审批说明"},
                    "approver_ids": {"type": "array", "items": {"type": "integer"}, "description": "审批人ID列表"},
                },
                "required": ["title", "approval_type", "approver_ids"],
            },
            handler=_create_approval,
            domain="approval",
            requires_user_id=True,
        ),
        ToolDef(
            name="list_approvals",
            description="查看待处理的审批事项。",
            parameters={
                "type": "object",
                "properties": {
                    "role": {"type": "string", "enum": ["approver", "applicant"], "description": "角色：审批人还是申请人"},
                },
            },
            handler=_list_approvals,
            domain="approval",
            requires_user_id=True,
        ),
        ToolDef(
            name="delete_approval",
            description="删除一个审批申请。只能删除自己的申请。",
            parameters={
                "type": "object",
                "properties": {
                    "approval_id": {"type": "integer", "description": "审批ID"},
                },
                "required": ["approval_id"],
            },
            handler=_delete_approval,
            domain="approval",
            requires_user_id=True,
        ),
    ]


def register_user_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="list_users",
            description="获取系统中所有用户列表（姓名、部门、角色）。用于查找用户ID。",
            parameters={"type": "object", "properties": {}},
            handler=_list_users,
            domain="user",
        ),
        ToolDef(
            name="get_current_time",
            description="获取当前日期和时间。",
            parameters={"type": "object", "properties": {}},
            handler=_get_current_time,
            domain="general",
        ),
    ]
