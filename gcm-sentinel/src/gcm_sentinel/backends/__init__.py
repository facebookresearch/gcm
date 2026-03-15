# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import Any


@dataclasses.dataclass
class ToolUseRequest:
    id: str
    name: str
    input: dict


@dataclasses.dataclass
class ChatResponse:
    text_parts: list[str]
    tool_requests: list[ToolUseRequest]
    done: bool
    raw_response: Any  # SDK-specific response for building follow-up messages.


class LLMBackend(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], system: str, tools: list[dict], max_tokens: int = 4096) -> ChatResponse: ...

    @abstractmethod
    def append_assistant_response(self, messages: list[dict], response: ChatResponse) -> None: ...

    @abstractmethod
    def append_tool_results(self, messages: list[dict], response: ChatResponse, results: list[tuple[ToolUseRequest, str]]) -> None: ...


def get_backend(api: str, api_key: str, model: str) -> LLMBackend:
    if api == "anthropic":
        from gcm_sentinel.backends.anthropic_backend import AnthropicBackend
        return AnthropicBackend(api_key=api_key, model=model)
    elif api == "openai":
        try:
            from gcm_sentinel.backends.openai_backend import OpenAIBackend
        except ImportError:
            raise ImportError("OpenAI backend requires the 'openai' package. Install with: pip install gcm-sentinel[openai]")
        return OpenAIBackend(api_key=api_key, model=model)
    else:
        raise ValueError(f"Unknown LLM API: {api!r}. Must be 'anthropic' or 'openai'.")
