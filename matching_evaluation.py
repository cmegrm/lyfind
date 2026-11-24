"""Run reproducible matching checks with fictional descriptions and illustrations."""
import json
import tempfile
from pathlib import Path

from ai_runtime import LocalAI
from matching import AIMatchingService, TypedDetailsMatchingService
from seed import sample_image


def evaluate():
    ai = LocalAI()
    ai.prepare()
    matchers = [TypedDetailsMatchingService()]
    if ai.adapter:
        matchers.append(AIMatchingService(ai.adapter))
    with tempfile.TemporaryDirectory(prefix="reunite-evaluation-") as directory:
        root = Path(directory)
        for name in ("bag", "wallet"):
            (root / (name + ".png")).write_bytes(sample_image(name))
        report = dict(category="bags", description="Dark green canvas backpack",
                      color="green", brand="Campus", place="Library", date_lost="2026-11-01")
        item = dict(report, date_found="2026-11-02", photo_path=str(root / "bag.png"))
        cases = [
            ("Matching description, same illustration", True,
             dict(report, photo_path=str(root / "bag.png")), item),
            ("Paraphrased description, no owner photo", True,
             dict(report, description="A green school bag made of canvas"), item),
            ("Same category, conflicting description and details", False,
             dict(report, description="Small red leather handbag", color="red",
                  brand="Other", place="Gym", photo_path=str(root / "wallet.png")), item),
            ("Only date agrees", False,
             dict(report, description="A red handbag", color="", brand="", place="Gym"), item),
            ("Only place and date available", False,
             dict(report, description="A red handbag", color="", brand=""), item),
            ("Matching color and place, unknown brand", True,
             dict(report, brand="Unknown"), item),
            ("Wrong category", False, dict(report, category="wallets"), item),
            ("Conflicting photo but matching typed details", False,
             dict(report, photo_path=str(root / "wallet.png")), item),
        ]
        results = []
        for name, expected, loss, received in cases:
            for matcher in matchers:
                score, level = matcher.compare(loss, received)
                results.append(dict(case=name, method=matcher.method, expected_suggestion=expected,
                                    score=score, level=level, suggested=level != "hidden"))
    summary = {}
    for matcher in matchers:
        rows = [row for row in results if row["method"] == matcher.method]
        summary[matcher.method] = dict(
            cases=len(rows),
            unexpected_suggestions=sum(row["suggested"] and not row["expected_suggestion"] for row in rows),
            missed_expected_suggestions=sum(not row["suggested"] and row["expected_suggestion"] for row in rows),
        )
    return dict(
        scope="Fictional descriptions and synthetic seed illustrations; local model inference.",
        limitation="These checks do not establish real-world accuracy. Verified photographs of the same objects "
                   "from different angles and in poor lighting or blur are still needed.",
        ai_ready=bool(ai.adapter), ai_status=ai.reason, summary=summary, results=results,
    )


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
