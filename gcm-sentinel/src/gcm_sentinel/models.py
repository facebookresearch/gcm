# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

import enum
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Severity(str, enum.Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    OK = "ok"


class Action(str, enum.Enum):
    CORDON = "cordon"
    DRAIN = "drain"
    TAINT = "taint"
    REBOOT = "reboot"
    NONE = "none"


class NodeConditionEvent(BaseModel):
    node_name: str
    condition_type: str
    status: str
    reason: str = ""
    message: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ToolCall(BaseModel):
    tool_name: str
    tool_input: dict
    result: str


class SentinelResult(BaseModel):
    node_name: str
    condition: str
    severity: Severity
    summary: str
    root_cause: str
    recommended_action: Action
    confidence: float = Field(ge=0.0, le=1.0)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    investigation_log: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
