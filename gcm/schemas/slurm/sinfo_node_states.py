# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from typing import Optional


@dataclass(kw_only=True)
class SinfoNodeStates:
    nodes_allocated: Optional[int] = None
    nodes_completing: Optional[int] = None
    nodes_down: Optional[int] = None
    nodes_drained: Optional[int] = None
    nodes_draining: Optional[int] = None
    nodes_fail: Optional[int] = None
    nodes_failing: Optional[int] = None
    nodes_future: Optional[int] = None
    nodes_idle: Optional[int] = None
    nodes_inval: Optional[int] = None
    nodes_maint: Optional[int] = None
    nodes_reboot_issued: Optional[int] = None
    nodes_reboot_requested: Optional[int] = None
    nodes_mixed: Optional[int] = None
    nodes_perfctrs: Optional[int] = None
    nodes_planned: Optional[int] = None
    nodes_power_down: Optional[int] = None
    nodes_powered_down: Optional[int] = None
    nodes_powering_down: Optional[int] = None
    nodes_powering_up: Optional[int] = None
    nodes_reserved: Optional[int] = None
    nodes_unknown: Optional[int] = None
    nodes_not_responding: Optional[int] = None
    nodes_unknown_state: Optional[int] = None
    nodes_total: Optional[int] = None
