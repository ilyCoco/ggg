"""Task Intelligence Agent — AI-powered task analysis with rule-based fallback."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from summary_system.llm_client import LLMClient

RISK_KEYWORDS = ["风险", "延期", "阻塞", "困难", "紧急", "问题", "故障", "事故", "隐患", "漏洞"]
URGENCY_KEYWORDS = ["紧急", "立即", "马上", "尽快", "ASAP", "立刻", "火速"]
COMPLEXITY_HIGH = ["复杂", "重构", "迁移", "架构", "大规模", "涉及多", "跨部门", "难点"]


class TaskIntelligenceAgent:
    """Analyzes task text to suggest priority, risks, deadline, and complexity."""

    name = "任务分析智能体"

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm

    def analyze(self, title: str, description: str = "", current_deadline: str = "") -> dict[str, Any]:
        full_text = f"{title}\n{description}"
        if self.llm:
            result = self._run_llm(full_text)
            if result:
                return result
        return self._run_rules(full_text, current_deadline)

    def _run_llm(self, text: str) -> dict[str, Any] | None:
        if not self.llm:
            return None
        data = self.llm.generate_json(
            system_prompt="你是任务分析智能体。请严格输出 JSON。",
            user_prompt=(
                "分析以下任务，返回 JSON：\n"
                '{"priority":"high|medium|low", "risks":["风险1"], '
                '"deadline_norm":"YYYY-MM-DD或空", "complexity":"high|medium|low", '
                '"suggestion":"一句话建议"}\n\n'
                f"{text[:3000]}"
            ),
        )
        if not isinstance(data, dict):
            return None
        return {
            "priority": data.get("priority", "medium"),
            "risks": data.get("risks") or [],
            "deadline_norm": data.get("deadline_norm") or "",
            "complexity": data.get("complexity", "medium"),
            "suggestion": data.get("suggestion", ""),
        }

    def _run_rules(self, text: str, current_deadline: str = "") -> dict[str, Any]:
        priority = self._classify_priority(text)
        risks = self._extract_risks(text)
        deadline_norm = self._normalize_deadline(text) or current_deadline
        complexity = self._classify_complexity(text)
        return {
            "priority": priority,
            "risks": risks,
            "deadline_norm": deadline_norm,
            "complexity": complexity,
            "suggestion": self._suggestion(priority, risks, deadline_norm, complexity),
        }

    def _classify_priority(self, text: str) -> str:
        count = sum(1 for kw in URGENCY_KEYWORDS if kw in text)
        if count >= 1:
            return "high"
        if any(kw in text for kw in ["必须", "务必", "关键", "核心"]):
            return "high"
        if any(kw in text for kw in ["不急", "有空", "低优"]):
            return "low"
        return "medium"

    def _extract_risks(self, text: str) -> list[str]:
        return [f"含关键词「{kw}」" for kw in RISK_KEYWORDS if kw in text][:5]

    def _normalize_deadline(self, text: str) -> str:
        today = datetime.now()
        m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", text)
        if m:
            return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
        m = re.search(r"(\d{1,2})月(\d{1,2})[日号]", text)
        if m:
            return f"{today.year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
        if "明天" in text:
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")
        if "后天" in text:
            return (today + timedelta(days=2)).strftime("%Y-%m-%d")
        m = re.search(r"(\d+)天后", text)
        if m:
            return (today + timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")
        if "下周" in text:
            return (today + timedelta(weeks=1)).strftime("%Y-%m-%d")
        return ""

    def _classify_complexity(self, text: str) -> str:
        if any(kw in text for kw in COMPLEXITY_HIGH):
            return "high"
        return "medium"

    def _suggestion(self, priority: str, risks: list[str], deadline: str, complexity: str) -> str:
        parts = []
        if priority == "high":
            parts.append("建议优先处理")
        if risks:
            parts.append(f"注意{len(risks)}个风险点")
        if deadline:
            parts.append(f"截止 {deadline}")
        if complexity == "high":
            parts.append("建议拆分子任务")
        return "；".join(parts) if parts else "暂无特别建议"
