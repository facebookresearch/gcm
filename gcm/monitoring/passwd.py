# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from typing import Protocol


class Passwd(Protocol):
    """The `passwd` structure protocol.

    Defined here as a protocol so we aren't tied to the nominal type in `pwd`.

    For more information, refer to https://docs.python.org/3/library/pwd.html
    """

    @property
    def pw_name(self) -> str: ...

    @property
    def pw_passwd(self) -> str: ...

    @property
    def pw_uid(self) -> int: ...

    @property
    def pw_gid(self) -> int: ...

    @property
    def pw_gecos(self) -> str: ...

    @property
    def pw_dir(self) -> str: ...

    @property
    def pw_shell(self) -> str: ...
