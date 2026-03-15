# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from kubernetes import client

from gcm_sentinel.k8s import get_core_api
from gcm_sentinel.models import SentinelResult

logger = logging.getLogger(__name__)


async def annotate_node(result: SentinelResult) -> None:
    try:
        api = get_core_api()
        api.patch_node(result.node_name, {"metadata": {"annotations": {
            "gcm-sentinel/severity": result.severity.value,
            "gcm-sentinel/action": result.recommended_action.value,
            "gcm-sentinel/confidence": f"{result.confidence:.2f}",
            "gcm-sentinel/summary": result.summary[:250],
            "gcm-sentinel/root-cause": result.root_cause[:250],
            "gcm-sentinel/condition": result.condition,
            "gcm-sentinel/timestamp": datetime.now(timezone.utc).isoformat(),
        }}})
    except Exception:
        logger.exception("Failed to annotate node %s", result.node_name)


async def emit_k8s_event(result: SentinelResult) -> None:
    try:
        now = datetime.now(timezone.utc)
        get_core_api().create_namespaced_event("default", client.CoreV1Event(
            metadata=client.V1ObjectMeta(generate_name="gcm-sentinel-", namespace="default"),
            involved_object=client.V1ObjectReference(kind="Node", name=result.node_name, api_version="v1"),
            reason="GCMSentinel",
            message=f"[{result.severity.value.upper()}] {result.summary} | Action: {result.recommended_action.value} | Confidence: {result.confidence:.0%}",
            type="Warning" if result.severity.value in ("critical", "warning") else "Normal",
            first_timestamp=now, last_timestamp=now,
            source=client.V1EventSource(component="gcm-sentinel"),
            reporting_component="gcm-sentinel",
        ))
    except Exception:
        logger.exception("Failed to create K8s Event for %s", result.node_name)


async def emit_webhook(result: SentinelResult, webhook_url: str) -> None:
    payload = {
        "text": (
            f"[{result.severity.value.upper()}] GPU Sentinel: {result.node_name} / {result.condition}\n"
            f"*Summary*: {result.summary}\n*Root cause*: {result.root_cause}\n"
            f"*Action*: {result.recommended_action.value} (confidence {result.confidence:.0%})"
        ),
        "sentinel_result": {
            "node_name": result.node_name, "condition": result.condition,
            "severity": result.severity.value, "summary": result.summary,
            "root_cause": result.root_cause,
            "recommended_action": result.recommended_action.value,
            "confidence": result.confidence, "timestamp": result.timestamp.isoformat(),
        },
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            (await http.post(webhook_url, json=payload)).raise_for_status()
    except Exception:
        logger.exception("Webhook delivery failed for %s", result.node_name)


async def notify(result: SentinelResult, webhook_url: str = "") -> None:
    await emit_k8s_event(result)
    if webhook_url:
        await emit_webhook(result, webhook_url)
