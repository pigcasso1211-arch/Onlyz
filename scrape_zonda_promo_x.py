#!/usr/bin/env python3
"""Scrape likely promotional X posts mentioning zonda in the last 12 months.

This script uses snscrape (no official X API token required) and applies
heuristics to find promotional content across languages.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import snscrape.modules.twitter as sntwitter


DEFAULT_TERMS = [
    "zonda",
    "zondacrypto",
    "@zondacrypto",
    "@zondacryptopl",
    '"zonda exchange"',
]

# Multi-language promo indicators (heuristic).
DEFAULT_PROMO_KEYWORDS = [
    "promo",
    "promotion",
    "promoted",
    "sponsored",
    '"paid partnership"',
    "ad",
    "ambassador",
    "affiliate",
    "referral",
    '"ref code"',
    "bonus",
    "giveaway",
    "airdrop",
    "campaign",
    "partner",
    "reklama",
    "współpraca",
    "polecam",
    "kod",
    "推荐",
    "返佣",
    "邀请",
    "推广",
    "プロモ",
    "紹介コード",
    "afiliado",
    "patrocinado",
]


@dataclass
class PostRow:
    id: int
    date_utc: str
    username: str
    display_name: str
    url: str
    text: str
    like_count: int
    repost_count: int
    reply_count: int
    quote_count: int
    lang: str | None
    matched_terms: str
    matched_keywords: str


def build_query(terms: list[str], keywords: list[str], since: dt.date, until: dt.date) -> str:
    terms_group = "(" + " OR ".join(terms) + ")"
    keywords_group = "(" + " OR ".join(keywords) + ")"
    return f"{terms_group} {keywords_group} since:{since.isoformat()} until:{until.isoformat()}"


def find_matches(text: str, candidates: Iterable[str]) -> list[str]:
    lower = text.lower()
    matched: list[str] = []
    for c in candidates:
        cleaned = c.strip('"').lower()
        if cleaned and cleaned in lower:
            matched.append(c)
    return matched


def scrape(query: str, max_results: int | None, terms: list[str], keywords: list[str]) -> list[PostRow]:
    rows: list[PostRow] = []
    seen_urls: set[str] = set()

    scraper = sntwitter.TwitterSearchScraper(query)
    for i, tweet in enumerate(scraper.get_items()):
        if max_results is not None and i >= max_results:
            break

        text = tweet.rawContent or ""
        matched_terms = find_matches(text + " " + (tweet.url or ""), terms)
        matched_keywords = find_matches(text, keywords)

        # Keep strict promo filter.
        if not matched_keywords:
            continue

        if tweet.url in seen_urls:
            continue
        seen_urls.add(tweet.url)

        rows.append(
            PostRow(
                id=tweet.id,
                date_utc=tweet.date.astimezone(dt.timezone.utc).isoformat(),
                username=tweet.user.username,
                display_name=tweet.user.displayname,
                url=tweet.url,
                text=text.replace("\n", " ").strip(),
                like_count=tweet.likeCount,
                repost_count=tweet.retweetCount,
                reply_count=tweet.replyCount,
                quote_count=tweet.quoteCount,
                lang=getattr(tweet, "lang", None),
                matched_terms=",".join(matched_terms),
                matched_keywords=",".join(matched_keywords),
            )
        )

    return rows


def write_csv(rows: list[PostRow], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()) if rows else list(PostRow.__annotations__.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_json(rows: list[PostRow], output_json: Path, query: str) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "query": query,
        "count": len(rows),
        "results": [asdict(r) for r in rows],
    }
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape likely promotional X posts mentioning zonda (last 12 months by default).")
    parser.add_argument("--since", type=str, default=None, help="Start date (YYYY-MM-DD). Default: today - 365 days.")
    parser.add_argument("--until", type=str, default=None, help="End date (YYYY-MM-DD). Default: today.")
    parser.add_argument("--max-results", type=int, default=3000, help="Maximum items to scan from search results.")
    parser.add_argument("--output-csv", type=Path, default=Path("output/zonda_promo_posts_12m.csv"))
    parser.add_argument("--output-json", type=Path, default=Path("output/zonda_promo_posts_12m.json"))
    parser.add_argument("--extra-keyword", action="append", default=[], help="Additional promo keyword. Repeatable.")
    parser.add_argument("--extra-term", action="append", default=[], help="Additional zonda mention term. Repeatable.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    today = dt.date.today()

    since = dt.date.fromisoformat(args.since) if args.since else today - dt.timedelta(days=365)
    until = dt.date.fromisoformat(args.until) if args.until else today

    terms = DEFAULT_TERMS + args.extra_term
    keywords = DEFAULT_PROMO_KEYWORDS + args.extra_keyword

    query = build_query(terms, keywords, since, until)
    rows = scrape(query=query, max_results=args.max_results, terms=terms, keywords=keywords)

    write_csv(rows, args.output_csv)
    write_json(rows, args.output_json, query)

    print(f"Query: {query}")
    print(f"Saved {len(rows)} rows -> {args.output_csv}")
    print(f"Saved {len(rows)} rows -> {args.output_json}")


if __name__ == "__main__":
    main()
