#!/usr/bin/env python3
import argparse
import csv
import json
import os
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dateutil import parser as dt_parser
from googleapiclient.discovery import build

TARGET_COUNTRIES = OrderedDict(
    {
        "Switzerland": {
            "code": "CH",
            "keywords": ["crypto", "bitcoin", "blockchain", "krypto"],
            "x_terms": ["Switzerland", "Swiss", "Suisse", "Schweiz"],
        },
        "France": {
            "code": "FR",
            "keywords": ["crypto", "bitcoin", "blockchain", "cryptomonnaie"],
            "x_terms": ["France", "Français", "French"],
        },
        "Germany": {
            "code": "DE",
            "keywords": ["krypto", "bitcoin", "blockchain", "crypto"],
            "x_terms": ["Germany", "Deutschland", "German"],
        },
        "Italy": {
            "code": "IT",
            "keywords": ["crypto", "bitcoin", "blockchain", "criptovalute"],
            "x_terms": ["Italy", "Italia", "Italian"],
        },
        "Netherlands": {
            "code": "NL",
            "keywords": ["crypto", "bitcoin", "blockchain", "nederland"],
            "x_terms": ["Netherlands", "Nederland", "Dutch"],
        },
        "Poland": {
            "code": "PL",
            "keywords": ["krypto", "bitcoin", "blockchain", "kryptowaluty"],
            "x_terms": ["Poland", "Polska", "Polish"],
        },
    }
)

UNIFIED_FIELDS = [
    "platform",
    "country",
    "creator_name",
    "creator_id",
    "profile_url",
    "followers",
    "content_count",
    "latest_post_published_at",
    "latest_post_url",
    "matched_query",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape EU crypto creators from YouTube and X.")
    parser.add_argument("--platform", choices=["youtube", "x", "both"], default="both")
    parser.add_argument("--min-subs", type=int, default=5_000)
    parser.add_argument("--max-subs", type=int, default=50_000)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--max-channels-per-country", type=int, default=80)
    parser.add_argument("--x-max-tweets-per-country", type=int, default=300)
    parser.add_argument("--output-csv", type=str, default="output/crypto_creators_eu.csv")
    parser.add_argument("--output-json", type=str, default="output/crypto_creators_eu.json")
    return parser.parse_args()


def get_youtube_client():
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing YOUTUBE_API_KEY environment variable.")
    return build("youtube", "v3", developerKey=api_key)


def get_x_bearer_token() -> str:
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        raise RuntimeError("Missing X_BEARER_TOKEN environment variable.")
    return token


def chunked(items: List[str], size: int = 50):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def search_candidate_channels(youtube, country_name: str, country_code: str, keywords: List[str], max_results: int):
    candidates = []
    for kw in keywords:
        query = f"{kw} {country_name}"
        page_token = None
        fetched = 0
        while fetched < max_results:
            req = youtube.search().list(
                part="snippet",
                q=query,
                type="channel",
                maxResults=min(50, max_results - fetched),
                regionCode=country_code,
                pageToken=page_token,
            )
            resp = req.execute()
            for item in resp.get("items", []):
                candidates.append(
                    {"channel_id": item["snippet"]["channelId"], "query": query, "country": country_name}
                )
            fetched += len(resp.get("items", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    return candidates


def get_channel_details(youtube, channel_ids: List[str]) -> Dict[str, dict]:
    details = {}
    for batch in chunked(channel_ids, 50):
        req = youtube.channels().list(part="snippet,statistics", id=",".join(batch), maxResults=50)
        resp = req.execute()
        for item in resp.get("items", []):
            details[item["id"]] = item
    return details


def latest_video_within_days(youtube, channel_id: str, days: int):
    published_after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")
    req = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        type="video",
        order="date",
        maxResults=1,
        publishedAfter=published_after,
    )
    resp = req.execute()
    items = resp.get("items", [])
    if not items:
        return None
    video = items[0]
    published_at = dt_parser.parse(video["snippet"]["publishedAt"])
    return {
        "published_at": published_at,
        "url": f"https://www.youtube.com/watch?v={video['id']['videoId']}",
    }


def run_youtube(youtube, min_subs: int, max_subs: int, days: int, max_channels_per_country: int):
    all_candidates = []
    for country, cfg in TARGET_COUNTRIES.items():
        all_candidates.extend(
            search_candidate_channels(
                youtube=youtube,
                country_name=country,
                country_code=cfg["code"],
                keywords=cfg["keywords"],
                max_results=max_channels_per_country,
            )
        )

    dedup = OrderedDict()
    for item in all_candidates:
        dedup.setdefault(item["channel_id"], item)

    channel_details = get_channel_details(youtube, list(dedup.keys()))

    rows = []
    for channel_id, meta in dedup.items():
        ch = channel_details.get(channel_id)
        if not ch:
            continue
        stats = ch.get("statistics", {})
        snippet = ch.get("snippet", {})
        subs = int(stats.get("subscriberCount", 0)) if stats.get("subscriberCount") else 0
        if subs < min_subs or subs > max_subs:
            continue

        latest = latest_video_within_days(youtube, channel_id, days)
        if not latest:
            continue

        rows.append(
            {
                "platform": "youtube",
                "country": meta["country"],
                "creator_name": snippet.get("title", ""),
                "creator_id": channel_id,
                "profile_url": f"https://www.youtube.com/channel/{channel_id}",
                "followers": subs,
                "content_count": int(stats.get("videoCount", 0)) if stats.get("videoCount") else 0,
                "latest_post_published_at": latest["published_at"].isoformat(),
                "latest_post_url": latest["url"],
                "matched_query": meta["query"],
            }
        )
    return rows


def x_recent_search(
    bearer_token: str,
    query: str,
    start_time: str,
    max_tweets: int,
) -> List[dict]:
    url = "https://api.x.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    params = {
        "query": query,
        "max_results": 100,
        "start_time": start_time,
        "tweet.fields": "created_at,author_id",
        "user.fields": "name,username,location,public_metrics",
        "expansions": "author_id",
    }

    collected = []
    next_token: Optional[str] = None
    while len(collected) < max_tweets:
        if next_token:
            params["next_token"] = next_token
        else:
            params.pop("next_token", None)

        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        tweets = payload.get("data", [])
        users = {u["id"]: u for u in payload.get("includes", {}).get("users", [])}

        for tw in tweets:
            user = users.get(tw.get("author_id"), {})
            if user:
                collected.append({"tweet": tw, "user": user})
            if len(collected) >= max_tweets:
                break

        next_token = payload.get("meta", {}).get("next_token")
        if not next_token:
            break

    return collected


def run_x(min_subs: int, max_subs: int, days: int, max_tweets_per_country: int):
    bearer = get_x_bearer_token()
    # X recent search API typically supports recent data; requesting 30 days may be constrained by your API tier.
    start_time = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")

    creators: Dict[str, dict] = {}
    for country, cfg in TARGET_COUNTRIES.items():
        base_terms = " OR ".join(["crypto", "bitcoin", "blockchain", "krypto", "cryptomonnaie", "criptovalute"])
        loc_terms = " OR ".join(cfg["x_terms"])
        query = f"({base_terms}) ({loc_terms}) -is:retweet"

        hits = x_recent_search(bearer, query, start_time, max_tweets_per_country)
        for hit in hits:
            tw = hit["tweet"]
            user = hit["user"]
            metrics = user.get("public_metrics", {})
            followers = int(metrics.get("followers_count", 0))
            if followers < min_subs or followers > max_subs:
                continue

            uid = user["id"]
            tweet_dt = dt_parser.parse(tw["created_at"])

            prev = creators.get(uid)
            if (not prev) or (tweet_dt > prev["latest_dt"]):
                creators[uid] = {
                    "platform": "x",
                    "country": country,
                    "creator_name": user.get("name", ""),
                    "creator_id": user.get("username", uid),
                    "profile_url": f"https://x.com/{user.get('username', '')}" if user.get("username") else "",
                    "followers": followers,
                    "content_count": int(metrics.get("tweet_count", 0)),
                    "latest_post_published_at": tweet_dt.isoformat(),
                    "latest_post_url": f"https://x.com/{user.get('username', 'i')}/status/{tw['id']}",
                    "matched_query": query,
                    "latest_dt": tweet_dt,
                }

    rows = []
    for item in creators.values():
        item.pop("latest_dt", None)
        rows.append(item)
    return rows


def write_outputs(rows: List[dict], output_csv: str, output_json: str):
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    Path(output_json).parent.mkdir(parents=True, exist_ok=True)

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=UNIFIED_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in UNIFIED_FIELDS})

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def main():
    args = parse_args()
    rows = []

    if args.platform in {"youtube", "both"}:
        youtube = get_youtube_client()
        rows.extend(
            run_youtube(
                youtube=youtube,
                min_subs=args.min_subs,
                max_subs=args.max_subs,
                days=args.days,
                max_channels_per_country=args.max_channels_per_country,
            )
        )

    if args.platform in {"x", "both"}:
        rows.extend(
            run_x(
                min_subs=args.min_subs,
                max_subs=args.max_subs,
                days=args.days,
                max_tweets_per_country=args.x_max_tweets_per_country,
            )
        )

    rows.sort(key=lambda x: (x["platform"], x["country"], -int(x["followers"])))
    write_outputs(rows, args.output_csv, args.output_json)

    print(f"Done. matched creators: {len(rows)}")
    print(f"CSV:  {args.output_csv}")
    print(f"JSON: {args.output_json}")


if __name__ == "__main__":
    main()
