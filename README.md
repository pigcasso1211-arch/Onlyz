# Zonda X 推广帖抓取脚本

这个仓库提供 `scrape_zonda_promo_x.py`，用于抓取 **最近 12 个月** 在 X 上提及 `zonda` 并且看起来是“宣传/推广”性质的帖子链接（语言不限）。

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 运行

```bash
python3 scrape_zonda_promo_x.py
```

默认输出：
- `output/zonda_promo_posts_12m.csv`
- `output/zonda_promo_posts_12m.json`

## 常用参数

```bash
python3 scrape_zonda_promo_x.py \
  --since 2025-04-22 \
  --until 2026-04-22 \
  --max-results 10000 \
  --extra-keyword "discount" \
  --extra-term "#zonda"
```

## 说明

- 采用 `snscrape` 搜索，不依赖官方 API Key。
- “宣传帖”基于多语言关键词启发式过滤（例如 promo、sponsored、affiliate、reklama、推广 等），不是官方广告归因标签。
- 如果你要“尽可能全量”，建议扩大 `--max-results`，并根据业务补充 `--extra-keyword`。
