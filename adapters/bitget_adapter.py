from datetime import datetime, timezone

import httpx

from adapters.base import BaseAdapter
from models import RateRecord, RateType, SourceType


class BitgetAdapter(BaseAdapter):
    platform = "bitget"

    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    async def fetch_rates(self) -> list[RateRecord]:
        # NOTE: endpoint may evolve; keep parser defensive.
        url = "https://api.bitget.com/api/v2/earn/savings/public/product-list"
        params = {"productType": "current", "pageNo": 1, "pageSize": 100}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()

        data = payload.get("data", {})
        products = data.get("productList", []) if isinstance(data, dict) else []

        now = datetime.now(timezone.utc)
        records: list[RateRecord] = []
        for p in products:
            asset = p.get("coin") or p.get("asset")
            apr_raw = p.get("apr") or p.get("rate") or "0"
            if not asset:
                continue
            total_rate = float(apr_raw)
            if total_rate > 1:
                total_rate = total_rate / 100
            records.append(
                RateRecord(
                    platform=self.platform,
                    product_type="flexible",
                    asset=asset.upper(),
                    rate_type=RateType.APR,
                    base_rate=total_rate,
                    promo_rate=0,
                    total_rate=total_rate,
                    source=SourceType.API,
                    as_of=now,
                    raw_payload=p,
                )
            )
        return records
