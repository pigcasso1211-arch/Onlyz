from abc import ABC, abstractmethod

from models import RateRecord


class BaseAdapter(ABC):
    platform: str

    @abstractmethod
    async def fetch_rates(self) -> list[RateRecord]:
        raise NotImplementedError
