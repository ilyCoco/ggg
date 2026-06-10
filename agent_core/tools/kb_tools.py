"""Knowledge base tools — wraps knowledge_base/manager.py for agent use."""

from __future__ import annotations

import json
from typing import Any

from agent_core.tool_registry import ToolDef


def _entry_to_dict(e: dict) -> dict:
    from knowledge_base import get_attachments
    atts = get_attachments(e["id"])
    return {
        "id": e["id"],
        "title": e["title"],
        "scene_type": e.get("scene_type", ""),
        "author": e.get("author_name", ""),
        "created_at": e.get("created_at", "")[:10],
        "has_attachments": len(atts) > 0,
        "attachment_count": len(atts),
        "attachments": [{"name": a["original_name"], "size_kb": round(a["file_size"] / 1024, 1),
                         "mime": a["mime_type"]} for a in atts],
    }


def _search_knowledge(query: str, **_: Any) -> str:
    from knowledge_base import search_entries
    result = search_entries(query, page_size=5)
    entries = [_entry_to_dict(e) for e in result.get("entries", [])]
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


def _list_all_entries(limit: int = 10, **_: Any) -> str:
    from knowledge_base import list_entries
    result = list_entries(page_size=limit)
    entries = [_entry_to_dict(e) for e in result.get("entries", [])]
    return json.dumps({"entries": entries, "total": result.get("total", 0)}, ensure_ascii=False)


def _get_entry_detail(entry_id: int, **_: Any) -> str:
    from knowledge_base import get_entry
    entry = get_entry(entry_id)
    if not entry:
        return json.dumps({"error": f"条目 {entry_id} 不存在"}, ensure_ascii=False)
    info = _entry_to_dict(entry)
    info["content"] = entry.get("content", "")[:2000]
    info["category"] = entry.get("category_id")
    return json.dumps(info, ensure_ascii=False)


def register_kb_tools() -> list[ToolDef]:
    return [
        ToolDef(
            name="search_knowledge",
            description="在知识库中全文搜索。返回匹配条目及附件信息。",
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
            name="list_kb_entries",
            description="列出知识库所有条目（含附件信息）。用户问'有什么'时优先用此工具。",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "返回条数，默认10"},
                },
            },
            handler=_list_all_entries,
            domain="knowledge",
        ),
        ToolDef(
            name="get_entry_detail",
            description="查看单条知识条目的详细信息，包括完整内容和附件列表。",
            parameters={
                "type": "object",
                "properties": {
                    "entry_id": {"type": "integer", "description": "条目ID"},
                },
                "required": ["entry_id"],
            },
            handler=_get_entry_detail,
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
