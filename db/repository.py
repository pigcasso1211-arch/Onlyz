from collections.abc import Iterable

from db.schema import RateHistory, SessionLocal
from models import RateRecord


class RateRepository:
    def save_many(self, records: Iterable[RateRecord]) -> int:
        rows = []
        for record in records:
            rows.append(
                RateHistory(
                    platform=record.platform,
                    product_type=record.product_type,
                    asset=record.asset,
                    rate_type=record.rate_type.value,
                    base_rate=record.base_rate,
                    promo_rate=record.promo_rate,
                    total_rate=record.total_rate,
                    effective_apr=record.effective_apr,
                    source=record.source.value,
                    as_of=record.as_of,
                    raw_payload=record.raw_payload,
                )
            )

        if not rows:
            return 0

        with SessionLocal() as session:
            session.add_all(rows)
            session.commit()

        return len(rows)
