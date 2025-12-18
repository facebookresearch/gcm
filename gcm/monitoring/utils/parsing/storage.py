# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from gcm.monitoring.constants import UNITS_IN_G, UNITS_IN_K, UNITS_IN_M


def parse_abbreviated_float(s: str) -> float:
    """Given a string of the form <float>?{K|M|G}, return the unitless float.
    Raises `ValueError` if the string could not be parsed.

    Examples:
    >>> parse_abbreviated_float('1.0K')
    1000.0
    >>> parse_abbreviated_float('1.23M')
    1230000.0
    >>> parse_abbreviated_float('1.69G')
    1690000000.0
    >>> parse_abbreviated_float('1.23')
    1.23
    """
    num = float(s[:-1])
    unit = s[-1]
    if unit == "G":
        return num * UNITS_IN_G
    elif unit == "M":
        return num * UNITS_IN_M
    elif unit == "K":
        return num * UNITS_IN_K
    elif unit.isdigit():
        return float(s)
    else:
        raise ValueError("Could not parse {}.".format(s))
