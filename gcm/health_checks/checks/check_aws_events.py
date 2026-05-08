# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
from typing import Callable, Collection, Optional, Tuple

import click
import requests
from gcm.health_checks.check_utils.runtime import HealthCheckRuntime
from gcm.health_checks.click import (
    common_arguments,
    telemetry_argument,
    timeout_argument,
)
from gcm.health_checks.types import CHECK_TYPE, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked

# Conservative bias: any IMDS error (off-EC2, network blip, IMDS misconfigured)
# returns ExitCode.OK so we never false-alarm the entire fleet on a transient
# IMDS outage — a real fleet-wide IMDS outage is its own incident, and
# falsely flipping every node would trigger fleet-wide drains via NLC.
#
# AWS endpoint reference:
#   https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-instances-status-check_sched.html#viewing_scheduled_events

DEFAULT_IMDS_BASE_URL = "http://169.254.169.254"
DEFAULT_IMDS_TIMEOUT_SECS = 3
DEFAULT_TOKEN_TTL_SECS = 60

# IMDS is link-local (169.254.169.254) and must NEVER be reached through an
# HTTP proxy. If a node ever inherits HTTP_PROXY / HTTPS_PROXY env vars, the
# default `requests` behavior of honoring them would route every node's IMDS
# query at the proxy server's metadata — and a single retirement event on the
# proxy host would fan out into a fleet-wide drain. Always pass an explicit
# empty proxies dict to bypass env-based proxy resolution for these calls.
_NO_PROXY: dict[str, str] = {"http": "", "https": ""}

FnFetchToken = Callable[[str, int, int], Optional[str]]
FnFetchEvents = Callable[[str, str, int], Tuple[ExitCode, str]]
ImdsFetchers = Tuple[FnFetchToken, FnFetchEvents]


def fetch_imds_token(
    base_url: str, ttl_seconds: int, timeout_secs: int
) -> Optional[str]:
    """Mint an IMDSv2 session token. Returns None on any transport or HTTP
    error (or empty body) so the caller can short-circuit to a healthy
    result."""
    try:
        resp = requests.put(
            f"{base_url.rstrip('/')}/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": str(ttl_seconds)},
            timeout=timeout_secs,
            proxies=_NO_PROXY,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None
    return resp.text or None


def fetch_scheduled_events(
    base_url: str, token: str, timeout_secs: int
) -> Tuple[ExitCode, str]:
    """GET the IMDS scheduled-events endpoint and translate the response into
    an exit code. Returns OK for the no-events / unreachable / malformed
    cases (don't false-alarm the fleet) and WARN with a one-line summary
    for the pending-event case."""
    url = f"{base_url.rstrip('/')}/latest/meta-data/events/maintenance/scheduled"
    try:
        resp = requests.get(
            url,
            headers={"X-aws-ec2-metadata-token": token},
            timeout=timeout_secs,
            proxies=_NO_PROXY,
        )
    except requests.RequestException:
        return ExitCode.OK, "IMDS events endpoint unreachable; skipping check"

    if resp.status_code == 404:
        return ExitCode.OK, "No pending AWS maintenance events"
    if resp.status_code != 200:
        return ExitCode.OK, (
            f"Unexpected HTTP {resp.status_code} from IMDS; skipping check"
        )

    body = resp.text.strip()
    if not body or body == "[]":
        return ExitCode.OK, "No pending AWS maintenance events"
    try:
        events = json.loads(body)
    except json.JSONDecodeError:
        return ExitCode.OK, "Failed to decode IMDS event payload; skipping check"
    # Validate payload shape — IMDS is documented to return a JSON array of
    # event objects, but a misbehaving proxy / mitm / future API change could
    # return something else. Treat any unexpected shape as healthy rather
    # than crashing on `events[0]` (which would exit 1 == ExitCode.WARN ==
    # fleet-wide drain trigger).
    if not isinstance(events, list):
        return ExitCode.OK, "Unexpected IMDS payload (not a list); skipping check"
    if not events:
        return ExitCode.OK, "No pending AWS maintenance events"
    head = events[0]
    if not isinstance(head, dict):
        return ExitCode.OK, "Unexpected IMDS event item (not a dict); skipping check"

    summary = (
        f"{head.get('Code', 'unknown')} "
        f"NotBefore={head.get('NotBefore', 'unknown')} "
        f"State={head.get('State', 'unknown')} "
        f"EventId={head.get('EventId', 'unknown')}"
    )
    return ExitCode.WARN, f"AWS maintenance pending ({len(events)} event(s)): {summary}"


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--imds-base-url",
    type=str,
    default=DEFAULT_IMDS_BASE_URL,
    help="IMDS base URL. Override only for testing.",
)
@click.option(
    "--imds-timeout",
    type=int,
    default=DEFAULT_IMDS_TIMEOUT_SECS,
    help="Per-call HTTP timeout in seconds for IMDS requests.",
)
@click.pass_obj
@typechecked
def check_aws_events(
    obj: Optional[ImdsFetchers],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    imds_base_url: str,
    imds_timeout: int,
) -> None:
    """Check for pending AWS scheduled maintenance / instance retirement
    events on this EC2 instance via IMDSv2. Exits non-zero with a
    one-line summary when any event is pending; exits 0 (healthy) on
    no-events, IMDS unreachable, or any other transport error to avoid
    false-alarming the fleet."""
    fetch_token, fetch_events = (
        (fetch_imds_token, fetch_scheduled_events) if obj is None else obj
    )

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_AWS_EVENTS,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_check_aws_events(),
    ) as rt:
        token = fetch_token(imds_base_url, DEFAULT_TOKEN_TTL_SECS, imds_timeout)
        if token is None:
            rt.finish(ExitCode.OK, "IMDS token unreachable; skipping check")

        exit_code, msg = fetch_events(imds_base_url, token, imds_timeout)
        rt.finish(exit_code, msg)
