"""ReAct agent — the core reasoning loop with tool use."""

from __future__ import annotations

import json
from typing import Any, Callable

from .llm_client import AgentLLMClient
from .models import AgentStep, ToolCall
from .tool_registry import ToolRegistry


class ReActAgent:
    """Single-agent ReAct execution loop.

    Implements: Thought → Action (tool call) → Observation → repeat until final answer.
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        llm: AgentLLMClient,
        registry: ToolRegistry,
        tools_domains: list[str] | None = None,
        max_steps: int = 10,
    ) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self.llm = llm
        self.registry = registry
        self.tools_domains = tools_domains
        self.max_steps = max_steps

    def _get_tool_schemas(self) -> list[dict[str, Any]]:
        return self.registry.get_openai_schema(self.tools_domains)

    def run(
        self,
        user_message: str,
        context: dict[str, Any],
        on_step: Callable[[AgentStep], None] | None = None,
        memory_context: str = "",
        chat_history: list[dict[str, str]] | None = None,
    ) -> tuple[str, list[AgentStep]]:
        """Execute the ReAct loop.

        Args:
            user_message: The user's input.
            context: Runtime context (user_id, display_name, etc.)
            on_step: Optional callback fired after each reasoning step.
            memory_context: Optional memory/context to inject into system prompt.
            chat_history: Recent conversation turns for multi-turn context.

        Returns:
            (final_answer, list_of_reasoning_steps)
        """
        steps: list[AgentStep] = []
        tool_schemas = self._get_tool_schemas()

        system_content = self.system_prompt
        if memory_context:
            system_content += f"\n\n## 上下文记忆\n{memory_context}"

        user_info = ""
        if context.get("display_name"):
            user_info += f"当前用户：{context['display_name']}"
        if context.get("user_id"):
            user_info += f"（ID: {context['user_id']}）"
        if context.get("department"):
            user_info += f"，部门：{context['department']}"

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_content},
        ]
        if user_info:
            messages.append({"role": "system", "content": f"用户信息：{user_info}"})

        # Inject recent chat history for multi-turn context
        if chat_history:
            for turn in chat_history[-6:]:  # last 3 rounds
                messages.append({"role": turn["role"], "content": turn["content"]})

        messages.append({"role": "user", "content": user_message})

        for step_num in range(self.max_steps):
            try:
                response = self.llm.chat(messages, tools=tool_schemas)
            except Exception as exc:
                error_step = AgentStep(
                    step_type="error",
                    content=f"LLM 调用失败: {exc}",
                    agent_name=self.name,
                )
                steps.append(error_step)
                if on_step:
                    on_step(error_step)
                return f"抱歉，AI 服务暂时不可用：{exc}", steps

            tool_calls = response.get("tool_calls")
            content = response.get("content")

            if not tool_calls:
                final_answer = content or "任务完成。"
                final_step = AgentStep(
                    step_type="final_answer",
                    content=final_answer,
                    agent_name=self.name,
                )
                steps.append(final_step)
                if on_step:
                    on_step(final_step)
                return final_answer, steps

            # LLM wants to call tools
            if content:
                thought_step = AgentStep(
                    step_type="thought",
                    content=content,
                    agent_name=self.name,
                )
                steps.append(thought_step)
                if on_step:
                    on_step(thought_step)

            # Append assistant message with tool_calls to conversation
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
            assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            # Execute each tool call
            for tc in tool_calls:
                func = tc["function"]
                tool_name = func["name"]
                try:
                    tool_args = json.loads(func["arguments"]) if isinstance(func["arguments"], str) else func["arguments"]
                except json.JSONDecodeError:
                    tool_args = {}

                # Emit tool_call step
                call_step = AgentStep(
                    step_type="tool_call",
                    content=f"调用工具: {tool_name}",
                    tool_name=tool_name,
                    tool_args=tool_args,
                    agent_name=self.name,
                )
                steps.append(call_step)
                if on_step:
                    on_step(call_step)

                # Execute the tool
                tool_result = self.registry.execute(tool_name, tool_args, context)

                # Emit observation step
                obs_step = AgentStep(
                    step_type="observation",
                    content=_truncate(tool_result, 500),
                    tool_name=tool_name,
                    tool_result=tool_result,
                    agent_name=self.name,
                )
                steps.append(obs_step)
                if on_step:
                    on_step(obs_step)

                # Append tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": _truncate(tool_result, 2000),
                })

        # Max steps reached
        fallback = "已达到最大推理步数，以下是目前的分析结果：\n"
        if content:
            fallback += content
        else:
            fallback += "请尝试更具体的指令。"
        final_step = AgentStep(
            step_type="final_answer",
            content=fallback,
            agent_name=self.name,
        )
        steps.append(final_step)
        if on_step:
            on_step(final_step)
        return fallback, steps


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "...(已截断)"
