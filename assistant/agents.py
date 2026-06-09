"""Personal assistant & natural language query agents."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from database import get_connection
from summary_system.llm_client import LLMClient


class PersonalAssistantAgent:
    """Daily briefing agent — aggregates tasks, meetings, notifications, and detects conflicts.

    Generates a morning briefing card for the dashboard: upcoming deadlines, today's
    meetings, unread notifications, and schedule conflict warnings.
    """

    name = "个人助理智能体"

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm

    def daily_briefing(self, user_id: int) -> dict[str, Any]:
        """Generate a daily briefing snapshot."""
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        now = datetime.now().isoformat(timespec="seconds")

        conn = get_connection()

        # ── Tasks ──
        pending_rows = conn.execute(
            """SELECT id, title, priority, deadline, status
               FROM tasks WHERE (assignee_id = ? OR creator_id = ?)
               AND status IN ('pending','in_progress')
               ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, deadline""",
            (user_id, user_id),
        ).fetchall()
        pending_tasks = [dict(t) for t in pending_rows]
        pending_tasks = [dict(t) for t in pending_rows]

        urgent_tasks = [t for t in pending_tasks if t["priority"] == "high"]
        due_today = [t for t in pending_tasks if t["deadline"] and t["deadline"][:10] == today]
        overdue = [t for t in pending_tasks if t["deadline"] and t["deadline"] < today]

        # ── Meetings today ──
        meetings_raw = conn.execute(
            """SELECT id, title, event_type, start_time, end_time, location
               FROM calendar_events
               WHERE (creator_id = ? OR attendees LIKE ?)
               AND start_time >= ? AND start_time < ?
               ORDER BY start_time""",
            (user_id, f"%{user_id}%", today, tomorrow),
        ).fetchall()
        meetings = [dict(m) for m in meetings_raw]

        # ── Notifications ──
        unread = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,),
        ).fetchone()[0]

        recent_notifs = conn.execute(
            "SELECT title, type, created_at FROM notifications WHERE user_id = ? AND is_read = 0 ORDER BY created_at DESC LIMIT 5",
            (user_id,),
        ).fetchall()

        # ── Pending approvals ──
        pending_approvals = conn.execute(
            "SELECT COUNT(*) FROM approvals WHERE current_approver_id = ? AND status = 'pending'",
            (user_id,),
        ).fetchone()[0]

        # ── Attendance ──
        att_today = conn.execute(
            "SELECT check_in, check_out, status FROM attendance WHERE user_id = ? AND date = ?",
            (user_id, today),
        ).fetchone()

        # ── Upcoming deadlines (next 3 days) ──
        end_window = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        upcoming_deadlines = conn.execute(
            """SELECT title, deadline, priority FROM tasks
               WHERE assignee_id = ? AND status != 'completed' AND status != 'cancelled'
               AND deadline >= ? AND deadline <= ?
               ORDER BY deadline""",
            (user_id, today, end_window),
        ).fetchall()
        conn.close()

        # ── Conflict detection ──
        conflicts = self._detect_conflicts(meetings, pending_tasks)

        # ── Build briefing ──
        briefing = {
            "date": today,
            "greeting": self._greeting(),
            "task_summary": {
                "total_pending": len(pending_tasks),
                "urgent_count": len(urgent_tasks),
                "due_today": due_today,
                "overdue": overdue,
                "upcoming_deadlines": [dict(d) for d in upcoming_deadlines],
            },
            "meetings_today": [dict(m) for m in meetings],
            "notifications": {
                "unread_count": unread,
                "highlights": [dict(n) for n in recent_notifs],
            },
            "pending_approvals": pending_approvals,
            "attendance": dict(att_today) if att_today else None,
            "conflicts": conflicts,
        }

        # AI enhancement
        if self.llm:
            ai = self._run_llm(briefing)
            if ai:
                briefing["ai_insight"] = ai.get("insight", "")
                briefing["ai_suggestion"] = ai.get("suggestion", "")
                briefing["ai_mood"] = ai.get("mood", "🙂")
        else:
            briefing["ai_insight"] = self._rule_insight(briefing)
            briefing["ai_suggestion"] = self._rule_suggestion(briefing)
            briefing["ai_mood"] = "🙂"

        return briefing

    def _run_llm(self, briefing: dict) -> dict[str, Any] | None:
        if not self.llm:
            return None
        tasks_text = "\n".join(
            f"- {t['title']} (截止:{t.get('deadline','')})"
            for t in briefing["task_summary"]["due_today"]
        ) or "无"
        meetings_text = "\n".join(
            f"- {m['title']} ({m.get('start_time','')[:16]})"
            for m in briefing["meetings_today"]
        ) or "无"

        data = self.llm.generate_json(
            system_prompt="你是个人办公助理。请用中文返回 JSON，语气亲切专业。",
            user_prompt=(
                "请给用户一句今日洞察、一条行动建议和心情表情。返回 JSON：\n"
                '{"insight":"今日洞察一句话", "suggestion":"行动建议一句话", "mood":"😊|😰|💪|🎯"}\n\n'
                f"今日待办：{tasks_text}\n今日会议：{meetings_text}\n"
                f"未读通知：{briefing['notifications']['unread_count']}条\n"
                f"待审批：{briefing['pending_approvals']}条\n"
            ),
        )
        if not isinstance(data, dict):
            return None
        return {
            "insight": data.get("insight", ""),
            "suggestion": data.get("suggestion", ""),
            "mood": data.get("mood", "🙂"),
        }

    def _rule_insight(self, briefing: dict) -> str:
        parts = []
        tasks = briefing["task_summary"]
        if tasks["overdue"]:
            parts.append(f"⚠️ 有 {len(tasks['overdue'])} 个任务已逾期")
        if tasks["due_today"]:
            parts.append(f"📌 今天有 {len(tasks['due_today'])} 个任务到期")
        if briefing["meetings_today"]:
            parts.append(f"📅 今天 {len(briefing['meetings_today'])} 场会议")
        if briefing["notifications"]["unread_count"] > 5:
            parts.append(f"🔔 {briefing['notifications']['unread_count']} 条未读通知")
        return "；".join(parts) if parts else "今天看起来比较轻松"

    def _rule_suggestion(self, briefing: dict) -> str:
        tasks = briefing["task_summary"]
        if tasks["urgent_count"] > 3:
            return "建议优先处理紧急任务，今天有多个高优先级事项"
        if tasks["overdue"]:
            return "先处理逾期任务，再参加今天的会议"
        if briefing["pending_approvals"] > 0:
            return f"有 {briefing['pending_approvals']} 条待审批，建议抽空处理"
        if not tasks["total_pending"] and not briefing["meetings_today"]:
            return "今天日程宽松，可以安排学习或优化工作"
        return "先处理今天的到期任务，再推进进行中的工作"

    def _detect_conflicts(self, meetings: list, tasks: list) -> list[dict[str, Any]]:
        conflicts = []
        for m in meetings:
            m_start = m.get("start_time", "")
            m_end = m.get("end_time", m_start)
            for t in tasks:
                deadline = t.get("deadline", "")
                if deadline and m_start[:10] == deadline[:10]:
                    conflicts.append({
                        "type": "deadline_vs_meeting",
                        "meeting": m["title"],
                        "task": t["title"],
                        "message": f"会议「{m['title']}」当天有任务「{t['title']}」截止",
                    })
        return conflicts[:3]

    def _greeting(self) -> str:
        hour = datetime.now().hour
        if hour < 9:
            return "早上好"
        elif hour < 12:
            return "上午好"
        elif hour < 14:
            return "中午好"
        elif hour < 18:
            return "下午好"
        return "晚上好"


class NaturalQueryAgent:
    """Natural language query agent — answers questions about the user's data.

    Supports questions like:
    - "我这周完成了什么？"
    - "张三在做什么？"
    - "项目X的进度？"
    - "这个月考勤怎么样？"
    - "最近有哪些公告？"
    """

    name = "自然语言查询智能体"

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm

    def query(self, question: str, user_id: int, user_name: str = "") -> dict[str, Any]:
        """Answer a natural language question by querying the database."""
        lower = question.lower()

        # Route to domain handler
        if self.llm:
            route = self._llm_route(question)
        else:
            route = self._rule_route(lower)

        if route == "work_summary":
            return self._work_summary(user_id, question)
        elif route == "colleague":
            return self._colleague_info(question)
        elif route == "project_progress":
            return self._project_progress(question)
        elif route == "attendance":
            return self._attendance_query(user_id, question)
        elif route == "announcements":
            return self._announcements_query()
        elif route == "kb_search":
            return self._kb_query(question)
        else:
            return self._general_query(question, user_id)

    def _llm_route(self, question: str) -> str:
        if not self.llm:
            return self._rule_route(question.lower())
        data = self.llm.generate_json(
            system_prompt="你是查询路由智能体。只返回 JSON。",
            user_prompt=(
                "判断用户意图，返回 JSON：{\"route\":\"work_summary|colleague|project_progress|attendance|announcements|kb_search|general\"}\n\n"
                f"用户问：{question[:500]}"
            ),
        )
        if isinstance(data, dict):
            return data.get("route", "general")
        return "general"

    def _rule_route(self, lower: str) -> str:
        if any(kw in lower for kw in ["完成", "这周", "本周", "最近", "做了", "工作"]):
            return "work_summary"
        if any(kw in lower for kw in ["在做什么", "忙什么", "任务"]):
            return "colleague"
        if any(kw in lower for kw in ["项目", "进度", "进展"]):
            return "project_progress"
        if any(kw in lower for kw in ["考勤", "打卡", "迟到", "签到"]):
            return "attendance"
        if any(kw in lower for kw in ["公告", "通知"]):
            return "announcements"
        if any(kw in lower for kw in ["知识", "学习", "文档", "会议纪要"]):
            return "kb_search"
        return "general"

    def _work_summary(self, user_id: int, question: str) -> dict[str, Any]:
        today = datetime.now()
        week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")

        conn = get_connection()
        # Completed this week
        done = conn.execute(
            """SELECT title FROM tasks WHERE assignee_id = ?
               AND status = 'completed' AND updated_at >= ?""",
            (user_id, week_start),
        ).fetchall()
        # Active
        active = conn.execute(
            """SELECT title, priority, deadline FROM tasks WHERE assignee_id = ?
               AND status IN ('pending','in_progress')""",
            (user_id,),
        ).fetchall()
        # Meetings this week
        meetings = conn.execute(
            """SELECT title, start_time FROM calendar_events
               WHERE (creator_id = ? OR attendees LIKE ?)
               AND start_time >= ? ORDER BY start_time""",
            (user_id, f"%{user_id}%", week_start),
        ).fetchall()
        # Attendance this month
        month_start = today.strftime("%Y-%m") + "-01"
        att = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM attendance WHERE user_id = ? AND date >= ? GROUP BY status",
            (user_id, month_start),
        ).fetchall()
        conn.close()

        done_list = [d["title"] for d in done]
        active_list = [dict(a) for a in active]
        meeting_list = [dict(m) for m in meetings]
        att_stats = {a["status"]: a["cnt"] for a in att}

        if self.llm:
            summary = self._llm_summary(done_list, active_list, meeting_list, att_stats)
        else:
            summary = f"本周已完成 {len(done_list)} 个任务，{len(active_list)} 个进行中，{len(meeting_list)} 场会议。正常出勤 {att_stats.get('normal', 0)} 天。"

        return {
            "type": "work_summary",
            "period": f"{week_start} ~ {today.strftime('%Y-%m-%d')}",
            "completed": done_list,
            "active": active_list,
            "meetings": meeting_list,
            "attendance": att_stats,
            "summary": summary,
        }

    def _llm_summary(self, done: list, active: list, meetings: list, att: dict) -> str:
        if not self.llm:
            return f"本周已完成 {len(done)} 个任务，{len(active)} 个进行中。"
        done_text = "\n".join(f"- {t}" for t in done[:10]) or "无"
        active_text = "\n".join(f"- {a['title']}" for a in active[:10]) or "无"
        data = self.llm.generate_json(
            system_prompt="你是工作总结助手。请用 2-3 句话中文总结本周工作。只返回 JSON。",
            user_prompt=(
                "总结本周工作。返回 JSON：{\"summary\":\"2-3句中文总结\"}\n\n"
                f"已完成：\n{done_text}\n\n进行中：\n{active_text}\n\n会议：{len(meetings)}场\n考勤正常：{att.get('normal',0)}天"
            ),
        )
        if isinstance(data, dict) and data.get("summary"):
            return str(data["summary"])
        return f"本周已完成 {len(done)} 个任务，{len(active)} 个进行中。"

    def _colleague_info(self, question: str) -> dict[str, Any]:
        conn = get_connection()
        # Extract name from question
        import re
        names = re.findall(r"[一-龥]{2,4}", question)
        result = {"type": "colleague", "found": False, "data": None}
        for name in names:
            if name in ("在做什么", "忙什么", "怎么样", "什么"):
                continue
            row = conn.execute(
                "SELECT id, display_name, department FROM users WHERE display_name = ? OR username = ?",
                (name, name),
            ).fetchone()
            if row:
                uid = row["id"]
                tasks = conn.execute(
                    "SELECT title, status, priority, deadline FROM tasks WHERE assignee_id = ? AND status != 'completed' AND status != 'cancelled' LIMIT 5",
                    (uid,),
                ).fetchall()
                events = conn.execute(
                    "SELECT title, start_time FROM calendar_events WHERE (creator_id = ? OR attendees LIKE ?) AND start_time >= datetime('now') ORDER BY start_time LIMIT 5",
                    (uid, f"%{uid}%"),
                ).fetchall()
                conn.close()
                result["found"] = True
                result["data"] = {
                    "name": row["display_name"],
                    "department": row.get("department", ""),
                    "tasks": [dict(t) for t in tasks],
                    "upcoming_events": [dict(e) for e in events],
                }
                return result
        conn.close()
        return result

    def _project_progress(self, question: str) -> dict[str, Any]:
        conn = get_connection()
        # Keyword search in task titles
        keywords = question.replace("项目", "").replace("的", "").replace("进度", "").replace("？", "").strip()
        like = f"%{keywords}%" if keywords else "%"

        tasks = conn.execute(
            """SELECT t.*, u.display_name AS assignee_name
               FROM tasks t LEFT JOIN users u ON t.assignee_id = u.id
               WHERE t.title LIKE ? ORDER BY t.created_at DESC LIMIT 10""",
            (like,),
        ).fetchall()

        # Also search KB
        kb = conn.execute(
            "SELECT title, scene_type FROM kb_entries WHERE title LIKE ? OR plain_text LIKE ? LIMIT 5",
            (like, f"%{keywords}%"),
        ).fetchall()
        conn.close()

        tlist = [dict(t) for t in tasks]
        status_count = {"pending": 0, "in_progress": 0, "completed": 0}
        for t in tlist:
            s = t.get("status", "pending")
            if s in status_count:
                status_count[s] += 1

        return {
            "type": "project_progress",
            "keyword": keywords,
            "tasks": tlist,
            "kb_entries": [dict(k) for k in kb],
            "status_summary": status_count,
            "summary": f"共找到 {len(tlist)} 个相关任务，{status_count['completed']} 已完成、{status_count['in_progress']} 进行中、{status_count['pending']} 待办",
        }

    def _attendance_query(self, user_id: int, question: str) -> dict[str, Any]:
        today = datetime.now()
        month_start = today.strftime("%Y-%m") + "-01"

        conn = get_connection()
        month_records = conn.execute(
            "SELECT date, check_in, check_out, status FROM attendance WHERE user_id = ? AND date >= ? ORDER BY date",
            (user_id, month_start),
        ).fetchall()
        conn.close()

        stats = {"normal": 0, "late": 0, "early": 0, "absent": 0}
        for r in month_records:
            s = r["status"]
            if s in stats:
                stats[s] += 1

        work_days = len(month_records)
        return {
            "type": "attendance",
            "month": today.strftime("%Y-%m"),
            "work_days": work_days,
            "stats": stats,
            "records": [dict(r) for r in month_records],
            "summary": f"本月出勤 {work_days} 天，正常 {stats['normal']} 天，迟到 {stats['late']} 次",
        }

    def _announcements_query(self) -> dict[str, Any]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT title, content, created_at FROM announcements WHERE is_published = 1 ORDER BY is_pinned DESC, created_at DESC LIMIT 5",
        ).fetchall()
        conn.close()
        return {
            "type": "announcements",
            "announcements": [dict(r) for r in rows],
            "summary": f"最近有 {len(rows)} 条公告",
        }

    def _kb_query(self, question: str) -> dict[str, Any]:
        conn = get_connection()
        keywords = question.replace("知识库", "").replace("搜索", "").replace("找", "").strip()
        like = f"%{keywords}%" if keywords else "%"
        try:
            rows = conn.execute(
                "SELECT e.title, e.scene_type, e.created_at FROM kb_entries_fts f JOIN kb_entries e ON f.rowid = e.id WHERE kb_entries_fts MATCH ? LIMIT 5",
                (keywords,),
            ).fetchall()
        except Exception:
            rows = conn.execute(
                "SELECT title, scene_type, created_at FROM kb_entries WHERE title LIKE ? OR plain_text LIKE ? LIMIT 5",
                (like, like),
            ).fetchall()
        conn.close()
        return {
            "type": "kb_search",
            "results": [dict(r) for r in rows],
            "summary": f"找到 {len(rows)} 条相关知识",
        }

    def _general_query(self, question: str, user_id: int) -> dict[str, Any]:
        # Fallback: aggregate summary
        conn = get_connection()
        task_count = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE assignee_id = ? AND status != 'completed'",
            (user_id,),
        ).fetchone()[0]
        unread = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,),
        ).fetchone()[0]
        events = conn.execute(
            "SELECT COUNT(*) FROM calendar_events WHERE (creator_id = ? OR attendees LIKE ?) AND start_time >= datetime('now')",
            (user_id, f"%{user_id}%"),
        ).fetchone()[0]
        conn.close()
        return {
            "type": "general",
            "summary": f"你当前有 {task_count} 个待办任务、{events} 个近期日程、{unread} 条未读通知。你可以问我：我这周完成了什么？/ 某同事在忙什么？/ 项目进度？/ 考勤情况？",
        }
