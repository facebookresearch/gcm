# Test Plan: Accelerator HAL Migration

This document outlines the test plan to verify that the migration to the Accelerator HAL (Hardware Abstraction Layer) preserves existing functionality for NVML-based monitoring and health checks.

## Objective

Ensure that all existing NVML paths (`nvml_monitor` and `check_nvidia_smi`) continue to function identically after being refactored to use the `AcceleratorManager` and `NVMLBackend` interface.

## Coverage Areas

1.  **Metric Collection (`nvml_monitor`)**: Verifying GPU metrics (utilization, memory, power, temperature, clocks, ECC) are collected correctly.
2.  **Health Checks (`check_nvidia_smi`)**: Verifying GPU presence, running processes, and error detection.
3.  **Error Handling**: Ensuring that backend unavailability or device errors are handled gracefully and logged appropriately.

## Test Cases

### 1. Unit Tests

Run existing unit tests to verify no regressions in logic.

```bash
pytest gcm/tests/test_accelerator_hal.py
pytest gcm/tests/health_checks_tests/test_check_nvidia_smi.py
pytest gcm/tests/test_nvml_monitor.py
```

### 2. Manual Verification (Stubbed)

Since we cannot run on actual GPU hardware in this environment, we rely on the stubbed NVML library used in tests.

#### A. NVML Monitor

**Refactored Logic:**
`nvml_monitor` now instantiates `AcceleratorManager`, probes backends, and uses `AcceleratorTelemetryAdapter` to interact with device handles provided by `NVMLBackend`.

**Verification Step:**
Verify that `nvml_monitor.py` correctly fetches device count and metrics via the adapter. The adapter ensures that underlying `pynvml` calls are routed through the `AcceleratorManager`'s backend instance.

#### B. Health Checks

**Refactored Logic:**
`check_nvidia_smi` now instantiates `AcceleratorManager` and uses `AcceleratorTelemetryAdapter` to perform checks.

**Verification Step:**
Verify that `check_nvidia_smi.py` correctly detects GPU count and running processes via the adapter.

## Refactoring Status

-   **`gcm/accelerator`**: Core HAL interfaces and NVML backend implementation are complete.
-   **`nvml_monitor.py`**: Refactored to use `AcceleratorManager` via `AcceleratorTelemetryAdapter`.
-   **`check_nvidia_smi.py`**: Refactored to use `AcceleratorManager` via `AcceleratorTelemetryAdapter`.
-   **Legacy Shim**: Added `gcm/monitoring/accelerator_adapter.py` to bridge `DeviceTelemetryClient` calls to the HAL backend, ensuring 100% backward compatibility for methods not yet fully exposed in `MetricSet` (e.g., specific ECC error counts).

## Rollout Strategy

1.  **Phase 1 (Current PR)**: Introduce HAL, migrate all NVML usage to `AcceleratorManager` via adapter shim.
2.  **Phase 2 (Future)**: Update `nvml_monitor` logic to use `AcceleratorManager.read_metrics()` directly, removing dependency on `DeviceTelemetryClient` interface once `MetricSet` is expanded to cover all needs.

This incremental approach ensures that the new architecture is active immediately while minimizing risk to existing business logic.
