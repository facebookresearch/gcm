# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import os
import socket
from collections import defaultdict
from typing import Any, Callable, Tuple, TypeVar

import pytest
from dotenv import load_dotenv

from gcm.tests.config import Config

E2E_METADATA = defaultdict(list)


@pytest.fixture
def config() -> Config:
    # loads .env file if any
    load_dotenv()
    try:
        return Config.from_env(os.environ)
    except KeyError:
        # TODO (T139413584): Remove if we figure out how to access secrets in Sandcastle
        hostname = socket.gethostname()
        # On FAIR cluster and OSS CI, the config should be constructible, so reraise the
        # exception
        if "fair" in hostname or "CIRCLECI" in os.environ:
            raise
        pytest.skip(
            f"Don't know how to load config in the current environment. Hostname: {hostname}"
        )


def pytest_configure(config: "pytest.Config") -> None:
    config.addinivalue_line("markers", "slow: the test takes some time to run")


F = TypeVar("F", bound=Callable[..., Any])


def report_url(e2e_results: Tuple[str, str]) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        E2E_METADATA[func.__name__].append(e2e_results)
        return func

    return decorator


def e2e_formatter() -> None:
    for func_name in E2E_METADATA:
        print(func_name)
        for item in E2E_METADATA[func_name]:
            source, url = item
            print(f"{source}: {url}")
        print()


def pytest_unconfigure(config: "pytest.Config") -> None:
    print("You can verify E2E test results in the following urls:\n")
    e2e_formatter()
