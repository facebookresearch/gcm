# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import pwd
import textwrap
import zoneinfo
from abc import ABC, abstractmethod
from datetime import tzinfo
from pathlib import Path
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Mapping,
    Optional,
    Protocol,
    Type,
    TypeVar,
    Union,
)

import click

import daemon
import tomli
from gcm.exporters import registry

from gcm.monitoring.coerce import ensure_dict
from gcm.monitoring.features.features_config import FeaturesConfig
from gcm.monitoring.passwd import Passwd
from gcm.monitoring.sink.utils import (
    Factory,
    format_factory_docstrings,
    get_factory_metadata,
)
from typeguard import typechecked
from typing_extensions import ParamSpec

logger = logging.getLogger(__name__)


class EpilogFormatter(Protocol):
    def format_epilog(self) -> str: ...


_Object = TypeVar("_Object", bound=EpilogFormatter)

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T")
FC = TypeVar("FC", bound=Union[Callable[..., Any], click.Command])


class DaemonGroup(click.Group):
    def invoke(self, ctx: click.Context) -> None:
        detach = ctx.params.get("detach", False)
        if detach:
            with daemon.DaemonContext():
                return super().invoke(ctx)
        else:
            return super().invoke(ctx)


detach_option = click.option(
    "--detach",
    "-d",
    is_flag=True,
    default=False,
    help=("Exit immediately instead of waiting for GCM to run. "),
)


class IntWithSISymbol(click.ParamType):
    name = "integer_si"
    _symbol_map = {"k": 1000, "M": 1_000_000}

    def convert(
        self, value: str, param: Optional[click.Parameter], ctx: Optional[click.Context]
    ) -> int:
        multiplier = 1
        extracted_value = value
        if not value[-1].isdigit():
            if any(value.endswith(s) for s in self._symbol_map):
                multiplier = self._symbol_map[value[-1]]
                extracted_value = value[:-1]
            else:
                allowed = ", ".join(self._symbol_map.keys())
                self.fail(
                    f"Unrecognized SI symbol '{value[-1]}'. Allowed symbols are: {allowed}",
                    param,
                    ctx,
                )
        try:
            return int(extracted_value) * multiplier
        except TypeError:
            self.fail(
                f"Expected string, but got {value!r} of type {type(value).__name__}",
                param,
                ctx,
            )
        except ValueError:
            self.fail(f"{value!r} is not a valid integer", param, ctx)


cluster_option = click.option(
    "--cluster",
    help=(
        "Which cluster to collect stats for (usually the cluster where the script is running). "
        "If omitted, then the cluster is inferred (may fail)."
    ),
)

sink_option = click.option(
    "--sink",
    default="stdout",
    help="The sink where data should be published.",
)

sink_opts_option = click.option(
    "-o",
    "--sink-opt",
    "sink_opts",
    multiple=True,
    help="Sink instantiation customization using OmegaConf dot-list syntax. See [1]",
)

log_level_option = click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    show_default=True,
    help="Logging verbosity level.",
)

log_folder_option = click.option(
    "--log-folder",
    type=click.Path(file_okay=False),
    default="sacct_running_logs",
    help="The directory where logs will be stored.",
)

stdout_option = click.option(
    "--stdout",
    is_flag=True,
    default=False,
    help="Whether to display logs to stdout.",
)

once_option = click.option(
    "--once",
    is_flag=True,
    default=False,
    help="Do only one round of data collection and publishing",
)

retries_option = click.option(
    "--retries",
    type=click.IntRange(min=0),
    default=2,
    show_default=True,
    help="The maximum number of times to retry writing to sink before failing.",
)

dry_run_option = click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    help="Print logs to STDOUT as JSON.",
)

chunk_size_option = click.option(
    "--chunk-size",
    type=IntWithSISymbol(),
    default="1M",
    show_default=True,
    help=(
        "The maximum size in bytes of each chunk when writing data to sink. "
        "Recognizes a subset of SI symbols for multiples for shorthand, e.g. 1k for "
        "1000, 1M for 1,000,000. Pass 0 to disable chunking."
    ),
)


def interval_option(default: int) -> Callable[[FC], FC]:
    return click.option(
        "--interval",
        type=click.IntRange(min=0),
        default=default,
        show_default=True,
        help="The interval in seconds for collecting data.",
    )


heterogeneous_cluster_v1_option = click.option(
    "--heterogeneous-cluster-v1",
    is_flag=True,
    default=False,
    help="Compute 'derived cluster' attribute for heterogeneous GPU SLURM clusters. "
    "Use when multiple types of GPUs are managed by separate partitions, e.g., "
    "NVIDIA H100 and H200 GPUs in separate 'h100' and 'h200' partitions."
    "This flag when passed will result in the 'derived cluster' attribute being: <cluster_name>.<partition_name>"
    "For QoS-based commands, this flag generates the <partition_name> by extracting characters from the QoS name string up to the first underscore (_) or using all characters if no underscore is present. For example, a QoS named: h100_myqos would result in `derived_cluster = <cluster_name>.h100`.",
)


def click_default_cmd(
    epilog: str = "",
    cls: Type[click.Command] = click.Command,
    context_settings: Optional[dict[str, Any]] = None,
) -> Callable[[Callable[..., T]], click.Command]:
    return click.command(
        cls=cls,
        context_settings=context_settings,
        epilog=f"\b{epilog}\nSink documentation:\n\n\b\n"
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


class DynamicEpilogCommand(Generic[_Object], click.Command):
    """A command which has its help epilog dynamically constructed by the object
    attached to the command's context.

    Example:
    >>> class Obj:
    ...     def format_epilog(self):
    ...         return "hello, world!"
    ...
    >>> class MyCommand(DynamicEpilogCommand[Obj], obj_cls=Obj):
    ...     pass
    ...
    >>> @click.command(cls=MyCommand, context_settings={"obj": Obj()})
    ... def main():
    ...     pass
    ...

    Now `--help` should yield:
    ```
    Usage: scratch.py [OPTIONS]

    Options:
      --help  Show this message and exit.

      hello, world!
    ```
    """

    obj_cls: Type[_Object]

    def __init_subclass__(cls, *, obj_cls: Type[_Object]) -> None:
        super().__init_subclass__()
        cls.obj_cls = obj_cls

    def format_epilog(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        obj = ctx.find_object(self.obj_cls)
        if not isinstance(obj, expected_cls := self.obj_cls):
            logger.debug(
                f"{obj} does not appear to be an instance of {expected_cls.__name__}"
            )
            return super().format_epilog(ctx, formatter)

        if self.epilog is not None:
            logger.debug("Epilog is set; not generating it dynamically.")
            return super().format_epilog(ctx, formatter)

        logger.debug("Generating epilog dynamically")
        self.epilog = obj.format_epilog()
        return super().format_epilog(ctx, formatter)


def get_docs_for_registry(r: Mapping[str, Factory]) -> str:
    """Get click-formatted documentation for a plugin registry."""
    return "\b\nSink documentation:\n" + textwrap.indent(
        format_factory_docstrings(get_factory_metadata(r), paragraph_marker="\b"),
        prefix=" " * 2,
        predicate=lambda _: True,
    )


def get_docs_for_references(refs: Iterable[str]) -> str:
    """Get click formatted documentation for an iterable of references. The output
    is an ordered list of each reference numbered started from 1.

    Examples:
    >>> get_docs_for_references(["r1", "r2"])
    '\\x08\\nReferences:\\n  [1]: r1\\n  [2]: r2'
    """
    return "\b\nReferences:\n" + textwrap.indent(
        "\n".join(f"[{i}]: {ref}" for i, ref in enumerate(refs, start=1)),
        prefix=" " * 2,
        predicate=lambda _: True,
    )


_Tv = TypeVar("_Tv")
_ClickCallback = Callable[[click.Context, click.Parameter, _Tv], None]


def _set_default_map(name: str) -> _ClickCallback[Path]:
    @typechecked
    def cb(ctx: click.Context, param: click.Parameter, path: Path) -> None:
        if not path.exists() or path == Path("/dev/null"):
            return

        logger.info(f"Reading config from {path}...")
        with path.open("rb") as f:
            try:
                conf = tomli.load(f)
            except tomli.TOMLDecodeError as e:
                # TODO: treat default differently?
                raise click.BadParameter(
                    f"{path} does not contain valid TOML.",
                    ctx=ctx,
                    param=param,
                ) from e
        try:
            default_map = ensure_dict(conf[name])
        except KeyError as e:
            raise click.BadParameter(
                f"'{name}' is not a top-level table name in {path}. Valid names: {list(conf.keys())}",
                ctx=ctx,
                param=param,
            ) from e
        logger.info(f"Loaded table '{name}'.")

        ctx.default_map = {**(ctx.default_map or {}), **default_map}

    return cb


_P = ParamSpec("_P")
_R = TypeVar("_R")


def toml_config_option(
    name: str,
    *,
    default_config_path: Union[str, Path] = "/etc/fb-gcm/config.toml",
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Shared decorator for loading default option values from a TOML config file.
    Adds a `--config` option to the given command which takes a path. A non-existent
    path or `/dev/null` is treated as an empty dictionary.

    Precedence (lowest to highest):
    * `default` argument to `click.option`
    * the context's `default_map` setting (unless it is a subcommand; see below)
    * the value in the config file
    * value passed at the command line

    If used on a command group, subtables will configure subcommands, recursively.
    However, if a subcommand sets `default_map` explicitly
    (e.g. `@click.command(context_settings={"default_map": ...})`), this will stop the
    propagation.

    Parameters:
        name: The top-level table name in the config file containing the default values
            to use.
        default_config_path: The path from which to load the config if the option is
            omitted at the command line.
    """

    def decorator(f: Callable[_P, _R]) -> Callable[_P, _R]:
        return click.option(
            "--config",
            type=click.Path(dir_okay=False, path_type=Path),
            callback=_set_default_map(name),
            default=default_config_path,
            show_default=True,
            expose_value=False,
            help=(
                f"Load option values from table '{name}' in the given TOML config file. "
                "A non-existent path or '/dev/null' are ignored and treated as empty tables."
            ),
        )(f)

    return decorator


class TypedParamType(click.ParamType, ABC, Generic[_Tv]):
    """Typesafe click.ParamType which is generic in the return type of `convert`"""

    @abstractmethod
    def convert(
        self,
        value: Any,
        param: Optional[click.Parameter],
        ctx: Optional[click.Context],
    ) -> _Tv:
        pass


class UserOrUid(TypedParamType[Passwd]):
    """Convert an integer user id or user name into a passwd structure."""

    name = "user"

    def __init__(
        self,
        *,
        from_uid: Callable[[int], Passwd] = pwd.getpwuid,
        from_name: Callable[[str], Passwd] = pwd.getpwnam,
    ):
        self.__from_uid = from_uid
        self.__from_name = from_name

    def convert(
        self,
        value: Any,
        param: Optional[click.Parameter],
        ctx: Optional[click.Context],
    ) -> Passwd:
        if isinstance(value, int):
            try:
                return self.__from_uid(value)
            except Exception:
                self.fail(f"Invalid user id: {value}.", param, ctx)

        if isinstance(value, str):
            try:
                n = int(value)
            except ValueError:
                pass
            else:
                return self.convert(n, param, ctx)

            try:
                return self.__from_name(value)
            except Exception:
                self.fail(f"Invalid user name: {value}.", param, ctx)

        self.fail(
            f"User must be either a numeric user ID (int) or user name (str), but got {type(value).__name__}",
            param,
            ctx,
        )


class Timezone(click.ParamType):
    name = "timezone"

    def convert(
        self, value: str, param: Optional[click.Parameter], ctx: Optional[click.Context]
    ) -> tzinfo:
        try:
            # SAFETY: https://github.com/pganssle/zoneinfo/issues/125
            return zoneinfo.ZoneInfo(value)  # type: ignore[abstract]
        except TypeError:
            self.fail(
                f"Expected string, but got {value!r} of type {type(value).__name__}",
                param,
                ctx,
            )
        except ValueError:
            self.fail(f"{value!r} is not a valid timezone", param, ctx)


def set_features_config_path(config: Type[FeaturesConfig]) -> _ClickCallback:
    def set_path(
        ctx: click.Context, param: click.Parameter, path: Optional[Path]
    ) -> None:
        if path is None:
            return
        if path.exists():
            config.config_path = path
        else:
            raise FileNotFoundError(f"features_config path doesn't exist: {path}")

    return set_path


def feature_flags_config(
    config: Type[FeaturesConfig],
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    def decorator(func: Callable[_P, _R]) -> Callable[_P, _R]:
        return click.option(
            "--features-config",
            type=click.Path(dir_okay=False, path_type=Path),
            callback=set_features_config_path(config),
            expose_value=False,
            help="Path parameter for the features config file, to load feature values.",
        )(func)

    return decorator
