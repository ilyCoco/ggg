"""Calendar/scheduling tools — wraps scheduler/manager.py for agent use."""

from __future__ import annotations

import json
from typing import Any

from agent_core.tool_registry import ToolDef


def _create_event(title: str, start_time: str, creator_id: int = 0,
                  description: str = "", event_type: str = "meeting",
                  end_time: str = "", location: str = "",
                  attendees: list[int] | None = None, user_id: int = 0, **_: Any) -> str:
    from scheduler import create_event
    cid = creator_id or user_id
    ev_id = create_event(
        title, cid, start_time,
        description=description,
        event_type=event_type,
        end_time=end_time,
        location=location,
        attendees=attendees,
    )
    return json.dumps({"success": True, "event_id": ev_id, "message": f"日程'{title}'已创建"}, ensure_ascii=False)


def _get_upcoming_events(user_id: int = 0, limit: int = 5, **_: Any) -> str:
    from scheduler import get_upcoming_events
    events = get_upcoming_events(user_id, limit=limit)
    brief = [
        {"id": e["id"], "title": e["title"], "start_time": e["start_time"],
         "end_time": e.get("end_time", ""), "location": e.get("location", ""),
         "event_type": e.get("event_type", "")}
        for e in events
    ]
    return json.dumps({"events": brief, "count": len(brief)}, ensure_ascii=False)


def _get_events_by_range(start_date: str, end_date: str, user_id: int = 0, **_: Any) -> str:
    from scheduler import get_events_by_date_range
    events = get_events_by_date_range(start_date, end_date, creator_id=user_id)
    brief = [
        {"id": e["id"], "title": e["title"], "start_time": e["start_time"],
         "end_time": e.get("end_time", ""), "event_type": e.get("event_type", "")}
        for e in events
    ]
    return json.dumps({"events": brief, "count": len(brief)}, ensure_ascii=False)


def register_calendar_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="create_event",
            description="创建日程或会议。需要标题和开始时间，可指定参与人员。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "日程标题"},
                    "start_time": {"type": "string", "description": "开始时间，格式 YYYY-MM-DD HH:MM"},
                    "end_time": {"type": "string", "description": "结束时间（可选）"},
                    "description": {"type": "string", "description": "描述"},
                    "event_type": {"type": "string", "enum": ["meeting", "personal", "reminder"], "description": "类型"},
                    "location": {"type": "string", "description": "地点"},
                    "attendees": {"type": "array", "items": {"type": "integer"}, "description": "参与人员用户ID列表"},
                },
                "required": ["title", "start_time"],
            },
            handler=_create_event,
            domain="calendar",
            requires_user_id=True,
        ),
        ToolDef(
            name="get_upcoming_events",
            description="获取当前用户近期的日程安排。",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "返回数量，默认5"},
                },
            },
            handler=_get_upcoming_events,
            domain="calendar",
            requires_user_id=True,
        ),
        ToolDef(
            name="get_events_by_range",
            description="查询某个日期范围内的日程。",
            parameters={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "起始日期 YYYY-MM-DD"},
                    "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                },
                "required": ["start_date", "end_date"],
            },
            handler=_get_events_by_range,
            domain="calendar",
            requires_user_id=True,
        ),
    ]
