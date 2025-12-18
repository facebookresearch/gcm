# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Shared utilities for setting up plugins"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
import re
import sys
import textwrap
import traceback
from dataclasses import dataclass, field
from functools import partial
from itertools import islice
from types import ModuleType
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Protocol,
    Type,
    TYPE_CHECKING,
    TypeVar,
    Union,
)

import click
from gcm.monitoring.decorators import exponential_backoff, OutOfRetries, retry
from gcm.monitoring.itertools import chunk_by_json_size, json_dumps_dataclass
from gcm.monitoring.sink.protocol import SinkAdditionalParams, SinkImpl, SinkWrite

from gcm.schemas.log import Log

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


logger = logging.getLogger(__name__)


def discover(module: ModuleType) -> Dict[str, ModuleType]:
    """Discover namespace package plugins.

    See https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/#using-namespace-packages
    """
    try:
        path = module.__path__
    except AttributeError as e:
        raise RuntimeError(f"{module.__name__} is not a package") from e

    logger.debug(f"Discovering plugins in namespace package {path}")
    modules = {}
    for _, name, ispkg in pkgutil.iter_modules(path, module.__name__ + "."):
        logger.debug(f"Discovered {name} {ispkg}")
        modules[name] = importlib.import_module(name)
    return modules


T = TypeVar("T")
Factory = Callable[[], T]
ClassDecorator = Callable[[Type[T]], Type[T]]
Register = Callable[[str], ClassDecorator[T]]

T_co = TypeVar("T_co", covariant=True)


def make_register(registry: MutableMapping[str, Factory[T_co]]) -> Register[T_co]:
    """Factory for a 'register' decorator (factory). A register decorator is
    used in the registry design pattern where factories of a particular protocol or
    abstract base class (ABC) can be stored and subsequently fetched + invoked
    dynamically.

    For example,
    >>> class Base(Protocol):
    ...   ...
    ...
    >>> registry: Dict[str, Factory[Base]] = {}
    >>> register: Register[Base] = make_register(registry)
    >>> @register("impl")
    ... class BaseImpl(Base):
    ...   ...
    ...
    >>> impl_factory = registry.get("impl")
    >>> impl = impl_factory()
    >>> assert isinstance(impl, BaseImpl)

    Parameters:
        registry: A mutable mapping of str to factory functions, i.e. nullary callables
            which return an instance of the protocol/ABC.

    Type Parameters:
        T_co (covariant): The protocol or ABC which registered factories will construct
            instances of.

    Returns:
        A decorator (factory) which maps a name to a factory. See example above.
    """

    def register(name: str) -> ClassDecorator[T_co]:
        def decorator(cls: Type[T_co]) -> Type[T_co]:
            if (factory := registry.get(name)) is not None:
                raise RuntimeError(f"'{name}' is already registered to {factory}")
            registry[name] = cls
            logger.debug(f"Registered '{name}' to {cls.__name__}")
            return cls

        return decorator

    return register


@dataclass
class FactoryMetadata:
    """Auxiliary data for registered factories useful for rendering documentation."""

    module: str
    signature: inspect.Signature
    docstring: Optional[str] = None

    @classmethod
    def from_factory(cls, factory: Factory) -> "FactoryMetadata":
        try:
            docstring = factory.__doc__
        except AttributeError:
            docstring = None
        if not isinstance(factory, type):
            sig = inspect.signature(factory)
        else:
            if super(factory, factory).__init__ is factory.__init__:  # type: ignore[misc,arg-type]
                # the class doesn't define an __init__ method
                sig = inspect.Signature()
            else:
                sig = inspect.signature(factory.__init__)  # type: ignore[misc]
        return cls(
            module=factory.__module__,
            signature=sig,
            docstring=docstring,
        )


def get_factory_metadata(
    registry: Mapping[str, Factory[T_co]],
) -> Mapping[str, FactoryMetadata]:
    """Given a registry, get the metadata for each factory."""
    metas = {}
    for name, factory in registry.items():
        m = FactoryMetadata.from_factory(factory)
        if m.docstring is None:
            logger.debug(f"Couldn't find docstring for '{name}'")
        metas[name] = m
    return metas


def format_factory_docstrings(
    metadatas: Mapping[str, FactoryMetadata],
    *,
    default_docstring: str = "No documentation found.",
    paragraph_marker: Optional[str] = None,
) -> str:
    """Pretty-print documentation for factories given their metadata. Factories are
    sorted by name.

    The output is split into sections. Each section corresponds to a particular factory.
    Sections are separated by an additional newline. Each section contains:
        * the name of the factory
        * which module the factory is defined
        * the docstring of the factory (__doc__)
    """
    indent = " " * 2
    parts = []
    for name, factory_meta in sorted(metadatas.items(), key=lambda i: i[0]):
        if paragraph_marker is not None:
            parts.append(paragraph_marker)
        parts.append(f"{name} - (from module: '{factory_meta.module}')")
        parts.append(
            textwrap.indent(
                f"Signature: {factory_meta.signature}",
                prefix=indent,
                predicate=lambda _: True,
            )
        )
        if factory_meta.docstring is None:
            parts.append(textwrap.indent(default_docstring, prefix=indent))
        else:
            parts.append(
                textwrap.indent(
                    factory_meta.docstring, prefix=indent, predicate=lambda _: True
                )
            )
        parts.append("")
    return "\n".join(parts)


_TSink = TypeVar("_TSink", bound=SinkImpl, covariant=True)


class HasRegistry(Protocol[_TSink]):
    @property
    def registry(self) -> Mapping[str, Factory[_TSink]]: ...


@dataclass
class InvalidParameterMessage:
    sink_name: str
    sink_factory: Factory
    sink_kwargs: Mapping[str, Any]

    sink_sig: inspect.Signature = field(init=False)
    kw_only_param_names: List[str] = field(init=False)
    unrecognized_opts: List[str] = field(init=False)

    def __post_init__(self) -> None:
        self.sink_sig = inspect.signature(self.sink_factory)
        kw_only_param_names = {
            name
            for name, p in self.sink_sig.parameters.items()
            if p.kind == p.KEYWORD_ONLY
        }
        self.kw_only_param_names = sorted(kw_only_param_names)
        self.unrecognized_opts = sorted(
            set(self.sink_kwargs.keys()) - kw_only_param_names
        )

    def __str__(self) -> str:
        msg_lines = [
            f"Sink '{self.sink_name}' got unrecognized options."
            "Its signature contains the following keyword-only parameters:",
            *(f"\t{name}" for name in self.kw_only_param_names),
            "But the following additional parameters were given:",
            *(f"\t{name}" for name in self.unrecognized_opts),
        ]
        return "\n".join(msg_lines)


@dataclass
class MissingParameterMessage:
    sink_name: str
    sink_factory: Factory
    sink_kwargs: Mapping[str, Any]

    sink_sig: inspect.Signature = field(init=False)
    kw_only_no_default_param_names: List[str] = field(init=False)
    given_opts: List[str] = field(init=False)
    missing_opts: List[str] = field(init=False)

    def __post_init__(self) -> None:
        self.sink_sig = inspect.signature(self.sink_factory)
        kw_only_no_default_param_names = {
            name
            for name, p in self.sink_sig.parameters.items()
            if p.kind == p.KEYWORD_ONLY and p.default is p.empty
        }
        self.kw_only_no_default_param_names = sorted(kw_only_no_default_param_names)
        self.given_opts = sorted(self.sink_kwargs.keys())
        self.missing_opts = sorted(
            kw_only_no_default_param_names - set(self.sink_kwargs.keys())
        )

    def __str__(self) -> str:
        msg_lines = [
            f"Sink '{self.sink_name}' is missing required parameters.",
            "Its signature contains the following keyword-only parameters without defaults:",
            *(f"\t{name}" for name in self.kw_only_no_default_param_names),
            "The following parameters were given:",
            *(f"\t{name}" for name in self.given_opts),
            "Missing parameters:",
            *(f"\t{name}" for name in self.missing_opts),
        ]
        return "\n".join(msg_lines)


def print_tb(verbose: bool) -> None:
    if not verbose:
        return

    exc_info = sys.exc_info()
    assert all(
        i is not None for i in exc_info
    ), "Can only be called in an exception handler"
    traceback.print_exception(*exc_info)


def get_message_for_sink_init_error(
    exc: TypeError,
    sink_name: str,
    sink_factory: Factory,
    sink_kwargs: Mapping[str, Any],
) -> Union[None, InvalidParameterMessage, MissingParameterMessage]:
    """Get a detailed error message for certain errors that occur during sink
    initialization.

    Currently it handles two cases (i.e. the "known" error cases):
    1. invalid/unexpected parameter
    2. missing required parameter

    NOTE: This function does not appropriately handle cases where the exception is
    thrown higher in the call stack (e.g. in a function called by the factory).

    Parameters:
        exc: The exception that was raised
        sink_name: The human-readable registered sink name
        sink_factory: The callable used to construct the sink instance
        sink_kwargs: The keyword arguments passed to the factory

    Returns:
        The error message if a known error occurs; `None` otherwise.
    """
    str_exc = str(exc)

    if "got an unexpected keyword argument" in str_exc:
        return InvalidParameterMessage(
            sink_name=sink_name, sink_factory=sink_factory, sink_kwargs=sink_kwargs
        )

    if (
        re.compile(r"^.*missing [0-9]+ required keyword-only arguments:.*$").match(
            str_exc
        )
        is not None
    ):
        return MissingParameterMessage(
            sink_name=sink_name, sink_factory=sink_factory, sink_kwargs=sink_kwargs
        )

    return None


def write_to_sink_with_retries(
    write: SinkWrite,
    sink: str,
    records: Iterable[DataclassInstance],
    chunk_size: int,
    retries: int,
    verbose: bool,
    log_time: int,
    additional_params: SinkAdditionalParams,
) -> None:
    write = partial(
        write,
        additional_params=additional_params,
    )
    retryable_write = retry(
        retry_schedule_factory=lambda: islice(exponential_backoff(), retries)
    )(write)

    try:
        if chunk_size > 0:
            for chunk in chunk_by_json_size(records, chunk_size, json_dumps_dataclass):
                log = Log(
                    ts=log_time,
                    message=chunk,
                )
                retryable_write(log)
        else:
            log = Log(
                ts=log_time,
                message=records,
            )
            retryable_write(log)
    except OutOfRetries as e:
        print_tb(verbose)
        raise click.ClickException(
            f"Failed even after retrying {retries} times. Please try again later."
        ) from e
    except ValueError as e:
        print_tb(verbose)
        raise click.UsageError(str(e)) from e
    except Exception as e:
        print_tb(verbose)
        raise click.ClickException(
            f"An error occurred writing logs to '{sink=}': {e}. Please try again later"
        ) from e
