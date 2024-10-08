"""
Periodic Task Execution Decorator

Provides a `repeat_every` decorator for periodic execution of tasks in asynchronous environments. 
Modified from fastapi_utils library to support passing a state object to the repeated function.

Features:
- Configurable execution interval and initial delay
- Exception handling with optional callback
- Completion callback and maximum repetitions limit
- Supports both sync and async functions

Usage:
    @repeat_every(seconds=60)
    async def my_task(state):
        # Task logic here

Note: Designed for use with asynchronous frameworks like FastAPI.

Original Source: https://github.com/dmontagu/fastapi-utils (MIT License)
"""

from __future__ import annotations

import asyncio
from functools import wraps
import logging
from traceback import format_exception
from typing import Any, Callable, Coroutine, TypeVar, Union
import warnings

from starlette.concurrency import run_in_threadpool


T = TypeVar("T")

ArgsReturnFuncT = Callable[[T], Any]
ArgsReturnAsyncFuncT = Callable[[T], Coroutine[Any, Any, Any]]
ExcArgNoReturnFuncT = Callable[[Exception], None]
ExcArgNoReturnAsyncFuncT = Callable[[Exception], Coroutine[Any, Any, None]]
ArgsReturnAnyFuncT = Union[ArgsReturnFuncT, ArgsReturnAsyncFuncT]
ExcArgNoReturnAnyFuncT = Union[ExcArgNoReturnFuncT, ExcArgNoReturnAsyncFuncT]
ArgsReturnDecorator = Callable[
    [ArgsReturnAnyFuncT], Callable[[T], Coroutine[Any, Any, None]]
]


async def _handle_func(func: ArgsReturnAnyFuncT, arg: T) -> Any:
    if asyncio.iscoroutinefunction(func):
        return await func(arg)
    else:
        return await run_in_threadpool(func, arg)


async def _handle_exc(
    exc: Exception, on_exception: ExcArgNoReturnAnyFuncT | None
) -> None:
    if on_exception:
        if asyncio.iscoroutinefunction(on_exception):
            await on_exception(exc)
        else:
            await run_in_threadpool(on_exception, exc)


def repeat_every(
    *,
    seconds: float,
    wait_first: float | None = None,
    logger: logging.Logger | None = None,
    raise_exceptions: bool = False,
    max_repetitions: int | None = None,
    on_complete: ArgsReturnAnyFuncT | None = None,
    on_exception: ExcArgNoReturnAnyFuncT | None = None,
) -> ArgsReturnDecorator:
    """
    This function returns a decorator that modifies a function so it is periodically re-executed after its first call.

    The function it decorates should accept one argument and can return a value.

    Parameters
    ----------
    seconds: float
        The number of seconds to wait between repeated calls
    wait_first: float (default None)
        If not None, the function will wait for the given duration before the first call
    logger: Optional[logging.Logger] (default None)
        Warning: This parameter is deprecated and will be removed in the 1.0 release.
        The logger to use to log any exceptions raised by calls to the decorated function.
        If not provided, exceptions will not be logged by this function (though they may be handled by the event loop).
    raise_exceptions: bool (default False)
        Warning: This parameter is deprecated and will be removed in the 1.0 release.
        If True, errors raised by the decorated function will be raised to the event loop's exception handler.
        Note that if an error is raised, the repeated execution will stop.
        Otherwise, exceptions are just logged and the execution continues to repeat.
        See https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.set_exception_handler for more info.
    max_repetitions: Optional[int] (default None)
        The maximum number of times to call the repeated function. If `None`, the function is repeated forever.
    on_complete: Optional[Callable[[T], Any]] (default None)
        A function to call after the final repetition of the decorated function.
    on_exception: Optional[Callable[[Exception], None]] (default None)
        A function to call when an exception is raised by the decorated function.
    """

    def decorator(func: ArgsReturnAnyFuncT) -> Callable[[T], Coroutine[Any, Any, None]]:
        """
        Converts the decorated function into a repeated, periodically-called version of itself.
        """

        @wraps(func)
        async def wrapped(arg: T) -> None:
            async def loop() -> None:
                if wait_first is not None:
                    await asyncio.sleep(wait_first)

                repetitions = 0
                while max_repetitions is None or repetitions < max_repetitions:
                    try:
                        await _handle_func(func, arg)

                    except Exception as exc:
                        if logger is not None:
                            warnings.warn(
                                "'logger' is to be deprecated in favor of 'on_exception' in the 1.0 release.",
                                DeprecationWarning,
                            )
                            formatted_exception = "".join(
                                format_exception(type(exc), exc, exc.__traceback__)
                            )
                            logger.error(formatted_exception)
                        if raise_exceptions:
                            warnings.warn(
                                "'raise_exceptions' is to be deprecated in favor of 'on_exception' in the 1.0 release.",
                                DeprecationWarning,
                            )
                            raise exc
                        await _handle_exc(exc, on_exception)

                    repetitions += 1
                    await asyncio.sleep(seconds)

                if on_complete:
                    await _handle_func(on_complete, arg)

            asyncio.ensure_future(loop())

        return wrapped

    return decorator
