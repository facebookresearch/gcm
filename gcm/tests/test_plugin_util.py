# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from typing import Dict, Protocol

import pytest

from gcm.monitoring.sink.utils import Factory, make_register


class Base(Protocol):
    pass


def test_make_register() -> None:
    registry: Dict[str, Factory[Base]] = {}
    register = make_register(registry)

    @register("a")
    class ImplA(Base):
        pass

    @register("b")
    class ImplB(Base):
        pass

    assert isinstance(registry["a"](), ImplA)
    assert isinstance(registry["b"](), ImplB)
    assert "does_not_exist" not in registry


def test_make_register_throws_if_name_is_already_registered() -> None:
    registry: Dict[str, Factory[Base]] = {}
    register = make_register(registry)

    @register("a")
    class ImplA(Base):
        pass

    with pytest.raises(RuntimeError):

        @register("a")
        class ImplB(Base):
            pass
