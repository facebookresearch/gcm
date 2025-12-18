# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from typing import Callable, Generic, Optional, TypeVar

T = TypeVar("T")


class Accumulator(Generic[T]):
    """An accumulator of T defined by a given binary operation.

    Accumulation happens "from the left," i.e.

        ( ... ((x_1 * x_2) * x_3) * ... * x_n)
    """

    def __init__(self, op: Callable[[T, T], T], *, initial: Optional[T] = None):
        self.__op = op
        self.__current = initial

    def tell(self, value: T) -> None:
        """Accumulate an additional value. The given value is not copied."""
        if self.__current is None:
            self.__current = value
            return
        self.__current = self.__op(self.__current, value)

    def ask(self) -> T:
        """Get the current accumulated value. The returned value is not copied."""
        if self.__current is None:
            raise ValueError("Must be told at least one value")
        return self.__current

    def ask_maybe(self) -> Optional[T]:
        """Get the current accumulated value or None if there is nothing to accumulate.
        The returned value is not copied.
        """
        return self.__current
