# DawaSaver 💊 — same salt, lower price

**Live:** https://srj-ai.github.io/dawasaver/

Type a medicine **brand name** and instantly see **same-composition** alternatives
ranked by **real per-unit price** — so you can spot when the exact same salt is
sold under another brand for a fraction of the cost. Covers **230,000+ products**
across **12,000+ salt groups**, including **Jan Aushadhi** generic options.

Solves a real India problem (from Razorpay's *Fix My Itch*):
*"Why do branded drugs dominate prescriptions despite equivalent, cheaper alternatives?"*

## Features

- 🔎 Fuzzy, typo-tolerant search by **brand** (`crocn` → Crocin) **or generic/salt name** (`paracetamol`, `cetirizine` → the whole group, ranked by popularity)
- ⚖️ **Per-unit** price comparison (a strip of 10 vs a strip of 15, compared honestly)
- 💸 Savings hero: how much you'd save switching to the cheapest same-salt brand
- 🧾 ~1000 medicines across 50+ salt groups, from **real open data**
- 🌗 Dark/light, mobile-first, zero dependencies
- 📍 Link to the nearest Jan Aushadhi Kendra

## How it works

100% static — no backend, no database. Runs free on GitHub Pages. To search
230k+ products without a giant download, the data is **sharded**: the browser
only fetches a tiny search shard as you type, then one group file when you pick.

```
index.html            fuzzy search + rendering in-browser; fetches only small shards
data/meta.json        summary + source attribution
data/idx/<pfx>.json   search shard by 2-char brand prefix: [[brand, salt, gid], ...]
data/grp/<bucket>.json group members by gid bucket: {gid: {s, uc, n, items:[...]}}
pipeline/build.py     multi-source pipeline that generates all of data/
pipeline/sources/     Jan Aushadhi seed list (expandable)
.github/workflows/    weekly cron reruns the pipeline and auto-commits fresh data
```

### Data pipeline (multi-source)

| Adapter | Source | Notes |
|---|---|---|
| `market` | [junioralive/Indian-Medicine-Dataset](https://github.com/junioralive/Indian-Medicine-Dataset) (MIT) | ~254k branded products |
| `jan-aushadhi` | `pipeline/sources/jan_aushadhi_seed.csv` (or `$JA_SOURCE_URL`) | Government generic scheme, indicative published prices; merges into matching salt groups |

The pipeline (`pipeline/build.py`, standard-library only):

1. Pulls every adapter's records
2. Drops discontinued / non-allopathy / unpriced rows (market)
3. Normalises `salt (strength) + salt (strength)` into an order-independent key
4. Parses pack labels (`strip of 10 tablets`) to compute **price per unit**
5. Filters combos the 2-column source can't fully capture (so a 3-salt drug is
   never grouped as if it were the 2-salt one)
6. Trims extreme per-unit outliers (pack-size parse errors / bulk packs)
7. Groups same-salt brands and writes the sharded `data/` tree

Add another source by writing an adapter function and appending it to `ADAPTERS`.

Refreshed weekly by GitHub Actions (`.github/workflows/refresh.yml`), or run it yourself:

```bash
python pipeline/build.py
python -m http.server 8000   # open http://localhost:8000
```

## Custom domain (optional)

The site lives at `https://<user>.github.io/dawasaver/`. To use your own domain,
add a `CNAME` file containing the domain at the repo root, set your DNS
(`CNAME` record → `<user>.github.io`, or `A` records to GitHub Pages IPs), then
enable it under **Settings → Pages → Custom domain**.

## ⚠️ Disclaimer

Information tool only — **not medical advice**, does not sell medicine.
Salt grouping uses the source's primary composition; some products may contain
extra actives. **Always confirm exact composition with a doctor or pharmacist
before switching.** Prices are a dataset snapshot — verify on the pack.

## Contributing & licence

PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Code under [MIT](LICENSE);
data attribution in [NOTICE.md](NOTICE.md).
