---
sidebar_position: 2
---

# Architecture

## Data flow

```
                    ┌─────────────────────────────────────┐
                    │        gcm-sentinel (Deployment)       │
                    │                                     │
                    │  NodeConditionWatcher                │
                    │  ├─ watches K8s nodes via watch API  │
NPD sets condition ─┤  ├─ cooldown / allowlist gates       │
  = True            │  └─ triggers run_investigation()     │
                    │          │                           │
                    │  DataSourceRegistry                  │
                    │  ├─ Prometheus (PromQL)               │
                    │  ├─ DCGMDirect (dcgm-exporter)       │
                    │  ├─ NodeDirect (node-exporter, IB)   │
                    │  ├─ KubernetesCore                    │
                    │  ├─ KubernetesWorkloads               │
                    │  ├─ GCMHealth                         │
                    │  ├─ Alertmanager                      │
                    │  └─ Remediation (execute mode only)   │
                    │      └─ rate limit enforced here      │
                    │          │                           │
                    │  LLM Backend (Anthropic or OpenAI)   │
                    │  ├─ tool-use loop (up to 25 rounds)  │
                    │  └─ returns JSON assessment           │
                    │          │                           │
                    │  Output                              │
                    │  ├─ K8s Event on node                │
                    │  ├─ Webhook (Slack/PagerDuty)        │
                    │  ├─ Node annotations (annotate mode) │
                    │  └─ Structured logs                  │
                    └─────────────────────────────────────┘
```

## Data sources

Each data source is a class that subclasses `DataSource` and contributes tools (for the LLM to call) and optional system prompt sections. The investigation engine doesn't know which data sources are registered — it just calls `registry.get_all_tools()` and `registry.execute(name, input)`.

See [Adding a New Data Source](./adding_new_datasource.md) for a step-by-step guide on integrating your own systems.

## LLM backends

The `backends/` package abstracts away the differences between LLM APIs:

| Backend | SDK | Tool-use protocol |
|---|---|---|
| `AnthropicBackend` | `anthropic` | `tool_use` blocks in content, `tool_result` in user messages |
| `OpenAIBackend` | `openai` | `tool_calls` on message, `role=tool` messages |

Both backends implement the same `LLMBackend` interface. The investigation engine calls `backend.chat()`, `backend.append_assistant_response()`, and `backend.append_tool_results()` without knowing which API is behind it.

## Condition name compatibility

GCM Sentinel watches for both OSS and internal condition name formats:

| OSS (Gcm prefix) | Internal (NPD prefix) | Health check |
|---|---|---|
| `GcmXidErrorsProblem` | `NPDXidErrorsProblem` | `check-syslogs xid` |
| `GcmSmiEccProblem` | `NPDSmiEccProblem` | `check-nvidia-smi ecc` |
| `GcmSmiDisconnectedProblem` | `NPDSmiDisconnectedProblem` | `check-nvidia-smi gpu_num` |
| `GcmProcZombieProblem` | `NPDProcZombieProblem` | `check-process zombie` |
| `GcmDcgmiNvlinkStatusProblem` | `NPDDcgmiNvlinkStatusProblem` | `check-dcgmi nvlink` |
| `GcmDcgmiDiagProblem` | `NPDDcgmiDiagProblem` | `check-dcgmi diag` |
| — | `NPDDcgmRunningProblem` | (internal only) |

Both prefixes are watched by default. Extra names that don't exist on your cluster are harmless.
