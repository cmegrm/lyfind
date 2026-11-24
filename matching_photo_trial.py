"""Compare local photo encoders on real, identified objects."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import time
from zipfile import ZipFile

from PIL import Image, ImageEnhance, ImageFilter


TUNING_IDS = range(41, 61)
TEST_IDS = range(61, 101)
CONDITIONS = ("60-degree view", "120-degree view, darkened and blurred")
LOOKALIKE_GROUPS = ((61, 64, 88, 90, 92), (62, 71, 93, 99), (69, 76, 91, 100),
                    (72, 87), (81, 89, 97))
UW_CONDITIONS = ("Second view", "Second view, darkened and blurred")
UW_OBJECTS = tuple(f"cap_{i}" for i in range(1, 5)) + tuple(f"coffee_mug_{i}" for i in (1, 2, 3, 4, 6, 7, 8))


def degrade(photo):
    return ImageEnhance.Brightness(photo).enhance(0.62).filter(ImageFilter.GaussianBlur(1.4))


def coil_photos(archive_path, object_ids):
    photos = []
    with ZipFile(archive_path) as archive:
        paths = {Path(name).name: name for name in archive.namelist()}
        for angle in (0, 60, 120):
            for object_id in object_ids:
                filename = f"obj{object_id}__{angle}.png"
                photo = Image.open(BytesIO(archive.read(paths[filename]))).convert("RGB")
                if angle == 120:
                    photo = degrade(photo)
                photos.append(photo)
    return photos


def uw_photos(directory):
    inventory = []
    queries = []
    for item in UW_OBJECTS:
        frame = 25 if item.startswith("cap_") else 170
        with Image.open(directory / f"{item}_1_100_crop.png") as photo:
            inventory.append(photo.convert("RGB"))
        with Image.open(directory / f"{item}_1_{frame}_crop.png") as photo:
            queries.append(photo.convert("RGB"))
    return inventory + queries + [degrade(photo) for photo in queries]


def compare_vectors(vectors, object_ids, conditions=CONDITIONS, lookalike_groups=LOOKALIKE_GROUPS):
    import numpy as np

    identities = np.asarray(object_ids)
    inventory, angle, degraded = np.split(vectors, 3)
    inventory_in_missing_trial = identities % 3 != 0
    results = {}
    for condition, query in zip(conditions, (angle, degraded)):
        scores = query @ inventory.T
        order = np.argsort(-scores, axis=1, kind="stable")
        same = np.eye(len(identities), dtype=bool)
        lookalikes = np.zeros_like(same)
        for group in lookalike_groups:
            members = np.isin(identities, group)
            lookalikes |= members[:, None] & members[None, :] & ~same
        top_five_wrong = sum(not hit for hit in (order[:, :5] == np.arange(len(identities))[:, None]).flat)
        missing_scores = scores[~inventory_in_missing_trial][:, inventory_in_missing_trial]
        results[condition] = {
            "queries": len(identities),
            "top_1": int(np.sum(order[:, 0] == np.arange(len(identities)))),
            "top_5": int(np.sum(np.any(order[:, :5] == np.arange(len(identities))[:, None], axis=1))),
            "wrong_in_top_5": top_five_wrong,
            "missing_queries": len(missing_scores),
            "thresholds": [
                {"cosine": cutoff,
                 "same_pairs_above": int(np.sum(scores[same] >= cutoff)),
                 "other_pairs_above": int(np.sum(scores[~same] >= cutoff)),
                 "lookalike_pairs_above": int(np.sum(scores[lookalikes] >= cutoff)),
                 "missing_queries_with_suggestion": int(np.sum(np.any(missing_scores >= cutoff, axis=1)))}
                for cutoff in (0.70, 0.76, 0.80, 0.85, 0.90, 0.93, 0.95, 0.97)
            ],
        }
    return results


def clip_queue(vectors, object_ids):
    """Use the actual score rule with intentionally identical, vague report text."""
    from matching import AIMatchingService

    class TrialAdapter:
        def __init__(self, vectors):
            self.vectors = vectors.tolist()

        def embed_text(self, _):
            return (1.0,)

        def embed_image(self, index):
            return self.vectors[int(index)]

    matcher = AIMatchingService(TrialAdapter(vectors))
    size = len(object_ids)
    inventory = [dict(category="accessories", description="Personal item", date_found="2026-01-02",
                      photo_path=str(index)) for index in range(size)]
    results = {}
    for block, condition in enumerate(CONDITIONS, start=1):
        counts = {"true_strong_before": 0, "true_strong_after": 0,
                  "wrong_strong_before": 0, "wrong_strong_after": 0,
                  "missing_queries_with_strong_before": 0, "missing_queries_with_strong_after": 0,
                  "wrong_visible": 0}
        for index, object_id in enumerate(object_ids):
            report = dict(category="accessories", description="Personal item", date_lost="2026-01-01",
                          photo_path=str(block * size + index))
            outcomes = [matcher.compare(report, item) for item in inventory]
            counts["true_strong_before"] += outcomes[index][0] >= 60
            counts["true_strong_after"] += outcomes[index][1] == "strong"
            alternatives = [outcome for i, outcome in enumerate(outcomes) if i != index]
            counts["wrong_strong_before"] += sum(score >= 60 for score, _ in alternatives)
            counts["wrong_strong_after"] += sum(level == "strong" for _, level in alternatives)
            counts["wrong_visible"] += sum(level != "hidden" for _, level in alternatives)
            if object_id % 3 == 0:
                missing = [outcome for candidate, outcome in zip(object_ids, outcomes) if candidate % 3 != 0]
                counts["missing_queries_with_strong_before"] += any(score >= 60 for score, _ in missing)
                counts["missing_queries_with_strong_after"] += any(level == "strong" for _, level in missing)
        results[condition] = counts
    return results


def encode_dino(photos, model_path):
    import numpy as np
    import torch
    from transformers import AutoImageProcessor, AutoModel

    processor = AutoImageProcessor.from_pretrained(model_path, local_files_only=True, use_fast=False)
    model = AutoModel.from_pretrained(model_path, local_files_only=True, use_safetensors=True)
    model.eval()
    batches = []
    with torch.inference_mode():
        for start in range(0, len(photos), 8):
            inputs = processor(images=photos[start:start + 8], return_tensors="pt")
            features = model(**inputs).last_hidden_state[:, 0]
            batches.append(torch.nn.functional.normalize(features).cpu().numpy())
    return np.concatenate(batches)


def evaluate(archive_path, dino_path, uw_path=None):
    from ai_runtime import LocalAI

    ai = LocalAI()
    adapter = ai.prepare()
    if adapter is None:
        raise RuntimeError(ai.reason)
    photos = {name: coil_photos(archive_path, ids) for name, ids in
              (("tuning", TUNING_IDS), ("held_out", TEST_IDS))}
    if uw_path:
        photos["uw"] = uw_photos(uw_path)
    results = {}
    for name, encode in (
        ("CLIP ViT-B/32", lambda batch: adapter._model.encode(batch, batch_size=8, normalize_embeddings=True)),
        ("DINOv2 Small", lambda batch: encode_dino(batch, dino_path)),
    ):
        started = time.perf_counter()
        vectors = {split: encode(batch) for split, batch in photos.items()}
        results[name] = {
            "seconds": round(time.perf_counter() - started, 1),
            "tuning": compare_vectors(vectors["tuning"], TUNING_IDS),
            "held_out": compare_vectors(vectors["held_out"], TEST_IDS),
        }
        if name.startswith("CLIP"):
            results[name]["held_out_queue_with_generic_descriptions"] = clip_queue(vectors["held_out"], TEST_IDS)
        if uw_path:
            results[name]["uw"] = compare_vectors(vectors["uw"], range(1, len(UW_OBJECTS) + 1),
                                                  UW_CONDITIONS, (range(1, 5), range(5, len(UW_OBJECTS) + 1)))
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coil_zip", type=Path)
    parser.add_argument("dinov2_model", type=Path)
    parser.add_argument("--uw-photos", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.coil_zip, args.dinov2_model, args.uw_photos), indent=2))
