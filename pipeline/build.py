#!/usr/bin/env python3
"""
DawaSaver data pipeline (multi-source, sharded output).

Pulls medicine data from one or more source adapters, normalises each product's
salt composition into a comparison key, computes a fair per-unit price, groups
same-salt brands, and writes a SHARDED static dataset so a browser can search
hundreds of thousands of products while only ever downloading a few small files:

  data/meta.json                summary + source attribution
  data/idx/<pfx>.json           search shard: [[brand, salt, gid], ...] by 2-char prefix
  data/grp/<bucket>.json        {gid: {s, uc, n, items:[[b,mf,m,u,p,kind], ...]}}

Sources (adapters):
  * market       junioralive/Indian-Medicine-Dataset (MIT) — ~254k branded products
  * jan-aushadhi pipeline/sources/jan_aushadhi_seed.csv (or $JA_SOURCE_URL) —
                 government generic-scheme products, indicative published prices

Stdlib only — no pip install needed in CI.
"""

import csv
import io
import json
import os
import re
import shutil
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "..", "data")
BUCKETS = 256

MARKET_URL = (
    "https://raw.githubusercontent.com/junioralive/"
    "Indian-Medicine-Dataset/main/DATA/indian_medicine_data.csv"
)
JA_SEED = os.path.join(HERE, "sources", "jan_aushadhi_seed.csv")
JA_URL = os.environ.get("JA_SOURCE_URL")  # optional override with a fuller list

SOURCES = []  # populated by adapters for the meta block


# ---------------------------------------------------------------- helpers
def fetch(url):
    print(f"downloading {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "dawasaver-pipeline"})
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read().decode("utf-8", errors="replace")
    print(f"  {len(raw):,} bytes", file=sys.stderr)
    return raw


def parse_price(s):
    if not s:
        return None
    s = str(s).replace(",", "").replace("₹", "").strip()
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


UNIT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(ml|tablet|tablets|capsule|capsules|gm|g\b|sachet|sachets|"
    r"injection|vial|drop|drops|piece|pieces|unit|units)",
    re.I,
)


def parse_pack(label):
    if not label:
        return 1.0, "unit"
    m = UNIT_RE.search(label)
    if not m:
        return 1.0, "unit"
    count = float(m.group(1)) or 1.0
    unitclass = "ml" if m.group(2).lower() == "ml" else "unit"
    return count, unitclass


WS_RE = re.compile(r"\s+")


def norm_salt(c1, c2):
    parts = []
    for c in (c1, c2):
        c = (c or "").strip()
        if not c:
            continue
        c = WS_RE.sub(" ", c).replace(" )", ")").replace("( ", "(")
        parts.append(c.strip())
    if not parts:
        return None, None
    disp = " + ".join(parts)
    key = " + ".join(sorted(p.lower() for p in parts))
    return key, disp


STRENGTH_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:mg|mcg|ml|iu|%|g)\b", re.I)
HIDDEN_ACTIVE_RE = re.compile(r"(?<![A-Za-z])(SP|MR)(?![A-Za-z])")


def pfx_of(name):
    t = re.sub(r"[^a-z0-9]", "", name.lower())
    if not t:
        return "__"
    if len(t) == 1:
        return t + "_"
    return t[:2]


# ---------------------------------------------------------------- adapters
def market_adapter():
    raw = fetch(MARKET_URL)
    rows = 0
    for row in csv.DictReader(io.StringIO(raw)):
        rows += 1
        if (row.get("Is_discontinued") or "").strip().upper() == "TRUE":
            continue
        if (row.get("type") or "").strip().lower() not in ("", "allopathy"):
            continue
        name = (row.get("name") or "").strip()
        if not name:
            continue
        # source has only 2 salt columns; skip products whose name implies more
        # actives than captured, so a 3-salt combo is never grouped as a 2-salt one.
        c1, c2 = row.get("short_composition1"), row.get("short_composition2")
        _, disp = norm_salt(c1, c2)
        if not disp:
            continue
        n_salts = disp.count("+") + 1
        if len(STRENGTH_RE.findall(name)) > n_salts:
            continue
        if HIDDEN_ACTIVE_RE.search(name):
            continue
        yield {
            "name": name,
            "price": row.get("price(₹)"),
            "pack": row.get("pack_size_label"),
            "c1": c1, "c2": c2,
            "mfr": (row.get("manufacturer_name") or "").strip(),
            "kind": "market",
        }
    SOURCES.append({
        "id": "market",
        "name": "junioralive/Indian-Medicine-Dataset (MIT)",
        "url": MARKET_URL,
        "rows": rows,
    })


def jan_aushadhi_adapter():
    """Government generic-scheme products. Merges into matching salt groups."""
    if JA_URL:
        text = fetch(JA_URL)
        origin = JA_URL
    else:
        with open(JA_SEED, encoding="utf-8") as f:
            text = f.read()
        origin = "pipeline/sources/jan_aushadhi_seed.csv"
    n = 0
    for row in csv.DictReader(io.StringIO(text)):
        name = (row.get("name") or "").strip()
        if not name:
            continue
        n += 1
        yield {
            "name": name,
            "price": row.get("price"),
            "pack": row.get("pack_size_label"),
            "c1": row.get("short_composition1"), "c2": row.get("short_composition2"),
            "mfr": "PMBJP (Jan Aushadhi)",
            "kind": "jan-aushadhi",
        }
    SOURCES.append({
        "id": "jan-aushadhi",
        "name": "Jan Aushadhi (PMBJP) — indicative published prices",
        "url": origin,
        "rows": n,
        "note": "Seed list; expand from the official PMBJP product list. Verify at Kendra.",
    })


ADAPTERS = [market_adapter, jan_aushadhi_adapter]


# ---------------------------------------------------------------- build
def build():
    groups = {}          # gkey -> {"salt", "unit", "items": {bname_lower: item}}
    for adapter in ADAPTERS:
        for rec in adapter():
            price = parse_price(rec["price"])
            if price is None:
                continue
            key, disp = norm_salt(rec["c1"], rec["c2"])
            if not key:
                continue
            count, unitclass = parse_pack(rec["pack"])
            gkey = f"{key}|{unitclass}"
            g = groups.setdefault(gkey, {"salt": disp, "unit": unitclass, "items": {}})
            dk = rec["name"].lower()
            item = {
                "b": rec["name"],
                "mf": rec["mfr"],
                "m": round(price, 2),
                "u": round(price / count, 3),
                "p": (rec["pack"] or "").strip(),
                "kind": rec["kind"],
            }
            # keep the cheaper entry if a duplicate name appears
            cur = g["items"].get(dk)
            if cur is None or item["u"] < cur["u"]:
                g["items"][dk] = item

    # assign integer group ids, prepare shards
    if os.path.isdir(DATA):
        shutil.rmtree(DATA)
    os.makedirs(os.path.join(DATA, "idx"))
    os.makedirs(os.path.join(DATA, "grp"))

    idx = {}                     # pfx -> [[b, salt, gid], ...]
    bucket_files = {}            # bucket -> {gid: {...}}
    gid = 0
    total_items = 0

    for gkey, g in groups.items():
        items = sorted(g["items"].values(), key=lambda it: it["u"])
        # drop extreme per-unit outliers (almost always pack-size parse errors or
        # bulk/hospital packs) so savings comparisons stay credible
        if len(items) >= 5:
            mid = items[len(items) // 2]["u"]
            if mid > 0:
                items = [it for it in items if it["u"] <= 25 * mid] or items
        gid += 1
        bucket = gid % BUCKETS
        bucket_files.setdefault(bucket, {})[gid] = {
            "s": g["salt"],
            "uc": g["unit"],
            "n": len(items),
            "items": [[it["b"], it["mf"], it["m"], it["u"], it["p"], it["kind"]] for it in items],
        }
        for it in items:
            idx.setdefault(pfx_of(it["b"]), []).append([it["b"], g["salt"], gid])
            total_items += 1

    for pfx, arr in idx.items():
        arr.sort(key=lambda e: e[0].lower())
        with open(os.path.join(DATA, "idx", f"{pfx}.json"), "w", encoding="utf-8") as f:
            json.dump(arr, f, ensure_ascii=False, separators=(",", ":"))

    for bucket, obj in bucket_files.items():
        with open(os.path.join(DATA, "grp", f"{bucket}.json"), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))

    meta = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": total_items,
        "groups": gid,
        "buckets": BUCKETS,
        "index_shards": len(idx),
        "sources": SOURCES,
        "note": "Comparison by per-unit price. Salt grouping uses primary composition; "
                "confirm exact composition with a pharmacist. Not medical advice.",
    }
    with open(os.path.join(DATA, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))

    # GitHub Pages: don't run these many files through Jekyll
    open(os.path.join(DATA, "..", ".nojekyll"), "w").close()

    print(
        f"products={total_items:,} groups={gid:,} "
        f"idx_shards={len(idx):,} buckets={len(bucket_files)} -> {os.path.relpath(DATA)}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    build()
