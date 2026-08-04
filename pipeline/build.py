#!/usr/bin/env python3
"""
DawaSaver data pipeline.

Downloads a real, openly-licensed Indian medicine dataset, normalises each
product's salt composition into a comparison key, computes a fair per-unit
price (so a strip of 10 is compared against a strip of 15 honestly), groups
same-salt brands together, keeps the most useful ~1000 products, and writes a
compact data/drugs.json the static frontend consumes.

Stdlib only — no pip install needed in CI.

Source: junioralive/Indian-Medicine-Dataset (MIT). Prices/compositions are the
dataset author's snapshot of publicly listed product info; verify on the pack.
"""

import csv
import io
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

SOURCE_URL = (
    "https://raw.githubusercontent.com/junioralive/"
    "Indian-Medicine-Dataset/main/DATA/indian_medicine_data.csv"
)
SOURCE_NAME = "junioralive/Indian-Medicine-Dataset (MIT)"

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "drugs.json")

TARGET_COUNT = 1000     # aim for ~this many products in the final file
MIN_GROUP = 3           # a salt group needs at least this many brands to be useful
MAX_PER_GROUP = 20      # cap a single salt group so one doesn't dominate


def fetch(url):
    print(f"downloading {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "dawasaver-pipeline"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read().decode("utf-8", errors="replace")
    print(f"  {len(raw):,} bytes", file=sys.stderr)
    return raw


def parse_price(s):
    if not s:
        return None
    s = s.replace(",", "").replace("₹", "").strip()
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
    """Return (count, unitclass) from a pack label like 'strip of 10 tablets'."""
    if not label:
        return 1, "unit"
    m = UNIT_RE.search(label)
    if not m:
        return 1, "unit"
    count = float(m.group(1))
    word = m.group(2).lower()
    if count <= 0:
        count = 1
    unitclass = "ml" if word == "ml" else "unit"
    return count, unitclass


WS_RE = re.compile(r"\s+")


def norm_salt(c1, c2):
    """Normalise composition into a stable, order-independent key + display string."""
    parts = []
    for c in (c1, c2):
        c = (c or "").strip()
        if not c:
            continue
        c = WS_RE.sub(" ", c)
        c = c.replace(" )", ")").replace("( ", "(")
        parts.append(c.strip())
    if not parts:
        return None, None
    disp = " + ".join(parts)
    key = " + ".join(sorted(p.lower() for p in parts))
    return key, disp


STRENGTH_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:mg|mcg|ml|iu|%|g)\b", re.I)


def name_strength_count(name):
    """How many dose strengths the brand name advertises (e.g. '100mg/325mg/15mg' -> 3)."""
    return len(STRENGTH_RE.findall(name or ""))


# brand-name markers for actives the 2-column source often omits (serratiopeptidase,
# muscle relaxants). Products carrying these can't be safely grouped by 2 salts.
HIDDEN_ACTIVE_RE = re.compile(r"(?<![A-Za-z])(SP|MR)(?![A-Za-z])")


def has_hidden_active(name):
    return bool(HIDDEN_ACTIVE_RE.search(name or ""))


def build():
    raw = fetch(SOURCE_URL)
    reader = csv.DictReader(io.StringIO(raw))

    groups = {}   # saltkey -> {"salt": disp, "unit": unitclass, "items": [...]}
    seen = set()
    total_rows = 0

    for row in reader:
        total_rows += 1
        if (row.get("Is_discontinued") or "").strip().upper() == "TRUE":
            continue
        if (row.get("type") or "").strip().lower() not in ("", "allopathy"):
            continue
        name = (row.get("name") or "").strip()
        if not name:
            continue
        price = parse_price(row.get("price(₹)"))
        if price is None:
            continue
        key, disp = norm_salt(row.get("short_composition1"), row.get("short_composition2"))
        if not key:
            continue
        # source only carries 2 salt columns; if the name advertises more dose
        # strengths than we captured, the composition is incomplete -> skip so we
        # never group a 3-salt combo as if it were the 2-salt drug.
        n_salts = disp.count("+") + 1
        if name_strength_count(name) > n_salts:
            continue
        if has_hidden_active(name):
            continue
        count, unitclass = parse_pack(row.get("pack_size_label"))
        gkey = f"{key}|{unitclass}"

        dedupe = (name.lower(), gkey)
        if dedupe in seen:
            continue
        seen.add(dedupe)

        item = {
            "b": name,
            "mf": (row.get("manufacturer_name") or "").strip(),
            "m": round(price, 2),                       # pack MRP
            "u": round(price / count, 3),               # per-unit price (fair compare)
            "p": (row.get("pack_size_label") or "").strip(),
        }
        g = groups.setdefault(gkey, {"salt": disp, "unit": unitclass, "items": []})
        g["items"].append(item)

    # keep only groups with real comparison value
    usable = {
        k: g for k, g in groups.items()
        if len(g["items"]) >= MIN_GROUP
    }
    # rank groups by how many brands they have (popularity proxy) then by spread
    def spread(g):
        us = [it["u"] for it in g["items"]]
        return (max(us) - min(us)) / max(us) if max(us) else 0

    ranked = sorted(
        usable.values(),
        key=lambda g: (len(g["items"]), spread(g)),
        reverse=True,
    )

    drugs = []
    groups_used = 0
    for g in ranked:
        items = sorted(g["items"], key=lambda it: it["u"])[:MAX_PER_GROUP]
        for it in items:
            it["s"] = g["salt"]
            it["uc"] = g["unit"]
            drugs.append(it)
        groups_used += 1
        if len(drugs) >= TARGET_COUNT:
            break

    payload = {
        "meta": {
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": SOURCE_NAME,
            "source_url": SOURCE_URL,
            "source_rows": total_rows,
            "count": len(drugs),
            "groups": groups_used,
            "note": "Prices are the source snapshot; per-unit price (u) enables fair "
                    "same-salt comparison. Verify on the pack. Not medical advice.",
        },
        "drugs": drugs,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    print(
        f"rows={total_rows:,} usable_groups={len(usable):,} "
        f"-> wrote {len(drugs):,} drugs in {groups_used} groups to {os.path.relpath(OUT)}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    build()
