# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from ctypes import CDLL
from ctypes.util import find_library


def first_existing_library(candidates: list[str]) -> str | None:
    for path in candidates:
        try:
            CDLL(path)
            return path
        except OSError:
            continue
    return None


def find_and_load_library(names: list[str], path_candidates: list[str]) -> str | None:
    for name in names:
        discovered = find_library(name)
        if discovered is not None:
            try:
                CDLL(discovered)
                return discovered
            except OSError:
                continue
    return first_existing_library(path_candidates)
