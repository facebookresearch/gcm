# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from typing import Optional


@dataclass(kw_only=True)
class Sdiag:
    server_thread_count: Optional[int]
    agent_queue_size: Optional[int]
    agent_count: Optional[int]
    agent_thread_count: Optional[int]
    dbd_agent_queue_size: Optional[int]
