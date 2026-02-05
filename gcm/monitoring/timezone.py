# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import os
import zoneinfo
from datetime import datetime, tzinfo
from pathlib import Path
from typing import Mapping


def get_local(*, environ: Mapping[str, str] | None = None) -> tzinfo:
    """Get the local timezone that Python uses for naive datetime conversions.

    This returns the timezone that Python's datetime module uses when converting
    naive datetimes via astimezone(). This may differ from /etc/localtime on some
    systems, so we use Python's actual local timezone for consistency.

    If the TZ environment variable is set, that timezone is used instead.
    """
    if environ is None:
        environ = os.environ
    tz = environ.get("TZ")
    if tz is not None:
        return zoneinfo.ZoneInfo(tz)
    # Use Python's actual local timezone for consistency with naive datetime handling
    # This is more reliable than reading /etc/localtime which may not match Python's behavior
    local_tz = datetime.now().astimezone().tzinfo
    if local_tz is None:
        # Fallback to /etc/localtime if Python can't determine the local timezone
        zinfo = Path("/usr/share/zoneinfo")
        system_tz = Path("/etc/localtime").resolve().relative_to(zinfo)
        return zoneinfo.ZoneInfo(str(system_tz))
    return local_tz
