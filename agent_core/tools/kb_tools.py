"""Knowledge base tools — wraps knowledge_base/manager.py for agent use."""

from __future__ import annotations

import json
from typing import Any

from agent_core.tool_registry import ToolDef


def _search_knowledge(query: str, **_: Any) -> str:
    from knowledge_base import search_entries
    result = search_entries(query, page_size=5)
    entries = [
        {"id": e["id"], "title": e["title"], "scene_type": e.get("scene_type", ""),
         "author": e.get("author_name", ""), "created_at": e.get("created_at", "")[:10]}
        for e in result.get("entries", [])
    ]
    return json.dumps({"results": entries, "total": result.get("total", 0)}, ensure_ascii=False)


def _create_kb_entry(title: str, content: str, user_id: int = 0,
                     scene_type: str = "general", category_id: int | None = None, **_: Any) -> str:
    from knowledge_base import create_entry
    entry_id = create_entry(
        title, content, user_id,
        scene_type=scene_type,
        category_id=category_id,
        is_public=True,
    )
    return json.dumps({"success": True, "entry_id": entry_id, "message": f"知识条目'{title}'已创建"}, ensure_ascii=False)


def _list_kb_categories(**_: Any) -> str:
    from knowledge_base import get_categories
    cats = get_categories()
    return json.dumps([{"id": c["id"], "name": c["name"], "icon": c.get("icon", "")} for c in cats], ensure_ascii=False)


def register_kb_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="search_knowledge",
            description="在知识库中全文搜索。输入关键词，返回匹配的知识条目。",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                },
                "required": ["query"],
            },
            handler=_search_knowledge,
            domain="knowledge",
        ),
        ToolDef(
            name="create_kb_entry",
            description="向知识库添加新的知识条目。",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "条目标题"},
                    "content": {"type": "string", "description": "条目内容（支持 Markdown）"},
                    "scene_type": {"type": "string", "enum": ["meeting", "classroom", "general"], "description": "内容类型"},
                    "category_id": {"type": "integer", "description": "分类ID（可选）"},
                },
                "required": ["title", "content"],
            },
            handler=_create_kb_entry,
            domain="knowledge",
            requires_user_id=True,
        ),
        ToolDef(
            name="list_kb_categories",
            description="获取知识库的所有分类列表。",
            parameters={"type": "object", "properties": {}},
            handler=_list_kb_categories,
            domain="knowledge",
        ),
    ]
