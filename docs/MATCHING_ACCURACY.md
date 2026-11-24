# Matching accuracy

> Historical LyFind 2.0 experiment: the eight-clue formula and results below are NOT the integrated website's scoring formula or accuracy. The live application retains the five proposal weights and 60/40 thresholds described in LOCAL_AI_MATCHING.md. Re-evaluate production matching with representative campus examples before making accuracy claims.

This page says how LyFind scores a possible match, how it was tested, and what the numbers do and do not show.

## How a score is made

Every pair of (lost report, found item) gets eight signals. Each has a weight. Weights are rescaled over the signals that exist, so a report without a photo is not punished twice.

| Signal | Weight | Source |
| --- | --- | --- |
| Photo looks alike | 36 | DINOv2 image to image (same *item*, not same category) |
| Words fit the photo | 14 | CLIP text to image |
| Description words | 14 | Typed description overlap |
| Category | 4 | Hard constraint |
| Color | 8 | Typed |
| Brand | 6 | Typed |
| Place | 10 | Typed |
| Date | 8 | Typed |

Rules on top of the weighted score:

- Different category, or an item found before the loss date: the pair is hidden.
- Typed details alone can never reach Strong (cap 79). So AI off means no Strong tier.
- If both sides sent a photo and DINOv2 does not see the same item (scaled photo signal below 0.5), the pair is hidden. Matching words cannot override that.
- A different color or a different brand caps the score at 69.
- Found long after the loss (more than 14 days, more than 30 days) lowers the cap.
- Little information (coverage under half the weight) is capped below Strong.
- Above a cap the score is compressed, not flattened, so the ranking stays useful.
- If two candidates for the same report, or the same item, are within 6 points, both are held at Possible and marked "another item looks almost the same".

Tiers: **Strong** 80 and up, **Possible** 60 to 79, below 60 is not shown. Staff always decide; a score only orders the list. A flagged guest report cannot be confirmed until staff mark it checked.

DINOv2 and CLIP are loaded once per server. If they cannot load, or fail for one pair, LyFind falls back to typed details and shows a note on the match.

## How it was tested

`scripts/eval_matching.py` builds a labelled set with Pillow: 12 kinds of object drawn in different colors, with a deliberate look-alike for most items (same color, brand, place and week) and reports that have no item in the office. Lost reports and found items are drawn on different backgrounds, positions, shadows and small rotations. The set is generated from a seed, so it is repeatable.

Two regimes:

- **Rich**: owners type color, brand, marks and place.
- **Text-poor**: half the owners write one generic line.

The weights and calibration were tuned on a separate seed (`--seeds 1 --tune`). The numbers below are from **held-out seeds 11, 12, 13**: 144 found items, 180 lost reports, 36 of them with no item in the office.

| Regime | Method | Top-1 | Top-3 | Strong precision | False Strong | Strong recall | No-match reports shown Strong |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Rich | **CLIP + typed (shipped)** | **94.4%** | **100%** | 100% | **0.0%** | 67.4% | 0.0% |
| Rich | Typed only (AI off) | 94.4% | 100% | n/a (no Strong) | 0.0% | 0% | 0.0% |
| Rich | Photo only | 90.3% | 100% | 96.8% | 3.2% | 59.7% | 5.6% |
| Text-poor | **CLIP + typed (shipped)** | **85.4%** | **100%** | 98.3% | **1.7%** | 40.3% | 0.0% |
| Text-poor | Typed only (AI off) | 77.8% | 100% | n/a | 0.0% | 0% | 0.0% |
| Text-poor | Photo only | 81.2% | 100% | 96.2% | 3.8% | 51.4% | 5.6% |

Top-1 means the right item was the best suggestion. Top-3 means it was in the best three. "False Strong" is the share of Strong suggestions that were wrong. CLIP alone names the drawn object type correctly for about 85% of the photos.

## Reading the results honestly

- The images are drawn, not photographed. Real photos are harder (lighting, clutter, hands). Treat the numbers as a regression check and a comparison between methods, not a promise.
- DINOv2 and CLIP are loaded from `models/` on this computer. There is no cloud vision API and no photo upload to the internet.
- A second check uses internet photos in `tests/fixtures/photos/`: the same backpack (owner shot vs a crop) can score Strong; a second, different backpack is hidden even when the typed description matches. Run `.venv/bin/python -m unittest discover -s tests -p 'test_matching_photos.py'`.
- When owners write rich text, typed details alone match the combined top-1. Photo AI (now DINOv2) is what can reach the Strong tier; CLIP still helps when the owner wrote words but sent no photo. The table above was measured with CLIP photos on drawn icons; treat it as a regression baseline, not the DINOv2 backpack proof.
- Strong recall is deliberately modest. Look-alikes are demoted to Possible so that Strong is rarely wrong. Staff still see those pairs under Possible.
- A false Strong costs a wasted invitation to an owner; it cannot hand over an item. Every claim still needs the ownership answers, two staff checks and a valid ID at the CSA office.
- The 100% top-3 means that, in this set, staff always found the right item within three suggestions when one existed.

## Run it

```text
.venv/bin/python scripts/eval_matching.py --seeds 11,12,13
.venv/bin/python scripts/eval_matching.py --seeds 1 --tune   # compare weight presets on a tuning seed
```

Change a weight with `MATCH_WEIGHT_<NAME>` (for example `MATCH_WEIGHT_PHOTO=40`) and run the script again to see the effect.
