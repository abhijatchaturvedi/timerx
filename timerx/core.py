"""Core timing utilities for timerx."""

from __future__ import annotations

import functools
import inspect
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar, overload

F = TypeVar("F", bound=Callable[..., Any])

_VALID_UNITS = frozenset({"auto", "s", "ms", "us", "µs", "microseconds"})
_VALID_SORT_KEYS = frozenset({"count", "total", "avg", "min", "max", "last"})


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
            "min": self.min if self.min is not None else 0.0,
            "max": self.max if self.max is not None else 0.0,
            "last": self.last,
            "avg": average,
        }


class _Lap:
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
        elapsed = self._timer._clock() - self._started
        with self._timer._lock:
            self._timer._record(self._name, elapsed)
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
        self._lock = threading.Lock()

    @overload
    def track(self, func: F, /) -> F: ...

    @overload
    def track(self, func: None = None, /, *, name: str | None = None) -> Callable[[F], F]: ...

    def track(
        self, func: F | None = None, /, *, name: str | None = None
    ) -> F | Callable[[F], F]:
        """Time a sync or async function.

        Works as ``@timer.track``, ``@timer.track()`` or
        ``@timer.track(name="custom")``.
        """

        def decorate(target: F) -> F:
            if name is not None and not name:
                raise ValueError("timerx track name must not be empty")
            label = name or target.__name__

            if inspect.iscoroutinefunction(target):

                @functools.wraps(target)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    started = self._clock()
                    try:
                        return await target(*args, **kwargs)
                    finally:
                        elapsed = self._clock() - started
                        with self._lock:
                            self._record(label, elapsed)

                return async_wrapper  # type: ignore[return-value]

            @functools.wraps(target)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                started = self._clock()
                try:
                    return target(*args, **kwargs)
                finally:
                    elapsed = self._clock() - started
                    with self._lock:
                        self._record(label, elapsed)

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
        t = self._clock()
        with self._lock:
            self._running.setdefault(name, []).append(t)

    def stop(self, name: str) -> float:
        """Stop a named stopwatch and return elapsed seconds."""

        t = self._clock()
        try:
            with self._lock:
                stack = self._running[name]
                started = stack.pop()
                if not stack:
                    del self._running[name]
        except KeyError as exc:
            raise KeyError(f"timerx stopwatch {name!r} was not started") from exc
        elapsed = t - started
        with self._lock:
            self._record(name, elapsed)
        return elapsed

    def get_stats(self) -> dict[str, dict[str, float | int]]:
        """Return a plain dictionary of accumulated timing statistics."""

        with self._lock:
            return {name: record.as_dict() for name, record in self._records.items()}

    def summary(self, unit: str = "auto", sort_by: str | None = None) -> str:
        """Return a formatted text table of accumulated timings.

        ``sort_by`` accepts any stat column name: count, total, avg, min, max,
        last. Rows are sorted descending by that column. Default is insertion
        order.
        """

        if unit not in _VALID_UNITS:
            raise ValueError("unit must be one of: auto, s, ms, us, µs, microseconds")
        if sort_by is not None and sort_by not in _VALID_SORT_KEYS:
            raise ValueError("sort_by must be one of: count, total, avg, min, max, last")

        with self._lock:
            if not self._records:
                return "timerx: no timings recorded"
            stats_list = [(name, record.as_dict()) for name, record in self._records.items()]

        if sort_by is not None:
            stats_list.sort(key=lambda item: item[1][sort_by], reverse=True)  # type: ignore[arg-type]

        rows: list[list[str]] = []
        for name, stats in stats_list:
            rows.append([
                name,
                str(stats["count"]),
                self._format(float(stats["total"]), unit),
                self._format(float(stats["avg"]), unit),
                self._format(float(stats["min"]), unit),
                self._format(float(stats["max"]), unit),
                self._format(float(stats["last"]), unit),
            ])

        headers = ["name", "count", "total", "avg", "min", "max", "last"]
        widths = [
            max(len(row[i]) for row in [headers, *rows])
            for i in range(len(headers))
        ]

        def _fmt_row(row: list[str]) -> str:
            parts = [row[0].ljust(widths[0])]
            parts += [row[i].rjust(widths[i]) for i in range(1, len(headers))]
            return "  ".join(parts)

        lines = [_fmt_row(headers), "  ".join("-" * w for w in widths)]
        lines.extend(_fmt_row(row) for row in rows)
        return "\n".join(lines)

    def reset(self) -> None:
        """Clear all recorded and running timings."""

        with self._lock:
            self._records.clear()
            self._running.clear()

    def _record(self, name: str, elapsed: float) -> None:
        self._records.setdefault(name, _Record()).add(elapsed)

    @staticmethod
    def _format(seconds: float, unit: str) -> str:
        if unit == "auto":
            unit = TimerX._auto_unit(seconds)
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
