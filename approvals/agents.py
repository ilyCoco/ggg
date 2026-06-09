"""Approval Review Agent — AI-assisted approval review."""

from __future__ import annotations

from typing import Any

from summary_system.llm_client import LLMClient


class ApprovalReviewAgent:
    """Reviews approval requests for anomalies and provides suggestions."""

    name = "审批审核智能体"

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm

    def review(self, approval_type: str, title: str, description: str,
               applicant_name: str = "", applicant_id: int = 0) -> dict[str, Any]:
        if self.llm:
            result = self._run_llm(approval_type, title, description, applicant_name)
            if result:
                return result
        return self._run_rules(approval_type, title, description)

    def _run_llm(self, atype: str, title: str, desc: str, name: str) -> dict[str, Any] | None:
        if not self.llm:
            return None
        data = self.llm.generate_json(
            system_prompt="你是审批辅助智能体。只返回 JSON。",
            user_prompt=(
                f"审核以下{atype}审批申请。返回 JSON 格式：\n"
                '{"risk_level":"low|medium|high", "suggestion":"一句话建议", '
                '"flags":["需要注意的点"]}\n\n'
                f"申请人：{name}\n标题：{title}\n说明：{desc[:2000]}"
            ),
        )
        if not isinstance(data, dict):
            return None
        return {
            "risk_level": data.get("risk_level", "low"),
            "suggestion": data.get("suggestion", ""),
            "flags": data.get("flags") or [],
        }

    def _run_rules(self, atype: str, title: str, desc: str) -> dict[str, Any]:
        flags = []
        risk = "low"
        full_text = f"{title} {desc}"

        if atype == "expense":
            import re
            amounts = re.findall(r"(\d+)元|¥(\d+)|￥(\d+)", full_text)
            for amt in amounts:
                val = int(amt[0] or amt[1] or amt[2] or 0)
                if val > 5000:
                    flags.append(f"金额较大（{val}元），建议核实明细")
                    risk = "high"
                elif val > 1000:
                    flags.append(f"金额 {val}元，注意核对")
                    risk = "medium"

        if atype == "leave":
            if any(kw in full_text for kw in ["月", "长期", "长假"]):
                flags.append("请假时间较长，注意工作交接")
                risk = "medium"

        return {
            "risk_level": risk,
            "suggestion": "请确认申请内容属实" if risk == "low" else "建议仔细审核后再批准",
            "flags": flags,
        }
