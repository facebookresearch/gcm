# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Test the check_ssh_certs health-check."""

import logging
from dataclasses import dataclass
from pathlib import Path
from subprocess import TimeoutExpired

import pytest
from click.testing import CliRunner
from gcm.health_checks.checks.check_ssh_certs import (
    check_ssh_certs,
    CMD_GEN,
    CMD_IPA,
    CMD_KEY,
)
from gcm.health_checks.subprocess import ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.schemas.health_check.health_check_name import HealthCheckName

from gcm.tests.fakes import FakeShellCommandOut

#############
# CONSTANTS #
#############

CHK_NAM = HealthCheckName.CHECK_SSH_CERTS.value
KEY_ONE = "SHA256:Forty-three-character-base64-encoded-string"
KEY_TWO = "SHA256:A-non-matching-key-that-should-never-happen"
TIMEOUT_SECS = 300

###########
# Classes #
###########


@dataclass(frozen=True)
class FakeSshCertsCheckImpl:
    """Supply pregenerated output instead of calling ssh-keyscan and ipa host-show."""

    params: list[ShellCommandOut]
    timeout_secs: int = TIMEOUT_SECS
    cluster: str = "test cluster"
    type: str = "prolog"
    log_level: str = "INFO"
    log_folder: str = "/tmp"

    def get_ipa_certs(self, _host: str, timeout_secs: int) -> ShellCommandOut:
        """
        Return first param instead of invoking ipa host-show.

        Raises:
            TimeoutExpired if self.params[0].args[0] == "Timeout"

        """
        if self.params[0].args[0] == "Timeout":
            raise TimeoutExpired(
                cmd=self.params[0].args[1],
                timeout=timeout_secs,
                output=self.params[0].stdout,
            )
        return self.params[0]

    def get_ssh_certs(self, _host: str, timeout_secs: int) -> ShellCommandOut:
        """
        Return second param instead of invoking ssh-keyscan and ssh-keygen.

        Raises:
            TimeoutExpired if self.params[1].args[0] == "Timeout

        """
        if self.params[1].args[0] == "Timeout":
            raise TimeoutExpired(
                cmd=self.params[1].args[1],
                timeout=timeout_secs,
                output=self.params[1].stdout,
            )
        return self.params[1]


#############
# Functions #
#############


def bad_ipa_out(hostname: str) -> str:
    """Provide ipa output for a host that is not in production."""
    return (
        f"fqdn: {hostname}.com\n"
        "  has_password: TRUE\n"
        "  has_keytab: FALSE\n"
        f"  managedby: fqdn={hostname}.com,"
        "cn=computers,cn=accounts,dc=air,dc=loc,dc=dom,dc=com"
    )


def good_ipa_out(hostname: str, key: str = KEY_ONE) -> str:
    """Provide ipa output for a host that is in production."""
    return (
        f"fqdn: {hostname}.com\n"
        f"  krbcanonicalname: host/{hostname}.com@DOMAIN.COM\n"
        f"  krbprincipalname: host/{hostname}.com@DOMAIN.COM\n"
        f"  sshpubkeyfp: {key}1 (ssh-rsa)\n"
        f"  sshpubkeyfp: {key}2 (ssh-ed25519)\n"
        f"  sshpubkeyfp: {key}3 (ecdsa-sha2-nistp256)\n"
        "  has_password: FALSE\n"
        "  has_keytab: TRUE\n"
        f"  managedby: fqdn={hostname}.com,"
        "cn=computers,cn=accounts,dc=air,dc=loc,dc=host,dc=com"
    )


def good_ssh_out(hostname: str, key: str = KEY_ONE) -> str:
    """Provide ssh-keygen output for a host that is up."""
    return (
        f"256 {key}1 {hostname} (ECDSA)\n"
        f"3072 {key}2 {hostname} (RSA)\n"
        f"256 {key}3 {hostname} (ED25519)"
    )


@pytest.fixture
def ssh_certs_tester(
    request: pytest.FixtureRequest,
) -> FakeSshCertsCheckImpl:
    """Create FakeSshCertsCheckImpl object."""
    return FakeSshCertsCheckImpl(request.param)


@pytest.mark.parametrize(
    ("ssh_certs_tester", "expected"),
    [
        (
            [
                FakeShellCommandOut(
                    args=[f"{CMD_IPA} ipa-down"],
                    returncode=1,
                    stdout="",
                ),
                FakeShellCommandOut(),
            ],
            (
                "ipa-down",
                ExitCode.UNKNOWN,
                f"exit code {ExitCode.UNKNOWN.value}: {CHK_NAM} - "
                f"Error 1 running `{CMD_IPA} ipa-down`: ",
            ),
        ),
        (
            [
                FakeShellCommandOut(args=["Timeout", f"{CMD_IPA} ipa-timeout"]),
                FakeShellCommandOut(),
            ],
            (
                "ipa-timeout",
                ExitCode.UNKNOWN,
                f"exit code {ExitCode.UNKNOWN.value}: {CHK_NAM} - "
                f"Timeout in {TIMEOUT_SECS} secs running `{CMD_IPA} ipa-timeout`: ",
            ),
        ),
        (
            [
                FakeShellCommandOut(
                    args=[f"{CMD_IPA} not-in-ipa"],
                    returncode=2,
                    stdout="ipa: ERROR: not-in-ipa: host not found",
                ),
                FakeShellCommandOut(),
            ],
            (
                "not-in-ipa",
                ExitCode.CRITICAL,
                f"exit code {ExitCode.CRITICAL.value}: {CHK_NAM} - "
                f"Error 2 running `{CMD_IPA} not-in-ipa`: "
                "ipa: ERROR: not-in-ipa: host not found",
            ),
        ),
        (
            [
                FakeShellCommandOut(
                    args=[f"{CMD_IPA} not-in-production"],
                    returncode=0,
                    stdout=bad_ipa_out("not-in-production"),
                ),
                FakeShellCommandOut(
                    args=[f"{CMD_KEY} not-in-production"],
                    returncode=1,
                ),
            ],
            (
                "not-in-production",
                ExitCode.CRITICAL,
                f"exit code {ExitCode.CRITICAL.value}: {CHK_NAM} - "
                "No certs for not-in-production found in IPA. "
                "Is not-in-production in production?",
            ),
        ),
        (
            [
                FakeShellCommandOut(
                    args=[f"{CMD_IPA} host-down"],
                    returncode=0,
                    stdout=good_ipa_out("host-down"),
                ),
                FakeShellCommandOut(args=["Timeout", f"{CMD_KEY} host-down"]),
            ],
            (
                "host-down",
                ExitCode.CRITICAL,
                f"exit code {ExitCode.CRITICAL.value}: {CHK_NAM} - "
                f"Timeout in {TIMEOUT_SECS} secs running `{CMD_KEY} host-down`: ",
            ),
        ),
        (
            [
                FakeShellCommandOut(
                    args=[f"{CMD_IPA} host-reprovisioned"],
                    returncode=0,
                    stdout=good_ipa_out("host-reprovisioned", KEY_ONE),
                ),
                FakeShellCommandOut(
                    args=[CMD_GEN],
                    returncode=0,
                    stdout=good_ssh_out("host-reprovisioned", KEY_TWO),
                ),
            ],
            (
                "host-reprovisioned",
                ExitCode.CRITICAL,
                f"exit code {ExitCode.CRITICAL.value}: {CHK_NAM} - "
                "3/3 certs registered in IPA but not found in host-reprovisioned ssh. "
                "Was host-reprovisioned reprovisioned but not re-registered?",
            ),
        ),
        (
            [
                FakeShellCommandOut(
                    args=[f"{CMD_IPA} host-up"],
                    returncode=0,
                    stdout=good_ipa_out("host-up"),
                ),
                FakeShellCommandOut(
                    args=[CMD_GEN],
                    returncode=0,
                    stdout=good_ssh_out("host-up"),
                ),
            ],
            (
                "host-up",
                ExitCode.OK,
                f"exit code {ExitCode.OK.value}: {CHK_NAM} - "
                f"3 certs registered in IPA and found in host-up ssh.",
            ),
        ),
    ],
    indirect=["ssh_certs_tester"],
)
def test_check_ssh_certs(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    ssh_certs_tester: FakeSshCertsCheckImpl,
    expected: tuple[str, ExitCode, str],
) -> None:
    """Invoke the check_sensors method."""
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_ssh_certs,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing --host={expected[0]}",
        obj=ssh_certs_tester,
    )

    assert result.exit_code == expected[1].value
    assert expected[2] in caplog.text
