# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Tests for CommunicationCheckLog and MORI metric parsing (AMD path only)."""

from gcm.health_checks.checks.check_mori import parse_mori_metrics_from_stdout
from gcm.schemas.health_check.communication_check_log import CommunicationCheckLog


def test_communication_check_log_optional_metrics() -> None:
    """CommunicationCheckLog accepts None for all optional metric fields."""
    r = CommunicationCheckLog(
        node="node1",
        gpu_node_id=None,
        cluster="c",
        derived_cluster="dc",
        health_check="mori-tests",
        type="nagios",
        result=0,
        _msg="ok",
        job_id=0,
        start_time=0.0,
        end_time=1.0,
        bandwidth_gbps=None,
        latency_us=None,
        dispatch_bw_gbps=None,
        combine_bw_gbps=None,
        extra_metrics=None,
    )
    assert r.result == 0
    assert r.bandwidth_gbps is None


def test_communication_check_log_with_metrics() -> None:
    """CommunicationCheckLog stores optional bandwidth/latency."""
    r = CommunicationCheckLog(
        node="node1",
        gpu_node_id=None,
        cluster="c",
        derived_cluster="dc",
        health_check="rccl-tests",
        type="prolog",
        result=0,
        _msg="ok",
        job_id=1,
        start_time=0.0,
        end_time=2.0,
        bandwidth_gbps=52.5,
        latency_us=None,
        dispatch_bw_gbps=None,
        combine_bw_gbps=None,
        extra_metrics={"dispatch_latency_us": 76.0},
    )
    assert r.bandwidth_gbps == 52.5
    assert r.extra_metrics == {"dispatch_latency_us": 76.0}


def test_parse_mori_metrics_from_stdout_full() -> None:
    """parse_mori_metrics_from_stdout extracts dispatch/combine bandwidth and total latency."""
    stdout = """
Best Dispatch  (fp8): 171.23 GB/s, latency=76 us
Best Combine   (bf16, quant=float): 219.45 GB/s, latency=122 us
Total Dispatch+Combine latency: 198 us
"""
    m = parse_mori_metrics_from_stdout(stdout)
    assert m.get("dispatch_bw_gbps") == 171.23
    assert m.get("combine_bw_gbps") == 219.45
    assert m.get("latency_us") == 198.0
    assert m.get("bandwidth_gbps") == 171.23  # prefer dispatch
    assert m.get("extra_metrics") == {
        "dispatch_latency_us": 76.0,
        "combine_latency_us": 122.0,
    }


def test_parse_mori_metrics_from_stdout_empty() -> None:
    """parse_mori_metrics_from_stdout returns empty dict for None or empty string."""
    assert parse_mori_metrics_from_stdout(None) == {}
    assert parse_mori_metrics_from_stdout("") == {}


def test_parse_mori_metrics_from_stdout_partial() -> None:
    """parse_mori_metrics_from_stdout handles only Combine line."""
    stdout = "Best Combine (float): 100.5 GB/s, latency=50 us"
    m = parse_mori_metrics_from_stdout(stdout)
    assert m.get("combine_bw_gbps") == 100.5
    assert m.get("bandwidth_gbps") == 100.5
    assert m.get("extra_metrics") == {"combine_latency_us": 50.0}
    assert "dispatch_bw_gbps" not in m
    assert "latency_us" not in m
