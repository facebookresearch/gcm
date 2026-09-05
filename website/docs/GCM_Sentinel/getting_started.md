---
sidebar_position: 1
---

# Getting Started

:::caution Experimental
GCM Sentinel is experimental. APIs, configuration, and behavior may change between releases.
:::

GCM Sentinel is an AI-powered sentinel agent that investigates GPU hardware failures detected by [GCM Health Checks](../GCM_Health_Checks/getting_started.md). It uses an LLM (Claude or GPT) to query Prometheus metrics, Kubernetes state, pod logs, and workload status — then recommends remediation actions.

## Quick Start

### Prerequisites

- An LLM API key ([Anthropic](https://console.anthropic.com/) or [OpenAI](https://platform.openai.com/))
- For cluster deployment: a Kubernetes GPU cluster with GPU metrics exposed to Prometheus (e.g. via [DCGM-exporter](https://github.com/NVIDIA/dcgm-exporter)) and a node health system that sets K8s node conditions (e.g. [GCM Health Checks](../GCM_Health_Checks/kubernetes_deployment.md))

### Try It (No Cluster Needed)

Run 5 GPU failure scenarios against mock backends:

```shell
pip install gcm-sentinel
export ANTHROPIC_API_KEY=your-key-here
python -m gcm_sentinel.demo.run
```

Or with OpenAI:

```shell
pip install gcm-sentinel[openai]
export OPENAI_API_KEY=your-key-here
python -m gcm_sentinel.demo.run
```

### Deploy to Your Cluster

```shell
helm install gcm-sentinel ./charts/gcm-sentinel \
  --set llm.apiKey=your-key-here \
  --set prometheus.url=http://prometheus.monitoring:9090
```

Or from source:

```shell
git clone https://github.com/facebookresearch/gcm.git
cd gcm
helm install gcm-sentinel ./charts/gcm-sentinel \
  --set llm.apiKey=your-key-here
```

The agent starts in **recommend mode** (observe-only) by default — zero cluster mutations.

### One-Shot Investigation (CLI)

```shell
pip install gcm-sentinel
export GCM_SENTINEL_API_KEY=your-key-here
gcm-sentinel investigate gpu-node-07 --condition GcmSmiEccProblem
```

## How It Works

```
GCM Health Check detects GPU failure
  → NPD sets node condition (e.g. GcmXidErrorsProblem = True)
  → gcm-sentinel watcher detects the change
  → LLM investigates using tools:
      query_prometheus          — PromQL queries (whatever Prometheus scrapes)
      query_dcgm_direct         — GPU metrics directly from dcgm-exporter on the node
      query_node_exporter_direct— host metrics directly from node-exporter
      query_infiniband_direct   — InfiniBand port metrics from node-exporter
      get_node_info             — K8s node conditions, taints, labels, pods
      get_node_events           — recent K8s Events
      get_pod_logs              — dcgm-exporter and NPD diagnostic logs
      get_gcm_health            — NPD problem gauges and counters
      get_workload_info         — training job identity, sibling workers
      get_workload_logs         — NCCL/CUDA error logs from training pods
      query_alertmanager        — currently firing alerts
  → SentinelResult: severity + root_cause + recommended_action + confidence
  → Output: K8s Event + webhook (Slack/PagerDuty) + optional node annotation
```

## Configuration

All settings via environment variables (`GCM_SENTINEL_` prefix) or Helm values:

| Variable | Default | Description |
|---|---|---|
| `API_KEY` | (required) | LLM API key |
| `LLM_API` | `anthropic` | `anthropic` or `openai` |
| `MODEL` | `claude-sonnet-4-6-20250725` | Model name |
| `ACTION_MODE` | `recommend` | `recommend` / `annotate` / `execute` |
| `PROMETHEUS_URL` | kube-prometheus-stack default | Prometheus URL |
| `WEBHOOK_URL` | (empty) | Slack/PagerDuty webhook |
| `WATCH_CONDITIONS` | GCM defaults | Comma-separated conditions |
| `MAX_TOOL_OUTPUT` | `8000` | Max chars per tool result sent to LLM. 0 = unlimited. |

See the [Safety & Rollout Guide](./safety.md) for the full configuration reference.

## Works Without GCM

GCM Sentinel works with **any** system that sets Kubernetes node conditions on GPU failures. Configure your condition names:

```shell
export GCM_SENTINEL_WATCH_CONDITIONS="MyGPUCheck,CustomXidCondition"
```

It also works without automated detection — use the CLI to trigger investigation manually.

## Adding New Data Sources

You can give the agent access to any system — IPMI sensors, cloud APIs, job schedulers, internal dashboards — by writing a data source (one Python file + one line of registration). See [Adding a New Data Source](./adding_new_datasource.md).
