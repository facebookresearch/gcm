---
sidebar_position: 10
description: Hardware-agnostic accelerator abstraction
---

# Accelerator HAL (Python)

This package provides a hardware-agnostic accelerator abstraction for a
Python-first observability codebase.

## Layout

```text
gcm.accelerator/
  backend.py                   # core interfaces and identity models
  metrics.py                   # normalized metrics and capability model
  errors.py                    # typed errors for backend operations
  manager.py                   # backend orchestration and routing
  probe.py                     # dynamic shared library probe helpers
  registry.py                  # default backend registration
  backends/
    nvml.py
```

## Design notes

- Backends are discovered and probed at runtime; missing drivers degrade
  gracefully.
- Metric output uses a single normalized `MetricSet` type.
- Optional vendor fields remain `None` unless supported by backend capability.
- This design can be implemented directly in Python or backed by Rust/C++
  worker processes behind the same backend protocol.

## Lifecycle

1. Build an `AcceleratorManager` from `default_backend_factories()`.
2. Call `probe_all()` to initialize and retain healthy backends.
3. Call `refresh_devices()` to enumerate backend devices and cache handles.
4. Call `read_all_metrics()` with a `MetricRequest` during each collection loop.
5. Call `close()` on shutdown.

## Backend authoring guide

- Implement `AcceleratorBackend` methods in `backends/<vendor>.py`.
- `probe()` should only verify runtime readiness and return a clear reason on
  failure.
- `enumerate_devices()` should return stable, backend-scoped `DeviceHandle.id`
  values.
- `read_metrics()` should map into normalized `MetricSet` fields and avoid
  failing the full read when a single metric is unavailable.
- Keep unsupported fields as `None` and gate behavior through `CapabilitySet`.

## Scope in this PR

- Includes a functional NVML backend only.
- Keeps the HAL contract/manager generic so additional backends can be added in
  follow-up PRs.

## Migration note

- HAL behavior is Python-first to simplify integration and testability.
- If needed later, vendor-specific FFI logic can move into Rust/C++ sidecar
  workers without changing the Python HAL interface.
