# Local AI matching in the integrated website

The website uses `lyfind/proposal_matching.py` to adapt the existing five-clue engine in root `matching.py` to the modular workflows. `lyfind/matching.py` retains the 2.0 embedding adapters and an experimental eight-clue engine; its experimental formula is not the live workflow formula.

## Five clues

| Clue | Weight |
|---|---:|
| Description | 30% |
| Photo | 30% |
| Color | 15% |
| Brand | 15% |
| Place and date | 10% |

Pairs must share a category. Unknown fields provide no positive evidence. Available clues are rescaled; typed-only scores require two agreeing typed clues and are capped at 59. Strong starts at 60 and requires supporting evidence; Possible starts at 40. Lower scores are hidden. A high numerical score may remain Possible when photo agreement is weak or the dates contradict. Scores are similarity indicators, not ownership probabilities.

CLIP compares descriptions and compares the owner's words with the CSA photo if the owner has no photo. DINOv2 compares two photos when available; CLIP is the photo fallback. The existing `models/dinov2-small` installation is supported, as is a prepared `models/dinov2-base`. Inference stays local. If loading or comparison fails, the workflow uses typed details and records the fallback. Only CSA sees suggestions, scores, photos and identifying details. Owners receive a notice after a CSA-confirmed invitation.

Staff see a saved explanation, clue points, weights and any Strong caveat. Near-equal suggestions show an ambiguity warning. Physical receipt is required before inventory can be matched. Expired, reserved and released items are excluded from new suggestions and claims.

## Preparation and checks

Use the existing Windows SETUP_AI launcher or the Mac application's Set up local AI control. `python setup_ai.py` prepares the project environment and local models. No models are downloaded while answering a web request. Internet is needed for initial model downloads, not recognition.

Run `python scripts/ai.py --check` in the prepared project environment for an offline inference check. `tests/test_proposal_photos.py` tests the production matcher with real fixtures. Run `python -m unittest discover -s tests` for the full suite. Model-dependent tests skip when dependencies or local models are absent.

`docs/MATCHING_ACCURACY.md`, `scripts/eval_matching.py`, and the opt-in `RUN_EXPERIMENTAL_MATCHING_TESTS=1` photo tests retain historical eight-clue experiments. Their accuracy figures do not describe this website. Neither model proves that two objects have the same owner. Evaluate with consented, representative campus items before making accuracy claims, and keep CSA's online questions, ID check, in-person consent, evidence, approval and physical handover.

Optional weights: `MATCH_WEIGHT_DESCRIPTION`, `MATCH_WEIGHT_PHOTO`, `MATCH_WEIGHT_COLOR`, `MATCH_WEIGHT_BRAND`, and `MATCH_WEIGHT_PLACE_DATE`; they must total 100. Restart and rerun matching after changing them.
