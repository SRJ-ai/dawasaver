# DawaSaver 💊 — same salt, lower price

Type a medicine **brand name** and instantly see the **same-composition** generic and **Jan Aushadhi** alternatives that cost less.

Solves a real India problem (from Razorpay's *Fix My Itch*): *"Why do branded drugs dominate prescriptions despite equivalent, cheaper generic alternatives?"*

## What it does
- Search any brand (fuzzy + typo-tolerant, e.g. `crocn` → Crocin)
- Shows the same salt/strength group, sorted cheapest first
- Highlights % and ₹ saved vs the brand you searched
- Flags **Generic** and **Jan Aushadhi** options; links to nearest Kendra

## Tech
- 100% client-side static site → runs on GitHub Pages, no backend
- Embedded drug table (brand → salt), in-browser fuzzy search (Levenshtein + prefix/substring scoring)
- No dependencies, single `index.html`, dark/light aware

## ⚠️ Disclaimer
Information tool only — not medical advice, does not sell medicine. Salt mappings are common-knowledge/real; **prices are illustrative demo data**. Confirm any substitution with a doctor or pharmacist.

## Roadmap
- Replace demo prices with live data (CDSCO + Jan Aushadhi list + marketplace MRP)
- Data-refresh pipeline
- Store-level stock + geolocation
- Optional: prescription OCR (v2)
