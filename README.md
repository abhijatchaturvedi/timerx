# timerx

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](pyproject.toml)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-28%20passing-brightgreen.svg)](tests/test_timerx.py)
[![Dependencies](https://img.shields.io/badge/runtime%20deps-zero-brightgreen.svg)](pyproject.toml)

Tiny dependency-free timing utilities for Python. Use it as a decorator, context
manager, or named stopwatch, then inspect cumulative stats or print a compact
summary.

## Install

```bash
pip install timerx
```

For local development:

```bash
pip install -e ".[test]"
pytest
```

## Quick Start

```python
import timerx


@timerx.track
def train_model():
    ...


@timerx.track(name="custom_step")
def transform():
    ...


with timerx.lap("preprocessing"):
    ...


timerx.start("postprocess")
...
elapsed = timerx.stop("postprocess")

print(elapsed)
print(timerx.summary())
```

## Decorator

`track` works with or without parentheses and supports sync and async functions.
It records calls that return normally and calls that raise.

```python
@timerx.track
def sync_work():
    ...


@timerx.track()
def also_sync_work():
    ...


@timerx.track(name="fetch")
async def async_work():
    ...
```

Stats accumulate across calls:

```python
sync_work()
sync_work()

stats = timerx.get_stats()
print(stats["sync_work"]["count"])
print(stats["sync_work"]["avg"])
```

## Laps

`lap` records a named block. It records in `finally`, so exceptions are included,
and nested laps work naturally.

```python
with timerx.lap("outer"):
    with timerx.lap("inner"):
        ...
```

## Stopwatches

Named stopwatches can run concurrently. Multiple starts with the same name are
stacked, so each `stop(name)` closes the most recent start.

```python
timerx.start("download")
timerx.start("parse")

timerx.stop("parse")
timerx.stop("download")
```

## Summaries

```python
print(timerx.summary())
print(timerx.summary(unit="ms"))
```

Supported units are `auto`, `s`, `ms`, `us`, and `µs`. Auto mode picks seconds,
milliseconds, or microseconds per value.

Example output:

```text
name           count  total    avg      min      max      last
-------------  -----  -------  -------  -------  -------  -------
preprocessing  1      5.12ms   5.12ms   5.12ms   5.12ms   5.12ms
```

## Programmatic Stats

`get_stats()` returns plain dictionaries:

```python
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

## Isolated Instances

Use `TimerX()` when building libraries or tests that should not write into
timerx's global state.

```python
from timerx import TimerX

tx = TimerX()

with tx.lap("local"):
    ...

print(tx.get_stats())
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
