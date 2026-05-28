# timerx

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](pyproject.toml)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-28%20passing-brightgreen.svg)](tests/test_timerx.py)
[![Dependencies](https://img.shields.io/badge/runtime%20deps-zero-brightgreen.svg)](pyproject.toml)

timerx is a tiny, dependency-free timing utility for Python. It gives you one
simple API for timing functions, code blocks, and named stopwatches, then keeps
cumulative stats so you can inspect timings programmatically or print a compact
summary.

Use it when you want quick timing information without setting up a profiler or
manually calling `time.perf_counter()` throughout your code.

## Features

- Works as a decorator, context manager, or manual stopwatch
- Supports sync and async functions
- Accumulates count, total, average, min, max, and last duration
- Records timings even when decorated functions or context blocks raise
- Supports concurrent named stopwatches
- Provides isolated `TimerX()` instances for libraries and tests
- Uses only the Python standard library at runtime

## Install

```bash
pip install timerx
```

For local development:

```bash
pip install -e ".[test]"
pytest
```

## Quick Example

This example shows the three main ways to use timerx: decorate a function,
measure a block, and manually start and stop a named timer.

```python
import time
import timerx


@timerx.track
def train_model():
    time.sleep(0.2)


train_model()
train_model()

with timerx.lap("preprocessing"):
    time.sleep(0.05)

timerx.start("postprocess")
time.sleep(0.01)
elapsed = timerx.stop("postprocess")

print(f"postprocess took {elapsed:.4f}s")
print(timerx.summary())
```

Example summary:

```text
name           count  total     avg       min       max       last
-------------  -----  --------  --------  --------  --------  --------
train_model    2      400ms     200ms     200ms     200ms     200ms
preprocessing  1      50ms      50ms      50ms      50ms      50ms
postprocess    1      10ms      10ms      10ms      10ms      10ms
```

## Timing Functions

Use `@timerx.track` when you want to measure every call to a function. It works
with or without parentheses. By default, the function name is used as the timing
label, but you can provide a custom name.

```python
@timerx.track
def load_data():
    return [1, 2, 3]


@timerx.track()
def preprocess():
    return "ready"


@timerx.track(name="model.fit")
def train():
    return "done"
```

Stats accumulate across multiple calls:

```python
load_data()
load_data()

stats = timerx.get_stats()
print(stats["load_data"]["count"])  # 2
print(stats["load_data"]["avg"])    # average duration in seconds
```

Decorated functions are recorded even if they raise an exception, and the
original exception is still raised normally.

## Timing Async Functions

`track` also supports coroutine functions.

```python
@timerx.track(name="fetch")
async def fetch_rows():
    return await client.get("/rows")
```

## Timing Code Blocks

Use `timerx.lap(name)` as a context manager when you want to measure part of a
function. Laps record timings even when the block raises, and nested laps work
naturally.

```python
with timerx.lap("pipeline"):
    with timerx.lap("load"):
        rows = load_rows()

    with timerx.lap("transform"):
        rows = transform(rows)
```

## Stopwatches

Use `start(name)` and `stop(name)` when the start and end of the work are in
different places. Named stopwatches can run concurrently. If you start the same
name more than once, timerx treats it as a stack, so `stop(name)` closes the most
recent start.

```python
timerx.start("download")
timerx.start("parse")

timerx.stop("parse")
timerx.stop("download")
```

`stop(name)` returns the elapsed duration in seconds and also records it in the
same stats store used by decorators and laps.

## Reading Results

Use `summary()` for human-readable output:

```python
print(timerx.summary())
print(timerx.summary(unit="ms"))
```

Supported units are `auto`, `s`, `ms`, `us`, and `microseconds`. Auto mode picks
seconds, milliseconds, or microseconds per value.

Use `get_stats()` when you need data for tests, logs, dashboards, or your own
formatting:

```python
stats = timerx.get_stats()

{
    "preprocessing": {
        "count": 1,
        "total": 0.00512,
        "min": 0.00512,
        "max": 0.00512,
        "last": 0.00512,
        "avg": 0.00512,
    }
}
```

Durations in `get_stats()` are always stored as seconds.

## Isolated Instances

The top-level `timerx.track`, `timerx.lap`, `timerx.start`, and `timerx.stop`
helpers share one global timer. For libraries, tests, or applications that need
separate timing state, create a `TimerX()` instance.

```python
from timerx import TimerX

tx = TimerX()

with tx.lap("local"):
    run_work()

print(tx.get_stats())
```

## Resetting

Use `reset()` to clear recorded timings and running stopwatches.

```python
timerx.reset()
```

## Development

```bash
pip install -e ".[test]"
pytest
python examples/demo.py
```

## Contributing

Contributions are welcome. If you find a bug, have an API idea, or want to add
coverage for an edge case, please open an issue or pull request.

## License

timerx is released under the MIT License. See [LICENSE](LICENSE) for details.
