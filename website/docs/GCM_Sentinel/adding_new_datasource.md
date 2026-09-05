---
sidebar_position: 4
---

# Adding a New Data Source

The sentinel agent investigates GPU failures by querying **data sources** — Prometheus metrics, Kubernetes state, pod logs, etc. Each data source is a Python class that subclasses `DataSource` and exposes tools the LLM can call during investigation.

The built-in data sources cover the common stack (Prometheus, K8s, DCGM, NPD, Alertmanager). You can add your own to give the agent access to any system you have — IPMI sensors, cloud APIs, job schedulers, internal dashboards, etc.

Adding a data source is one Python file plus one line of registration. This guide walks through a complete example: adding IPMI/BMC sensor queries.

## 1. Create the data source file

Create a new file under `src/gcm_sentinel/datasources/`. The naming convention is `<source_name>.py`.

```python
# src/gcm_sentinel/datasources/ipmi.py
from __future__ import annotations

import json
import httpx
from gcm_sentinel.datasources import DataSource


class IPMIDataSource(DataSource):
    name = "ipmi"

    def is_available(self):
        # Return False to auto-skip if prerequisites aren't met.
        # The registry will log "Data source 'ipmi' not available, skipping".
        return bool(self.cfg.ipmi_url)  # Add ipmi_url to SentinelConfig first.

    def get_tools(self):
        # Return Anthropic-format tool definitions. These are automatically
        # converted for OpenAI if that backend is in use.
        return [{
            "name": "get_ipmi_sensors",
            "description": "Read IPMI sensor data (temperatures, fan speeds, PSU status) for a node via its BMC.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "Name of the Kubernetes node.",
                    },
                },
                "required": ["node_name"],
            },
        }]

    async def execute(self, tool_name, tool_input):
        # Called when the LLM invokes your tool.
        node_name = tool_input["node_name"]
        bmc_host = f"{node_name}-bmc"  # Your BMC naming convention.

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.cfg.ipmi_url}/sensors",
                params={"host": bmc_host},
            )
            resp.raise_for_status()
            data = resp.json()

        # Return a string — this becomes the tool result the LLM sees.
        text = json.dumps(data, indent=2)
        return text[:8000]  # Truncate to avoid filling the context window.

    def get_system_prompt_section(self):
        # Optional: add reference information to the system prompt.
        # The LLM sees this alongside the investigation guidelines and
        # metrics reference, so it knows when/how to use your tool.
        return """\
## IPMI sensor reference

The `get_ipmi_sensors` tool returns BMC sensor readings:
- Inlet/outlet temperatures (celsius)
- Fan speeds (RPM)
- PSU voltage and status
- CPU temperatures

Use this to check for cooling failures or power supply issues when
investigating thermal throttling or unexpected GPU shutdowns."""
```

## 2. Add the config field (if needed)

If your data source needs configuration (URLs, credentials, feature flags), add fields to `SentinelConfig` in `src/gcm_sentinel/config.py`:

```python
class SentinelConfig(BaseSettings):
    model_config = {"env_prefix": "GCM_SENTINEL_"}

    # ... existing fields ...

    ipmi_url: str = Field(
        default="",
        description="IPMI/BMC API URL. Leave empty to disable.",
    )
```

This automatically creates the env var `GCM_SENTINEL_IPMI_URL`.

## 3. Register the data source

Add one line to `build_datasources()` in `src/gcm_sentinel/datasources/__init__.py`:

```python
def build_datasources(cfg: SentinelConfig) -> DataSourceRegistry:
    from gcm_sentinel.datasources.alertmanager import AlertmanagerDataSource
    from gcm_sentinel.datasources.gcm_health import GCMHealthDataSource
    from gcm_sentinel.datasources.ipmi import IPMIDataSource  # NEW
    from gcm_sentinel.datasources.kubernetes_core import KubernetesCoreDataSource
    from gcm_sentinel.datasources.kubernetes_workloads import KubernetesWorkloadsDataSource
    from gcm_sentinel.datasources.prometheus import PrometheusDataSource
    from gcm_sentinel.datasources.remediation import RemediationDataSource

    registry = DataSourceRegistry(cfg)
    registry.register(PrometheusDataSource(cfg))
    registry.register(KubernetesCoreDataSource(cfg))
    registry.register(GCMHealthDataSource(cfg))
    registry.register(KubernetesWorkloadsDataSource(cfg))
    registry.register(AlertmanagerDataSource(cfg))
    registry.register(IPMIDataSource(cfg))  # NEW
    registry.register(RemediationDataSource(cfg))
    return registry
```

That's it. The investigation engine will automatically:
- Include your tool in the LLM's tool list
- Route tool calls to your `execute()` method
- Include your system prompt section in the investigation context

## 4. Add Helm values (if needed)

If your data source has configurable URLs or settings, expose them in `charts/gcm-sentinel/values.yaml` and wire them through `charts/gcm-sentinel/templates/deployment.yaml`:

```yaml
# values.yaml
ipmi:
  url: ""  # Set to enable IPMI sensor queries.
```

```yaml
# deployment.yaml (in the env section)
{{- if .Values.ipmi.url }}
- name: GCM_SENTINEL_IPMI_URL
  value: "{{ .Values.ipmi.url }}"
{{- end }}
```

## 5. Test

Add a test verifying your data source registers correctly and handles errors:

```python
# tests/test_engine.py
def test_ipmi_skipped_when_url_empty():
    from gcm_sentinel.datasources import build_datasources

    cfg = SentinelConfig(api_key="test")  # ipmi_url defaults to ""
    registry = build_datasources(cfg)
    assert "get_ipmi_sensors" not in {t["name"] for t in registry.get_all_tools()}

def test_ipmi_registered_when_url_set():
    from gcm_sentinel.datasources import build_datasources

    cfg = SentinelConfig(api_key="test", ipmi_url="http://bmc-api:8080")
    registry = build_datasources(cfg)
    assert "get_ipmi_sensors" in {t["name"] for t in registry.get_all_tools()}
```

## Data source API reference

Each data source implements the `DataSource` base class:

| Method | Required | Description |
|---|---|---|
| `name` | Yes | Class attribute. Short identifier (e.g. `"ipmi"`). |
| `get_tools()` | Yes | Return tool definitions (Anthropic format). |
| `execute(tool_name, tool_input)` | Yes | Handle tool calls. Return a string. |
| `is_available()` | No | Return `False` to skip registration. Default: `True`. |
| `get_system_prompt_section()` | No | Return extra system prompt text. Default: `""`. |

## Built-in data sources

| Data source | File | Tools | `is_available` condition |
|---|---|---|---|
| `prometheus` | `prometheus.py` | `query_prometheus` | Always |
| `dcgm_direct` | `dcgm_direct.py` | `query_dcgm_direct` | Always |
| `node_direct` | `node_direct.py` | `query_node_exporter_direct`, `query_infiniband_direct` | Always |
| `kubernetes_core` | `kubernetes_core.py` | `get_node_info`, `get_node_events`, `get_pod_logs` | Always |
| `kubernetes_workloads` | `kubernetes_workloads.py` | `get_workload_info`, `get_workload_logs` | Always |
| `gcm_health` | `gcm_health.py` | `get_gcm_health` | Always |
| `alertmanager` | `alertmanager.py` | `query_alertmanager` | `alertmanager_url` is set |
| `remediation` | `remediation.py` | `cordon_node`, `drain_node`, `taint_node` | `action_mode == "execute"` |

## Ideas for new data sources

| Name | Data source | What it adds |
|---|---|---|
| `IPMIDataSource` | BMC/IPMI API | Baseboard temps, fan speeds, PSU health |
| `SlurmDataSource` | `squeue`/`sinfo` CLI | Job info on Slurm-native clusters |
| `CloudDataSource` | AWS EC2 / GCP / Azure | Scheduled maintenance, instance health |
| `FabricManagerDataSource` | NVIDIA FM API | NVSwitch topology and health |
| `EFADataSource` | EFA metrics | AWS Elastic Fabric Adapter errors |

## Tips

- **Handle errors gracefully**: If your data source is unreachable, return an error string instead of raising. The LLM will adapt.
- **System prompt section**: Keep it concise. The LLM sees this on every investigation — long sections waste tokens.
- **`is_available()`**: Use this to auto-skip when prerequisites aren't met (URL not configured, library not installed). The registry logs "not available, skipping" — no error.
