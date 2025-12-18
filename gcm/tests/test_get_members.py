# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from typing import Tuple

import pytest
from click.testing import CliRunner

from gcm.monitoring.get_members import CliObject, get_members, HEADER


@dataclass
class FakeGetMembersCliObject:
    def __init__(self, get_members_raw_return: str):
        self.get_members_raw_return = get_members_raw_return

    def get_members_raw(self, groups: Tuple[str, ...]) -> str:
        return self.get_members_raw_return


@pytest.mark.parametrize(
    "cmd_output, expected",
    [
        (": : :", f"{HEADER}\n"),
        ("g1: : :", f"{HEADER}\n"),
        ("g1: : :u1,u2", f"{HEADER}g1,u1\ng1,u2\n"),
        ("g1: : :\ng2: : :u1\n", f"{HEADER}g2,u1\n"),
        ("g1:a:b:u1,u2\ng2:c:d:u1\n", f"{HEADER}g1,u1\ng1,u2\ng2,u1\n"),
    ],
)
def test_valid_get_members(cmd_output: str, expected: str) -> None:
    fake_obj: CliObject = FakeGetMembersCliObject(cmd_output)
    runner = CliRunner(mix_stderr=False)

    result = runner.invoke(
        get_members,
        ["fake_group1", "fake_group2"],
        obj=fake_obj,
    )
    assert result.stdout == expected


@dataclass
class FakeGetMembersExceptCliObject:
    def get_members_raw(self, groups: Tuple[str, ...]) -> str:
        raise Exception


def test_invalid_get_members() -> None:
    fake_obj: CliObject = FakeGetMembersExceptCliObject()
    runner = CliRunner(mix_stderr=False)

    result = runner.invoke(
        get_members,
        ["fake_group1", "fake_group2"],
        obj=fake_obj,
    )
    assert result.stdout == ""
