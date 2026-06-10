"""Enhanced LLM client with function calling / tool use support.

Built on top of the existing LLMConfig, adds:
- tools parameter in API calls
- tool_calls parsing from responses
- Multi-turn conversation support (message history)
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from typing import Generator

from summary_system.llm_client import LLMConfig, load_env_file

from .llm_streaming import StreamingDelta, stream_chat as _stream_chat


class AgentLLMClient:
    """LLM client supporting OpenAI-compatible function calling."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.last_error: str | None = None

    @classmethod
    def from_env(cls) -> "AgentLLMClient | None":
        load_env_file()
        config = LLMConfig.from_env()
        return cls(config) if config else None

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Call the chat completions API with optional tool definitions.

        Returns the assistant message dict:
        {
            "content": str | None,
            "tool_calls": [{"id": ..., "type": "function", "function": {"name": ..., "arguments": ...}}] | None
        }
        """
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.config.temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"LLM HTTP {exc.code}: {detail}") from exc

        result = json.loads(raw)
        message = result["choices"][0]["message"]

        return {
            "content": message.get("content"),
            "tool_calls": message.get("tool_calls"),
        }

    def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> Generator[StreamingDelta, None, None]:
        """Stream chat completions, yielding token-by-token deltas.

        Handles text tokens and tool_call accumulation transparently.
        """
        yield from _stream_chat(self.config, messages, tools, temperature)

    def simple_chat(self, system_prompt: str, user_prompt: str) -> str:
        """Single-turn chat without tools, returns content string."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response = self.chat(messages)
        return response["content"] or ""
