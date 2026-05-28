"""Public API for timerx."""

from .core import TimerX

_global = TimerX()

track = _global.track
lap = _global.lap
start = _global.start
stop = _global.stop
summary = _global.summary
get_stats = _global.get_stats
reset = _global.reset

__all__ = [
    "TimerX",
    "track",
    "lap",
    "start",
    "stop",
    "summary",
    "get_stats",
    "reset",
]
