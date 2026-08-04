# DawaSaver 💊 — same salt, lower price

**Live:** https://srj-ai.github.io/dawasaver/

Type a medicine **brand name** and instantly see **same-composition** alternatives
ranked by **real per-unit price** — so you can spot when the exact same salt is
sold under another brand for a fraction of the cost.

Solves a real India problem (from Razorpay's *Fix My Itch*):
*"Why do branded drugs dominate prescriptions despite equivalent, cheaper alternatives?"*

## Features

- 🔎 Fuzzy, typo-tolerant brand search (`crocn` → Crocin)
- ⚖️ **Per-unit** price comparison (a strip of 10 vs a strip of 15, compared honestly)
- 💸 Savings hero: how much you'd save switching to the cheapest same-salt brand
- 🧾 ~1000 medicines across 50+ salt groups, from **real open data**
- 🌗 Dark/light, mobile-first, zero dependencies
- 📍 Link to the nearest Jan Aushadhi Kendra

## How it works

100% static — no backend, no database. Runs free on GitHub Pages.

```
index.html            fetches data/drugs.json, does fuzzy search + grouping in-browser
data/drugs.json       generated, compact real dataset
pipeline/build.py     downloads the source dataset, normalises composition,
                      computes fair per-unit price, groups same-salt brands
.github/workflows/    weekly cron reruns the pipeline and auto-commits fresh data
```

### Data pipeline

Source: **[junioralive/Indian-Medicine-Dataset](https://github.com/junioralive/Indian-Medicine-Dataset)** (MIT, ~254k products).

The pipeline (`pipeline/build.py`, standard-library only):

1. Downloads the source CSV
2. Drops discontinued / non-allopathy / unpriced rows
3. Normalises `salt (strength) + salt (strength)` into an order-independent key
4. Parses pack labels (`strip of 10 tablets`) to compute **price per unit**
5. Filters combos whose composition the 2-column source can't fully capture
   (so a 3-salt drug is never grouped as if it were the 2-salt one)
6. Keeps the most useful same-salt groups (≥3 brands) up to ~1000 products
7. Writes compact `data/drugs.json`

Refreshed weekly by GitHub Actions (`.github/workflows/refresh.yml`), or run it yourself:

```bash
python pipeline/build.py
python -m http.server 8000   # open http://localhost:8000
```

## ⚠️ Disclaimer

Information tool only — **not medical advice**, does not sell medicine.
Salt grouping uses the source's primary composition; some products may contain
extra actives. **Always confirm exact composition with a doctor or pharmacist
before switching.** Prices are a dataset snapshot — verify on the pack.

## Contributing & licence

PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Code under [MIT](LICENSE);
data attribution in [NOTICE.md](NOTICE.md).
