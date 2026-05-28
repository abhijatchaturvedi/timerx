"""Core timing utilities for timerx."""

from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Callable
from contextlib import ContextDecorator
from dataclasses import dataclass
from typing import Any, TypeVar, overload

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class _Record:
    count: int = 0
    total: float = 0.0
    min: float | None = None
    max: float | None = None
    last: float = 0.0

    def add(self, elapsed: float) -> None:
        self.count += 1
        self.total += elapsed
        self.last = elapsed
        self.min = elapsed if self.min is None else min(self.min, elapsed)
        self.max = elapsed if self.max is None else max(self.max, elapsed)

    def as_dict(self) -> dict[str, float | int]:
        average = self.total / self.count if self.count else 0.0
        return {
            "count": self.count,
            "total": self.total,
            "min": self.min or 0.0,
            "max": self.max or 0.0,
            "last": self.last,
            "avg": average,
        }


class _Lap(ContextDecorator):
    def __init__(self, timer: "TimerX", name: str) -> None:
        self._timer = timer
        self._name = name
        self._started: float | None = None

    def __enter__(self) -> "_Lap":
        self._started = self._timer._clock()
        return self

    def __exit__(self, *exc_info: object) -> bool:
        if self._started is None:
            raise RuntimeError("timerx lap exited before it was entered")
        self._timer._record(self._name, self._timer._clock() - self._started)
        return False


class TimerX:
    """An isolated timing collector.

    Use an instance when library code or tests should not write into timerx's
    global process-wide timing state.
    """

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.perf_counter
        self._records: dict[str, _Record] = {}
        self._running: dict[str, list[float]] = {}

    @overload
    def track(self, func: F, /) -> F:
        ...

    @overload
    def track(self, func: None = None, /, *, name: str | None = None) -> Callable[[F], F]:
        ...

    def track(
        self, func: F | None = None, /, *, name: str | None = None
    ) -> F | Callable[[F], F]:
        """Time a sync or async function.

        Works as ``@timer.track``, ``@timer.track()`` or
        ``@timer.track(name="custom")``.
        """

        def decorate(target: F) -> F:
            label = name or target.__name__

            if inspect.iscoroutinefunction(target):

                @functools.wraps(target)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    started = self._clock()
                    try:
                        return await target(*args, **kwargs)
                    finally:
                        self._record(label, self._clock() - started)

                return async_wrapper  # type: ignore[return-value]

            @functools.wraps(target)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                started = self._clock()
                try:
                    return target(*args, **kwargs)
                finally:
                    self._record(label, self._clock() - started)

            return wrapper  # type: ignore[return-value]

        if func is None:
            return decorate
        return decorate(func)

    def lap(self, name: str) -> _Lap:
        """Return a context manager that records elapsed time under ``name``."""

        if not name:
            raise ValueError("timerx lap name must not be empty")
        return _Lap(self, name)

    def start(self, name: str) -> None:
        """Start a named stopwatch.

        Multiple starts with the same name are supported and behave like a
        stack: each ``stop(name)`` records the most recently started stopwatch.
        """

        if not name:
            raise ValueError("timerx stopwatch name must not be empty")
        self._running.setdefault(name, []).append(self._clock())

    def stop(self, name: str) -> float:
        """Stop a named stopwatch and return elapsed seconds."""

        try:
            stack = self._running[name]
        except KeyError as exc:
            raise KeyError(f"timerx stopwatch {name!r} was not started") from exc

        started = stack.pop()
        if not stack:
            del self._running[name]
        elapsed = self._clock() - started
        self._record(name, elapsed)
        return elapsed

    def get_stats(self) -> dict[str, dict[str, float | int]]:
        """Return a plain dictionary of accumulated timing statistics."""

        return {name: record.as_dict() for name, record in self._records.items()}

    def summary(self, unit: str = "auto") -> str:
        """Return a formatted text table of accumulated timings."""

        if unit not in {"auto", "s", "ms", "us", "µs"}:
            raise ValueError("unit must be one of: auto, s, ms, us, µs")
        if not self._records:
            return "timerx: no timings recorded"

        rows = []
        for name, stats in self.get_stats().items():
            rows.append(
                [
                    name,
                    str(stats["count"]),
                    self._format(float(stats["total"]), unit),
                    self._format(float(stats["avg"]), unit),
                    self._format(float(stats["min"]), unit),
                    self._format(float(stats["max"]), unit),
                    self._format(float(stats["last"]), unit),
                ]
            )

        headers = ["name", "count", "total", "avg", "min", "max", "last"]
        widths = [
            max(len(str(row[index])) for row in [headers, *rows])
            for index in range(len(headers))
        ]
        lines = [
            "  ".join(value.ljust(widths[index]) for index, value in enumerate(headers)),
            "  ".join("-" * width for width in widths),
        ]
        lines.extend(
            "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
            for row in rows
        )
        return "\n".join(lines)

    def reset(self) -> None:
        """Clear all recorded and running timings."""

        self._records.clear()
        self._running.clear()

    def _record(self, name: str, elapsed: float) -> None:
        self._records.setdefault(name, _Record()).add(elapsed)

    @classmethod
    def _format(cls, seconds: float, unit: str) -> str:
        if unit == "auto":
            unit = cls._auto_unit(seconds)
        if unit == "s":
            return f"{seconds:.6g}s"
        if unit == "ms":
            return f"{seconds * 1_000:.6g}ms"
        return f"{seconds * 1_000_000:.6g}µs"

    @staticmethod
    def _auto_unit(seconds: float) -> str:
        if seconds >= 1:
            return "s"
        if seconds >= 0.001:
            return "ms"
        return "µs"
