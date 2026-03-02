# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""ROCm/AMD GPU device telemetry via amd-smi or rocm-smi (subprocess + JSON)."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Any, Dict, Iterable, List, Optional

from gcm.monitoring.device_telemetry_client import (
    ApplicationClockInfo,
    DeviceTelemetryException,
    GPUMemory,
    GPUUtilization,
    ProcessInfo,
    RemappedRowInfo,
)

logger = logging.getLogger(__name__)

# Default vbios string when not available from ROCm (satisfies protocol).
_AMD_VBIOS_PLACEHOLDER = "AMD-ROCm"


def _run_cmd(args: List[str], timeout_secs: int = 30) -> str:
    try:
        out = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_secs,
        )
    except FileNotFoundError as e:
        raise DeviceTelemetryException(
            f"ROCm tool not found: {args[0]}. Is amd-smi or rocm-smi installed?"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise DeviceTelemetryException(f"Command timed out: {args}") from e
    if out.returncode != 0 and out.stderr:
        raise DeviceTelemetryException(
            f"Command failed (exit {out.returncode}): {out.stderr.strip() or out.stdout.strip()}"
        )
    return out.stdout or ""


def _extract_json_from_stdout(raw: str) -> str:
    """Extract JSON from amd-smi stdout; it may print warnings or info before the JSON."""
    raw = (raw or "").strip()
    if not raw:
        return raw
    # Find first { or [ (amd-smi typically returns an object).
    start_obj = raw.find("{")
    start_arr = raw.find("[")
    if start_obj == -1 and start_arr == -1:
        return raw
    if start_obj == -1:
        start, open_ch, close_ch = start_arr, "[", "]"
    elif start_arr == -1:
        start, open_ch, close_ch = start_obj, "{", "}"
    else:
        start = min(start_obj, start_arr)
        open_ch = raw[start]
        close_ch = "]" if open_ch == "[" else "}"
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == open_ch:
            depth += 1
        elif raw[i] == close_ch:
            depth -= 1
            if depth == 0:
                return raw[start : i + 1]
    return raw[start:]


def _find_rocm_tool() -> Optional[str]:
    """Return 'amd-smi' or 'rocm-smi' if available, else None."""
    for name in ("amd-smi", "rocm-smi"):
        if shutil.which(name):
            return name
    return None


class ROCmGPUDevice:
    """Per-device telemetry for one AMD GPU; implements GPUDevice protocol."""

    def __init__(
        self,
        index: int,
        metrics: Dict[str, Any],
        memory: Dict[str, Any],
        processes: List[Dict[str, Any]],
    ) -> None:
        self._index = index
        self._metrics = metrics or {}
        self._memory = memory or {}
        self._processes = processes or []

    def get_compute_processes(self) -> List[ProcessInfo]:
        out: List[ProcessInfo] = []
        for p in self._processes:
            pid = p.get("pid") or p.get("process_id")
            mem = p.get("used_gpu_memory") or p.get("memory") or 0
            if pid is not None:
                out.append(ProcessInfo(pid=int(pid), usedGpuMemory=int(mem)))
        return out

    def get_retired_pages_double_bit_ecc_error(self) -> Iterable[int]:
        return []

    def get_retired_pages_multiple_single_bit_ecc_errors(self) -> Iterable[int]:
        return []

    def get_retired_pages_pending_status(self) -> int:
        return 0

    def get_remapped_rows(self) -> RemappedRowInfo:
        return RemappedRowInfo(
            correctable=0, uncorrectable=0, pending=0, failure=0
        )

    def get_ecc_uncorrected_volatile_total(self) -> int:
        return 0

    def get_ecc_corrected_volatile_total(self) -> int:
        return 0

    def get_enforced_power_limit(self) -> Optional[int]:
        val = self._metrics.get("average_socket_power_cap") or self._metrics.get(
            "power_cap"
        )
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                pass
        return None

    def get_power_usage(self) -> Optional[int]:
        val = self._metrics.get("average_socket_power") or self._metrics.get(
            "current_socket_power"
        )
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                pass
        return None

    def get_temperature(self) -> int:
        # Prefer hotspot, then edge (Celsius).
        val = (
            self._metrics.get("temperature_hotspot")
            or self._metrics.get("temperature_edge")
            or self._metrics.get("temperature")
        )
        if val is not None:
            try:
                return int(val)
            except (TypeError, ValueError):
                pass
        return 0

    def get_memory_info(self) -> GPUMemory:
        total = self._memory.get("total") or self._memory.get("total_memory") or 0
        free = self._memory.get("free") or self._memory.get("free_memory") or 0
        used = self._memory.get("used") or self._memory.get("used_memory")
        if used is None and total is not None and free is not None:
            used = total - free
        elif used is None:
            used = 0
        # amd-smi/rocm-smi often report in MB; convert to bytes for schema.
        if isinstance(total, (int, float)) and total < 1e7:
            total = int(total) * 1024 * 1024
        if isinstance(free, (int, float)) and free < 1e7:
            free = int(free) * 1024 * 1024
        if isinstance(used, (int, float)) and used < 1e7:
            used = int(used) * 1024 * 1024
        return GPUMemory(total=int(total), free=int(free), used=int(used))

    def get_utilization_rates(self) -> GPUUtilization:
        gpu = self._metrics.get("average_gfx_activity") or self._metrics.get(
            "gpu_activity"
        ) or 0
        mem = self._metrics.get("average_umc_activity") or self._metrics.get(
            "memory_activity"
        ) or 0
        try:
            gpu_pct = int(float(gpu) * 100) if float(gpu) <= 1.0 else int(gpu)
        except (TypeError, ValueError):
            gpu_pct = 0
        try:
            mem_pct = int(float(mem) * 100) if float(mem) <= 1.0 else int(mem)
        except (TypeError, ValueError):
            mem_pct = 0
        return GPUUtilization(gpu=gpu_pct, memory=mem_pct)

    def get_clock_freq(self) -> ApplicationClockInfo:
        gfx = self._metrics.get("current_gfxclk") or self._metrics.get(
            "average_gfxclk"
        ) or 0
        mem = self._metrics.get("current_uclk") or self._metrics.get(
            "average_uclk"
        ) or self._metrics.get("current_memclk") or 0
        try:
            gfx_int = int(gfx)
        except (TypeError, ValueError):
            gfx_int = 0
        try:
            mem_int = int(mem)
        except (TypeError, ValueError):
            mem_int = 0
        return ApplicationClockInfo(
            graphics_freq=gfx_int, memory_freq=mem_int
        )

    def get_vbios_version(self) -> str:
        return self._memory.get("vbios_version") or self._metrics.get(
            "vbios_version"
        ) or _AMD_VBIOS_PLACEHOLDER


class ROCmDeviceTelemetryClient:
    """DeviceTelemetryClient implementation using amd-smi or rocm-smi."""

    def __init__(self, tool_path: Optional[str] = None, timeout_secs: int = 30) -> None:
        self._tool: Optional[str] = tool_path or _find_rocm_tool()
        self._timeout = timeout_secs
        self._device_count: Optional[int] = None
        self._cache: Dict[int, ROCmGPUDevice] = {}

    def _ensure_init(self) -> None:
        if self._tool is None:
            raise DeviceTelemetryException(
                "No ROCm tool found. Install amd-smi or rocm-smi and ensure it is on PATH."
            )
        if self._device_count is not None:
            return
        try:
            if self._tool == "amd-smi":
                self._device_count = self._amd_smi_get_count()
            else:
                self._device_count = self._rocm_smi_get_count()
        except Exception as e:
            if isinstance(e, DeviceTelemetryException):
                raise
            raise DeviceTelemetryException(str(e)) from e

    def _amd_smi_get_count(self) -> int:
        out = _run_cmd([self._tool, "list", "--json"], self._timeout)
        json_str = _extract_json_from_stdout(out)
        if not json_str:
            raise DeviceTelemetryException(
                "amd-smi list --json produced no JSON output. Check amd-smi and GPU visibility."
            )
        data = json.loads(json_str)
        # Format: {"system": {"host_driver_version": "...", "gpus": [...]}} or {"gpus": [...]}
        # depending on version; some amd-smi versions return a top-level array of GPU objects.
        if isinstance(data, list):
            gpus = data
        else:
            gpus = data.get("gpus") or data.get("system", {}).get("gpus") or []
        if isinstance(gpus, dict):
            gpus = list(gpus.values()) if gpus else []
        return len(gpus)

    def _rocm_smi_get_count(self) -> int:
        # rocm-smi -i (show id) or -a; count GPUs from output or --json if supported.
        out = _run_cmd([self._tool, "-i"], self._timeout)
        count = 0
        for line in out.splitlines():
            if "GPU[" in line or "card" in line.lower() or "device" in line.lower():
                count += 1
        if count == 0:
            # Try rocm-smi --showproductname (one line per GPU).
            out2 = _run_cmd([self._tool, "--showproductname"], self._timeout)
            count = max(1, out2.strip().count("\n") + 1) if out2.strip() else 1
        return max(1, count)

    def get_device_count(self) -> int:
        self._ensure_init()
        assert self._device_count is not None
        return self._device_count

    def _get_device_data(self, index: int) -> ROCmGPUDevice:
        if index in self._cache:
            return self._cache[index]
        self._ensure_init()
        if index < 0 or index >= (self._device_count or 0):
            raise DeviceTelemetryException(f"Invalid GPU index: {index}")
        try:
            if self._tool == "amd-smi":
                dev = self._amd_smi_get_device(index)
            else:
                dev = self._rocm_smi_get_device(index)
        except Exception as e:
            if isinstance(e, DeviceTelemetryException):
                raise
            raise DeviceTelemetryException(str(e)) from e
        self._cache[index] = dev
        return dev

    def _amd_smi_get_device(self, index: int) -> ROCmGPUDevice:
        metrics: Dict[str, Any] = {}
        memory: Dict[str, Any] = {}
        processes: List[Dict[str, Any]] = []
        try:
            out = _run_cmd(
                [self._tool, "metric", "--gpu", str(index), "--json"],
                self._timeout,
            )
            data = json.loads(_extract_json_from_stdout(out))
            # Nested by gpu_id or in a list.
            if isinstance(data, dict):
                metrics = data.get(str(index)) or data.get("gpu_metrics") or data
            elif isinstance(data, list) and len(data) > index:
                metrics = data[index] if isinstance(data[index], dict) else {}
        except (json.JSONDecodeError, DeviceTelemetryException):
            pass
        try:
            out = _run_cmd(
                [self._tool, "static", "-v", "--gpu", str(index), "--json"],
                self._timeout,
            )
            data = json.loads(_extract_json_from_stdout(out))
            vram = data.get("vram") or data.get("VRAM") or {}
            if isinstance(vram, dict):
                memory = vram
            elif isinstance(data, dict):
                memory = data
        except (json.JSONDecodeError, DeviceTelemetryException):
            # Derive from metric if available (e.g. mem_used / total).
            pass
        try:
            out = _run_cmd(
                [self._tool, "process", "--gpu", str(index), "--json"],
                self._timeout,
            )
            data = json.loads(_extract_json_from_stdout(out))
            if isinstance(data, list):
                processes = data
            elif isinstance(data, dict):
                processes = data.get("processes") or data.get("process_list") or []
        except (json.JSONDecodeError, DeviceTelemetryException):
            pass
        return ROCmGPUDevice(index, metrics, memory, processes)

    def _rocm_smi_get_device(self, index: int) -> ROCmGPUDevice:
        metrics: Dict[str, Any] = {}
        memory: Dict[str, Any] = {}
        processes: List[Dict[str, Any]] = []
        # rocm-smi --showmeminfo vram --showtemp --showuse -d N (or all).
        try:
            out = _run_cmd(
                [self._tool, "--showmeminfo", "vram", "-d", str(index)],
                self._timeout,
            )
            for line in out.splitlines():
                if "VRAM Total Memory (B)" in line or "Total" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        try:
                            memory["total"] = int(parts[-1].strip().split()[0])
                        except (ValueError, IndexError):
                            pass
                if "VRAM Total Used Memory (B)" in line or "Used" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        try:
                            memory["used"] = int(parts[-1].strip().split()[0])
                        except (ValueError, IndexError):
                            pass
            if "total" in memory and "used" in memory:
                memory["free"] = memory["total"] - memory["used"]
        except DeviceTelemetryException:
            pass
        try:
            out = _run_cmd(
                [self._tool, "--showtemp", "-d", str(index)],
                self._timeout,
            )
            for line in out.splitlines():
                if "GPU temperature" in line or "Temperature" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        try:
                            metrics["temperature"] = int(
                                parts[-1].strip().replace("C", "").split()[0]
                            )
                            break
                        except (ValueError, IndexError):
                            pass
        except DeviceTelemetryException:
            pass
        try:
            out = _run_cmd(
                [self._tool, "--showuse", "-d", str(index)],
                self._timeout,
            )
            for line in out.splitlines():
                if "GPU use" in line or "Gpu use" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        try:
                            metrics["average_gfx_activity"] = (
                                int(parts[-1].strip().replace("%", "").split()[0]) / 100.0
                            )
                            break
                        except (ValueError, IndexError):
                            pass
        except DeviceTelemetryException:
            pass
        return ROCmGPUDevice(index, metrics, memory, processes)

    def get_device_by_index(self, index: int) -> ROCmGPUDevice:
        return self._get_device_data(index)
