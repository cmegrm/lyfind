"""Matching: several signals, hard rules, calibrated tiers, and a plain explanation for staff.

AI only suggests. Staff always make the final decision.

Signals, each scaled to 0..1 (or unknown):
  photo        DINOv2 image-to-image: the owner's photo against the item photo (same physical item)
  text_image   CLIP text-to-image: each side's words against the other side's photo
  description  typed words that both reports share (marks and private details included)
  category, color, brand, place, date   typed fields

Hard rules: a different category is never compared; an item found before the loss date is impossible;
contradictions (colour, brand) and far-apart dates stop a match from reaching Strong, or from showing at all.
If both sides sent a photo and the photos are clearly different objects, matching words cannot save the pair.
A close crop that falls away marks a look-alike (two phones, two backpacks) and keeps it below a real angle change.
A dull photo is brightened before comparison, then judged on the item rather than the background.
Two photos of the same item from different angles often sit below the DINOv2 Strong floor; those pairs stay visible as Possible.
"""
import os
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import date as _date
from functools import lru_cache
from math import isfinite, sqrt
from pathlib import Path
from threading import RLock

STRONG, POSSIBLE = 80, 60  # tiers: Strong >= 80, Possible 60-79, below 60 is hidden (never shown as a match)
# Raw DINOv2 cosine below this is a different object (shoe vs bag ~0.20). Same item, different angle can be ~0.60.
PHOTO_MISMATCH = 0.40
# Same physical item, similar framing sits here (same bag ~0.96). Two different phones in hand sit ~0.80–0.84.
PHOTO_STRONG = 0.88

AMBIGUITY_MARGIN = 6.0  # a Strong match must lead the next-best look-alike by at least this many points

SIGNALS = ("photo", "text_image", "description", "category", "color", "brand", "place", "date")
LABELS = {"photo": "Photo looks alike", "text_image": "Words fit the photo", "description": "Description words",
          "category": "Category", "color": "Color", "brand": "Brand", "place": "Place", "date": "Date"}


@dataclass(frozen=True)
class ScoreWeights:
    photo: float = 36
    text_image: float = 14
    description: float = 14
    category: float = 4
    color: float = 8
    brand: float = 6
    place: float = 10
    date: float = 8

    def __post_init__(self):
        values = asdict(self).values()
        if any(not isfinite(v) or v < 0 for v in values) or abs(sum(values) - 100) > 0.0001:
            raise ValueError("The matching weights must be non-negative and total 100.")
        if self.typed_total <= 0:
            raise ValueError("Keep a positive typed-details weight for fallback matching.")

    @classmethod
    def from_environment(cls):
        return cls(**{k: float(os.getenv("MATCH_WEIGHT_" + k.upper(), v)) for k, v in asdict(cls()).items()})

    @property
    def typed_total(self):
        return self.category + self.color + self.brand + self.place + self.date + self.description


@dataclass(frozen=True)
class Calibration:
    """Raw cosine is scaled to 0..1.

    DINOv2 (default photo path) is an instance model: the same bag vs a crop sits
    high (~0.96); a second backpack of the same kind sits lower (~0.72). CLIP
    ViT-B/32 is semantic (two different backpacks ~0.90), so CLIP-only photo
    matching uses CLIP_CALIBRATION instead of these defaults.
    """
    photo_low: float = PHOTO_STRONG
    photo_high: float = 0.96
    text_low: float = 0.17
    text_high: float = 0.28


CLIP_CALIBRATION = Calibration(photo_low=0.915, photo_high=0.985)
DINO_CALIBRATION = Calibration()


def _norm(value):
    return str(value or "").strip().casefold()


def brand_key(value):
    """Unknown is missing evidence, never a positive brand match."""
    key = _norm(value).replace("’", "'")
    return "" if key in {"unknown", "not known", "not sure", "i don't know", "i do not know", "n/a", "?"} else key


def cosine(a, b):
    if a is None or b is None or len(a) != len(b) or not len(a):
        return 0.0
    a, b = [float(x) for x in a], [float(x) for x in b]
    if any(not isfinite(x) for x in a + b):
        raise ValueError("The embedding model returned non-finite values.")
    den = sqrt(sum(x * x for x in a)) * sqrt(sum(y * y for y in b))
    return max(0.0, min(1.0, sum(x * y for x, y in zip(a, b)) / den)) if den else 0.0


def _scale(value, low, high):
    return max(0.0, min(1.0, (value - low) / (high - low))) if high > low else 0.0


def photo_from_raw(raw, low, high):
    """Map DINOv2 cosine to 0..1 without treating a new camera angle as 'not the same item'.

    Strong floor is `low` (~0.88). Same shoes from the side vs from above often sit ~0.60.
    That band gets partial credit. Below PHOTO_MISMATCH is a different object.
    """
    if raw is None:
        return None
    if raw >= high:
        return 1.0
    if raw >= low:
        return round(0.5 + 0.5 * _scale(raw, low, high), 3)
    if raw >= PHOTO_MISMATCH:
        return round(0.15 + 0.35 * _scale(raw, PHOTO_MISMATCH, low), 3)
    return 0.0


STOP = frozenset("""a an and are as at be been but by for from had has have i if in into is it its just lost found my me of on or our
that the their there this to was were with while near around inside outside very some one it's""".split())
COLORS = {"black", "white", "gray", "silver", "red", "blue", "green", "yellow", "orange", "pink", "purple", "brown", "beige", "gold"}
COLOR_ALIASES = {"grey": "gray", "navy": "blue", "teal": "green", "maroon": "red", "tan": "beige", "cream": "beige", "violet": "purple",
                 "transparent": "white", "clear": "white", "golden": "gold"}
COLOR_NEAR = {frozenset(p) for p in (("gray", "silver"), ("brown", "beige"), ("gold", "yellow"), ("black", "gray"),
                                      ("white", "silver"), ("white", "beige"), ("orange", "brown"), ("red", "pink"))}


def tokens(text):
    out = set()
    for word in re.findall(r"[a-z0-9]+", _norm(text)):
        if word in STOP or len(word) < 2:
            continue
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        out.add(word)
    return out


def color_set(value):
    found = set()
    for word in re.findall(r"[a-z]+", _norm(value)):
        word = COLOR_ALIASES.get(word, word)
        if word in COLORS:
            found.add(word)
    return found


def compare_colors(a, b):
    """1 same, 0.45 close shades, 0 different, None when either side gave no usable color."""
    ca, cb = color_set(a), color_set(b)
    if not ca or not cb:
        return (1.0, "same") if _norm(a) and _norm(a) == _norm(b) else (None, "unknown")
    if ca & cb:
        return 1.0, "same"
    if any(frozenset((x, y)) in COLOR_NEAR for x in ca for y in cb):
        return 0.45, "close"
    return 0.0, "different"


def compare_brands(a, b):
    ka, kb = brand_key(a), brand_key(b)
    if not ka or not kb:
        return None, "unknown"
    if ka == kb:
        return 1.0, "same"
    if ka in kb or kb in ka:
        return 0.8, "same"
    return 0.0, "different"


def compare_places(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return None, "unknown"
    if _norm(a) == _norm(b):
        return 1.0, "same"
    share = len(ta & tb)
    if share and share / min(len(ta), len(tb)) >= 0.5:
        return 0.75, "near"
    return (0.4, "near") if share else (0.1, "different")


def compare_dates(lost, found):
    """(value, state, gap_days). A found date before the lost date is impossible."""
    try:
        gap = (_date.fromisoformat(str(found)[:10]) - _date.fromisoformat(str(lost)[:10])).days
    except ValueError:
        return None, "unknown", None
    if gap < 0:
        return 0.0, "impossible", gap
    for limit, value in ((1, 1.0), (3, 0.85), (7, 0.6), (14, 0.35), (30, 0.15)):
        if gap <= limit:
            return value, "close" if value >= 0.6 else "far", gap
    return 0.0, "far", gap


def compare_words(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return None
    return min(1.0, len(ta & tb) / sqrt(len(ta) * len(tb)) / 0.6)


def report_words(report):
    return " ".join(str(report.get(k) or "") for k in ("description", "identifying_marks"))


def item_words(item):
    return " ".join(str(item.get(k) or "") for k in ("description", "private_details"))


def description_signal(report, item):
    """Owner-only marks count more than a generic 'black backpack' line."""
    marks = compare_words(report.get("identifying_marks"), item.get("private_details"))
    generic = compare_words(report.get("description"), item.get("description"))
    if marks is None and generic is None:
        return compare_words(report_words(report), item_words(item))
    if marks is None:
        return generic
    if generic is None:
        return marks
    return min(1.0, 0.7 * marks + 0.3 * generic)


def spoken(row):
    """A short phrase for CLIP's text side: colour, brand, category, description. CLIP reads at most about 77 tokens."""
    brand = brand_key(row.get("brand"))
    brand = "" if brand == "unbranded" else str(row.get("brand") or "").strip()
    lead = " ".join(x for x in (str(row.get("color") or "").strip(), brand) if x and x.casefold() not in str(row.get("description", "")).casefold())
    return ("a photo of " + (lead + " " if lead else "") + str(row.get("description") or row.get("category") or "an item").strip())[:180]


class EmbeddingAdapter(ABC):
    @abstractmethod
    def embed_text(self, text):
        pass

    @abstractmethod
    def embed_image(self, path):
        pass


class ClipAdapter(EmbeddingAdapter):
    """Convert a sentence-transformers CLIP model's encode API to our domain API. Results are cached."""
    matching_method = "clip_ai"

    def __init__(self, model):
        self._model = model
        self._lock = RLock()

    @lru_cache(maxsize=1024)
    def embed_text(self, text):
        text = str(text)[:200]
        with self._lock:
            try:
                return [float(x) for x in self._model.encode(text)]
            except Exception:  # CLIP accepts about 77 tokens; retry with a shorter text
                return [float(x) for x in self._model.encode(text[:70])]

    def embed_image(self, path):
        p = Path(path)
        stat = p.stat()
        return list(self._image(str(p.resolve()), stat.st_size, stat.st_mtime_ns))

    @lru_cache(maxsize=256)
    def _image(self, path, size, modified):
        from PIL import Image
        with self._lock, Image.open(path) as picture:
            return tuple(float(x) for x in self._model.encode(picture.convert("RGB")))


class DinoAdapter:
    """DINOv2 patch-token mean embedding, L2-normalised. Image-only; no text encoder.

    Mean pooling of patch tokens separates two backpacks better than the CLS token,
    which still leans semantic.
    """
    matching_method = "dino_ai"

    def __init__(self, model, processor):
        self._model = model
        self._processor = processor
        self._lock = RLock()

    def embed_text(self, text):
        return None

    def embed_image(self, path):
        p = Path(path)
        stat = p.stat()
        return list(self._image(str(p.resolve()), stat.st_size, stat.st_mtime_ns))

    def embed_image_views(self, path):
        """Full frame plus isolated/mirrored crops so a new camera angle still matches."""
        p = Path(path)
        stat = p.stat()
        return [list(v) for v in self._views(str(p.resolve()), stat.st_size, stat.st_mtime_ns)]

    @lru_cache(maxsize=256)
    def _image(self, path, size, modified):
        from PIL import Image
        with Image.open(path) as picture:
            return self._embed_rgb(picture.convert("RGB"))

    @lru_cache(maxsize=128)
    def _views(self, path, size, modified):
        from PIL import Image
        from lyfind.vision_prep import photo_views
        with Image.open(path) as picture:
            return tuple(self._embed_rgb(view) for view in photo_views(picture))

    def _embed_rgb(self, rgb):
        import torch
        with self._lock, torch.inference_mode():
            inputs = self._processor(images=rgb.convert("RGB"), return_tensors="pt")
            hidden = self._model(**inputs).last_hidden_state[:, 1:].mean(dim=1)
            vec = torch.nn.functional.normalize(hidden, dim=-1).squeeze(0)
            return tuple(float(x) for x in vec.tolist())


class HybridAdapter(EmbeddingAdapter):
    """DINOv2 for photo-to-photo instance matching; CLIP for words against photos."""
    matching_method = "dino_clip_ai"

    def __init__(self, instance, clip):
        self._instance = instance
        self._clip = clip

    def embed_text(self, text):
        return self._clip.embed_text(text)

    def embed_image(self, path):
        return self._instance.embed_image(path)

    def embed_image_views(self, path):
        views = getattr(type(self._instance), "embed_image_views", None)
        if callable(views):
            return views(self._instance, path)
        one = self.embed_image(path)
        return [one] if one is not None else []

    def embed_clip_image(self, path):
        return self._clip.embed_image(path)


def clip_image_vec(adapter, path):
    """CLIP image embedding when the adapter keeps a separate instance encoder."""
    method = getattr(type(adapter), "embed_clip_image", None)
    if callable(method):
        return adapter.embed_clip_image(path)
    return adapter.embed_image(path)


def _photo_vectors(adapter, path):
    """Prefer isolated crops when the encoder implements them; MagicMocks stay on embed_image."""
    views = getattr(type(adapter), "embed_image_views", None)
    if callable(views):
        try:
            vecs = [v for v in (views(adapter, path) or []) if v]
            if vecs:
                return vecs
        except Exception:
            pass
    one = adapter.embed_image(path)
    return [one] if one is not None else []


def _aligned_photo_cosine(owner_vecs, item_vecs):
    """(score, relation) from the full frame plus the same-slot crops.

    relation is "angle" when the center and the lower crop both look more alike than the
    whole frame (the background was the problem), "lookalike" when the full frames look
    similar but a close crop falls away (two phones, two backpacks), otherwise "direct".
    A single lucky crop cannot raise the score on its own.
    """
    full = cosine(owner_vecs[0], item_vecs[0])
    if len(owner_vecs) < 3 or len(item_vecs) < 3:
        return round(full, 4), "direct"
    center = cosine(owner_vecs[1], item_vecs[1])
    lower = cosine(owner_vecs[2], item_vecs[2])
    if center >= full + 0.04 and lower >= full + 0.04:
        return round(0.30 * full + 0.70 * min(center, lower), 4), "angle"
    weak = min(center, lower)
    if full >= 0.64 and weak + 0.10 < full:
        return round(0.40 * full + 0.60 * weak, 4), "lookalike"
    # Full frames of two phones agree a little, and neither close crop gets more alike.
    if PHOTO_MISMATCH < full < PHOTO_STRONG and center < full and lower < full and (center + lower) / 2 + 0.015 < full:
        return round((center + lower) / 2, 4), "lookalike"
    return round(full, 4), "direct"


class MatchingService(ABC):
    method = "abstract"

    def __init__(self, weights=None, calibration=None):
        self.weights = weights or ScoreWeights()
        self.calibration = calibration or Calibration()

    @abstractmethod
    def visual_signals(self, report, item):
        """Return ({'photo': 0..1, 'text_image': 0..1, ...}, note). Typed matching has no photo signals."""

    def evaluate(self, report, item):
        """Everything staff and the database need: score, tier, per-signal points and plain reasons."""
        w = asdict(self.weights)
        if _norm(report.get("category")) != _norm(item.get("category")):
            return self._blocked("Different categories are never compared.")
        date_value, date_state, gap = compare_dates(report.get("date_lost"), item.get("date_found"))
        if date_state == "impossible":
            return self._blocked("The item was found before the loss date, which is not possible.")
        color_value, color_state = compare_colors(report.get("color"), item.get("color"))
        brand_value, brand_state = compare_brands(report.get("brand"), item.get("brand"))
        place_value, place_state = compare_places(report.get("place"), item.get("place"))
        words = description_signal(report, item)
        visual, note = self.visual_signals(report, item)

        values = {"photo": visual.get("photo"), "text_image": visual.get("text_image"), "description": words, "category": 1.0,
                  "color": color_value, "brand": brand_value, "place": place_value, "date": date_value}
        available = {k: v for k, v in values.items() if v is not None}
        total_weight = sum(w[k] for k in available)
        coverage = total_weight / 100.0
        scale = (100.0 / total_weight) * (0.7 + 0.3 * coverage) if total_weight else 0.0
        points = {k: round(w[k] * v * scale, 2) for k, v in available.items()}
        raw = sum(points.values())

        caps = []
        raw_photo = (visual.get("raw") or {}).get("photo")
        if "photo" not in available and "text_image" not in available:
            caps.append((POSSIBLE + 19, "No photo comparison was possible, so typed details alone cannot make a Strong match."))
        elif raw_photo is not None and raw_photo < PHOTO_MISMATCH:
            # Wallet vs shoes sits ~0.17. Matching words cannot override a different object.
            caps.append((POSSIBLE - 1, "The photos are not of the same item. Matching words are not enough."))
        elif visual.get("relation") == "lookalike":
            # Two phones or two backpacks: the full frame agrees, a close crop does not.
            caps.append((69, "The photos look like the same kind of item, not the same one."))
        elif available.get("photo") is not None and available["photo"] < 0.5:
            # Same pair of shoes from another angle often scores ~0.70 raw, below the Strong floor (~0.88).
            caps.append((STRONG - 1, "The photos were taken from different angles, so this cannot be Strong. CSA should compare them."))
        elif max(available.get("photo", 0), available.get("text_image", 0)) < 0.3:
            caps.append((74, "The photo comparison does not support this match."))
        if color_state == "different":
            caps.append((69, "The colors differ."))
        if brand_state == "different":
            caps.append((69, "The brands differ."))
        if gap is not None and gap > 30:
            caps.append((POSSIBLE - 1, f"The item was found {gap} days after the loss date."))
        elif gap is not None and gap > 14:
            caps.append((74, f"The item was found {gap} days after the loss date."))
        if coverage < 0.5:
            caps.append((POSSIBLE + 14, "Too little information was given to call this Strong."))
        cap = min((c for c, _ in caps), default=100)
        # A cap never flattens the ranking: above the cap the score only creeps up, so look-alikes keep their order.
        total = round(max(0.0, min(raw, 100.0) if raw <= cap else cap - 0.2 * (100.0 - min(raw, 100.0))), 1)
        level = "strong" if total >= STRONG else "possible" if total >= POSSIBLE else "hidden"

        states = {"color": color_state, "brand": brand_state, "place": place_state, "date": date_state}
        reasons = []
        for key in SIGNALS:
            value = values[key]
            reasons.append(dict(key=key, label=LABELS[key], ok=value is not None and value >= 0.6, points=points.get(key, 0.0),
                                max=round(w[key] * scale, 2) if value is not None else 0.0,
                                state="unknown" if value is None else "good" if value >= 0.6 else "partial" if value >= 0.3 else "bad",
                                text=self._say(key, value, states.get(key), report, item, gap, visual)))
        return dict(version=2, method=self.method, level=level, total=total, raw_total=round(raw, 1), cap=cap if cap < 100 else None,
                    weights=w, scale=round(scale, 4), coverage=round(coverage, 2), contributions=points,
                    signals={k: (None if v is None else round(v, 3)) for k, v in values.items()},
                    similarity=visual.get("raw", {}), photo_source=visual.get("source", "not_used"),
                    reasons=reasons, caps=[t for _, t in caps], note=note,
                    explanation="A suggestion for staff to review. It is not proof of ownership and not a probability.")

    def _blocked(self, why):
        return dict(version=2, method=self.method, level="hidden", total=0.0, raw_total=0.0, cap=None, weights=asdict(self.weights),
                    scale=0, coverage=0, contributions={}, signals={}, similarity={}, photo_source="not_used", reasons=[],
                    caps=[why], note="", explanation=why)

    @staticmethod
    def _say(key, value, state, report, item, gap, visual):
        pct = "" if value is None else f" ({round(value * 100)}%)"
        if value is None:
            return {"photo": "No owner photo to compare",
                    "text_image": "Not checked", "description": "A description is missing, so words were not compared",
                    "color": "Color not given on one side", "brand": "Brand unknown on one side",
                    "place": "Place not given on one side", "date": "Date not clear"}.get(key, "Not compared")
        if key == "photo":
            alike = (visual.get("raw") or {}).get("photo")
            if alike is not None:
                pct = f" ({round(alike * 100)}% similar as photos)"
                if visual.get("relation") == "lookalike":
                    return "The photos look like the same kind of item, not the same one." + pct
                if visual.get("lighting") == "uneven" and visual.get("relation") == "angle":
                    return "One photo is much darker and the backgrounds differ. The item still lines up. CSA should compare the two photos." + pct
                if alike >= PHOTO_STRONG or value >= 0.6:
                    return "The two photos look like the same item" + pct
                if visual.get("relation") == "angle" or alike >= PHOTO_MISMATCH:
                    return "Same item can look different from another angle. CSA should compare the two photos." + pct
                return "The photos look like different items" + pct
            return ("The two photos look like the same item" if value >= 0.6 else "The photos only look similar, not like the same item" if value >= 0.3 else "The photos are not of the same item") + pct
        if key == "text_image":
            return ("The words fit the other photo" if value >= 0.6 else "The words only partly fit the photo" if value >= 0.3 else "The words do not fit the photo") + pct
        if key == "description":
            return ("The owner-only marks match" if value >= 0.6 else "Some of the same words, including marks" if value >= 0.3 else "Few shared marks or words") + pct
        if key == "category":
            return "Same category: " + str(item.get("category", "")).strip().title()
        if key == "color":
            return {"same": "Same color: " + str(item.get("color", "")), "close": "Close colors: %s and %s" % (report.get("color"), item.get("color"))}.get(
                state, "Colors differ: lost %s, found %s" % (str(report.get("color", "")).lower(), str(item.get("color", "")).lower()))
        if key == "brand":
            return "Same brand: " + str(item.get("brand", "")) if value >= 0.6 else "Brands differ"
        if key == "place":
            return {"same": "Same place: " + str(item.get("place", "")), "near": "Similar place"}.get(
                state, "Different place: lost at %s, found at %s" % (report.get("place"), item.get("place")))
        if key == "date":
            return f"Found {gap} day{'s' if gap != 1 else ''} after the loss date" if gap else "Found on the loss date"
        return ""

    def compare(self, report, item):
        info = self.evaluate(report, item)
        return info["total"], info["level"]

    def score(self, report, item):
        return self.evaluate(report, item)["total"]

    def explain(self, report, item):
        return self.evaluate(report, item)


class TypedDetailsMatchingService(MatchingService):
    method = "typed_details"

    def visual_signals(self, report, item):
        return {}, ""

    def evaluate(self, report, item):
        info = super().evaluate(report, item)
        if info.get("signals"):
            info["note"] = info["note"] or "Photo AI was not used for this suggestion. Typed details were compared and the result is capped below Strong."
        return info


class AIMatchingService(MatchingService):
    method = "clip_ai"

    def __init__(self, adapter, weights=None, calibration=None):
        super().__init__(weights, calibration)
        self._adapter = adapter
        method = getattr(type(adapter), "matching_method", "clip_ai")
        self.method = method if isinstance(method, str) else "clip_ai"

    def visual_signals(self, report, item):
        a, c = self._adapter, self.calibration
        raw, out, text_scores = {}, {}, []
        item_photo = item.get("photo_path")
        owner_photo = report.get("photo_path")
        item_vecs = _photo_vectors(a, item_photo) if item_photo else []
        owner_vecs = _photo_vectors(a, owner_photo) if owner_photo else []
        source = "none"
        if item_vecs and owner_vecs:
            raw["photo"], out["relation"] = _aligned_photo_cosine(owner_vecs, item_vecs)
            out["photo"] = photo_from_raw(raw["photo"], c.photo_low, c.photo_high)
            source = "owner_photo"
            if owner_photo and item_photo:
                from lyfind.vision_prep import brightness
                from PIL import Image
                try:
                    with Image.open(owner_photo) as owner_pic, Image.open(item_photo) as item_pic:
                        levels = (brightness(owner_pic), brightness(item_pic))
                except OSError:
                    levels = None
                if levels and min(levels) < 0.32 and max(levels) - min(levels) >= 0.15:
                    out["lighting"] = "uneven"
        clip_item = clip_image_vec(a, item_photo) if item_photo else None
        clip_owner = clip_image_vec(a, owner_photo) if owner_photo else None
        owner_words = a.embed_text(spoken(report)) if clip_item is not None else None
        item_words = a.embed_text(spoken(item)) if clip_owner is not None else None
        if clip_item is not None and owner_words is not None:
            raw["owner_words_vs_item_photo"] = cosine(owner_words, clip_item)
            text_scores.append(_scale(raw["owner_words_vs_item_photo"], c.text_low, c.text_high))
        if clip_owner is not None and item_words is not None:
            raw["item_words_vs_owner_photo"] = cosine(item_words, clip_owner)
            text_scores.append(_scale(raw["item_words_vs_owner_photo"], c.text_low, c.text_high))
        if text_scores:
            out["text_image"] = sum(text_scores) / len(text_scores)
            source = source if source != "none" else "owner_description"
        out["source"] = source
        out["raw"] = {k: round(v, 4) for k, v in raw.items()}
        return out, ""


class MatchingServiceFactory:
    @staticmethod
    def create(ai_available=False, embedder=None, log=None, weights=None, calibration=None):
        if ai_available and embedder is not None:
            return AIMatchingService(embedder, weights, calibration)
        if log:
            log("AI_UNAVAILABLE", "Using typed details matching; no AI score is claimed.")
        return TypedDetailsMatchingService(weights, calibration)


def settle_ambiguity(entries, margin=AMBIGUITY_MARGIN):
    """Two look-alike candidates cannot both be Strong. entries: [(report_id, item_id, info)], changed in place.

    When a Strong score is within `margin` of another candidate for the same report (or the same item), it becomes Possible
    (score held at 79) and says why, so staff compare the two instead of trusting one number.
    """
    for side in (0, 1):
        groups = {}
        for entry in entries:
            groups.setdefault(entry[side], []).append(entry[2])
        for infos in groups.values():
            if len(infos) < 2:
                continue
            for info in infos:
                info.setdefault("score_before_ambiguity", info["total"])
            close = [info for info in infos if info["level"] == "strong" and any(
                other is not info and other["score_before_ambiguity"] >= info["score_before_ambiguity"] - margin
                and other["score_before_ambiguity"] >= POSSIBLE for other in infos)]
            for info in close:  # decided on the original scores, so the order of the list cannot matter
                info["total"], info["level"], info["ambiguous"] = min(info["total"], STRONG - 1.0), "possible", True
                info["caps"] = list(info.get("caps", [])) + ["Another item looks almost the same, so CSA needs to compare them."]
                info["cap"] = STRONG - 1.0
    return entries


def calculate_match_score(owner_data, office_data, matcher=None):
    """Backend score used by staff UI. Weights stay 36 / 14 / 14 / 4 / 8 / … — this only fills them."""
    info = (matcher or TypedDetailsMatchingService()).evaluate(owner_data, office_data)
    weights = info.get("weights") or asdict(ScoreWeights())
    reasons = {row["key"]: row for row in info.get("reasons") or []}

    def block(key):
        row = reasons.get(key, {})
        return {
            "score": round(float(row.get("points") or 0), 2),
            "max": round(float(row.get("max") or weights.get(key) or 0), 2),
            "reason": row.get("text") or "",
        }

    return {
        "photoLooksAlike": block("photo"),
        "wordsFitPhoto": block("text_image"),
        "descriptionWords": block("description"),
        "category": block("category"),
        "color": block("color"),
        "overallPercentage": info.get("total", 0),
        "level": info.get("level"),
    }


calculateMatchScore = calculate_match_score
