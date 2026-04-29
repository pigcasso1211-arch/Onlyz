import asyncio
import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from adapters.bitget_adapter import BitgetAdapter
from config import settings
from db.repository import RateRepository
from db.schema import init_db

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)


async def collect_once() -> None:
    repo = RateRepository()
    adapters = [BitgetAdapter(timeout_seconds=settings.http_timeout_seconds)]

    all_records = []
    for adapter in adapters:
        try:
            records = await adapter.fetch_rates()
            all_records.extend(records)
            logger.info("adapter=%s records=%s", adapter.platform, len(records))
        except Exception as exc:  # noqa: BLE001
            logger.exception("adapter=%s failed: %s", adapter.platform, exc)

    saved = repo.save_many(all_records)
    logger.info("saved=%s", saved)


def run_job() -> None:
    asyncio.run(collect_once())


def main() -> None:
    init_db()
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_job, "interval", minutes=settings.fetch_interval_minutes, max_instances=1)
    logger.info("scheduler started, interval=%s minutes", settings.fetch_interval_minutes)
    run_job()
    scheduler.start()


if __name__ == "__main__":
    main()
