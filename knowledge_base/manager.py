from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from database import get_connection


# ── Categories ──

def get_categories() -> list[dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT c.*, (SELECT COUNT(*) FROM kb_entries WHERE category_id = c.id) AS entry_count "
        "FROM kb_categories c ORDER BY c.id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_category(name: str, description: str = "", icon: str = "📁") -> tuple[bool, str]:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO kb_categories (name, description, icon) VALUES (?, ?, ?)",
            (name, description, icon),
        )
        conn.commit()
        conn.close()
        return True, "创建成功"
    except Exception as e:
        conn.close()
        return False, str(e)


def update_category(cat_id: int, name: str = "", description: str = "", icon: str = "") -> bool:
    conn = get_connection()
    parts = []
    vals: list[Any] = []
    if name:
        parts.append("name = ?")
        vals.append(name)
    if description:
        parts.append("description = ?")
        vals.append(description)
    if icon:
        parts.append("icon = ?")
        vals.append(icon)
    if not parts:
        conn.close()
        return False
    vals.append(cat_id)
    conn.execute(f"UPDATE kb_categories SET {', '.join(parts)} WHERE id = ?", vals)
    conn.commit()
    conn.close()
    return True


def delete_category(cat_id: int) -> bool:
    conn = get_connection()
    conn.execute("UPDATE kb_entries SET category_id = NULL WHERE category_id = ?", (cat_id,))
    conn.execute("DELETE FROM kb_categories WHERE id = ?", (cat_id,))
    conn.commit()
    conn.close()
    return True


# ── Tags ──

def get_tags() -> list[dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT t.*, (SELECT COUNT(*) FROM entry_tags WHERE tag_id = t.id) AS entry_count "
        "FROM tags t ORDER BY t.name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_tag(name: str, color: str = "#6B7280") -> tuple[bool, str]:
    conn = get_connection()
    try:
        conn.execute("INSERT INTO tags (name, color) VALUES (?, ?)", (name, color))
        conn.commit()
        conn.close()
        return True, "创建成功"
    except Exception as e:
        conn.close()
        return False, str(e)


def delete_tag(tag_id: int) -> bool:
    conn = get_connection()
    conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    conn.commit()
    conn.close()
    return True


def get_entry_tags(entry_id: int) -> list[dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT t.* FROM tags t JOIN entry_tags et ON t.id = et.tag_id WHERE et.entry_id = ?",
        (entry_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Entries ──

def create_entry(
    title: str,
    content: str,
    created_by: int,
    scene_type: str = "general",
    category_id: int | None = None,
    tag_ids: list[int] | None = None,
    summary_json: str | None = None,
    is_public: bool = False,
) -> int:
    plain = _strip_markdown(content)
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO kb_entries (title, content, plain_text, scene_type, category_id, summary_json, created_by, is_public) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (title, content, plain, scene_type, category_id, summary_json, created_by, 1 if is_public else 0),
    )
    entry_id = cur.lastrowid
    if tag_ids:
        for tid in tag_ids:
            conn.execute("INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", (entry_id, tid))
    conn.commit()
    conn.close()
    return entry_id


def update_entry(
    entry_id: int,
    title: str | None = None,
    content: str | None = None,
    scene_type: str | None = None,
    category_id: int | None = None,
    tag_ids: list[int] | None = None,
    is_public: bool | None = None,
) -> bool:
    conn = get_connection()
    fields = ["updated_at = ?"]
    vals: list[Any] = [datetime.now().isoformat(timespec="seconds")]
    if title is not None:
        fields.append("title = ?")
        vals.append(title)
    if content is not None:
        fields.append("content = ?")
        vals.append(content)
        fields.append("plain_text = ?")
        vals.append(_strip_markdown(content))
    if scene_type is not None:
        fields.append("scene_type = ?")
        vals.append(scene_type)
    if category_id is not None:
        fields.append("category_id = ?")
        vals.append(category_id)
    if is_public is not None:
        fields.append("is_public = ?")
        vals.append(1 if is_public else 0)
    vals.append(entry_id)
    conn.execute(f"UPDATE kb_entries SET {', '.join(fields)} WHERE id = ?", vals)
    if tag_ids is not None:
        conn.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry_id,))
        for tid in tag_ids:
            conn.execute("INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)", (entry_id, tid))
    conn.commit()
    conn.close()
    return True


def get_entry(entry_id: int) -> dict[str, Any] | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT e.*, u.display_name AS author_name "
        "FROM kb_entries e LEFT JOIN users u ON e.created_by = u.id WHERE e.id = ?",
        (entry_id,),
    ).fetchone()
    if row:
        conn.execute("UPDATE kb_entries SET view_count = view_count + 1 WHERE id = ?", (entry_id,))
        conn.commit()
    conn.close()
    if not row:
        return None
    result = dict(row)
    result["tags"] = get_entry_tags(entry_id)
    return result


def delete_entry(entry_id: int) -> bool:
    conn = get_connection()
    conn.execute("DELETE FROM kb_entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return True


def list_entries(
    page: int = 1,
    page_size: int = 20,
    category_id: int | None = None,
    scene_type: str = "",
    tag_id: int | None = None,
    created_by: int | None = None,
    only_public: bool = False,
    viewer_id: int | None = None,
    sort_by: str = "created_at",
) -> dict[str, Any]:
    conn = get_connection()
    where = []
    params: list[Any] = []
    if category_id is not None:
        where.append("e.category_id = ?")
        params.append(category_id)
    if scene_type:
        where.append("e.scene_type = ?")
        params.append(scene_type)
    if created_by is not None:
        where.append("e.created_by = ?")
        params.append(created_by)
    if only_public:
        if viewer_id is not None:
            where.append("(e.is_public = 1 OR e.created_by = ?)")
            params.append(viewer_id)
        else:
            where.append("e.is_public = 1")
    if tag_id is not None:
        where.append("e.id IN (SELECT entry_id FROM entry_tags WHERE tag_id = ?)")
        params.append(tag_id)

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""
    sort_col = "e.created_at" if sort_by == "created_at" else "e.updated_at" if sort_by == "updated_at" else "e.view_count"

    count = conn.execute(
        f"SELECT COUNT(*) FROM kb_entries e {where_clause}", params
    ).fetchone()[0]

    offset = (page - 1) * page_size
    rows = conn.execute(
        f"SELECT e.*, u.display_name AS author_name "
        f"FROM kb_entries e LEFT JOIN users u ON e.created_by = u.id "
        f"{where_clause} ORDER BY {sort_col} DESC LIMIT ? OFFSET ?",
        params + [page_size, offset],
    ).fetchall()
    conn.close()

    entries = []
    for r in rows:
        d = dict(r)
        d["tags"] = get_entry_tags(d["id"])
        entries.append(d)

    return {
        "entries": entries,
        "total": count,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (count + page_size - 1) // page_size),
    }


def search_entries(
    query: str,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    conn = get_connection()
    try:
        count_row = conn.execute(
            "SELECT COUNT(*) FROM kb_entries_fts WHERE kb_entries_fts MATCH ?",
            (query,),
        ).fetchone()
        total = count_row[0] if count_row else 0
        offset = (page - 1) * page_size
        rows = conn.execute(
            "SELECT e.*, u.display_name AS author_name "
            "FROM kb_entries_fts f JOIN kb_entries e ON f.rowid = e.id "
            "LEFT JOIN users u ON e.created_by = u.id "
            "WHERE kb_entries_fts MATCH ? ORDER BY rank LIMIT ? OFFSET ?",
            (query, page_size, offset),
        ).fetchall()
    except Exception:
        # Fallback to LIKE search if FTS query is invalid
        like = f"%{query}%"
        count_row = conn.execute(
            "SELECT COUNT(*) FROM kb_entries WHERE title LIKE ? OR plain_text LIKE ?",
            (like, like),
        ).fetchone()
        total = count_row[0] if count_row else 0
        offset = (page - 1) * page_size
        rows = conn.execute(
            "SELECT e.*, u.display_name AS author_name FROM kb_entries e "
            "LEFT JOIN users u ON e.created_by = u.id "
            "WHERE e.title LIKE ? OR e.plain_text LIKE ? ORDER BY e.created_at DESC LIMIT ? OFFSET ?",
            (like, like, page_size, offset),
        ).fetchall()
    conn.close()

    entries = []
    for r in rows:
        d = dict(r)
        d["tags"] = get_entry_tags(d["id"])
        entries.append(d)

    return {
        "entries": entries,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


def get_recent_entries(limit: int = 10) -> list[dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT e.*, u.display_name AS author_name "
        "FROM kb_entries e LEFT JOIN users u ON e.created_by = u.id "
        "ORDER BY e.created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def import_from_summary(
    summary_json_path: str, created_by: int, category_id: int | None = None
) -> int | None:
    """Import an archived summary JSON into the knowledge base."""
    import json as _json
    from pathlib import Path

    path = Path(summary_json_path)
    if not path.exists():
        return None

    data = _json.loads(path.read_text(encoding="utf-8"))
    title = data.get("title", path.stem)
    scene_type = data.get("scene", {}).get("scene_type", "general")
    content_md = _summary_to_markdown(data)

    return create_entry(
        title=title,
        content=content_md,
        created_by=created_by,
        scene_type=scene_type,
        category_id=category_id,
        summary_json=_json.dumps(data, ensure_ascii=False),
        is_public=False,
    )


# ── Helpers ──

def _strip_markdown(text: str) -> str:
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    text = re.sub(r"`{1,3}.+?`{1,3}", "", text)
    text = re.sub(r"[-*+]\s+", "", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _summary_to_markdown(data: dict[str, Any]) -> str:
    lines = [f"# {data.get('title', '未命名')}", ""]
    scene = data.get("scene", {})
    lines.append(f"- 场景类型：{scene.get('scene_type', '')}")
    lines.append(f"- 生成时间：{data.get('created_at', '')}")
    lines.append("")
    content = data.get("content", {})
    for key, val in content.items():
        lines.append(f"## {key}")
        lines.extend(_dict_to_lines(val, 3))
        lines.append("")
    return "\n".join(lines)


def _dict_to_lines(value: Any, level: int) -> list[str]:
    out: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            prefix = "#" * min(level, 6)
            out.append(f"{prefix} {k}")
            out.extend(_dict_to_lines(v, level + 1))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                out.append("- " + "；".join(f"{k}：{v}" for k, v in item.items()))
            else:
                out.append(f"- {item}")
    else:
        out.append(str(value))
    return out
