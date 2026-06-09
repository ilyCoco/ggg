"""Tool registry — registers manager functions as callable agent tools."""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolDef:
    """Definition of a tool available to agents."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for function parameters
    handler: Callable[..., Any]
    domain: str = "general"
    requires_user_id: bool = False


class ToolRegistry:
    """Central registry that maps tool names to their definitions and handlers."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    def register(self, tool: ToolDef) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDef]:
        return list(self._tools.values())

    def execute(self, name: str, arguments: dict[str, Any], context: dict[str, Any]) -> str:
        """Execute a tool by name, injecting user context as needed.

        Returns a JSON string with the result or error.
        """
        tool = self._tools.get(name)
        if not tool:
            return json.dumps({"error": f"Tool '{name}' not found"}, ensure_ascii=False)

        try:
            if tool.requires_user_id:
                arguments["user_id"] = context.get("user_id")
            result = tool.handler(**arguments)
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as exc:
            return json.dumps(
                {"error": f"Tool execution failed: {exc}"},
                ensure_ascii=False,
            )

    def get_openai_schema(self, domains: list[str] | None = None) -> list[dict[str, Any]]:
        """Export tools as OpenAI-compatible function definitions.

        If domains is provided, only return tools matching those domains.
        """
        schemas = []
        for tool in self._tools.values():
            if domains and tool.domain not in domains:
                continue
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        return schemas

    def get_tools_for_domains(self, domains: list[str]) -> list[ToolDef]:
        """Get tool definitions for specific domains."""
        return [t for t in self._tools.values() if t.domain in domains]
