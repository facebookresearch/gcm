# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""OpenAI backend. Also works with any OpenAI-compatible API (vLLM, Ollama,
Azure OpenAI) — set OPENAI_BASE_URL env var to point at your endpoint."""

from __future__ import annotations

import json

from openai import OpenAI

from gcm_sentinel.backends import ChatResponse, LLMBackend, ToolUseRequest


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    return [
        {"type": "function", "function": {
            "name": t["name"], "description": t.get("description", ""),
            "parameters": t.get("input_schema", {}),
        }}
        for t in tools
    ]


class OpenAIBackend(LLMBackend):
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def chat(self, messages, system, tools, max_tokens=4096):
        full_messages = [{"role": "system", "content": system}] + messages
        openai_tools = _to_openai_tools(tools)

        resp = self._client.chat.completions.create(
            model=self._model, messages=full_messages,
            tools=openai_tools or None, max_tokens=max_tokens,
        )
        choice = resp.choices[0]
        msg = choice.message

        text_parts = [msg.content] if msg.content else []
        tool_requests = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_requests.append(ToolUseRequest(id=tc.id, name=tc.function.name, input=args))

        return ChatResponse(
            text_parts=text_parts, tool_requests=tool_requests,
            done=choice.finish_reason != "tool_calls" or not tool_requests,
            raw_response=resp,
        )

    def append_assistant_response(self, messages, response):
        choice = response.raw_response.choices[0]
        msg = {"role": "assistant"}
        if choice.message.content:
            msg["content"] = choice.message.content
        if choice.message.tool_calls:
            msg["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in choice.message.tool_calls
            ]
        messages.append(msg)

    def append_tool_results(self, messages, response, results):
        for req, text in results:
            messages.append({"role": "tool", "tool_call_id": req.id, "content": text})
