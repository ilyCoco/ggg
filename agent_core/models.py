"""Data models for the agent framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ToolCall:
    """A single tool invocation from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class AgentStep:
    """One step in the agent's reasoning chain."""

    step_type: str  # "thought" | "tool_call" | "observation" | "final_answer" | "error"
    content: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: str | None = None
    agent_name: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


@dataclass
class SubTask:
    """A decomposed subtask for multi-agent collaboration."""

    domain: str
    prompt: str
    depends_on: list[int] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    """Coordinator's plan for handling a user request."""

    domains: list[str]
    subtasks: list[SubTask]
    reasoning: str = ""
