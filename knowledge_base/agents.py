"""Knowledge Intelligence Agent — auto-categorize, discover relations, smart summaries."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from database import get_connection
from summary_system.llm_client import LLMClient


class KnowledgeIntelligenceAgent:
    """Analyzes knowledge base entries for auto-categorization, related discovery,
    and smart summarization.
    """

    name = "知识智能体"

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm

    # ── Auto-categorize ──

    def suggest_category(self, title: str, content: str) -> dict[str, Any]:
        """Suggest best matching category and confidence."""
        cats = self._get_categories()
        if self.llm:
            result = self._llm_categorize(title, content, cats)
            if result:
                return result
        return self._rule_categorize(title, content, cats)

    def _get_categories(self) -> list[dict[str, Any]]:
        conn = get_connection()
        rows = conn.execute("SELECT id, name, description FROM kb_categories ORDER BY id").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def _llm_categorize(self, title: str, content: str, cats: list) -> dict[str, Any] | None:
        if not self.llm:
            return None
        cat_desc = "\n".join(f"- {c['name']}: {c.get('description','')}" for c in cats)
        data = self.llm.generate_json(
            system_prompt="你是知识分类智能体。只返回 JSON。",
            user_prompt=(
                "请将以下内容分入合适的分类。返回 JSON：\n"
                '{"category_name":"分类名或空", "confidence":0.0-1.0, '
                '"suggested_tags":["标签1"], "reason":"原因"}\n\n'
                f"可选分类：\n{cat_desc}\n\n"
                f"标题：{title}\n内容：{content[:3000]}"
            ),
        )
        if not isinstance(data, dict):
            return None
        cat_name = data.get("category_name", "")
        matched = next((c for c in cats if c["name"] == cat_name), None)
        return {
            "category_id": matched["id"] if matched else None,
            "category_name": cat_name if matched else "",
            "confidence": float(data.get("confidence") or 0.6),
            "suggested_tags": data.get("suggested_tags") or [],
            "reason": data.get("reason", ""),
        }

    def _rule_categorize(self, title: str, content: str, cats: list) -> dict[str, Any]:
        text = title + " " + content[:2000]
        cat_scores = {}
        for c in cats:
            score = 0
            name = c["name"]
            # Keyword matching
            if name in text:
                score += 3
            kw_map = {
                "会议纪要": ["会议", "议题", "决策", "待办", "纪要", "讨论"],
                "课堂知识": ["课程", "知识", "老师", "考试", "学习", "定理", "公式"],
                "项目文档": ["项目", "需求", "方案", "计划", "进度", "开发", "上线"],
                "规章制度": ["制度", "规定", "规则", "合规", "管理", "流程", "标准"],
                "其他": [],
            }
            for kw in kw_map.get(name, []):
                if kw in text:
                    score += 1
            cat_scores[c["id"]] = score

        best_id = max(cat_scores, key=cat_scores.get) if cat_scores else None
        best_score = cat_scores.get(best_id, 0) if best_id else 0
        confidence = min(0.9, 0.4 + best_score * 0.1)
        best_name = next((c["name"] for c in cats if c["id"] == best_id), "")

        # Suggested tags from content
        tags = self._extract_keywords(text)

        return {
            "category_id": best_id if best_score > 0 else None,
            "category_name": best_name,
            "confidence": round(confidence, 2),
            "suggested_tags": tags[:5],
            "reason": f"基于关键词匹配，{best_name}，得分 {best_score}",
        }

    def _extract_keywords(self, text: str, limit: int = 5) -> list[str]:
        import re
        # Extract meaningful 2-4 char Chinese phrases
        words = re.findall(r"[一-龥]{2,4}", text)
        stopwords = {"这个", "那个", "我们", "他们", "一个", "可以", "没有", "这个", "不是",
                     "什么", "因为", "所以", "但是", "如果", "已经", "还是", "这些", "那些"}
        filtered = [w for w in words if w not in stopwords]
        counter = Counter(filtered)
        return [w for w, _ in counter.most_common(limit)]

    # ── Related entries discovery ──

    def find_related(self, entry_id: int, limit: int = 5) -> list[dict[str, Any]]:
        """Find related entries by scene type, keyword overlap, and category."""
        conn = get_connection()
        current = conn.execute(
            "SELECT id, title, plain_text, scene_type, category_id FROM kb_entries WHERE id = ?",
            (entry_id,),
        ).fetchone()
        if not current:
            conn.close()
            return []

        # Strategy 1: Same category
        if current["category_id"]:
            related_cat = conn.execute(
                "SELECT id, title, scene_type FROM kb_entries WHERE category_id = ? AND id != ? LIMIT ?",
                (current["category_id"], entry_id, limit),
            ).fetchall()
        else:
            related_cat = []

        # Strategy 2: Same scene type
        related_scene = conn.execute(
            "SELECT id, title, scene_type FROM kb_entries WHERE scene_type = ? AND id != ? LIMIT ?",
            (current["scene_type"], entry_id, limit),
        ).fetchall()

        # Strategy 3: FTS keyword search on title terms
        import re
        keywords = re.findall(r"[一-龥]{2,4}", current["title"])
        fts_related = []
        for kw in keywords[:3]:
            try:
                rows = conn.execute(
                    "SELECT e.id, e.title, e.scene_type FROM kb_entries_fts f JOIN kb_entries e ON f.rowid = e.id WHERE kb_entries_fts MATCH ? AND e.id != ? LIMIT 3",
                    (kw, entry_id),
                ).fetchall()
                fts_related.extend([dict(r) for r in rows])
            except Exception:
                continue
        conn.close()

        # Deduplicate and merge
        seen = set()
        merged = []
        for r in related_cat + related_scene + fts_related:
            d = dict(r)
            if d["id"] not in seen:
                seen.add(d["id"])
                merged.append(d)
        return merged[:limit]

    def find_related_with_llm(self, entry_id: int, limit: int = 5) -> dict[str, Any]:
        """Use LLM to discover deeper relations, or fall back to rules."""
        related = self.find_related(entry_id, limit)
        current = self._get_entry(entry_id)
        if not current:
            return {"related": related, "ai_analysis": ""}

        if self.llm:
            return self._llm_relations(current, related)
        return {
            "related": related,
            "ai_analysis": self._rule_relations(current, related),
        }

    def _get_entry(self, entry_id: int) -> dict[str, Any] | None:
        conn = get_connection()
        row = conn.execute("SELECT * FROM kb_entries WHERE id = ?", (entry_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def _llm_relations(self, current: dict, related: list) -> dict[str, Any]:
        if not self.llm:
            return {"related": related, "ai_analysis": ""}
        rel_text = "\n".join(f"- {r['title']}" for r in related[:5])
        data = self.llm.generate_json(
            system_prompt="你是知识关联分析智能体。只返回 JSON。",
            user_prompt=(
                "分析当前条目与候选条目的关系。返回 JSON：\n"
                '{"analysis":"一句话分析", "related_ids":[相关条目ID], "connections":["关联说明"]}\n\n'
                f"当前：{current['title']}\n候选项：\n{rel_text}"
            ),
        )
        if not isinstance(data, dict):
            return {"related": related, "ai_analysis": ""}
        return {
            "related": related,
            "ai_analysis": data.get("analysis", ""),
            "connections": data.get("connections") or [],
        }

    def _rule_relations(self, current: dict, related: list) -> str:
        if not related:
            return "暂未发现关联条目"
        cats = [r.get("scene_type", "") for r in related if r.get("scene_type")]
        common = Counter(cats).most_common(1)
        return f"发现 {len(related)} 条可能相关，主要关联场景为 {common[0][0]}" if common else f"发现 {len(related)} 条可能相关"

    # ── Smart Summarization ──

    def summarize(self, entry_id: int, max_length: int = 200) -> str:
        entry = self._get_entry(entry_id)
        if not entry:
            return ""
        content = entry.get("content", "") or entry.get("plain_text", "")
        if not content:
            return "（无内容）"

        if self.llm and len(content) > 500:
            result = self._llm_summarize(entry["title"], content, max_length)
            if result:
                return result

        # Rule-based: first N chars + extract headings
        lines = content.split("\n")
        headings = [l.lstrip("# ").strip() for l in lines if l.startswith("#")]
        if headings:
            return f"本文涵盖：{'、'.join(headings[:8])}"
        return content[:max_length] + ("..." if len(content) > max_length else "")

    def _llm_summarize(self, title: str, content: str, max_len: int) -> str | None:
        if not self.llm:
            return None
        data = self.llm.generate_json(
            system_prompt="你是文档摘要智能体。请生成精炼摘要。只返回 JSON。",
            user_prompt=(
                f"请为以下文档生成不超过 {max_len} 字的中文摘要。JSON 格式：{{\"summary\":\"...\"}}\n\n"
                f"标题：{title}\n内容：{content[:6000]}"
            ),
        )
        if isinstance(data, dict) and data.get("summary"):
            return str(data["summary"])
        return None

    # ── Natural Language KB Q&A ──

    def answer_question(self, question: str, deep: bool = False) -> dict[str, Any]:
        """Answer a question by searching the knowledge base with multi-strategy retrieval.

        Strategy: FTS5 → LIKE → combined ranking, then inject actual content into LLM.
        """
        import re

        # 1. Extract meaningful query terms
        # Split Chinese text into 2-3 char n-grams for FTS, keep long keywords intact
        raw_kw = re.findall(r"[一-龥]{2,6}|[a-zA-Z]{3,}", question)

        # 2. Multi-strategy search
        results = self._multi_search(question, raw_kw)

        # 3. Fetch actual content for top results — this is the key improvement
        enriched = self._enrich_results(results, max_content_chars=600 if deep else 0)

        # 4. Build LLM prompt with real content
        if self.llm and enriched:
            answer = self._llm_answer_with_content(question, enriched, deep=deep)
        elif enriched:
            answer = self._rule_answer_with_content(question, enriched)
        elif results:
            titles = [r["title"] for r in results[:5]]
            answer = f"找到 {len(results)} 条可能相关的内容，但没有足够信息回答。试试更具体的问题？相关条目：{'、'.join(titles)}"
        else:
            answer = self._fallback_answer(question)

        return {
            "question": question,
            "results": results,
            "answer": answer,
        }

    def _multi_search(self, question: str, keywords: list[str]) -> list[dict[str, Any]]:
        """Multi-strategy: FTS5 + LIKE + scene match, merged and deduplicated."""
        conn = get_connection()
        seen_ids: set[int] = set()
        results: list[dict[str, Any]] = []

        # Strategy 1: FTS5 on meaningful keywords (filter out question words)
        question_words = {"什么", "哪些", "怎么", "为什么", "如何", "哪里", "是谁", "有没有", "是否",
                          "可以", "能不能", "怎样", "什么样", "吗", "呢", "吧", "的", "了", "是", "在", "有"}
        clean_kw = [kw for kw in keywords if kw not in question_words and len(kw) >= 2]

        fts_q = " OR ".join(clean_kw[:8])
        if fts_q:
            try:
                rows = conn.execute(
                    "SELECT e.id, e.title, e.scene_type, e.created_at, e.view_count, e.category_id, "
                    "snippet(kb_entries_fts, 1, '<b>', '</b>', '...', 40) AS snippet "
                    "FROM kb_entries_fts f JOIN kb_entries e ON f.rowid = e.id "
                    "WHERE kb_entries_fts MATCH ? ORDER BY rank LIMIT 15",
                    (fts_q,),
                ).fetchall()
                for r in rows:
                    d = dict(r)
                    if d["id"] not in seen_ids:
                        d["search_method"] = "fts"
                        d["relevance"] = 3
                        seen_ids.add(d["id"])
                        results.append(d)
            except Exception:
                pass

        # Strategy 2: LIKE on cleaned keywords + whole question
        all_terms = clean_kw[:6] + [question.replace(" ", "")]
        for term in all_terms:
            if len(term) < 2:
                continue
            like = f"%{term}%"
            try:
                existing_ids = list(seen_ids) if seen_ids else []
                if existing_ids:
                    placeholders = ",".join("?" * len(existing_ids))
                    rows = conn.execute(
                        f"SELECT id, title, scene_type, created_at, view_count, category_id "
                        f"FROM kb_entries WHERE (title LIKE ? OR plain_text LIKE ?) "
                        f"AND id NOT IN ({placeholders}) LIMIT 5",
                        [like, like] + existing_ids,
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT id, title, scene_type, created_at, view_count, category_id "
                        "FROM kb_entries WHERE title LIKE ? OR plain_text LIKE ? LIMIT 5",
                        (like, like),
                    ).fetchall()
                for r in rows:
                    d = dict(r)
                    if d["id"] not in seen_ids:
                        d["search_method"] = "like"
                        d["relevance"] = 2
                        d["snippet"] = f"...{term}..."
                        seen_ids.add(d["id"])
                        results.append(d)
            except Exception:
                continue

        # Strategy 3: Scene-type matching — check if question contains scene-trigger words
        scene_triggers = [
            (["会议", "讨论", "决定", "议题", "纪要", "评审", "上线"], "meeting"),
            (["课堂", "课程", "老师", "学习", "考试", "知识", "重点", "复习", "Python", "知识点", "例题"], "classroom"),
            (["项目", "需求", "方案", "计划", "进度", "开发", "技术", "上线"], "meeting"),
            (["制度", "规定", "考勤", "请假", "报销", "规范"], "general"),
        ]
        matched_scenes = set()
        for trigger_words, scene in scene_triggers:
            if any(tw in question for tw in trigger_words):
                matched_scenes.add(scene)

        for scene in matched_scenes:
            if len(results) >= 15:
                break
            try:
                existing_ids = list(seen_ids) if seen_ids else []
                if existing_ids:
                    placeholders = ",".join("?" * len(existing_ids))
                    rows = conn.execute(
                        f"SELECT id, title, scene_type, created_at, view_count, category_id "
                        f"FROM kb_entries WHERE scene_type = ? AND id NOT IN ({placeholders}) LIMIT 5",
                        [scene] + existing_ids,
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT id, title, scene_type, created_at, view_count, category_id "
                        "FROM kb_entries WHERE scene_type = ? LIMIT 5",
                        (scene,),
                    ).fetchall()
                for r in rows:
                    d = dict(r)
                    if d["id"] not in seen_ids:
                        d["search_method"] = "scene"
                        d["relevance"] = 1
                        d["snippet"] = f"场景匹配：{scene}"
                        seen_ids.add(d["id"])
                        results.append(d)
            except Exception:
                continue
        conn.close()

        # Sort by relevance desc, then by view_count
        results.sort(key=lambda r: (r.get("relevance", 0), r.get("view_count", 0)), reverse=True)
        return results[:15]

    def _enrich_results(self, results: list[dict[str, Any]],
                        max_content_chars: int = 0) -> list[dict[str, Any]]:
        """Fetch actual plain_text content for top results."""
        if not results:
            return results
        conn = get_connection()
        top_ids = [r["id"] for r in results[:10]]
        placeholders = ",".join("?" * len(top_ids))
        rows = conn.execute(
            f"SELECT id, plain_text FROM kb_entries WHERE id IN ({placeholders})",
            top_ids,
        ).fetchall()
        content_map = {r["id"]: r["plain_text"] for r in rows}
        conn.close()

        for r in results:
            full = content_map.get(r["id"], "")
            if max_content_chars > 0 and len(full) > max_content_chars:
                r["content_preview"] = full[:max_content_chars] + "..."
            else:
                r["content_preview"] = full[:800] if full else ""
        return results

    def _llm_answer_with_content(self, question: str, results: list[dict[str, Any]],
                                  deep: bool = False) -> str:
        """Send actual entry content (not just titles) to the LLM."""
        # Build rich context: title + first 400 chars of actual content per entry
        ctx_parts = []
        for i, r in enumerate(results[:8]):
            preview = r.get("content_preview", "")
            scene_label = {"meeting": "会议纪要", "classroom": "课堂知识",
                           "mixed": "混合", "general": "通用"}.get(r.get("scene_type", ""), "")
            ctx_parts.append(
                f"[{i + 1}] {r['title']}（{scene_label}）\n"
                f"内容摘要：{preview[:500]}"
            )
        ctx = "\n\n".join(ctx_parts)
        char_limit = 8000 if deep else 5000

        data = self.llm.generate_json(
            system_prompt=(
                "你是知识库智能问答助手。请根据提供的知识库内容回答用户问题。\n"
                "规则：\n"
                "1. 如果知识库有相关信息，请基于内容给出具体回答，引用来源条目\n"
                "2. 如果信息不足，请诚实告知，不要编造\n"
                "3. 回答用中文，简洁有条理，必要时分点列出\n"
                "4. 返回 JSON：{\"answer\":\"回答内容\", \"sources\":[1,3]}（来源条目编号）"
            ),
            user_prompt=(
                f"用户问题：{question}\n\n"
                f"知识库内容（共 {len(results)} 条可能相关）：\n{ctx[:char_limit]}"
            ),
        )
        if isinstance(data, dict):
            answer = data.get("answer", "")
            sources = data.get("sources", [])
            if answer:
                if sources:
                    src_names = []
                    for s in sources:
                        if isinstance(s, int) and 1 <= s <= len(results):
                            src_names.append(results[s - 1]["title"])
                    if src_names:
                        answer += f"\n\n📎 参考：{'、'.join(src_names)}"
                return answer
        # Fallback
        return self._rule_answer_with_content(question, results)

    def _rule_answer_with_content(self, question: str, results: list[dict[str, Any]]) -> str:
        """Rule-based answer when no LLM available."""
        top = results[:5]
        parts = []
        for r in top:
            preview = r.get("content_preview", "")
            if preview:
                parts.append(f"**{r['title']}**：{preview[:200]}")
            else:
                parts.append(f"**{r['title']}**（{r.get('scene_type', '')}）")
        if not parts:
            return "未找到相关知识条目的内容。"
        return "找到以下相关内容：\n\n" + "\n\n".join(parts)

    def _fallback_answer(self, question: str) -> str:
        """Gentle fallback when no results found."""
        if "会议" in question:
            return "知识库中暂未找到相关会议记录。你可以通过「语音总结」页面导入会议纪要后再提问。"
        if "课堂" in question or "学习" in question or "知识" in question:
            return "知识库中暂未找到相关课堂笔记。你可以通过「语音总结」页面导入课堂内容后再提问。"
        return "知识库中暂未找到与问题相关的内容。尝试用更具体的关键词提问，或者先通过「语音总结」导入更多内容。"
