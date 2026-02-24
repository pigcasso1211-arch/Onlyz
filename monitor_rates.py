#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List
from zoneinfo import ZoneInfo


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("deposit-rate-monitor")


@dataclass
class CoinRate:
    exchange: str
    symbol: str
    apr: float
    source: str
    timestamp: str


class BaseSource:
    def fetch(self, exchange_name: str, coins: List[str]) -> List[CoinRate]:
        raise NotImplementedError


class ManualSource(BaseSource):
    def __init__(self, apr_map: Dict[str, float]):
        self.apr_map = apr_map

    def fetch(self, exchange_name: str, coins: List[str]) -> List[CoinRate]:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        rows: List[CoinRate] = []
        for symbol in coins:
            apr = self.apr_map.get(symbol)
            if apr is None:
                logger.warning("%s 缺少 %s 的 APR 手动配置", exchange_name, symbol)
                continue
            rows.append(CoinRate(exchange_name, symbol, float(apr), "manual", now))
        return rows


class HttpJsonSource(BaseSource):
    def __init__(self, cfg: Dict[str, Any]):
        self.url = cfg["url"]
        self.method = cfg.get("method", "GET").upper()
        self.headers = cfg.get("headers", {})
        self.params = cfg.get("params", {})
        self.timeout_s = int(cfg.get("timeout_s", 15))
        self.symbol_param = cfg.get("symbol_param", "symbol")
        self.json_path = cfg["json_path"]

    @staticmethod
    def _extract_json_path(payload: Any, path: str) -> Any:
        cur = payload
        for part in path.split("."):
            if isinstance(cur, list):
                cur = cur[int(part)]
            else:
                cur = cur[part]
        return cur

    def _request_json(self, params: Dict[str, Any]) -> Any:
        url = self.url
        data = None
        if self.method == "GET":
            query = urllib.parse.urlencode(params)
            sep = "&" if "?" in self.url else "?"
            url = f"{self.url}{sep}{query}" if query else self.url
        else:
            data = json.dumps(params).encode("utf-8")

        req = urllib.request.Request(url=url, method=self.method)
        for k, v in self.headers.items():
            req.add_header(k, str(v))
        if data is not None:
            req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, data=data, timeout=self.timeout_s) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)

    def fetch(self, exchange_name: str, coins: List[str]) -> List[CoinRate]:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        rows: List[CoinRate] = []
        for symbol in coins:
            params = dict(self.params)
            params[self.symbol_param] = symbol
            try:
                payload = self._request_json(params)
                apr = float(self._extract_json_path(payload, self.json_path))
                rows.append(CoinRate(exchange_name, symbol, apr, self.url, now))
            except Exception as exc:  # noqa: BLE001
                logger.exception("%s/%s 拉取失败: %s", exchange_name, symbol, exc)
        return rows


class Monitor:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg

    def _build_source(self, source_cfg: Dict[str, Any]) -> BaseSource:
        kind = source_cfg["kind"]
        if kind == "manual":
            return ManualSource(apr_map=source_cfg.get("apr_map", {}))
        if kind == "http_json":
            return HttpJsonSource(source_cfg)
        raise ValueError(f"不支持的 source.kind: {kind}")

    def run_once(self) -> List[CoinRate]:
        output: List[CoinRate] = []
        exchanges = self.cfg.get("exchanges", [])
        for ex in exchanges:
            name = ex["name"]
            coins = ex["coins"]
            source = self._build_source(ex["source"])
            output.extend(source.fetch(name, coins))
        self._print_table(output)
        self._emit_webhook(output)
        return output

    def _print_table(self, rows: List[CoinRate]) -> None:
        if not rows:
            logger.warning("本次没有采集到任何利率")
            return
        logger.info("\n%-12s %-8s %-8s %s", "Exchange", "Coin", "APR%", "Timestamp")
        logger.info("%s", "-" * 62)
        for r in sorted(rows, key=lambda x: (x.exchange, x.symbol)):
            logger.info("%-12s %-8s %-8.4f %s", r.exchange, r.symbol, r.apr, r.timestamp)

    def _emit_webhook(self, rows: List[CoinRate]) -> None:
        if not rows:
            return
        notify_cfg = self.cfg.get("notify", {})
        webhook = notify_cfg.get("webhook_url")
        if not webhook:
            return

        threshold = notify_cfg.get("alert_apr_below")
        lines = [f"{r.exchange} {r.symbol}: {r.apr:.4f}%" for r in rows]
        content = "\n".join(lines)
        if threshold is not None:
            below = [r for r in rows if r.apr < float(threshold)]
            if below:
                content += "\n\n⚠️ 低于阈值：\n" + "\n".join(
                    f"{r.exchange} {r.symbol}: {r.apr:.4f}%" for r in below
                )

        payload = json.dumps({"text": content}).encode("utf-8")
        req = urllib.request.Request(webhook, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10):
                logger.info("告警推送成功")
        except Exception as exc:  # noqa: BLE001
            logger.exception("告警推送失败: %s", exc)


def load_cfg(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def seconds_until(hour: int, minute: int, tz_name: str) -> float:
    now = dt.datetime.now(ZoneInfo(tz_name))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += dt.timedelta(days=1)
    return (target - now).total_seconds()


def main() -> None:
    parser = argparse.ArgumentParser(description="每日11点监控多交易所活期存款利率")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--once", action="store_true", help="只执行一次")
    args = parser.parse_args()

    cfg = load_cfg(args.config)
    monitor = Monitor(cfg)

    if args.once:
        monitor.run_once()
        return

    tz = cfg.get("timezone", "Asia/Shanghai")
    hour = int(cfg.get("schedule", {}).get("hour", 11))
    minute = int(cfg.get("schedule", {}).get("minute", 0))

    logger.info("调度已启动：每天 %02d:%02d (%s)", hour, minute, tz)
    while True:
        wait = seconds_until(hour, minute, tz)
        logger.info("距离下次执行还有 %.0f 秒", wait)
        time.sleep(wait)
        monitor.run_once()


if __name__ == "__main__":
    main()
