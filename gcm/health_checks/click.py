# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Helper functionality for click commands"""

import textwrap
from functools import wraps
from typing import Callable, get_args, TypeVar

import click
from gcm.exporters import registry
from gcm.health_checks.types import CHECK_TYPE, LOG_LEVEL

from gcm.monitoring.click import get_docs_for_references
from gcm.monitoring.sink.utils import format_factory_docstrings, get_factory_metadata
from typing_extensions import ParamSpec

P = ParamSpec("P")
R = TypeVar("R")


DEFAULT_CONFIG_PATH = "/etc/fb-healthchecks/config.toml"


def common_arguments(f: Callable[P, R]) -> Callable[P, R]:
    @click.argument(
        "cluster",
        type=click.STRING,
    )
    @click.argument(
        "type",
        type=click.Choice(
            get_args(CHECK_TYPE),
            case_sensitive=True,
        ),
    )
    @click.option(
        "--log-level",
        type=click.Choice(get_args(LOG_LEVEL)),
        default="INFO",
        show_default=True,
        help="Logging verbosity level.",
    )
    @click.option(
        "--log-folder",
        type=click.Path(file_okay=False),
        default="healthchecks",
        help="The folder where logs will be stored.",
    )
    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return f(*args, **kwargs)

    return wrapper


def timeout_argument(f: Callable[P, R]) -> Callable[P, R]:
    @click.option(
        "--timeout",
        type=click.INT,
        default=300,
        help="Seconds until the check command times out",
    )
    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return f(*args, **kwargs)

    return wrapper


def telemetry_argument(f: Callable[P, R]) -> Callable[P, R]:
    @click.option(
        "--sink",
        type=click.Choice(list(registry)),
        default="do_nothing",
        show_default=True,
        help="The sink where data should be published."
        + "\n\n"
        + "Sink documentation:\n\n\n\b\n"
        + textwrap.indent(
            format_factory_docstrings(get_factory_metadata(registry)),
            prefix=" " * 2,
            predicate=lambda _: True,
        )
        + get_docs_for_references(
            [
                "https://omegaconf.readthedocs.io/en/2.2_branch/usage.html#from-a-dot-list",
            ]
        ),
    )
    @click.option(
        "--sink-opt",
        "-o",
        "sink_opts",
        multiple=True,
        help="Sink initialization options in OmegaConf dot-list syntax (see [1]).",
    )
    @click.option(
        "--verbose-out",
        is_flag=True,
        help="Flag for printing verbose output on stdout",
    )
    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return f(*args, **kwargs)

    return wrapper
