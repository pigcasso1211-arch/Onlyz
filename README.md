# 每日 11 点监控 7 家交易所活期存款利率

这是一个可配置的 Python 脚本：每天固定时间（默认上海时间 11:00）采集多交易所、多币种的活期存款 APR，并支持 webhook 告警。

## 功能

- 每天定时执行（默认 11:00）。
- 支持 7 家交易所、多个币种。
- 支持两种数据源：
  - `manual`：先手动录入 APR，快速跑通流程。
  - `http_json`：接交易所 API 自动拉取并解析 JSON。
- 可选 webhook 通知，支持低于阈值高亮。
- **零第三方依赖**（仅 Python 标准库）。

## 快速开始

```bash
cp config.example.json config.json
python3 monitor_rates.py --config config.json --once
```

长期运行（每天自动执行）：

```bash
python3 monitor_rates.py --config config.json
```

## 配置结构

### 定时

```json
"timezone": "Asia/Shanghai",
"schedule": {
  "hour": 11,
  "minute": 0
}
```

### 交易所配置

#### manual 示例

```json
{
  "name": "Binance",
  "coins": ["USDT", "BTC"],
  "source": {
    "kind": "manual",
    "apr_map": {
      "USDT": 3.1,
      "BTC": 1.2
    }
  }
}
```

#### http_json 示例

```json
{
  "name": "ExampleEx",
  "coins": ["USDT", "BTC"],
  "source": {
    "kind": "http_json",
    "url": "https://api.example.com/v1/earn/apr",
    "method": "GET",
    "symbol_param": "symbol",
    "params": {
      "accountType": "flexible"
    },
    "headers": {
      "X-API-KEY": "YOUR_KEY_IF_NEEDED"
    },
    "json_path": "data.0.apr"
  }
}
```

### webhook 通知

```json
"notify": {
  "webhook_url": "https://your-webhook",
  "alert_apr_below": 1.5
}
```

## 实际接入建议

当前示例中的 7 家交易所都使用 `manual`（便于你马上运行）。你可以逐个替换为各交易所真实接口（`http_json`），实现全自动监控。
