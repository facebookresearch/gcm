---
sidebar_position: 3
---

# Safety & Rollout Guide

:::danger Critical
GCM Sentinel can investigate GPU failures on your production cluster. When configured in `execute` mode, it can **cordon and drain nodes**, which evicts running training jobs. Read this page carefully before deploying.
:::

## Default: Observe-Only

Out of the box, gcm-sentinel is **completely safe**:

```shell
# This is observe-only — zero cluster mutations
helm install gcm-sentinel ./charts/gcm-sentinel \
  --set llm.apiKey=your-key-here
```

The default `actionMode=recommend` means:
- The agent **cannot** cordon, drain, or taint any node
- The remediation tools are **not even in the LLM's tool schema** — it cannot attempt to call them
- The RBAC ClusterRole is **read-only** — even if something went wrong, K8s won't allow mutations
- The agent only reads metrics, node info, events, and pod logs

## Five Layers of Defense

| Layer | What it does | How it works |
|---|---|---|
| **1. Action mode** | Controls whether the LLM even sees remediation tools | `recommend`/`annotate`: tools absent from schema — LLM cannot call them. `execute`: tools present. Enforced in Python before anything reaches the LLM. |
| **2. RBAC** | Kubernetes-level permission enforcement | `recommend`: no `patch`/`eviction` verbs. `annotate`: adds node `patch` only. `execute`: adds `pods/eviction`. Even if code has a bug, K8s rejects unauthorized calls. |
| **3. Rate limiter** | Prevents cascading drain | Max 3 remediation actions per hour. Enforced **before** the K8s API call — if the limit is hit, the tool returns "RATE LIMITED" to the LLM and no mutation happens. |
| **4. Cooldown** | Prevents runaway re-investigation | Same node+condition won't be re-investigated within 1 hour. Stops NPD flapping from burning API credits. |

## Controlling via Helm

Every safety parameter is a Helm value and a corresponding environment variable:

:::tip API Key Security
For production, store the API key in a Kubernetes Secret instead of passing it as plaintext:
```shell
kubectl create secret generic gcm-sentinel-llm --from-literal=api-key=your-key-here
helm install gcm-sentinel ./charts/gcm-sentinel --set llm.existingSecret=gcm-sentinel-llm
```
:::

```shell
# Observe-only (DEFAULT — no flag needed)
helm install gcm-sentinel ./charts/gcm-sentinel \
  --set llm.apiKey=your-key-here

# Annotate mode — writes K8s annotations, no cordon/drain
helm install gcm-sentinel ./charts/gcm-sentinel \
  --set llm.apiKey=your-key-here \
  --set sentinel.actionMode=annotate

# Execute mode — can cordon/drain, with safety rails
helm install gcm-sentinel ./charts/gcm-sentinel \
  --set llm.apiKey=your-key-here \
  --set sentinel.actionMode=execute \
  --set sentinel.maxActionsPerHour=1 \
  --set sentinel.nodeAllowlist="gpu-node-01"
```

### Safety Parameters Reference

| Helm Value | Env Var | Default | Description |
|---|---|---|---|
| `sentinel.actionMode` | `GCM_SENTINEL_ACTION_MODE` | `recommend` | `recommend` / `annotate` / `execute` |
| `sentinel.cooldownSeconds` | `GCM_SENTINEL_COOLDOWN_SECONDS` | `3600` | Seconds between investigations for same node+condition |
| `sentinel.nodeAllowlist` | `GCM_SENTINEL_NODE_ALLOWLIST` | `""` (all) | Comma-separated node patterns (fnmatch) |
| `sentinel.maxActionsPerHour` | `GCM_SENTINEL_MAX_ACTIONS_PER_HOUR` | `3` | Max remediations per hour (circuit-breaker) |

### Helm Validation

Invalid `actionMode` values are rejected at deploy time:

```
$ helm install gcm-sentinel ./charts/gcm-sentinel --set sentinel.actionMode=yolo
Error: ... Invalid sentinel.actionMode: "yolo". Must be one of: recommend, annotate, execute
```

## Recommended Rollout

### Week 1-2: Recommend Mode (Observe)

```shell
helm install gcm-sentinel ./charts/gcm-sentinel \
  --set llm.apiKey=your-key-here \
  --set sentinel.webhookUrl=https://hooks.slack.com/services/...
```

- Review investigation results in Slack/PagerDuty
- Compare the agent's assessments with your team's diagnosis
- Check K8s Events: `kubectl get events --field-selector reason=GCMSentinel`

### Week 3-4: Annotate Mode (Validate)

```shell
helm upgrade gcm-sentinel ./charts/gcm-sentinel \
  --set sentinel.actionMode=annotate
```

- Check node annotations: `kubectl get node <name> -o jsonpath='{.metadata.annotations}' | jq 'with_entries(select(.key | startswith("gcm-sentinel")))'`
- Verify the recommended actions match what you'd do manually
- Optionally build a controller that reads `gcm-sentinel/action` annotations

### Week 5+: Execute Mode (Targeted)

```shell
helm upgrade gcm-sentinel ./charts/gcm-sentinel \
  --set sentinel.actionMode=execute \
  --set sentinel.maxActionsPerHour=1 \
  --set sentinel.nodeAllowlist="gpu-node-01,gpu-node-02"
```

- Start with 1-2 test nodes via `nodeAllowlist`
- Set `maxActionsPerHour=1` (conservative)
- Monitor K8s Events: `kubectl get events --field-selector reason=GCMSentinel`
- Expand `nodeAllowlist` gradually as you gain confidence

### Full Auto (Mature)

```shell
helm upgrade gcm-sentinel ./charts/gcm-sentinel \
  --set sentinel.actionMode=execute \
  --set sentinel.nodeAllowlist="" \
  --set sentinel.maxActionsPerHour=5
```

## Kill Switch

To immediately disable all remediation without redeploying:

```shell
# Downgrade to observe-only
helm upgrade gcm-sentinel ./charts/gcm-sentinel \
  --set sentinel.actionMode=recommend

# Or via env var (restart required, replace RELEASE_NAME with your Helm release name)
kubectl set env deployment/RELEASE_NAME-gcm-sentinel GCM_SENTINEL_ACTION_MODE=recommend
```

## Verifying Safety at Runtime

The agent logs its action mode prominently at startup:

```
============================================================
GCM Sentinel Agent
Action mode: recommend — OBSERVE-ONLY (no cluster mutations)
Node allowlist: (all nodes)
Cooldown: 3600s, Prometheus: http://prometheus.monitoring:9090
============================================================
```

In execute mode, you'll see a warning:

```
============================================================
GCM Sentinel Agent
Action mode: execute — EXECUTE (can cordon/drain/taint nodes!)
WARNING: EXECUTE MODE ACTIVE — agent can modify cluster state.
  Max actions/hour: 1
Node allowlist: gpu-node-01, gpu-node-02
============================================================
```

Check the current mode by inspecting the pod logs:

```shell
kubectl logs deployment/RELEASE_NAME-gcm-sentinel | head -10
```
