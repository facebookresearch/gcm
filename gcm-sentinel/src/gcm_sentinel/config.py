# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

DEFAULT_WATCH_CONDITIONS: list[str] = [
    # OSS GCM conditions (https://github.com/facebookresearch/gcm)
    "GcmXidErrorsProblem",
    "GcmSmiEccProblem",
    "GcmSmiDisconnectedProblem",
    "GcmProcZombieProblem",
    "GcmDcgmiNvlinkStatusProblem",
    "GcmDcgmiDiagProblem",
    # Internal variants (some deployments use NPD prefix)
    "NPDXidErrorsProblem",
    "NPDSmiEccProblem",
    "NPDSmiDisconnectedProblem",
    "NPDProcZombieProblem",
    "NPDDcgmiNvlinkStatusProblem",
    "NPDDcgmiDiagProblem",
    "NPDDcgmRunningProblem",
]

ACTION_MODES = ("recommend", "annotate", "execute")


def _parse_csv(v: object) -> list[str]:
    if isinstance(v, str):
        return [c.strip() for c in v.split(",") if c.strip()]
    return v  # type: ignore[return-value]


class SentinelConfig(BaseSettings):
    model_config = {"env_prefix": "GCM_SENTINEL_"}

    llm_api: str = Field(default="anthropic", description="'anthropic' or 'openai'")
    api_key: str = Field(default="", description="API key for the LLM provider")
    model: str = Field(default="claude-sonnet-4-6-20250725", description="Model name/ID")

    prometheus_url: str = Field(
        default="http://kube-prometheus-stack-prometheus.monitoring:9090",
    )
    alertmanager_url: str = Field(
        default="http://kube-prometheus-stack-alertmanager.monitoring:9093",
        description="Leave empty to disable",
    )

    action_mode: str = Field(default="recommend")
    cooldown_seconds: int = Field(default=3600)
    node_allowlist: list[str] = Field(default_factory=list)
    max_actions_per_hour: int = Field(default=3)

    watch_conditions: list[str] = Field(
        default_factory=lambda: list(DEFAULT_WATCH_CONDITIONS),
    )
    max_tool_rounds: int = Field(default=25)
    max_tool_output: int = Field(default=8000, description="Max chars per tool result sent to LLM. 0 = unlimited.")
    system_prompt_path: str = Field(default="/etc/gcm-sentinel/system-prompt.txt")
    log_level: str = Field(default="INFO")
    webhook_url: str = Field(default="")

    _parse_watch_conditions = field_validator("watch_conditions", mode="before")(_parse_csv)
    _parse_node_allowlist = field_validator("node_allowlist", mode="before")(_parse_csv)

    @field_validator("action_mode")
    @classmethod
    def _validate_action_mode(cls, v: str) -> str:
        if v not in ACTION_MODES:
            raise ValueError(f"action_mode must be one of {ACTION_MODES}, got '{v}'")
        return v

    @property
    def can_execute(self) -> bool:
        return self.action_mode == "execute"

    @property
    def can_annotate(self) -> bool:
        return self.action_mode in ("annotate", "execute")
