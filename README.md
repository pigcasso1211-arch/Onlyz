# Yield Harvester (MVP)

多平台活期利率自动采集脚手架（先实现 Bitget 示例），可扩展到 Binance/OKX/Bybit/MEXC/Gate/Coinbase 以及 Aave/Compound/Jito/Marinade/Tonstakers。

## 功能

- 统一 `RateRecord` 数据模型（APR/APY + effective_apr）
- 定时任务采集（APScheduler）
- PostgreSQL 入库（SQLAlchemy）
- Adapter 模式，便于扩展各平台

## 快速开始

```bash
cp .env.example .env
docker compose up -d db
python -m venv .venv && source .venv/bin/activate
pip install -e .
python scheduler.py
```

## 目录

- `adapters/`: 各平台抓取器
- `db/`: 表结构与仓储
- `models.py`: 统一数据模型
- `scheduler.py`: 定时调度入口

## 扩展建议

1. 每个平台新增 `adapters/<platform>_adapter.py`
2. 在 `scheduler.py` 中注册 adapter
3. 若平台无公开 API，用 Playwright 兜底抓取公开页面
4. DeFi 优先链上读取（RPC）而非页面抓取
