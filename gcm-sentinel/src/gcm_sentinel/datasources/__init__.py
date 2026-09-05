# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Data source plugin system.

Each data source exposes tools the LLM can call during investigation.
To add a new data source, subclass DataSource and register it in build_datasources().
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from gcm_sentinel.config import SentinelConfig

logger = logging.getLogger(__name__)


class DataSource(ABC):
    """Base class for data sources."""

    name: str  # Short identifier, set as class attribute.

    def __init__(self, cfg: SentinelConfig) -> None:
        self.cfg = cfg

    def is_available(self) -> bool:
        return True

    @abstractmethod
    def get_tools(self) -> list[dict]: ...

    @abstractmethod
    async def execute(self, tool_name: str, tool_input: dict) -> str: ...

    def get_system_prompt_section(self) -> str:
        return ""


class DataSourceRegistry:
    def __init__(self, cfg: SentinelConfig) -> None:
        self.cfg = cfg
        self._sources: list[DataSource] = []
        self._tool_to_source: dict[str, DataSource] = {}
        self._all_tools: list[dict] = []

    def register(self, ds: DataSource) -> None:
        if not ds.is_available():
            logger.info("Data source '%s' not available, skipping", ds.name)
            return
        tools = ds.get_tools()
        for tool in tools:
            self._tool_to_source[tool["name"]] = ds
        self._all_tools.extend(tools)
        self._sources.append(ds)
        logger.info("Registered data source '%s' (%d tools)", ds.name, len(tools))

    def get_all_tools(self) -> list[dict]:
        return self._all_tools

    def get_system_prompt_additions(self) -> str:
        return "\n\n".join(s for ds in self._sources if (s := ds.get_system_prompt_section()))

    async def execute(self, tool_name: str, tool_input: dict) -> str:
        ds = self._tool_to_source.get(tool_name)
        if ds is None:
            return f"Unknown tool: {tool_name}"
        return await ds.execute(tool_name, tool_input)

    @property
    def datasource_names(self) -> list[str]:
        return [ds.name for ds in self._sources]


def build_datasources(cfg: SentinelConfig) -> DataSourceRegistry:
    from gcm_sentinel.datasources.alertmanager import AlertmanagerDataSource
    from gcm_sentinel.datasources.dcgm_direct import DCGMDirectDataSource
    from gcm_sentinel.datasources.gcm_health import GCMHealthDataSource
    from gcm_sentinel.datasources.kubernetes_core import KubernetesCoreDataSource
    from gcm_sentinel.datasources.node_direct import NodeDirectDataSource
    from gcm_sentinel.datasources.kubernetes_workloads import KubernetesWorkloadsDataSource
    from gcm_sentinel.datasources.prometheus import PrometheusDataSource
    from gcm_sentinel.datasources.remediation import RemediationDataSource

    registry = DataSourceRegistry(cfg)
    registry.register(PrometheusDataSource(cfg))
    registry.register(DCGMDirectDataSource(cfg))
    registry.register(NodeDirectDataSource(cfg))
    registry.register(KubernetesCoreDataSource(cfg))
    registry.register(GCMHealthDataSource(cfg))
    registry.register(KubernetesWorkloadsDataSource(cfg))
    registry.register(AlertmanagerDataSource(cfg))
    registry.register(RemediationDataSource(cfg))
    return registry
