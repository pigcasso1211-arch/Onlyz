from sqlalchemy import JSON, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config import settings


class Base(DeclarativeBase):
    pass


class RateHistory(Base):
    __tablename__ = "rates_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(32), index=True)
    product_type: Mapped[str] = mapped_column(String(32), index=True)
    asset: Mapped[str] = mapped_column(String(16), index=True)
    rate_type: Mapped[str] = mapped_column(String(8))
    base_rate: Mapped[float] = mapped_column(Float)
    promo_rate: Mapped[float] = mapped_column(Float)
    total_rate: Mapped[float] = mapped_column(Float)
    effective_apr: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(16))
    as_of: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON)


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
