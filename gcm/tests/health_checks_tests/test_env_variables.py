# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import os
from typing import Generator

import pytest

from gcm.health_checks.env_variables import EnvCtx


@pytest.fixture(scope="module")
def env_var_fixture() -> Generator[None, None, None]:
    if "TEST_VAR" in os.environ:
        original_value = os.environ["TEST_VAR"]
    else:
        original_value = None
    os.environ["TEST_VAR"] = "initial_value"
    yield
    if original_value is None:
        os.environ.pop("TEST_VAR", None)
    else:
        os.environ["TEST_VAR"] = original_value


def test_setting_existing_env_var(env_var_fixture: None) -> None:
    with EnvCtx({"TEST_VAR": "new_value"}):
        assert os.environ["TEST_VAR"] == "new_value"
    assert os.environ["TEST_VAR"] == "initial_value"


def test_deleting_existing_env_var(env_var_fixture: None) -> None:
    with EnvCtx({"TEST_VAR": None}):
        assert "TEST_VAR" not in os.environ
    assert os.environ["TEST_VAR"] == "initial_value"


def test_deleting_non_existing_env_var(env_var_fixture: None) -> None:
    with EnvCtx({"TEST_VAR2": None}):
        assert "TEST_VAR2" not in os.environ
    assert "TEST_VAR2" not in os.environ


def test_setting_non_existing_env_var(env_var_fixture: None) -> None:
    with EnvCtx({"TEST_VAR2": "new_value"}):
        assert os.environ["TEST_VAR2"] == "new_value"
    assert "TEST_VAR2" not in os.environ
