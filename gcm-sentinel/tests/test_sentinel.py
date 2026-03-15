# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Tests for the critical paths: safety gating, config parsing, scenario validation."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from gcm_sentinel.config import DEFAULT_WATCH_CONDITIONS, SentinelConfig
from gcm_sentinel.models import Action, Severity


class TestSafety:
    """The most important tests: verify remediation tools are gated by action_mode."""

    def test_recommend_mode_has_no_remediation_tools(self):
        from gcm_sentinel.datasources import build_datasources

        registry = build_datasources(SentinelConfig(api_key="test", action_mode="recommend"))
        tool_names = {t["name"] for t in registry.get_all_tools()}
        assert "cordon_node" not in tool_names
        assert "drain_node" not in tool_names
        assert "taint_node" not in tool_names
        # Read-only tools present.
        assert "query_prometheus" in tool_names
        assert "get_node_info" in tool_names

    def test_annotate_mode_has_no_remediation_tools(self):
        from gcm_sentinel.datasources import build_datasources

        registry = build_datasources(SentinelConfig(api_key="test", action_mode="annotate"))
        assert "cordon_node" not in {t["name"] for t in registry.get_all_tools()}

    def test_execute_mode_has_remediation_tools(self):
        from gcm_sentinel.datasources import build_datasources

        registry = build_datasources(SentinelConfig(api_key="test", action_mode="execute"))
        tool_names = {t["name"] for t in registry.get_all_tools()}
        assert "cordon_node" in tool_names
        assert "drain_node" in tool_names
        assert "taint_node" in tool_names

    @pytest.mark.asyncio
    async def test_unknown_tool_blocked_by_registry(self):
        from gcm_sentinel.datasources import build_datasources

        registry = build_datasources(SentinelConfig(api_key="test", action_mode="recommend"))
        result = await registry.execute("cordon_node", {"node_name": "x"})
        assert "Unknown tool" in result

    def test_invalid_action_mode_rejected(self):
        with pytest.raises(ValueError, match="action_mode must be one of"):
            SentinelConfig(api_key="test", action_mode="yolo")


class TestConfig:
    def test_defaults(self):
        cfg = SentinelConfig(api_key="test")
        assert cfg.llm_api == "anthropic"
        assert cfg.action_mode == "recommend"
        assert cfg.can_execute is False
        assert cfg.can_annotate is False
        assert cfg.cooldown_seconds == 3600
        assert len(cfg.watch_conditions) == len(DEFAULT_WATCH_CONDITIONS)

    def test_csv_watch_conditions(self):
        cfg = SentinelConfig(api_key="t", watch_conditions="GcmXidErrorsProblem,GcmSmiEccProblem")
        assert cfg.watch_conditions == ["GcmXidErrorsProblem", "GcmSmiEccProblem"]

    def test_csv_node_allowlist(self):
        cfg = SentinelConfig(api_key="t", node_allowlist="gpu-node-0*,gpu-node-12")
        assert cfg.node_allowlist == ["gpu-node-0*", "gpu-node-12"]

    def test_action_mode_properties(self):
        assert SentinelConfig(api_key="t", action_mode="recommend").can_execute is False
        assert SentinelConfig(api_key="t", action_mode="annotate").can_annotate is True
        assert SentinelConfig(api_key="t", action_mode="execute").can_execute is True


class TestWatcherSafety:
    def test_node_allowlist_filtering(self):
        from gcm_sentinel.watcher import NodeConditionWatcher

        watcher = NodeConditionWatcher(SentinelConfig(api_key="t", node_allowlist=["gpu-node-0*", "gpu-node-12"]))
        assert watcher._node_in_scope("gpu-node-01") is True
        assert watcher._node_in_scope("gpu-node-21") is False

    def test_cooldown(self):
        from gcm_sentinel.watcher import NodeConditionWatcher

        watcher = NodeConditionWatcher(SentinelConfig(api_key="t", cooldown_seconds=60))
        assert watcher._in_cooldown("n1", "cond") is False
        watcher._last_run_time[("n1", "cond")] = time.monotonic()
        assert watcher._in_cooldown("n1", "cond") is True
        assert watcher._in_cooldown("n1", "other") is False

    def test_rate_limiter(self):
        from gcm_sentinel.datasources.remediation import RemediationDataSource

        ds = RemediationDataSource(SentinelConfig(api_key="t", action_mode="execute", max_actions_per_hour=2))
        assert ds._is_rate_limited() is False
        ds._action_timestamps.append(time.monotonic())
        ds._action_timestamps.append(time.monotonic())
        assert ds._is_rate_limited() is True


class TestScenarios:
    @pytest.mark.parametrize("name", [
        "hbm_degradation", "gpu_fallen_off_bus", "nvlink_errors",
        "thermal_throttle", "transient_xid",
    ])
    def test_scenario_valid(self, name):
        path = Path(__file__).parent / "scenarios" / f"{name}.json"
        scenario = json.loads(path.read_text())
        assert scenario["condition_type"] in DEFAULT_WATCH_CONDITIONS
        assert scenario["expected_severity"] in [s.value for s in Severity]
        assert scenario["expected_action"] in [a.value for a in Action]
