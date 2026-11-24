"""Useful abstraction, Factory pattern and CLIP Adapter with an offline fallback."""
from abc import ABC, abstractmethod
from math import sqrt, isfinite
from dataclasses import dataclass, asdict
import json
import hashlib
import os
from functools import lru_cache
from pathlib import Path
from threading import RLock


@dataclass(frozen=True)
class ScoreWeights:
    description: float = 30
    photo: float = 30
    color: float = 15
    brand: float = 15
    place_date: float = 10

    def __post_init__(self):
        values = asdict(self).values()
        if any(not isfinite(v) or v < 0 for v in values) or abs(sum(values)-100) > 0.0001:
            raise ValueError("The five matching weights must be non-negative and total 100.")
        if self.color+self.brand+self.place_date <= 0:
            raise ValueError("Keep a positive typed-details weight for fallback matching.")

    @classmethod
    def from_environment(cls):
        return cls(**{k: float(os.getenv('MATCH_WEIGHT_'+k.upper(), v)) for k,v in asdict(cls()).items()})

    @property
    def typed_total(self):
        return self.color+self.brand+self.place_date


def _norm(value):
    return str(value or "").strip().casefold()


def _description_with_marks(row, extra_field):
    base = str(row.get("description") or "").strip()
    extra = str(row.get(extra_field) or "").strip()
    if base and extra:
        return f"{base}. {extra}"
    return base or extra


def brand_key(value):
    """Unknown is missing evidence, never a positive brand match."""
    key = _norm(value).replace('’', "'")
    return '' if key in {'unknown','not known','not sure',"i don't know",'i do not know','n/a','?'} else key


def cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    a,b = [float(x) for x in a], [float(x) for x in b]
    if any(not isfinite(float(x)) for x in list(a) + list(b)):
        raise ValueError("The embedding model returned non-finite values.")
    den = sqrt(sum(x*x for x in a)) * sqrt(sum(y*y for y in b))
    return max(0.0, min(1.0, sum(x*y for x, y in zip(a, b))/den)) if den else 0.0


class EmbeddingAdapter(ABC):
    @abstractmethod
    def embed_text(self, text):
        pass

    @abstractmethod
    def embed_image(self, path):
        pass


class ClipAdapter(EmbeddingAdapter):
    """Convert a sentence-transformers model's encode API to our domain API."""
    def __init__(self, model):
        self._model = model
        self._lock = RLock()

    @lru_cache(maxsize=512)
    def embed_text(self, text):
        with self._lock:
            return [float(x) for x in self._model.encode(text)]

    def embed_image(self, path):
        p = Path(path)
        stat = p.stat()
        return list(self._image(str(p.resolve()), stat.st_size, stat.st_mtime_ns))

    @lru_cache(maxsize=256)
    def _image(self, path, size, modified):
        from PIL import Image
        with self._lock, Image.open(path) as picture:
            return tuple(float(x) for x in self._model.encode(picture.convert("RGB")))


class MatchingService(ABC):
    method = "abstract"

    def __init__(self, weights=None):
        self.weights = weights or ScoreWeights()

    @abstractmethod
    def explain(self, report, item):
        pass

    def compare(self, report, item):
        if _norm(report["category"]) != _norm(item["category"]):
            return 0.0, "hidden"
        return self._label(self.score(report, item))

    @staticmethod
    def _label(total, strong_caveat=None):
        raw = float(total)
        if not isfinite(raw):
            raise ValueError("The matching model returned a non-finite score.")
        score = round(max(0.0, min(100.0, raw)), 1)
        return score, "strong" if score >= 60 and not strong_caveat else "possible" if score >= 40 else "hidden"

    def typed_parts(self, report, item):
        parts = {}
        for clue in ("color", "brand", "place"):
            left, right = (brand_key(row.get(clue)) for row in (report, item))
            if clue == "color" and "other" in (left,right):
                left = ""
            maximum = self.weights.place_date / 2 if clue == "place" else getattr(self.weights, clue)
            parts[clue] = (maximum if left == right else 0) if left and right else None
        parts["date"] = self.weights.place_date / 2 * (report["date_lost"] <= item["date_found"])
        return parts

    def summarize(self, parts, source, report):
        weights = asdict(self.weights)
        weights["place"] = weights["date"] = weights.pop("place_date") / 2
        scale = sum(weights[k] for k,v in parts.items() if v is not None)
        raw = sum(v for v in parts.values() if v is not None)
        total = raw * 100 / scale if scale else 0
        if self.method == "typed_details":
            total = min(59, total)
            supporting = sum(parts.get(key) is not None and parts[key] > 0 for key in ("color", "brand", "place"))
            if supporting < 2:
                total = min(39, total)
        return dict(version=2, method=self.method, weights=weights, contributions=parts,
                    raw_total=raw, scale=scale, total=total, photo_source=source,
                    statement=self._typed_statement(parts, weights, report),
                    explanation="Available clues rescaled. Typed-only suggestions require two agreeing color, brand, or place clues and are capped at 59.")

    @staticmethod
    def _typed_statement(parts, weights, report):
        matching = [f'{report[key]} for {key}' for key in ("color", "brand", "place") if (parts[key] or 0) > 0]
        differing = [key for key in ("color", "brand", "place") if parts[key] == 0 and weights[key] > 0]
        sentences = []
        if matching:
            sentences.append(f"Both records list {', '.join(matching)}.")
        if differing:
            sentences.append(f"Different report details include {', '.join(differing)}.")
        return " ".join(sentences)

    def score(self, report, item):
        return self.explain(report, item)["total"]


class TypedDetailsMatchingService(MatchingService):
    method = "typed_details"

    def explain(self, report, item):
        return self.summarize(dict(description=None, photo=None, **self.typed_parts(report,item)), "not_used", report)


class AIMatchingService(MatchingService):
    method = "clip_ai"
    STRONG_PHOTO_SIMILARITY = .95
    STRONG_DINO_SIMILARITY = .93

    def __init__(self, adapter, weights=None, photo_adapter=None):
        super().__init__(weights)
        self._adapter = adapter
        self._photo_adapter = photo_adapter

    @staticmethod
    def calibrated(raw, floor, ceiling):
        return min(1, max(0, (raw-floor)/(ceiling-floor)))

    def compare(self, report, item):
        score, level, _ = self.evaluate(report, item)
        return score, level

    def evaluate(self, report, item):
        if _norm(report["category"]) != _norm(item["category"]):
            return 0.0, "hidden", {}
        details = self.explain(report, item)
        score, level = self._label(details["total"], details["strong_caveat"])
        return score, level, details

    def _strong_caveat(self, report, item, parts, photo_similarity, photo_model):
        if report["date_lost"] > item["date_found"]:
            return "The reported loss date is after the found date."
        typed_agreement = sum((parts[key] or 0) > 0 for key in ("color", "brand", "place"))
        description_agrees = self.weights.description > 0 and parts["description"] >= self.weights.description / 2
        if photo_similarity is not None and self.weights.photo > 0:
            cutoff = self.STRONG_DINO_SIMILARITY if photo_model == "DINOv2" else self.STRONG_PHOTO_SIMILARITY
            if photo_similarity < cutoff:
                return "The owner and CSA photos do not agree closely enough for a Strong match."
            if not description_agrees and typed_agreement < 2:
                return "The photo needs support from the descriptions or at least two typed details."
        elif not description_agrees or typed_agreement < 2:
            return "Without an owner photo comparison, Strong needs agreeing descriptions and at least two of color, brand and place."
        return None

    def _compare_photos(self, first, second):
        if self._photo_adapter:
            try:
                similarity = cosine(self._photo_adapter.embed_image(first), self._photo_adapter.embed_image(second))
                return similarity, self.calibrated(similarity, .70, .95), "DINOv2"
            except Exception:
                # Keep CLIP available for individual images DINOv2 cannot process.
                pass
        similarity = cosine(self._adapter.embed_image(first), self._adapter.embed_image(second))
        return similarity, self.calibrated(similarity, .76, .97), "CLIP"

    @staticmethod
    def _statement(details):
        parts, weights = details["contributions"], details["weights"]
        sentences = []
        if weights["description"] > 0:
            strength = "close" if parts["description"] >= weights["description"] / 2 else "limited"
            sentences.append(f"CLIP found {strength} similarity between the written descriptions.")
        if weights["photo"] > 0 and parts["photo"] is not None:
            strength = "close" if parts["photo"] >= weights["photo"] * .85 else "some" if parts["photo"] > 0 else "little"
            subject = ("the two photos" if details["photo_source"] == "owner_photo"
                       else "the owner’s description and the CSA photo")
            sentences.append(f"{details['photo_model']} found {strength} similarity between {subject}.")
        elif weights["photo"] > 0:
            sentences.append("The photo comparison was unavailable.")
        sentences.append(details["statement"])
        return " ".join(sentence for sentence in sentences if sentence)

    def explain(self, report, item):
        adapter = self._adapter
        report_text = _description_with_marks(report, "identifying_marks")
        item_text = _description_with_marks(item, "private_details")
        words = adapter.embed_text(report_text)
        similarity = cosine(words, adapter.embed_text(item_text))
        parts = self.typed_parts(report,item)
        parts["description"] = self.weights.description * self.calibrated(similarity,.30,.95)
        source = "owner_photo" if report.get("photo_path") else "owner_description"
        parts["photo"] = None
        photo_similarity = None
        photo_model = None
        if item.get("photo_path"):
            if source == "owner_photo":
                photo_similarity, fraction, photo_model = self._compare_photos(report["photo_path"], item["photo_path"])
            else:
                picture = adapter.embed_image(item["photo_path"])
                try:
                    fraction = self.calibrated(cosine(words,picture),.17,.33)
                    photo_model = "CLIP"
                except (TypeError, NotImplementedError):
                    source = "unavailable"
                    fraction = None
            if fraction is not None:
                parts["photo"] = self.weights.photo * fraction
        details = self.summarize(parts, source, report)
        details["photo_model"] = photo_model
        details["statement"] = self._statement(details)
        details["strong_caveat"] = self._strong_caveat(report, item, parts, photo_similarity, photo_model)
        return details


class SavedEmbeddings:
    def __init__(self, conn, adapter, image_namespace="clip-b32-v1"):
        self.conn, self.adapter = conn, adapter
        self.image_namespace = image_namespace

    def cached(self, key, encode, value):
        row = self.conn.execute("SELECT vector FROM embeddings WHERE cache_key=?", (key,)).fetchone()
        if row:
            return json.loads(row[0])
        vector = list(encode(value))
        self.conn.execute("INSERT INTO embeddings VALUES(?,?)",(key,json.dumps(vector)))
        return vector

    def embed_text(self, text):
        return self.cached("clip-b32-v1:text:"+text,self.adapter.embed_text,text)

    def embed_image(self, path):
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        return self.cached(self.image_namespace+":image:"+digest,self.adapter.embed_image,path)


class MatchingServiceFactory:
    @staticmethod
    def create(ai_available=False, embedder=None, log=None, weights=None, photo_adapter=None):
        if ai_available and embedder is not None:
            return AIMatchingService(embedder, weights, photo_adapter)
        if log:
            log("AI_UNAVAILABLE", "Using typed details matching; no AI score is claimed.")
        return TypedDetailsMatchingService(weights)
