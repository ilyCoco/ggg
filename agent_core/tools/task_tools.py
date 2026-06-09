"""Task management tools — wraps tasks/manager.py for agent use."""

from __future__ import annotations

import json
from typing import Any

from agent_core.tool_registry import ToolDef


def _create_task(title: str, description: str = "",
                 assignee_id: int | None = None, priority: str = "medium",
                 deadline: str = "", user_id: int = 0, **_: Any) -> str:
    from tasks import create_task
    task_id = create_task(
        title, user_id,
        description=description,
        assignee_id=assignee_id,
        priority=priority,
        deadline=deadline,
    )
    return json.dumps({"success": True, "task_id": task_id, "message": f"任务'{title}'已创建"}, ensure_ascii=False)


def _update_task(task_id: int, **fields: Any) -> str:
    from tasks import update_task
    ok = update_task(task_id, **{k: v for k, v in fields.items() if k != "task_id"})
    if ok:
        return json.dumps({"success": True, "message": f"任务 {task_id} 已更新"}, ensure_ascii=False)
    return json.dumps({"success": False, "message": "任务不存在或无有效更新字段"}, ensure_ascii=False)


def _list_tasks(status: str = "", priority: str = "", assignee_id: int | None = None,
                user_id: int | None = None, **_: Any) -> str:
    from tasks import list_tasks
    result = list_tasks(
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        my_tasks=user_id,
        page_size=10,
    )
    tasks_brief = [
        {"id": t["id"], "title": t["title"], "status": t["status"],
         "priority": t["priority"], "deadline": t.get("deadline", ""),
         "assignee": t.get("assignee_name", "")}
        for t in result["tasks"]
    ]
    return json.dumps({"tasks": tasks_brief, "total": result["total"]}, ensure_ascii=False)


def _get_task_detail(task_id: int, **_: Any) -> str:
    from tasks import get_task
    task = get_task(task_id)
    if not task:
        return json.dumps({"error": "任务不存在"}, ensure_ascii=False)
    return json.dumps({
        "id": task["id"], "title": task["title"], "description": task.get("description", ""),
        "status": task["status"], "priority": task["priority"],
        "deadline": task.get("deadline", ""), "assignee": task.get("assignee_name", ""),
        "creator": task.get("creator_name", ""), "created_at": task.get("created_at", ""),
    }, ensure_ascii=False)


def register_task_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="create_task",
            description="创建一个新任务。可指定标题、描述、负责人、优先级(high/medium/low)、截止日期。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "任务标题"},
                    "description": {"type": "string", "description": "任务描述（可选）"},
                    "assignee_id": {"type": "integer", "description": "负责人用户ID（可选）"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "优先级"},
                    "deadline": {"type": "string", "description": "截止日期，格式 YYYY-MM-DD"},
                },
                "required": ["title"],
            },
            handler=_create_task,
            domain="task",
            requires_user_id=True,
        ),
        ToolDef(
            name="update_task",
            description="更新任务的状态、优先级、负责人或截止日期。",
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "任务ID"},
                    "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "cancelled"], "description": "新状态"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "新优先级"},
                    "assignee_id": {"type": "integer", "description": "新负责人ID"},
                    "deadline": {"type": "string", "description": "新截止日期"},
                },
                "required": ["task_id"],
            },
            handler=_update_task,
            domain="task",
        ),
        ToolDef(
            name="list_tasks",
            description="列出任务。可按状态、优先级、负责人筛选。不传参数则列出当前用户的所有任务。",
            parameters={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "cancelled"], "description": "按状态筛选"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "按优先级筛选"},
                    "assignee_id": {"type": "integer", "description": "按负责人ID筛选"},
                },
            },
            handler=_list_tasks,
            domain="task",
            requires_user_id=True,
        ),
        ToolDef(
            name="get_task_detail",
            description="获取某个任务的详细信息。",
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "任务ID"},
                },
                "required": ["task_id"],
            },
            handler=_get_task_detail,
            domain="task",
        ),
    ]
