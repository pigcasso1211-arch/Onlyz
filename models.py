from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RateType(str, Enum):
    APR = "APR"
    APY = "APY"


class SourceType(str, Enum):
    API = "api"
    ONCHAIN = "onchain"
    SCRAPE = "scrape"


class RateRecord(BaseModel):
    platform: str
    product_type: str = "flexible"
    asset: str
    rate_type: RateType
    base_rate: float = Field(ge=0)
    promo_rate: float = Field(default=0, ge=0)
    total_rate: float = Field(ge=0)
    source: SourceType
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: dict[str, Any]

    @property
    def effective_apr(self) -> float:
        if self.rate_type == RateType.APR:
            return self.total_rate
        # APY -> APR (daily compounding approximation)
        daily = (1 + self.total_rate) ** (1 / 365) - 1
        return daily * 365
