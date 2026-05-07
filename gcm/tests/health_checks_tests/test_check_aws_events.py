# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import logging
from pathlib import Path
from typing import NoReturn, Tuple

import pytest
import requests
import requests_mock as rm
from click.testing import CliRunner
from gcm.health_checks.checks.check_aws_events import (
    check_aws_events,
    fetch_imds_token,
    fetch_scheduled_events,
)
from gcm.health_checks.types import ExitCode

IMDS = "http://imds.test"  # any non-link-local URL works with requests_mock
TOKEN_URL = f"{IMDS}/latest/api/token"
EVENTS_URL = f"{IMDS}/latest/meta-data/events/maintenance/scheduled"

# A canonical AWS scheduled-events response (one pending instance retirement).
# Source: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-instances-status-check_sched.html
SAMPLE_EVENTS = [
    {
        "Code": "instance-retirement",
        "Description": "The instance is scheduled for retirement",
        "EventId": "instance-event-0123abcd",
        "NotBefore": "2026-05-12T03:00:00Z",
        "NotAfter": "2026-05-12T04:00:00Z",
        "State": "active",
    }
]


def test_fetch_imds_token_success() -> None:
    with rm.Mocker() as m:
        m.put(TOKEN_URL, text="FAKE-TOKEN")
        token = fetch_imds_token(IMDS, ttl_seconds=60, timeout_secs=3)
    assert token == "FAKE-TOKEN"


def test_fetch_imds_token_off_ec2_returns_none() -> None:
    with rm.Mocker() as m:
        m.put(TOKEN_URL, exc=requests.ConnectionError)
        token = fetch_imds_token(IMDS, ttl_seconds=60, timeout_secs=3)
    assert token is None


def test_fetch_imds_token_500_returns_none() -> None:
    with rm.Mocker() as m:
        m.put(TOKEN_URL, status_code=500, text="boom")
        token = fetch_imds_token(IMDS, ttl_seconds=60, timeout_secs=3)
    assert token is None


def test_fetch_imds_token_empty_body_returns_none() -> None:
    """A 200 with an empty body should be treated as 'no token' so we
    short-circuit to OK rather than sending an empty Authorization header."""
    with rm.Mocker() as m:
        m.put(TOKEN_URL, status_code=200, text="")
        token = fetch_imds_token(IMDS, ttl_seconds=60, timeout_secs=3)
    assert token is None


def test_fetch_imds_token_strips_trailing_slash_in_base_url() -> None:
    with rm.Mocker() as m:
        m.put(TOKEN_URL, text="FAKE-TOKEN")
        token = fetch_imds_token(f"{IMDS}/", ttl_seconds=60, timeout_secs=3)
    assert token == "FAKE-TOKEN"


def test_fetch_imds_token_bypasses_http_proxy() -> None:
    """IMDS is link-local and must never be reached through a proxy. Verify
    the request was sent with proxies={} so requests doesn't honor
    HTTP_PROXY env vars."""
    with rm.Mocker() as m:
        m.put(TOKEN_URL, text="FAKE-TOKEN")
        fetch_imds_token(IMDS, ttl_seconds=60, timeout_secs=3)
        last = m.last_request
    assert last is not None
    # requests-mock exposes proxies via the prepared request when explicitly
    # set; verify the call did not fall back to env-based proxy resolution.
    assert last.proxies == {"http": "", "https": ""}


def test_fetch_events_no_pending_returns_ok() -> None:
    """200 + empty array is the documented "no events" response."""
    with rm.Mocker() as m:
        m.get(EVENTS_URL, status_code=200, text="[]")
        code, msg = fetch_scheduled_events(IMDS, "tok", timeout_secs=3)
    assert code == ExitCode.OK
    assert "No pending AWS maintenance events" in msg


def test_fetch_events_404_returns_ok() -> None:
    """404 on the endpoint is also a valid "no events" signal."""
    with rm.Mocker() as m:
        m.get(EVENTS_URL, status_code=404)
        code, msg = fetch_scheduled_events(IMDS, "tok", timeout_secs=3)
    assert code == ExitCode.OK
    assert "No pending AWS maintenance events" in msg


def test_fetch_events_one_pending_returns_warn_with_summary() -> None:
    with rm.Mocker() as m:
        m.get(EVENTS_URL, status_code=200, text=json.dumps(SAMPLE_EVENTS))
        code, msg = fetch_scheduled_events(IMDS, "tok", timeout_secs=3)
    assert code == ExitCode.WARN
    assert "AWS maintenance pending (1 event(s))" in msg
    assert "instance-retirement" in msg
    assert "NotBefore=2026-05-12T03:00:00Z" in msg
    assert "EventId=instance-event-0123abcd" in msg
    assert "State=active" in msg


def test_fetch_events_multiple_pending_reports_count() -> None:
    events = SAMPLE_EVENTS + [
        {
            "Code": "system-reboot",
            "EventId": "instance-event-deadbeef",
            "NotBefore": "2026-06-01T00:00:00Z",
            "State": "active",
        }
    ]
    with rm.Mocker() as m:
        m.get(EVENTS_URL, status_code=200, text=json.dumps(events))
        code, msg = fetch_scheduled_events(IMDS, "tok", timeout_secs=3)
    assert code == ExitCode.WARN
    assert "AWS maintenance pending (2 event(s))" in msg


def test_fetch_events_unreachable_returns_ok() -> None:
    """Don't false-alarm the fleet on a transient IMDS network error."""
    with rm.Mocker() as m:
        m.get(EVENTS_URL, exc=requests.ConnectionError)
        code, msg = fetch_scheduled_events(IMDS, "tok", timeout_secs=3)
    assert code == ExitCode.OK
    assert "skipping check" in msg


def test_fetch_events_unexpected_5xx_returns_ok() -> None:
    with rm.Mocker() as m:
        m.get(EVENTS_URL, status_code=503, text="boom")
        code, msg = fetch_scheduled_events(IMDS, "tok", timeout_secs=3)
    assert code == ExitCode.OK
    assert "Unexpected HTTP 503" in msg


def test_fetch_events_garbage_body_returns_ok() -> None:
    """Malformed JSON shouldn't false-alarm — drop and skip."""
    with rm.Mocker() as m:
        m.get(EVENTS_URL, status_code=200, text="not-json{")
        code, msg = fetch_scheduled_events(IMDS, "tok", timeout_secs=3)
    assert code == ExitCode.OK
    assert "Failed to decode IMDS event payload" in msg


def test_fetch_events_non_list_payload_returns_ok() -> None:
    """Valid JSON of the wrong shape (dict instead of list) must not
    crash on `events[0]`; would otherwise exit 1 == fleet-wide drain."""
    with rm.Mocker() as m:
        m.get(EVENTS_URL, status_code=200, text=json.dumps({"error": "Forbidden"}))
        code, msg = fetch_scheduled_events(IMDS, "tok", timeout_secs=3)
    assert code == ExitCode.OK
    assert "not a list" in msg


def test_fetch_events_non_dict_item_returns_ok() -> None:
    """List of scalars (a misbehaving proxy or future API shape) must not
    crash on head.get(...); would otherwise exit 1 == fleet-wide drain."""
    with rm.Mocker() as m:
        m.get(EVENTS_URL, status_code=200, text=json.dumps([42, "scheduled"]))
        code, msg = fetch_scheduled_events(IMDS, "tok", timeout_secs=3)
    assert code == ExitCode.OK
    assert "not a dict" in msg


def test_fetch_events_strips_trailing_slash_in_base_url() -> None:
    with rm.Mocker() as m:
        m.get(EVENTS_URL, status_code=404)
        code, _ = fetch_scheduled_events(f"{IMDS}/", "tok", timeout_secs=3)
    assert code == ExitCode.OK


def test_fetch_events_bypasses_http_proxy() -> None:
    with rm.Mocker() as m:
        m.get(EVENTS_URL, status_code=404)
        fetch_scheduled_events(IMDS, "tok", timeout_secs=3)
        last = m.last_request
    assert last is not None
    assert last.proxies == {"http": "", "https": ""}


def test_check_aws_events_off_ec2_exits_ok(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """End-to-end: on an off-EC2 host (no token), the Click command exits 0
    with a skipped-check message — never false-alarms."""
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    def fake_fetch_token(_url: str, _ttl: int, _timeout: int) -> None:
        return None

    def fake_fetch_events(_url: str, _token: str, _timeout: int) -> NoReturn:
        raise AssertionError("should not be called when token is None")

    result = runner.invoke(
        check_aws_events,
        f"test-cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=(fake_fetch_token, fake_fetch_events),
    )
    assert result.exit_code == ExitCode.OK.value
    assert "IMDS token unreachable; skipping check" in caplog.text


def test_check_aws_events_pending_event_exits_warn(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """End-to-end: with a real event payload, the Click command exits WARN
    and the summary makes it into the log (which becomes the NPD condition
    message)."""
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    def fake_fetch_token(_url: str, _ttl: int, _timeout: int) -> str:
        return "tok"

    def fake_fetch_events(
        _url: str, _token: str, _timeout: int
    ) -> Tuple[ExitCode, str]:
        return ExitCode.WARN, (
            "AWS maintenance pending (1 event(s)): instance-retirement "
            "NotBefore=2026-05-12T03:00:00Z State=active "
            "EventId=instance-event-0123abcd"
        )

    result = runner.invoke(
        check_aws_events,
        f"test-cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=(fake_fetch_token, fake_fetch_events),
    )
    assert result.exit_code == ExitCode.WARN.value
    assert "AWS maintenance pending" in caplog.text
    assert "instance-retirement" in caplog.text
