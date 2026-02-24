# 每日交易所币种汇率监控程序

这个小程序会定时抓取多个交易所（Binance / Coinbase / Kraken）上多个币种的价格，按天保存快照，便于你做日常跟踪和价差观察。

## 功能

- 支持多个交易所
- 支持多个币种（默认 BTC, ETH, SOL）
- 默认每 24 小时抓取一次
- 输出两种文件：
  - `data/rates.csv`：所有抓取明细
  - `data/rates-YYYY-MM-DD.json`：每日快照（含各币种交易所间价差）

## 使用方法

```bash
python3 monitor_rates.py --once
```

### 常见参数

```bash
python3 monitor_rates.py \
  --coins BTC,ETH,BNB \
  --quote USD \
  --interval-hours 24
```

- `--coins`：逗号分隔币种列表
- `--quote`：计价币种（默认 `USD`）
- `--interval-hours`：轮询间隔（小时）
- `--once`：只执行一次（建议先用这个测试）

## 后台长期运行（Linux）

可结合 `nohup` 或 systemd 使用，例如：

```bash
nohup python3 monitor_rates.py --coins BTC,ETH,SOL --interval-hours 24 > monitor.log 2>&1 &
```

## 说明

- Binance 的 USD 报价内部会使用 USDT 对（如 `BTCUSDT`）近似替代。
- 若某交易所某币对暂不可用，会输出 warning，但不会中断整个任务。
