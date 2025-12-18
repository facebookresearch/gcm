# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from pathlib import Path
from typing import ClassVar, Optional, Protocol


class FeaturesConfig(Protocol):
    config_path: ClassVar[Optional[Path]]
