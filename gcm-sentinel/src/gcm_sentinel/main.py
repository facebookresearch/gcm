# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Main entry point for the GCM sentinel agent.

The agent is a pure watcher process — no listening ports, no HTTP server.
It watches K8s node conditions and triggers investigation when a GPU problem is
detected. Results go to logs, K8s Events, webhooks, and node annotations.
"""

from __future__ import annotations

import asyncio
import logging

import click

from gcm_sentinel.config import SentinelConfig
from gcm_sentinel.watcher import NodeConditionWatcher

logger = logging.getLogger(__name__)


@click.group()
def cli():
    """GCM Sentinel — AI-powered GPU cluster sentinel agent."""
    pass


@cli.command()
@click.option("--log-level", default="INFO", help="Log level")
def serve(log_level: str):
    """Start the sentinel agent (watches for GPU failures, triggers investigation)."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    cfg = SentinelConfig()

    # Print safety status prominently at startup.
    mode_banner = {
        "recommend": "OBSERVE-ONLY (no cluster mutations)",
        "annotate": "ANNOTATE (writes node annotations, no cordon/drain)",
        "execute": "EXECUTE (can cordon/drain/taint nodes!)",
    }
    logger.info("=" * 60)
    logger.info("GCM Sentinel Agent")
    logger.info("Action mode: %s — %s", cfg.action_mode, mode_banner[cfg.action_mode])
    if cfg.action_mode == "execute":
        logger.warning(
            "EXECUTE MODE ACTIVE — agent can modify cluster state. "
            "Max actions/hour: %d",
            cfg.max_actions_per_hour,
        )
    if cfg.node_allowlist:
        logger.info("Node allowlist: %s", cfg.node_allowlist)
    else:
        logger.info("Node allowlist: (all nodes)")
    logger.info("Cooldown: %ds, Prometheus: %s", cfg.cooldown_seconds, cfg.prometheus_url)
    logger.info("=" * 60)

    # Run the watcher loop — blocks forever, reconnects on errors.
    watcher = NodeConditionWatcher(cfg)
    asyncio.run(watcher.watch_loop())


@cli.command()
@click.argument("node_name")
@click.option("--condition", default="GcmXidErrorsProblem", help="Condition to investigate")
@click.option("--message", default="XID errors detected on GPU", help="Condition message")
def investigate(node_name: str, condition: str, message: str):
    """Run a one-shot investigation for a specific node."""
    from gcm_sentinel.models import NodeConditionEvent
    from gcm_sentinel.engine import run_investigation

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    cfg = SentinelConfig()
    event = NodeConditionEvent(
        node_name=node_name,
        condition_type=condition,
        status="True",
        reason=condition,
        message=message,
    )
    result = asyncio.run(run_investigation(event, cfg))
    print(f"\n{'='*60}")
    print(f"Node:       {result.node_name}")
    print(f"Severity:   {result.severity.value}")
    print(f"Confidence: {result.confidence:.0%}")
    print(f"Action:     {result.recommended_action.value}")
    print(f"Summary:    {result.summary}")
    print(f"Root cause: {result.root_cause}")
    print(f"Tool calls: {len(result.tool_calls)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    cli()
