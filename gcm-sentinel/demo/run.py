# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Demo: run investigation scenarios against mock data.

Usage: python -m gcm_sentinel.demo.run [--scenario NAME]
Requires ANTHROPIC_API_KEY or OPENAI_API_KEY to be set.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from gcm_sentinel.config import SentinelConfig
from gcm_sentinel.datasources import DataSource, DataSourceRegistry
from gcm_sentinel.engine import run_investigation
from gcm_sentinel.models import NodeConditionEvent

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "tests" / "scenarios"


class MockDataSource(DataSource):
    """Returns canned data from a scenario JSON file for all tools."""
    name = "mock"

    def __init__(self, cfg, scenario):
        super().__init__(cfg)
        self._scenario = scenario

    def get_tools(self):
        node_schema = {"type": "object", "properties": {"node_name": {"type": "string"}}, "required": ["node_name"]}
        return [
            {"name": "get_node_info", "description": "Node info.", "input_schema": node_schema},
            {"name": "get_node_events", "description": "Node events.", "input_schema": node_schema},
            {"name": "get_gcm_health", "description": "GCM/NPD health.", "input_schema": node_schema},
            {
                "name": "query_prometheus",
                "description": "Execute a PromQL query. Use the metrics reference in the system prompt.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "duration": {"type": "string", "default": "5m"},
                    },
                    "required": ["query"],
                },
            },
            {"name": "query_dcgm_direct", "description": "GPU metrics from dcgm-exporter.", "input_schema": node_schema},
        ]

    async def execute(self, tool_name, tool_input):
        if tool_name == "get_node_info":
            return json.dumps(self._scenario.get("node_info", {}), indent=2)
        elif tool_name == "get_gcm_health":
            return json.dumps(self._scenario.get("gcm_health", {}), indent=2)
        elif tool_name in ("query_prometheus", "query_dcgm_direct"):
            query = tool_input.get("query", "")
            for metric_name, response in self._scenario.get("prometheus_responses", {}).items():
                if metric_name in query:
                    return json.dumps(response.get("data", {}), indent=2)
            return json.dumps({"resultType": "vector", "result": []})
        return "[]"

    def get_system_prompt_section(self):
        return ""


async def run_scenario(scenario_path: Path, cfg: SentinelConfig) -> None:
    with open(scenario_path) as f:
        scenario = json.load(f)

    event = NodeConditionEvent(
        node_name=scenario["node_name"], condition_type=scenario["condition_type"],
        status="True", reason=scenario.get("reason", scenario["condition_type"]),
        message=scenario.get("message", ""),
    )

    print(f"\n{'='*70}\nSCENARIO: {scenario['name']}\n{'='*70}")
    print(f"Node: {event.node_name}  Condition: {event.condition_type}")
    print(f"Expected: severity={scenario.get('expected_severity')}, action={scenario.get('expected_action')}\n")

    registry = DataSourceRegistry(cfg)
    registry.register(MockDataSource(cfg, scenario))

    try:
        result = await run_investigation(event, cfg, registry)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return

    print(f"{'='*70}\nRESULT: severity={result.severity.value} action={result.recommended_action.value} confidence={result.confidence:.0%}")
    print(f"Summary: {result.summary}\nRoot cause: {result.root_cause}\nTool calls: {len(result.tool_calls)}\n{'='*70}\n")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("GCM_SENTINEL_API_KEY")
    if not api_key:
        print("Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GCM_SENTINEL_API_KEY")
        sys.exit(1)

    llm_api = os.environ.get("GCM_SENTINEL_LLM_API", "anthropic")
    if not os.environ.get("GCM_SENTINEL_LLM_API") and os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
        llm_api = "openai"

    cfg = SentinelConfig(api_key=api_key, llm_api=llm_api)

    scenario_filter = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--scenario" else None
    files = sorted(SCENARIOS_DIR.glob("*.json"))
    if scenario_filter:
        files = [f for f in files if scenario_filter in f.stem]
    if not files:
        print(f"No scenarios found in {SCENARIOS_DIR}")
        sys.exit(1)

    for f in files:
        asyncio.run(run_scenario(f, cfg))
    print("All scenarios complete.")


if __name__ == "__main__":
    main()
