# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import sys

# plugin subpackages to initialize
from types import ModuleType
from typing import Dict

from gcm.monitoring.sink.protocol import SinkImpl

from gcm.monitoring.sink.utils import discover, Factory, make_register, Register

registry: Dict[str, Factory[SinkImpl]] = {}
register: Register[SinkImpl] = make_register(registry)

current_module = sys.modules[__name__]

discovered_plugins: Dict[str, ModuleType] = {}
discovered_plugins.update(discover(current_module))
