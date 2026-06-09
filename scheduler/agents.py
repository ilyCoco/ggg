"""Calendar agents — Scheduling AI + Report Generation AI."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from summary_system.llm_client import LLMClient
from database import get_connection


class SchedulingAgent:
    """AI-powered meeting scheduling: find optimal time, generate agenda."""

    name = "智能排期智能体"

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm

    def suggest_time(self, title: str, description: str = "",
                     attendees: list[int] | None = None) -> dict[str, Any]:
        if self.llm:
            result = self._run_llm(title, description, attendees)
            if result:
                return result
        return self._run_rules(title, description, attendees)

    def _run_llm(self, title: str, desc: str, attendees: list[int] | None) -> dict[str, Any] | None:
        if not self.llm:
            return None
        data = self.llm.generate_json(
            system_prompt="你是会议排期智能体。只返回 JSON。",
            user_prompt=(
                "根据会议需求建议合适的时间和时长。返回 JSON：\n"
                '{"suggested_date":"YYYY-MM-DD", "suggested_time":"HH:MM", '
                '"duration_minutes":60, "suggestion":"理由"}\n\n'
                f"会议：{title}\n描述：{desc[:2000]}\n参会人数：{len(attendees or [])}"
            ),
        )
        if not isinstance(data, dict):
            return None
        return {
            "suggested_date": data.get("suggested_date", ""),
            "suggested_time": data.get("suggested_time", ""),
            "duration_minutes": int(data.get("duration_minutes") or 60),
            "suggestion": data.get("suggestion", ""),
        }

    def _run_rules(self, title: str, desc: str, attendees: list[int] | None) -> dict[str, Any]:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        return {
            "suggested_date": tomorrow,
            "suggested_time": "10:00",
            "duration_minutes": 30,
            "suggestion": "建议提前发送议程，控制在30分钟内",
        }

    def detect_conflicts(self, start_time: str, end_time: str,
                         attendees: list[int] | None = None) -> list[dict[str, Any]]:
        conn = get_connection()
        conflicts = []
        for uid in (attendees or []):
            rows = conn.execute(
                """SELECT * FROM calendar_events
                   WHERE (creator_id = ? OR attendees LIKE ?)
                   AND start_time < ? AND end_time > ?""",
                (uid, f"%{uid}%", end_time, start_time),
            ).fetchall()
            for r in rows:
                conflicts.append(dict(r))
        conn.close()
        return conflicts


class ReportGenerationAgent:
    """AI weekly/monthly report generation from task + calendar data."""

    name = "周报生成智能体"

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm

    def generate_weekly_report(self, user_id: int) -> str:
        today = datetime.now()
        week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        week_end = today.strftime("%Y-%m-%d")

        conn = get_connection()
        # Completed tasks this week
        done = conn.execute(
            """SELECT title FROM tasks WHERE (assignee_id = ? OR creator_id = ?)
               AND status = 'completed' AND updated_at >= ?""",
            (user_id, user_id, week_start),
        ).fetchall()
        # In-progress tasks
        active = conn.execute(
            """SELECT title, priority, deadline FROM tasks
               WHERE (assignee_id = ? OR creator_id = ?)
               AND status IN ('pending','in_progress')""",
            (user_id, user_id),
        ).fetchall()
        # Events this week
        events = conn.execute(
            """SELECT title, start_time FROM calendar_events
               WHERE (creator_id = ? OR attendees LIKE ?)
               AND start_time >= ? AND start_time <= ?""",
            (user_id, f"%{user_id}%", week_start, week_end + "T23:59:59"),
        ).fetchall()
        conn.close()

        if self.llm:
            return self._run_llm(user_id, done, active, events)

        # Fallback: template-based
        lines = [
            f"# 周报 ({week_start} ~ {week_end})",
            "",
            "## 本周完成",
        ]
        for t in done:
            lines.append(f"- ✅ {t['title']}")
        lines.extend(["", "## 进行中"])
        for t in active:
            deadline_str = f" (截止: {t['deadline']})" if t["deadline"] else ""
            lines.append(f"- 🔄 {t['title']}{deadline_str}")
        lines.extend(["", "## 本周日程"])
        for ev in events:
            lines.append(f"- 📅 {ev['start_time'][:16]} {ev['title']}")
        return "\n".join(lines) + "\n"

    def _run_llm(self, user_id: int, done: list, active: list,
                 events: list) -> str:
        done_text = "\n".join(f"- {t['title']}" for t in done)
        active_text = "\n".join(f"- {t['title']} (优先级:{t['priority']})" for t in active)
        events_text = "\n".join(f"- {ev['start_time'][:16]} {ev['title']}" for ev in events)

        data = self.llm.generate_json(
            system_prompt="你是周报助手。请生成专业周报，输出 Markdown。只返回 JSON。",
            user_prompt=(
                "请根据以下数据生成周报。返回 JSON 格式：{\"report\":\"Markdown格式周报\"}\n\n"
                f"## 已完成任务\n{done_text}\n\n"
                f"## 进行中任务\n{active_text}\n\n"
                f"## 本周日程\n{events_text}\n\n"
                "周报应包含：本周工作概要、重点项目进展、遇到的问题、下周计划。"
            ),
        )
        if isinstance(data, dict) and data.get("report"):
            return str(data["report"])
        return self._run_rules(done, active, events)

    def _run_rules(self, done, active, events):
        # Already handled in the main method
        return ""
