# Project tools

Start the website from the project root with `python3 main.py`.

| Command | Purpose |
|---|---|
| `python3 scripts/demo.py` | Complete claim workflow using a temporary database |
| `python3 scripts/ai.py --prepare` | Download missing DINOv2 and CLIP models |
| `python3 scripts/ai.py --check` | Verify local AI with network connections blocked |
| `python3 scripts/eval_matching.py --help` | Matching evaluation options |
| `python3 setup_ai.py` | Create the environment, install AI dependencies, prepare and check models |

The two former AI helper scripts are combined in `ai.py`. The one-off proposal
builder was removed because it referenced unavailable files outside the project
and was not used by the application.

Test photos live in `tests/fixtures/photos/`; sample inventory photos live in
`demo_images/`. Runtime databases, uploads, and backups remain in `data/`.
