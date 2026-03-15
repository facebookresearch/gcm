# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Investigation engine — drives an LLM through a tool-use loop."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from gcm_sentinel.backends import get_backend
from gcm_sentinel.config import SentinelConfig
from gcm_sentinel.models import Action, NodeConditionEvent, Severity, ToolCall, SentinelResult
from gcm_sentinel.datasources import DataSourceRegistry, build_datasources

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = """\
You are an expert GPU cluster reliability engineer. A Kubernetes node has reported
a GPU-related problem.

Investigate thoroughly using ALL available tools — explore every data source you
have access to before making your assessment. The tools available to you are your
eyes and hands into the cluster. Use them extensively.

For XID error code reference, see: https://docs.nvidia.com/deploy/xid-errors/

## Assessment

Provide your final assessment as JSON:
```json
{"severity": "critical|warning|info|ok", "summary": "...", "root_cause": "...", "recommended_action": "cordon|drain|taint|reboot|none", "confidence": 0.0-1.0}
```
"""

_MODE_DESCRIPTIONS = {
    "recommend": "Action mode: RECOMMEND (observe-only). Do NOT attempt cluster mutations.",
    "annotate": "Action mode: ANNOTATE. Recommendations will be written as node annotations. Do NOT mutate directly.",
    "execute": "Action mode: EXECUTE. You may cordon/drain/taint nodes for confirmed hardware failures.",
}


def _load_system_prompt(cfg: SentinelConfig, registry: DataSourceRegistry) -> str:
    path = Path(cfg.system_prompt_path)
    base = path.read_text() if path.is_file() else DEFAULT_SYSTEM_PROMPT
    additions = registry.get_system_prompt_additions()
    return f"{base}\n\n{additions}" if additions else base


def _parse_assessment(text: str) -> dict:
    # Strip markdown fences.
    cleaned = text
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[-1].split("```")[0]
    elif "```" in cleaned:
        parts = cleaned.split("```")
        if len(parts) >= 3:
            cleaned = parts[-2]

    # Find JSON object with assessment fields.
    target_keys = {"severity", "recommended_action", "confidence"}
    depth, start = 0, -1
    for i, ch in enumerate(cleaned):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    parsed = json.loads(cleaned[start:i + 1])
                    if isinstance(parsed, dict) and target_keys & parsed.keys():
                        return parsed
                except json.JSONDecodeError:
                    pass
                start = -1
    return {}


async def run_investigation(
    event: NodeConditionEvent,
    cfg: SentinelConfig,
    registry: DataSourceRegistry | None = None,
) -> SentinelResult:
    if registry is None:
        registry = build_datasources(cfg)

    # Restrict remediation tools to the node being investigated.
    from gcm_sentinel.datasources.remediation import RemediationDataSource
    for ds in registry._sources:
        if isinstance(ds, RemediationDataSource):
            ds.set_allowed_node(event.node_name)

    start_time = time.monotonic()
    system_prompt = _load_system_prompt(cfg, registry)
    tools = registry.get_all_tools()
    backend = get_backend(cfg.llm_api, cfg.api_key, cfg.model)
    tool_calls_log: list[ToolCall] = []
    text_parts: list[str] = []

    logger.info("Investigating %s/%s via %s/%s (%d tools)", event.node_name, event.condition_type, cfg.llm_api, cfg.model, len(tools))

    messages: list[dict] = [{"role": "user", "content": (
        f"Node condition change detected:\n\n"
        f"- **Node**: {event.node_name}\n- **Condition**: {event.condition_type}\n"
        f"- **Status**: {event.status}\n- **Message**: {event.message}\n"
        f"- **Time**: {event.timestamp}\n\n{_MODE_DESCRIPTIONS[cfg.action_mode]}\n\n"
        f"Investigate and provide your assessment."
    )}]

    investigation_parts = [f"== Investigation for {event.node_name} =="]

    for round_num in range(1, cfg.max_tool_rounds + 1):
        response = backend.chat(messages=messages, system=system_prompt, tools=tools)
        text_parts = response.text_parts
        investigation_parts.extend(text_parts)

        if response.done:
            break

        backend.append_assistant_response(messages, response)
        results = []
        for req in response.tool_requests:
            investigation_parts.append(f"\n> {req.name}({json.dumps(req.input, default=str)[:200]})")
            try:
                result = await registry.execute(req.name, req.input)
            except Exception as exc:
                result = f"Tool error: {type(exc).__name__}: {exc}"
                logger.exception("Tool %s failed", req.name)

            # Truncate if configured (controls LLM context cost).
            llm_result = result
            if cfg.max_tool_output and len(result) > cfg.max_tool_output:
                llm_result = result[:cfg.max_tool_output] + (
                    f"\n\n[OUTPUT TRUNCATED: showing {cfg.max_tool_output} of {len(result)} chars. "
                    f"Call the tool again with a more specific query to get the data you need.]"
                )

            tool_calls_log.append(ToolCall(tool_name=req.name, tool_input=req.input, result=result))
            investigation_parts.append(f"Result: {result}")
            results.append((req, llm_result))

        backend.append_tool_results(messages, response, results)

    final_text = "\n".join(text_parts)
    assessment = _parse_assessment(final_text)

    logger.info("Investigation complete for %s in %.1fs (%d tool calls)", event.node_name, time.monotonic() - start_time, len(tool_calls_log))

    try:
        severity = Severity(assessment.get("severity", "warning"))
    except ValueError:
        severity = Severity.WARNING
    try:
        action = Action(assessment.get("recommended_action", "none"))
    except ValueError:
        action = Action.NONE
    try:
        confidence = max(0.0, min(1.0, float(assessment.get("confidence", 0.5))))
    except (ValueError, TypeError):
        confidence = 0.5

    return SentinelResult(
        node_name=event.node_name,
        condition=event.condition_type,
        severity=severity,
        summary=assessment.get("summary", final_text[:500]),
        root_cause=assessment.get("root_cause", "Unknown"),
        recommended_action=action,
        confidence=confidence,
        tool_calls=tool_calls_log,
        investigation_log="\n".join(investigation_parts),
    )
