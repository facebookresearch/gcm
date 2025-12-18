# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import subprocess
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable, Tuple

import click
from typeguard import typechecked

GETENT_GROUP_IDX = 0
GROUP_USER_IDX = 3
HEADER = "group,user\n"
DELIMITER = ","

logger = logging.getLogger(__name__)


@runtime_checkable
class CliObject(Protocol):
    def get_members_raw(self, groups: Tuple[str, ...]) -> str: ...


@dataclass
class CliObjectImpl:
    def get_members_raw(self, groups: Tuple[str, ...]) -> str:
        return subprocess.check_output(["getent", "group", *groups], text=True)


@click.command(epilog="get_member")
@click.argument(
    "groups",
    type=str,
    nargs=-1,
)
@click.pass_obj
@typechecked
def get_members(
    obj: Optional[CliObject],
    groups: Tuple[str, ...],
) -> None:
    if obj is None:
        obj = CliObjectImpl()
    output_buffer = []
    try:
        results = obj.get_members_raw(groups)
    except Exception:
        logger.exception("Fail to execute getent group {}.".format(groups))
    else:
        lines = results.split("\n")
        for line in lines:
            if len(line) > 0:
                toks = line.split(":")
                group = toks[GETENT_GROUP_IDX]
                users = toks[GROUP_USER_IDX]
                if len(users) > 0:
                    users_list = users.split(",")
                    for user in users_list:
                        output_buffer.append(group + DELIMITER + user)
        print(HEADER + "\n".join(output_buffer))


if __name__ == "__main__":
    get_members()
