import asyncio
import random

from oopsys_python import configure, guard, timeit
from structlog import getLogger

logger = getLogger("PARSER")

_FEED = ["10.5", "20.0", "bad-row", "30.25", "", "42", "NaNaN", "7.7"]


@timeit
@guard(fallback=None)
def parse_prices(rows: list[str]) -> float:
    values = [float(row) for row in rows]
    return sum(values) / len(values)


@guard(critical=True, fallback=0)
def risky_division(total: float) -> float:
    divisor = random.choice([2, 4, 0])  # noqa: S311
    return total / divisor


async def main() -> None:
    configure()
    await logger.ainfo("parser started")

    cycle = 0
    while True:
        cycle += 1
        batch = random.sample(_FEED, k=random.randint(1, len(_FEED)))  # noqa: S311
        average = parse_prices(batch)

        if average is None:
            await logger.awarning("batch skipped due to parse error", cycle=cycle, batch=batch)
        else:
            result = risky_division(average)
            await logger.ainfo("batch parsed", cycle=cycle, average=round(average, 2), result=round(result, 2))

        await asyncio.sleep(3)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("parser stopped by user")
