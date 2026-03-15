# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Watches K8s node conditions and triggers investigation on GPU problems."""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import time

from kubernetes import client, config, watch

from gcm_sentinel.config import SentinelConfig
from gcm_sentinel.models import NodeConditionEvent
from gcm_sentinel.notify import annotate_node, notify
from gcm_sentinel.datasources import build_datasources
from gcm_sentinel.engine import run_investigation

logger = logging.getLogger(__name__)


class NodeConditionWatcher:
    def __init__(self, cfg: SentinelConfig) -> None:
        self.cfg = cfg
        self._registry = None
        self._condition_states: dict[tuple[str, str], str] = {}
        self._last_run_time: dict[tuple[str, str], float] = {}
        self._active_tasks: set[asyncio.Task] = set()

    def _init_k8s(self) -> None:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

    def _node_in_scope(self, node_name: str) -> bool:
        if not self.cfg.node_allowlist:
            return True
        return any(fnmatch.fnmatch(node_name, p) for p in self.cfg.node_allowlist)

    def _in_cooldown(self, node_name: str, condition: str) -> bool:
        last = self._last_run_time.get((node_name, condition))
        if last is None:
            return False
        remaining = self.cfg.cooldown_seconds - (time.monotonic() - last)
        if remaining > 0:
            logger.info("Cooldown: %s/%s (%.0fs left)", node_name, condition, remaining)
            return True
        return False

    def _detect_changes(self, node_name: str, conditions: list) -> list[NodeConditionEvent]:
        events = []
        for cond in conditions:
            if cond.type not in self.cfg.watch_conditions:
                continue
            key = (node_name, cond.type)
            prev = self._condition_states.get(key)
            if prev != cond.status:
                self._condition_states[key] = cond.status
                if cond.status == "True":
                    events.append(NodeConditionEvent(
                        node_name=node_name, condition_type=cond.type,
                        status=cond.status, reason=cond.reason or "", message=cond.message or "",
                    ))
        return events

    async def _handle_event(self, event: NodeConditionEvent) -> None:
        node, cond = event.node_name, event.condition_type
        if not self._node_in_scope(node) or self._in_cooldown(node, cond):
            return

        self._last_run_time[(node, cond)] = time.monotonic()
        logger.info("Investigation triggered: %s on %s (%s)", cond, node, event.message)

        try:
            if self._registry is None:
                self._registry = build_datasources(self.cfg)
            result = await run_investigation(event, self.cfg, self._registry)

            logger.info("Result for %s: severity=%s action=%s confidence=%.2f",
                        node, result.severity.value, result.recommended_action.value, result.confidence)
            logger.info("Summary: %s", result.summary)

            if self.cfg.can_annotate:
                await annotate_node(result)
            await notify(result, webhook_url=self.cfg.webhook_url)

        except Exception:
            logger.exception("Investigation failed for %s", node)

    async def watch_loop(self) -> None:
        self._init_k8s()
        api = client.CoreV1Api()
        w = watch.Watch()

        logger.info("Watcher started (mode=%s, conditions=%d, allowlist=%s, cooldown=%ds)",
                     self.cfg.action_mode, len(self.cfg.watch_conditions),
                     self.cfg.node_allowlist or "(all)", self.cfg.cooldown_seconds)

        while True:
            try:
                for event in w.stream(api.list_node, timeout_seconds=0):
                    if event["type"] not in ("ADDED", "MODIFIED"):
                        continue
                    node = event["object"]
                    for change in self._detect_changes(node.metadata.name, node.status.conditions or []):
                        task = asyncio.create_task(self._handle_event(change))
                        self._active_tasks.add(task)
                        task.add_done_callback(self._active_tasks.discard)
            except Exception:
                logger.exception("Watch stream error, reconnecting in 5s (%d active investigations)", len(self._active_tasks))
                await asyncio.sleep(5)
