# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import os
import zoneinfo
from pathlib import Path
from typing import Mapping


def get_local(*, environ: Mapping[str, str] | None = None) -> zoneinfo.ZoneInfo:
    """Get the local IANA timezone according to https://www.man7.org/linux/man-pages/man5/localtime.5.html"""
    if environ is None:
        environ = os.environ
    tz = environ.get("TZ")
    if tz is not None:
        return zoneinfo.ZoneInfo(tz)
    zinfo = Path("/usr/share/zoneinfo")
    system_tz = Path("/etc/localtime").resolve().relative_to(zinfo)
    return zoneinfo.ZoneInfo(str(system_tz))
