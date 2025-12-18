# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_ibstat import check_ib_interfaces, check_ibstat
from gcm.health_checks.subprocess import PipedShellCommandOut, ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeIBStatImpl:
    ib_status: PipedShellCommandOut

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_ibstat(
        self,
        use_physical_state: bool,
        iblinks_only: bool,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> PipedShellCommandOut:
        return self.ib_status

    def get_ib_interfaces(
        self,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> ShellCommandOut:
        return FakeShellCommandOut(
            [], self.ib_status.returncode[0], self.ib_status.stdout
        )


@pytest.fixture
def ibstat_tester(request: pytest.FixtureRequest) -> FakeIBStatImpl:
    """Create FakeIBStatImpl object"""
    return FakeIBStatImpl(request.param)


pass_ibstat_physical_state = PipedShellCommandOut(
    [0, 0],
    """Physical state: LinkUp
       Physical state: LinkUp""",
)
error_ibstat_physical_state = PipedShellCommandOut(
    [1, 0],
    "Error",
)
empty_ibstat_physical_state = PipedShellCommandOut(
    [0, 0],
    "",
)
critical_ibstat_physical_state = PipedShellCommandOut(
    [0, 0],
    """Physical state: LinkDown
       Physical state: LinkUp""",
)


@pytest.mark.parametrize(
    "ibstat_tester, expected",
    [
        (
            pass_ibstat_physical_state,
            (
                ExitCode.OK,
                "ib stat reported ok status",
            ),
        ),
        (
            error_ibstat_physical_state,
            (
                ExitCode.WARN,
                "ibstat command FAILED to execute. error_code: 1 output: Error",
            ),
        ),
        (
            empty_ibstat_physical_state,
            (
                ExitCode.WARN,
                "ibstat command FAILED to execute. error_code: 0 output: ",
            ),
        ),
        (
            critical_ibstat_physical_state,
            (
                ExitCode.CRITICAL,
                "Link status is not LinkUp",
            ),
        ),
    ],
    indirect=["ibstat_tester"],
)
def test_ibstat_physical_state(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    ibstat_tester: FakeIBStatImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_ibstat,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing --physical-state",
        obj=ibstat_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


pass_ibstat_physical_state = PipedShellCommandOut(
    [0, 0],
    """State: Active
       State: Active""",
)
error_ibstat_physical_state = PipedShellCommandOut(
    [1, 0],
    "Error",
)
empty_ibstat_physical_state = PipedShellCommandOut(
    [0, 0],
    "",
)
critical_ibstat_physical_state = PipedShellCommandOut(
    [0, 0],
    """State: Down
       State: Down""",
)


@pytest.mark.parametrize(
    "ibstat_tester, expected",
    [
        (
            pass_ibstat_physical_state,
            (
                ExitCode.OK,
                "ib stat reported ok status",
            ),
        ),
        (
            error_ibstat_physical_state,
            (
                ExitCode.WARN,
                "ibstat command FAILED to execute. error_code: 1 output: Error",
            ),
        ),
        (
            empty_ibstat_physical_state,
            (
                ExitCode.WARN,
                "ibstat command FAILED to execute. error_code: 0 output: ",
            ),
        ),
        (
            critical_ibstat_physical_state,
            (
                ExitCode.CRITICAL,
                "Link state is not Active",
            ),
        ),
    ],
    indirect=["ibstat_tester"],
)
def test_ibstat_state(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    ibstat_tester: FakeIBStatImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_ibstat,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing --state",
        obj=ibstat_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


pass_ib_interfaces = PipedShellCommandOut(
    [0, 0, 0],
    """
[{"ifindex":7,"ifname":"ibp12s0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":2044,"qdisc":"mq","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":256,"link_type":"infiniband","address":"00:00:10:29:fe:80:00:00:00:00:00:00:0c:42:a1:03:00:0b:cc:d6","broadcast":"00:ff:ff:ff:ff:12:40:1b:ff:ff:00:00:00:00:00:00:ff:ff:ff:ff","vfinfo_list":[]},{"ifindex":8,"ifname":"ibp18s0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":2044,"qdisc":"mq","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":256,"link_type":"infiniband","address":"00:00:10:29:fe:80:00:00:00:00:00:00:0c:42:a1:03:00:0b:cd:42","broadcast":"00:ff:ff:ff:ff:12:40:1b:ff:ff:00:00:00:00:00:00:ff:ff:ff:ff","vfinfo_list":[]},{"ifindex":9,"ifname":"ibp75s0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":2044,"qdisc":"mq","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":256,"link_type":"infiniband","address":"00:00:10:29:fe:80:00:00:00:00:00:00:0c:42:a1:03:00:5d:f4:54","broadcast":"00:ff:ff:ff:ff:12:40:1b:ff:ff:00:00:00:00:00:00:ff:ff:ff:ff","vfinfo_list":[]},{"ifindex":10,"ifname":"ibp84s0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":2044,"qdisc":"mq","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":256,"link_type":"infiniband","address":"00:00:10:29:fe:80:00:00:00:00:00:00:0c:42:a1:03:00:5d:ee:14","broadcast":"00:ff:ff:ff:ff:12:40:1b:ff:ff:00:00:00:00:00:00:ff:ff:ff:ff","vfinfo_list":[]},{"ifindex":11,"ifname":"ibp141s0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":2044,"qdisc":"mq","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":256,"link_type":"infiniband","address":"00:00:10:29:fe:80:00:00:00:00:00:00:0c:42:a1:03:00:5d:f4:5c","broadcast":"00:ff:ff:ff:ff:12:40:1b:ff:ff:00:00:00:00:00:00:ff:ff:ff:ff","vfinfo_list":[]},{"ifindex":12,"ifname":"ibp148s0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":2044,"qdisc":"mq","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":256,"link_type":"infiniband","address":"00:00:10:29:fe:80:00:00:00:00:00:00:0c:42:a1:03:00:5d:f4:14","broadcast":"00:ff:ff:ff:ff:12:40:1b:ff:ff:00:00:00:00:00:00:ff:ff:ff:ff","vfinfo_list":[]},{"ifindex":13,"ifname":"ibp186s0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":2044,"qdisc":"mq","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":256,"link_type":"infiniband","address":"00:00:10:29:fe:80:00:00:00:00:00:00:0c:42:a1:03:00:5d:ee:a0","broadcast":"00:ff:ff:ff:ff:12:40:1b:ff:ff:00:00:00:00:00:00:ff:ff:ff:ff","vfinfo_list":[]},{"ifindex":14,"ifname":"ibp204s0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":2044,"qdisc":"mq","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":256,"link_type":"infiniband","address":"00:00:10:29:fe:80:00:00:00:00:00:00:0c:42:a1:03:00:74:7a:3e","broadcast":"00:ff:ff:ff:ff:12:40:1b:ff:ff:00:00:00:00:00:00:ff:ff:ff:ff","vfinfo_list":[]}]
""",
)
error_ib_interfaces = PipedShellCommandOut(
    [2, 0, 0],
    "Error Message",
)
fail_ib_interfaces = PipedShellCommandOut(
    [0, 0, 0],
    """
[{"ifindex":7,"ifname":"ibp12s0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":2044,"qdisc":"mq","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":256,"link_type":"infiniband","address":"00:00:10:29:fe:80:00:00:00:00:00:00:0c:42:a1:03:00:0b:cc:d6","broadcast":"00:ff:ff:ff:ff:12:40:1b:ff:ff:00:00:00:00:00:00:ff:ff:ff:ff","vfinfo_list":[]},{"ifindex":8,"ifname":"ibp18s0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":2044,"qdisc":"mq","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":256,"link_type":"infiniband","address":"00:00:10:29:fe:80:00:00:00:00:00:00:0c:42:a1:03:00:0b:cd:42","broadcast":"00:ff:ff:ff:ff:12:40:1b:ff:ff:00:00:00:00:00:00:ff:ff:ff:ff","vfinfo_list":[]},{"ifindex":9,"ifname":"ibp75s0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":2044,"qdisc":"mq","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":256,"link_type":"infiniband","address":"00:00:10:29:fe:80:00:00:00:00:00:00:0c:42:a1:03:00:5d:f4:54","broadcast":"00:ff:ff:ff:ff:12:40:1b:ff:ff:00:00:00:00:00:00:ff:ff:ff:ff","vfinfo_list":[]},{"ifindex":10,"ifname":"ibp84s0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":2044,"qdisc":"mq","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":256,"link_type":"infiniband","address":"00:00:10:29:fe:80:00:00:00:00:00:00:0c:42:a1:03:00:5d:ee:14","broadcast":"00:ff:ff:ff:ff:12:40:1b:ff:ff:00:00:00:00:00:00:ff:ff:ff:ff","vfinfo_list":[]},{"ifindex":11,"ifname":"ibp141s0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":2044,"qdisc":"mq","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":256,"link_type":"infiniband","address":"00:00:10:29:fe:80:00:00:00:00:00:00:0c:42:a1:03:00:5d:f4:5c","broadcast":"00:ff:ff:ff:ff:12:40:1b:ff:ff:00:00:00:00:00:00:ff:ff:ff:ff","vfinfo_list":[]},{"ifindex":12,"ifname":"ibp148s0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":2044,"qdisc":"mq","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":256,"link_type":"infiniband","address":"00:00:10:29:fe:80:00:00:00:00:00:00:0c:42:a1:03:00:5d:f4:14","broadcast":"00:ff:ff:ff:ff:12:40:1b:ff:ff:00:00:00:00:00:00:ff:ff:ff:ff","vfinfo_list":[]},{"ifindex":13,"ifname":"ibp186s0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":2044,"qdisc":"mq","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":256,"link_type":"infiniband","address":"00:00:10:29:fe:80:00:00:00:00:00:00:0c:42:a1:03:00:5d:ee:a0","broadcast":"00:ff:ff:ff:ff:12:40:1b:ff:ff:00:00:00:00:00:00:ff:ff:ff:ff","vfinfo_list":[]}]
    """,
)
wrong_output_ib_interfaces = PipedShellCommandOut(
    [0, 0, 0],
    "InvalidOut",
)


@pytest.mark.parametrize(
    "ibstat_tester, expected",
    [
        (
            pass_ib_interfaces,
            (
                ExitCode.OK,
                "Number of ib interfaces present is the same as expected, 8",
            ),
        ),
        (
            error_ib_interfaces,
            (
                ExitCode.WARN,
                "ib interfaces command FAILED to execute. error_code: 2 output: Error Message",
            ),
        ),
        (
            fail_ib_interfaces,
            (
                ExitCode.CRITICAL,
                "Number of interfaces present, 7, is different than expected, 8",
            ),
        ),
        (
            wrong_output_ib_interfaces,
            (
                ExitCode.CRITICAL,
                "Invalid output returned: InvalidOut",
            ),
        ),
    ],
    indirect=["ibstat_tester"],
)
def test_ib_interfaces_state(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    ibstat_tester: FakeIBStatImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_ib_interfaces,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing --interface-num=8",
        obj=ibstat_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
