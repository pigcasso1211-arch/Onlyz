#!/usr/bin/env python3
"""Monitor daily crypto rates across multiple exchanges.

The script fetches spot prices for configured coins from Binance, Coinbase,
and Kraken, then stores snapshots to CSV and JSON files.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class PriceRecord:
    timestamp_utc: str
    exchange: str
    symbol: str
    quote: str
    price: float


class ExchangeClient:
    name: str = "base"

    def fetch_price(self, coin: str, quote: str) -> Optional[float]:
        raise NotImplementedError

    def _get_json(self, url: str) -> dict:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "RateMonitor/1.0",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))


class BinanceClient(ExchangeClient):
    name = "binance"

    def fetch_price(self, coin: str, quote: str) -> Optional[float]:
        pair_quote = "USDT" if quote.upper() == "USD" else quote.upper()
        symbol = f"{coin.upper()}{pair_quote}"
        url = (
            "https://api.binance.com/api/v3/ticker/price?"
            + urllib.parse.urlencode({"symbol": symbol})
        )
        data = self._get_json(url)
        return float(data["price"])


class CoinbaseClient(ExchangeClient):
    name = "coinbase"

    def fetch_price(self, coin: str, quote: str) -> Optional[float]:
        product = f"{coin.upper()}-{quote.upper()}"
        url = f"https://api.exchange.coinbase.com/products/{product}/ticker"
        data = self._get_json(url)
        return float(data["price"])


class KrakenClient(ExchangeClient):
    name = "kraken"

    _coin_alias = {
        "BTC": "XBT",
    }

    def fetch_price(self, coin: str, quote: str) -> Optional[float]:
        pair = f"{self._coin_alias.get(coin.upper(), coin.upper())}{quote.upper()}"
        url = "https://api.kraken.com/0/public/Ticker?" + urllib.parse.urlencode(
            {"pair": pair}
        )
        data = self._get_json(url)
        result = data.get("result", {})
        if not result:
            raise ValueError(f"Kraken has no data for pair {pair}")
        first_pair = next(iter(result.values()))
        close_info = first_pair.get("c")
        if not close_info:
            raise ValueError(f"Kraken response missing close price for {pair}")
        return float(close_info[0])


def collect_prices(clients: List[ExchangeClient], coins: List[str], quote: str) -> List[PriceRecord]:
    records: List[PriceRecord] = []
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    for client in clients:
        for coin in coins:
            try:
                price = client.fetch_price(coin, quote)
                if price is None:
                    continue
                records.append(
                    PriceRecord(
                        timestamp_utc=now,
                        exchange=client.name,
                        symbol=coin.upper(),
                        quote=quote.upper(),
                        price=price,
                    )
                )
            except (urllib.error.URLError, ValueError, KeyError, TimeoutError) as exc:
                print(f"[WARN] {client.name} {coin}/{quote}: {exc}")
    return records


def write_csv(records: List[PriceRecord], csv_path: pathlib.Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        if not file_exists:
            writer.writerow(["timestamp_utc", "exchange", "symbol", "quote", "price"])
        for record in records:
            writer.writerow(
                [
                    record.timestamp_utc,
                    record.exchange,
                    record.symbol,
                    record.quote,
                    f"{record.price:.8f}",
                ]
            )


def write_daily_json(records: List[PriceRecord], output_dir: pathlib.Path) -> pathlib.Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    json_path = output_dir / f"rates-{day}.json"

    if json_path.exists():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    else:
        payload = {"date": day, "snapshots": []}

    payload["snapshots"].append(
        {
            "timestamp_utc": records[0].timestamp_utc if records else dt.datetime.now(dt.timezone.utc).isoformat(),
            "records": [record.__dict__ for record in records],
            "spread": calculate_spread(records),
        }
    )
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return json_path


def calculate_spread(records: List[PriceRecord]) -> Dict[str, Dict[str, float]]:
    grouped: Dict[str, List[float]] = {}
    for record in records:
        grouped.setdefault(record.symbol, []).append(record.price)

    spread: Dict[str, Dict[str, float]] = {}
    for symbol, prices in grouped.items():
        if not prices:
            continue
        min_price = min(prices)
        max_price = max(prices)
        diff = max_price - min_price
        pct = (diff / min_price * 100) if min_price else 0.0
        spread[symbol] = {
            "min": min_price,
            "max": max_price,
            "diff": diff,
            "diff_pct": pct,
        }
    return spread


def print_summary(records: List[PriceRecord]) -> None:
    if not records:
        print("[INFO] No price records collected.")
        return

    spread = calculate_spread(records)
    print("\n=== Snapshot Summary ===")
    for symbol, info in spread.items():
        print(
            f"{symbol}: min={info['min']:.4f} max={info['max']:.4f} "
            f"diff={info['diff']:.4f} ({info['diff_pct']:.2f}%)"
        )


def run_loop(coins: List[str], quote: str, csv_path: pathlib.Path, output_dir: pathlib.Path, interval_hours: float, once: bool) -> None:
    clients: List[ExchangeClient] = [BinanceClient(), CoinbaseClient(), KrakenClient()]
    interval_seconds = max(1, int(interval_hours * 3600))

    while True:
        records = collect_prices(clients, coins, quote)
        write_csv(records, csv_path)
        json_path = write_daily_json(records, output_dir)
        print_summary(records)
        print(f"[INFO] Saved {len(records)} rows -> {csv_path}")
        print(f"[INFO] Updated daily snapshot -> {json_path}\n")

        if once:
            break
        print(f"[INFO] Sleeping for {interval_seconds} seconds...")
        time.sleep(interval_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor daily exchange rates for multiple exchanges.")
    parser.add_argument("--coins", default="BTC,ETH,SOL", help="Comma-separated coin symbols (default: BTC,ETH,SOL)")
    parser.add_argument("--quote", default="USD", help="Quote currency, e.g. USD (default: USD)")
    parser.add_argument("--interval-hours", type=float, default=24, help="Polling interval in hours (default: 24)")
    parser.add_argument("--csv", default="data/rates.csv", help="CSV output path")
    parser.add_argument("--output-dir", default="data", help="Directory for daily JSON snapshots")
    parser.add_argument("--once", action="store_true", help="Run one collection cycle and exit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    coins = [coin.strip().upper() for coin in args.coins.split(",") if coin.strip()]
    if not coins:
        raise SystemExit("No coin symbols provided.")

    run_loop(
        coins=coins,
        quote=args.quote.upper(),
        csv_path=pathlib.Path(args.csv),
        output_dir=pathlib.Path(args.output_dir),
        interval_hours=args.interval_hours,
        once=args.once,
    )


if __name__ == "__main__":
    main()
