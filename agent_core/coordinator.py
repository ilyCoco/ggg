"""Coordinator agent — decomposes requests and delegates to domain agents."""

from __future__ import annotations

import json
from typing import Any, Callable

from .domain_agents import AGENT_CONFIGS
from .llm_client import AgentLLMClient
from .memory import MemoryManager
from .models import AgentStep, ExecutionPlan, SubTask
from .react_agent import ReActAgent
from .tool_registry import ToolRegistry
from .tools.task_tools import register_task_tools
from .tools.kb_tools import register_kb_tools
from .tools.calendar_tools import register_calendar_tools
from .tools.announcement_tools import register_announcement_tools
from .tools.general_tools import (
    register_notification_tools,
    register_message_tools,
    register_attendance_tools,
    register_approval_tools,
    register_user_tools,
)


def build_registry() -> ToolRegistry:
    """Build the global tool registry with all available tools."""
    registry = ToolRegistry()
    all_tools = (
        register_task_tools()
        + register_kb_tools()
        + register_calendar_tools()
        + register_notification_tools()
        + register_message_tools()
        + register_attendance_tools()
        + register_approval_tools()
        + register_announcement_tools()
        + register_user_tools()
    )
    for tool in all_tools:
        registry.register(tool)
    return registry


class CoordinatorAgent:
    """Top-level orchestrator that routes requests to the appropriate domain agent."""

    def __init__(self, llm: AgentLLMClient, registry: ToolRegistry | None = None) -> None:
        self.llm = llm
        self.registry = registry or build_registry()
        self.agents = self._init_agents()

    def _init_agents(self) -> dict[str, ReActAgent]:
        agents = {}
        for key, config in AGENT_CONFIGS.items():
            agents[key] = ReActAgent(
                name=config["name"],
                system_prompt=config["system_prompt"],
                llm=self.llm,
                registry=self.registry,
                tools_domains=config["domains"],
                max_steps=10,
            )
        return agents

    def handle_request(
        self,
        user_message: str,
        context: dict[str, Any],
        memory: MemoryManager | None = None,
        on_step: Callable[[AgentStep], None] | None = None,
    ) -> tuple[str, list[AgentStep]]:
        """Process a user request through the appropriate agent(s).

        Returns (final_answer, reasoning_chain).
        """
        all_steps: list[AgentStep] = []

        # Route the request (with conversation context for better intent understanding)
        chat_history = context.get("chat_history") or (memory.get_recent_turns(6) if memory else [])
        plan = self._plan_request(user_message, chat_history)

        # Emit planning step
        plan_step = AgentStep(
            step_type="thought",
            content=f"意图分析: {plan.reasoning}",
            agent_name="协调智能体",
        )
        all_steps.append(plan_step)
        if on_step:
            on_step(plan_step)

        # Get memory context
        memory_ctx = memory.get_context_string() if memory else ""

        if len(plan.subtasks) <= 1:
            # Single domain — delegate directly
            domain = plan.domains[0] if plan.domains else "general"
            agent = self.agents.get(domain, self.agents["general"])

            # Emit delegation step
            delegate_step = AgentStep(
                step_type="thought",
                content=f"委派给: {agent.name}",
                agent_name="协调智能体",
            )
            all_steps.append(delegate_step)
            if on_step:
                on_step(delegate_step)

            answer, steps = agent.run(user_message, context, on_step=on_step,
                                      memory_context=memory_ctx, chat_history=chat_history)
            all_steps.extend(steps)
        else:
            # Multi-domain — execute subtasks sequentially
            results = []
            for i, subtask in enumerate(plan.subtasks):
                agent = self.agents.get(subtask.domain, self.agents["general"])

                delegate_step = AgentStep(
                    step_type="thought",
                    content=f"子任务 {i+1}/{len(plan.subtasks)}: {subtask.prompt[:50]}... → {agent.name}",
                    agent_name="协调智能体",
                )
                all_steps.append(delegate_step)
                if on_step:
                    on_step(delegate_step)

                # Inject previous results into prompt if there are dependencies
                augmented_prompt = subtask.prompt
                if results and subtask.depends_on:
                    prev_context = "\n".join(
                        f"前序结果 {j+1}: {results[j][:200]}"
                        for j in subtask.depends_on if j < len(results)
                    )
                    augmented_prompt = f"{subtask.prompt}\n\n参考上下文：\n{prev_context}"

                sub_answer, sub_steps = agent.run(augmented_prompt, context, on_step=on_step,
                                                  memory_context=memory_ctx, chat_history=chat_history)
                all_steps.extend(sub_steps)
                results.append(sub_answer)

            # Synthesize final answer
            answer = self._synthesize(user_message, results, plan)
            final_step = AgentStep(
                step_type="final_answer",
                content=answer,
                agent_name="协调智能体",
            )
            all_steps.append(final_step)
            if on_step:
                on_step(final_step)

        # Store memory
        if memory:
            memory.add_turn("user", user_message)
            memory.add_turn("assistant", answer)

        return answer, all_steps

    def _plan_request(self, user_message: str, chat_history: list[dict[str, str]] | None = None) -> ExecutionPlan:
        """Use LLM to analyze intent and decompose if needed."""
        history_text = ""
        if chat_history:
            history_text = "\n最近对话历史：\n" + "\n".join(
                f"{'用户' if t['role'] == 'user' else 'AI'}: {t['content'][:100]}"
                for t in chat_history[-4:]
            ) + "\n"

        routing_prompt = (
            "你是请求路由智能体。分析用户请求，判断需要哪些领域的智能体来处理。\n"
            "可用领域：task(任务管理), calendar(日程安排), knowledge(知识库), approval(审批), "
            "announcement(公告通知), general(通用)\n\n"
            "返回 JSON 格式：\n"
            '{"domains": ["task"], "reasoning": "用户想创建任务", '
            '"subtasks": [{"domain": "task", "prompt": "创建一个任务...", "depends_on": []}]}\n\n'
            "规则：\n"
            "- 简单请求只需一个领域和一个子任务\n"
            "- 复杂请求（涉及多个操作）分解为多个子任务\n"
            "- depends_on 是子任务索引列表，表示依赖关系\n"
            "- 结合对话历史理解用户的指代和省略（如'常用的'指代前文提到的内容）\n"
            f"{history_text}"
            f"\n用户当前请求：{user_message}"
        )

        try:
            response = self.llm.simple_chat("只返回合法 JSON，不要其他文字。", routing_prompt)
            data = json.loads(response.strip().removeprefix("```json").removesuffix("```").strip())

            domains = data.get("domains", ["general"])
            reasoning = data.get("reasoning", "")
            subtasks = []
            for st in data.get("subtasks", []):
                subtasks.append(SubTask(
                    domain=st.get("domain", "general"),
                    prompt=st.get("prompt", user_message),
                    depends_on=st.get("depends_on", []),
                ))

            if not subtasks:
                subtasks = [SubTask(domain=domains[0], prompt=user_message)]

            return ExecutionPlan(domains=domains, subtasks=subtasks, reasoning=reasoning)
        except Exception:
            return ExecutionPlan(
                domains=["general"],
                subtasks=[SubTask(domain="general", prompt=user_message)],
                reasoning="路由解析失败，使用通用智能体处理",
            )

    def _synthesize(self, original_request: str, results: list[str], plan: ExecutionPlan) -> str:
        """Synthesize results from multiple agents into a unified response."""
        if len(results) == 1:
            return results[0]

        try:
            results_text = "\n---\n".join(f"子任务 {i+1} 结果：\n{r}" for i, r in enumerate(results))
            synthesis = self.llm.simple_chat(
                "你是总结智能体，将多个子任务的结果合并为一个连贯的回复。用中文，简洁明了。",
                f"原始请求：{original_request}\n\n各子任务结果：\n{results_text}\n\n请合并为一个完整的回复。",
            )
            return synthesis or "\n\n".join(results)
        except Exception:
            return "\n\n".join(results)
