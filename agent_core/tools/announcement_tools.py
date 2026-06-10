"""Announcement tools — wraps announcements/manager.py for agent use."""

from __future__ import annotations

import json
from typing import Any

from agent_core.tool_registry import ToolDef


def _create_announcement(title: str, content: str, user_id: int = 0, is_pinned: bool = False, **_: Any) -> str:
    from announcements import create_announcement
    ann_id = create_announcement(title, content, user_id, is_pinned=is_pinned)
    return json.dumps({"success": True, "announcement_id": ann_id, "message": f"公告「{title}」已发布"}, ensure_ascii=False)


def _list_announcements(limit: int = 10, **_: Any) -> str:
    from announcements import list_announcements
    result = list_announcements(page_size=limit)
    items = [
        {"id": a["id"], "title": a["title"], "author": a.get("author_name", ""),
         "is_pinned": bool(a.get("is_pinned")), "created_at": a.get("created_at", "")[:10]}
        for a in result.get("announcements", [])
    ]
    return json.dumps({"announcements": items, "total": result.get("total", 0)}, ensure_ascii=False)


def register_announcement_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="create_announcement",
            description="发布系统公告。当用户要求'发公告'、'发通知给所有人'时使用此工具。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "公告标题"},
                    "content": {"type": "string", "description": "公告内容（支持 Markdown）"},
                    "is_pinned": {"type": "boolean", "description": "是否置顶，默认 false"},
                },
                "required": ["title", "content"],
            },
            handler=_create_announcement,
            domain="notification",
            requires_user_id=True,
        ),
        ToolDef(
            name="list_announcements",
            description="列出所有系统公告。",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "返回条数，默认10"},
                },
            },
            handler=_list_announcements,
            domain="notification",
        ),
    ]
