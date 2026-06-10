"""Streaming LLM client — SSE-based streaming for real-time token output.

Yields incremental tokens and tool_call deltas from OpenAI-compatible streaming APIs.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Generator

from summary_system.llm_client import LLMConfig


class StreamingDelta:
    """A single streaming delta from the LLM."""

    __slots__ = ("type", "content", "tool_name", "tool_id", "arguments")

    def __init__(
        self,
        type: str,              # "text" | "tool_call_start" | "tool_call_delta" | "tool_call_end" | "done" | "error"
        content: str = "",
        tool_name: str = "",
        tool_id: str = "",
        arguments: str = "",
    ) -> None:
        self.type = type
        self.content = content
        self.tool_name = tool_name
        self.tool_id = tool_id
        self.arguments = arguments


def stream_chat(
    config: LLMConfig,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float | None = None,
) -> Generator[StreamingDelta, None, None]:
    """Stream chat completions, yielding StreamingDelta objects.

    Handles both text streaming and tool_call streaming (accumulated).

    Usage:
        for delta in stream_chat(config, messages, tools):
            if delta.type == "text":
                print(delta.content, end="", flush=True)
            elif delta.type == "tool_call_start":
                print(f"\\nCalling {delta.tool_name}...")
            ...
    """
    url = config.base_url.rstrip("/") + "/chat/completions"
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "temperature": temperature if temperature is not None else config.temperature,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=config.timeout) as response:
            # Read SSE stream line by line
            buffer = b""
            current_tool_id: str | None = None
            current_tool_name: str | None = None
            tool_args_buffer: str = ""

            while True:
                chunk = response.read(4096)
                if not chunk:
                    break
                buffer += chunk

                while b"\n" in buffer:
                    line_end = buffer.index(b"\n")
                    line = buffer[:line_end].decode("utf-8", errors="ignore").strip()
                    buffer = buffer[line_end + 1:]

                    if not line or line.startswith(":"):
                        continue

                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]

                    if data_str == "[DONE]":
                        # Flush any pending tool call
                        if current_tool_id:
                            yield StreamingDelta(
                                type="tool_call_end",
                                tool_id=current_tool_id,
                                tool_name=current_tool_name or "",
                                arguments=tool_args_buffer,
                            )
                        yield StreamingDelta(type="done")
                        return

                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = event.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    finish_reason = choices[0].get("finish_reason")

                    # ── Tool calls in delta ──
                    tc_deltas = delta.get("tool_calls")
                    if tc_deltas:
                        for tc in tc_deltas:
                            tc_id = tc.get("id")
                            tc_func = tc.get("function", {})

                            # New tool call starting
                            if tc_id:
                                # Flush previous if exists
                                if current_tool_id:
                                    yield StreamingDelta(
                                        type="tool_call_end",
                                        tool_id=current_tool_id,
                                        tool_name=current_tool_name or "",
                                        arguments=tool_args_buffer,
                                    )
                                current_tool_id = tc_id
                                current_tool_name = tc_func.get("name", "")
                                tool_args_buffer = ""
                                yield StreamingDelta(
                                    type="tool_call_start",
                                    tool_id=current_tool_id,
                                    tool_name=current_tool_name,
                                )

                            # Append arguments
                            args_chunk = tc_func.get("arguments", "")
                            if args_chunk:
                                tool_args_buffer += args_chunk
                                yield StreamingDelta(
                                    type="tool_call_delta",
                                    content=args_chunk,
                                    tool_id=current_tool_id or "",
                                )

                    # ── Plain text content ──
                    content = delta.get("content")
                    if content:
                        yield StreamingDelta(type="text", content=content)

                    # Handle finish
                    if finish_reason == "tool_calls" and current_tool_id:
                        yield StreamingDelta(
                            type="tool_call_end",
                            tool_id=current_tool_id,
                            tool_name=current_tool_name or "",
                            arguments=tool_args_buffer,
                        )
                        current_tool_id = None
                        current_tool_name = None
                        tool_args_buffer = ""

    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        yield StreamingDelta(type="error", content=f"LLM HTTP {exc.code}: {detail}")
    except Exception as exc:
        yield StreamingDelta(type="error", content=str(exc))
