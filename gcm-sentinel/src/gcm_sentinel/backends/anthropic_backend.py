# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

import anthropic

from gcm_sentinel.backends import ChatResponse, LLMBackend, ToolUseRequest


class AnthropicBackend(LLMBackend):
    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def chat(self, messages, system, tools, max_tokens=4096):
        resp = self._client.messages.create(
            model=self._model, max_tokens=max_tokens,
            system=system, tools=tools, messages=messages,
        )
        text_parts, tool_requests = [], []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_requests.append(ToolUseRequest(id=block.id, name=block.name, input=block.input))

        return ChatResponse(
            text_parts=text_parts, tool_requests=tool_requests,
            done=resp.stop_reason == "end_turn" or not tool_requests,
            raw_response=resp,
        )

    def append_assistant_response(self, messages, response):
        messages.append({"role": "assistant", "content": response.raw_response.content})

    def append_tool_results(self, messages, response, results):
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": req.id, "content": text}
            for req, text in results
        ]})
