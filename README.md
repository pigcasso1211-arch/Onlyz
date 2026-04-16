# Crypto Influencer Scraper (Europe)

这个项目支持抓取 **YouTube + X（Twitter）** 的欧洲加密货币领域博主，并统一输出到同一个结果表。

## 目标过滤条件

- 粉丝数：`5,000 - 50,000`
- 地区：瑞士、法国、德国、意大利、荷兰、波兰
- 最后更新：近 1 个月（`--days 30`）

## 1) 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) 配置环境变量

```bash
export YOUTUBE_API_KEY="你的_youtube_api_key"
export X_BEARER_TOKEN="你的_x_api_bearer_token"
```

> 如果只跑单平台，可只配置对应平台的变量。

## 3) 运行示例

### 仅 YouTube

```bash
python scraper.py --platform youtube --days 30
```

### 仅 X

```bash
python scraper.py --platform x --days 30
```

### YouTube + X 合并输出（推荐）

```bash
python scraper.py \
  --platform both \
  --min-subs 5000 \
  --max-subs 50000 \
  --days 30 \
  --max-channels-per-country 80 \
  --x-max-tweets-per-country 300 \
  --output-csv output/crypto_creators_eu.csv \
  --output-json output/crypto_creators_eu.json
```

## 4) 统一输出字段

- `platform` (youtube/x)
- `country`
- `creator_name`
- `creator_id` (YouTube channel_id / X username)
- `profile_url`
- `followers`
- `content_count` (视频数 / 推文数)
- `latest_post_published_at`
- `latest_post_url`
- `matched_query`

## 5) X API 说明

- 当前使用 **X API v2 recent search**（`/2/tweets/search/recent`）。
- 具体可回溯天数受你的 API 套餐限制；若套餐只支持近 7 天数据，`--days 30` 可能无法完整覆盖整月。
