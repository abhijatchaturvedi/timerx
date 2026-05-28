"""Feature showcase for timerx."""

from __future__ import annotations

import asyncio
import time

import timerx
from timerx import TimerX


@timerx.track
def train_model() -> None:
    time.sleep(0.02)


@timerx.track(name="async_fetch")
async def fetch_data() -> str:
    await asyncio.sleep(0.01)
    return "rows"


async def main() -> None:
    train_model()
    train_model()

    with timerx.lap("preprocessing"):
        time.sleep(0.005)
        with timerx.lap("feature_engineering"):
            time.sleep(0.004)

    timerx.start("postprocess")
    time.sleep(0.003)
    timerx.stop("postprocess")

    await fetch_data()

    print("Global timer summary")
    print(timerx.summary())

    local = TimerX()
    with local.lap("isolated"):
        time.sleep(0.001)
    print("\nIsolated instance stats")
    print(local.get_stats())


if __name__ == "__main__":
    asyncio.run(main())
