import asyncio
import re

import pytest

import timerx
from timerx import TimerX


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TestTrackDecorator:
    def test_track_without_parentheses_records_sync_call(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)

        @tx.track
        def work() -> str:
            clock.advance(0.25)
            return "done"

        assert work() == "done"
        assert tx.get_stats()["work"]["count"] == 1
        assert tx.get_stats()["work"]["total"] == pytest.approx(0.25)

    def test_track_with_parentheses_records_sync_call(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)

        @tx.track()
        def work() -> None:
            clock.advance(0.1)

        work()
        assert tx.get_stats()["work"]["last"] == pytest.approx(0.1)

    def test_track_accepts_custom_name(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)

        @tx.track(name="custom")
        def work() -> None:
            clock.advance(0.2)

        work()
        assert "custom" in tx.get_stats()

    def test_track_accumulates_multiple_calls(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)

        @tx.track
        def work(seconds: float) -> None:
            clock.advance(seconds)

        work(0.1)
        work(0.3)
        stats = tx.get_stats()["work"]
        assert stats["count"] == 2
        assert stats["total"] == pytest.approx(0.4)
        assert stats["avg"] == pytest.approx(0.2)
        assert stats["min"] == pytest.approx(0.1)
        assert stats["max"] == pytest.approx(0.3)

    def test_track_records_when_function_raises(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)

        @tx.track
        def boom() -> None:
            clock.advance(0.4)
            raise ValueError("broken")

        with pytest.raises(ValueError):
            boom()
        assert tx.get_stats()["boom"]["total"] == pytest.approx(0.4)

    def test_track_preserves_function_metadata(self) -> None:
        tx = TimerX()

        @tx.track
        def work() -> None:
            """docstring"""

        assert work.__name__ == "work"
        assert work.__doc__ == "docstring"

    def test_track_rejects_empty_name(self) -> None:
        tx = TimerX()

        with pytest.raises(ValueError):
            @tx.track(name="")
            def work() -> None:
                pass


class TestAsyncTrack:
    def test_track_records_async_call(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)

        @tx.track
        async def work() -> str:
            clock.advance(0.05)
            return "async"

        assert asyncio.run(work()) == "async"
        assert tx.get_stats()["work"]["total"] == pytest.approx(0.05)

    def test_track_records_async_exception(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)

        @tx.track
        async def boom() -> None:
            clock.advance(0.07)
            raise RuntimeError("broken")

        with pytest.raises(RuntimeError):
            asyncio.run(boom())
        assert tx.get_stats()["boom"]["count"] == 1

    def test_async_wrapper_remains_coroutine_function(self) -> None:
        tx = TimerX()

        @tx.track
        async def work() -> None:
            pass

        assert asyncio.iscoroutinefunction(work)


class TestLapContextManager:
    def test_lap_records_elapsed_time(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)

        with tx.lap("load"):
            clock.advance(0.2)

        assert tx.get_stats()["load"]["last"] == pytest.approx(0.2)

    def test_lap_records_on_exception(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)

        with pytest.raises(ValueError):
            with tx.lap("load"):
                clock.advance(0.3)
                raise ValueError("bad")

        assert tx.get_stats()["load"]["total"] == pytest.approx(0.3)

    def test_lap_supports_nesting(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)

        with tx.lap("outer"):
            clock.advance(0.1)
            with tx.lap("inner"):
                clock.advance(0.2)
            clock.advance(0.3)

        assert tx.get_stats()["inner"]["last"] == pytest.approx(0.2)
        assert tx.get_stats()["outer"]["last"] == pytest.approx(0.6)

    def test_lap_rejects_empty_name(self) -> None:
        tx = TimerX()

        with pytest.raises(ValueError):
            tx.lap("")


class TestStopwatches:
    def test_start_stop_records_and_returns_elapsed(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)

        tx.start("job")
        clock.advance(0.5)

        assert tx.stop("job") == pytest.approx(0.5)
        assert tx.get_stats()["job"]["total"] == pytest.approx(0.5)

    def test_named_stopwatches_can_run_concurrently(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)

        tx.start("a")
        clock.advance(0.1)
        tx.start("b")
        clock.advance(0.2)

        assert tx.stop("a") == pytest.approx(0.3)
        clock.advance(0.3)
        assert tx.stop("b") == pytest.approx(0.5)

    def test_same_name_stopwatches_are_stacked(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)

        tx.start("job")
        clock.advance(0.1)
        tx.start("job")
        clock.advance(0.2)

        assert tx.stop("job") == pytest.approx(0.2)
        clock.advance(0.3)
        assert tx.stop("job") == pytest.approx(0.6)

    def test_stop_without_start_raises_key_error(self) -> None:
        tx = TimerX()

        with pytest.raises(KeyError):
            tx.stop("missing")

    def test_start_rejects_empty_name(self) -> None:
        tx = TimerX()

        with pytest.raises(ValueError):
            tx.start("")


class TestSummaryAndStats:
    def test_get_stats_returns_plain_dict_copy(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)
        tx.start("job")
        clock.advance(0.25)
        tx.stop("job")

        stats = tx.get_stats()
        stats["job"]["count"] = 99

        assert tx.get_stats()["job"]["count"] == 1

    def test_summary_returns_table(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)
        tx.start("job")
        clock.advance(0.25)
        tx.stop("job")

        text = tx.summary()

        assert "name" in text
        assert "job" in text
        assert "250ms" in text

    def test_summary_empty_state_is_clear(self) -> None:
        assert TimerX().summary() == "timerx: no timings recorded"

    def test_summary_supports_seconds_unit(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)
        tx.start("job")
        clock.advance(2)
        tx.stop("job")

        assert re.search(r"2s\b", tx.summary(unit="s"))

    def test_summary_supports_milliseconds_unit(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)
        tx.start("job")
        clock.advance(0.002)
        tx.stop("job")

        assert "2ms" in tx.summary(unit="ms")

    def test_summary_supports_microseconds_alias(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)
        tx.start("job")
        clock.advance(0.000002)
        tx.stop("job")

        assert "2µs" in tx.summary(unit="us")

    def test_summary_supports_microseconds_spelled_out(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)
        tx.start("job")
        clock.advance(0.000002)
        tx.stop("job")

        assert "2µs" in tx.summary(unit="microseconds")

    def test_summary_rejects_unknown_unit(self) -> None:
        with pytest.raises(ValueError):
            TimerX().summary(unit="minutes")

    def test_summary_sort_by_total(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)
        tx.start("fast")
        clock.advance(0.1)
        tx.stop("fast")
        tx.start("slow")
        clock.advance(0.5)
        tx.stop("slow")

        lines = tx.summary(sort_by="total").splitlines()
        assert lines[2].startswith("slow")
        assert lines[3].startswith("fast")

    def test_summary_rejects_invalid_sort_by(self) -> None:
        with pytest.raises(ValueError):
            TimerX().summary(sort_by="unknown")

    def test_summary_right_aligns_numeric_columns(self) -> None:
        clock = FakeClock()
        tx = TimerX(clock=clock)
        with tx.lap("job"):
            pass

        data_line = tx.summary().splitlines()[2]
        # "count" header is 5 chars wide; value "1" right-aligned gives "    1"
        assert "    1" in data_line

    def test_reset_clears_records_and_running_stopwatches(self) -> None:
        tx = TimerX()
        tx.start("job")
        tx.reset()

        assert tx.get_stats() == {}
        with pytest.raises(KeyError):
            tx.stop("job")


class TestGlobalApi:
    def test_public_api_exports_global_helpers(self) -> None:
        timerx.reset()

        @timerx.track
        def work() -> None:
            pass

        work()

        assert "work" in timerx.get_stats()

    def test_isolated_instances_do_not_touch_global_state(self) -> None:
        timerx.reset()
        tx = TimerX()

        with tx.lap("local"):
            pass

        assert "local" in tx.get_stats()
        assert timerx.get_stats() == {}
