# gcm-sentinel

AI-powered GPU cluster sentinel agent. Watches for GPU hardware failures on Kubernetes clusters and uses an LLM (Claude or GPT) to investigate — querying Prometheus metrics, Kubernetes state, pod logs, and training job status — then recommends remediation actions.

## Quick Start

### Try it (no cluster needed)

```bash
pip install gcm-sentinel
export ANTHROPIC_API_KEY=your-key-here
python -m gcm_sentinel.demo.run
```

This runs 5 GPU failure scenarios (ECC errors, GPU off bus, NVLink, thermal, transient XID) against mock backends. Only an API key is needed.

To use OpenAI instead:

```bash
pip install gcm-sentinel[openai]
export OPENAI_API_KEY=your-key-here
python -m gcm_sentinel.demo.run
```

### Deploy to a cluster

```bash
helm install gcm-sentinel ./charts/gcm-sentinel \
  --set llm.apiKey=your-key-here \
  --set prometheus.url=http://prometheus.monitoring:9090
```

The agent starts in **observe-only mode** by default. It investigates GPU failures and sends results to K8s Events and webhooks, but makes **zero cluster mutations**.

### One-shot investigation (CLI)

```bash
pip install gcm-sentinel
export GCM_SENTINEL_API_KEY=your-key-here
gcm-sentinel investigate gpu-node-07 --condition GcmSmiEccProblem
```

## How It Works

```
GCM health check detects GPU failure
  → NPD sets node condition = True (e.g. GcmXidErrorsProblem)
  → gcm-sentinel watches for condition changes via K8s watch API
  → LLM investigates using tools (up to 25 rounds):
      query_prometheus          — PromQL queries (kube-state-metrics, node-exporter, etc.)
      query_dcgm_direct         — GPU metrics directly from dcgm-exporter on the node
      query_node_exporter_direct— host metrics directly from node-exporter
      query_infiniband_direct   — InfiniBand port metrics from node-exporter
      get_node_info             — conditions, taints, labels, pods
      get_node_events           — recent K8s Events
      get_pod_logs              — dcgm-exporter, NPD diagnostic output
      get_gcm_health            — NPD problem gauges and counters
      get_workload_info         — training job identity, sibling pods
      get_workload_logs         — NCCL/CUDA error logs from training pods
      query_alertmanager        — currently firing alerts
  → Assessment: severity + root_cause + recommended_action + confidence
  → Output: K8s Event + webhook (Slack/PagerDuty) + optional node annotation
```

## Safety

The agent defaults to **observe-only**. It must be explicitly configured to modify cluster state.

| Mode | Behavior | Helm flag |
|---|---|---|
| `recommend` (default) | Investigate + report. No mutations. | `--set sentinel.actionMode=recommend` |
| `annotate` | Above + write `gcm-sentinel/*` annotations on node. | `--set sentinel.actionMode=annotate` |
| `execute` | Above + can cordon/drain/taint. Gated by confidence + rate limit. | `--set sentinel.actionMode=execute` |

Additional safety:
- **Cooldown**: 1 hour between investigations for the same node+condition
- **Node allowlist**: scope to specific nodes (`--set sentinel.nodeAllowlist="gpu-node-01"`)
- **Rate limit**: max 3 remediation actions per hour (circuit-breaker)
- **RBAC**: ClusterRole only gets `patch`/`eviction` verbs in annotate/execute modes
- **Tool removal**: remediation tools are absent from the LLM's schema unless `execute` mode

See [Safety & Rollout Guide](https://facebookresearch.github.io/gcm/docs/GCM_Sentinel/safety) for the full rollout playbook.

## Configuration

All via environment variables (`GCM_SENTINEL_` prefix) or Helm values:

| Variable | Default | Description |
|---|---|---|
| `API_KEY` | (required) | LLM API key |
| `LLM_API` | `anthropic` | `anthropic` or `openai` |
| `MODEL` | `claude-sonnet-4-6-20250725` | Model name |
| `PROMETHEUS_URL` | `http://kube-prometheus-stack-prometheus.monitoring:9090` | Prometheus URL |
| `ALERTMANAGER_URL` | (Alertmanager URL) | Leave empty to disable |
| `ACTION_MODE` | `recommend` | `recommend` / `annotate` / `execute` |
| `COOLDOWN_SECONDS` | `3600` | Cooldown per node+condition |
| `NODE_ALLOWLIST` | (all) | Comma-separated node patterns |
| `MAX_ACTIONS_PER_HOUR` | `3` | Circuit-breaker |
| `WATCH_CONDITIONS` | GCM defaults | Comma-separated conditions to watch |
| `MAX_TOOL_OUTPUT` | `8000` | Max chars per tool result sent to LLM. 0 = unlimited. |
| `WEBHOOK_URL` | (empty) | Slack/PagerDuty webhook |

All variables use the `GCM_SENTINEL_` prefix (e.g. `GCM_SENTINEL_API_KEY`).

## Watch Conditions

Defaults watch for [GCM health check](https://facebookresearch.github.io/gcm/docs/GCM_Health_Checks/kubernetes_deployment) conditions (`Gcm*` prefix). If you use different NPD condition names:

```bash
export GCM_SENTINEL_WATCH_CONDITIONS="MyGPUCheck,CustomXidCondition"
```

## Adding New Data Sources

The agent queries data sources via a plugin system. Each data source is a Python class that exposes tools the LLM can call — Prometheus queries, K8s API calls, HTTP requests to any service.

To give the agent access to a new system (IPMI sensors, cloud APIs, job schedulers, etc.), create a data source file and register it:

```python
# src/gcm_sentinel/datasources/my_source.py
from gcm_sentinel.datasources import DataSource

class MyDataSource(DataSource):
    name = "my_source"

    def get_tools(self):
        return [{"name": "query_my_source", "description": "...", "input_schema": {...}}]

    async def execute(self, tool_name, tool_input):
        return await my_query(tool_input["node_name"])
```

Then add `registry.register(MyDataSource(cfg))` in `datasources/__init__.py`.

See the full [Adding a New Data Source](https://facebookresearch.github.io/gcm/docs/GCM_Sentinel/adding_new_datasource) guide for a complete walkthrough with a real example.

## License

See [LICENSE](../LICENSE).
