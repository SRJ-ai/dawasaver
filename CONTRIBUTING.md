# Contributing to DawaSaver

Thanks for helping make medicine prices transparent. 🙌

## Project shape

```
index.html                  static frontend (no build step, no framework)
data/drugs.json             generated data the frontend fetches — do not hand-edit
pipeline/build.py           regenerates drugs.json from the source dataset (stdlib only)
.github/workflows/refresh.yml   weekly CI that reruns the pipeline and commits changes
```

## Run locally

```bash
python pipeline/build.py            # regenerate data/drugs.json
python -m http.server 8000          # then open http://localhost:8000
```

No dependencies — Python 3.9+ standard library only.

## Good first issues

- **Add a data source.** Merge Jan Aushadhi / NPPA ceiling prices for real
  generic + government price points. Add an adapter in `pipeline/build.py`.
- **Better composition parsing.** The source has only two salt columns; improve
  detection of hidden actives (`SP`, `MR`, `Plus`, `DSR`, …) so grouping stays safe.
- **Unit normalisation.** Handle more pack labels (`vial`, `pre-filled syringe`, `respules`).
- **Accessibility / i18n.** Regional-language labels, screen-reader passes.

## Ground rules

- Keep the frontend dependency-free and the pipeline stdlib-only.
- Never present a medicine as substitutable without the "verify with pharmacist"
  guardrail. Correctness of composition grouping is a safety issue, not a nicety.
- `data/drugs.json` is generated — change `pipeline/build.py`, not the JSON.

## PRs

Small, focused PRs. Describe the data-quality impact (e.g. "adds 120 groups,
removes 3-salt mis-groupings in NSAID combos").
