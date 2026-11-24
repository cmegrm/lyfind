"""Google AI Studio (Gemini) multimodal matcher using the official google-genai SDK."""
import base64
import io
import json
import os
from math import isfinite
from pathlib import Path
from threading import RLock

from matching import MatchingService

DEFAULT_GEMINI_MODEL = "gemini-4-hydrogen"
FALLBACK_GEMINI_MODELS = ("gemini-4-argon", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite")
_DEPRECATED_PREFIXES = ("gemini-2.5", "gemini-2.0", "gemini-1.5", "gemini-1.0")

MATCH_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "description_similarity": {
            "type": "number",
            "description": "0.0 to 1.0 score for how closely the lost report description and owner-only marks match the found item description and CSA private notes.",
        },
        "photo_similarity": {
            "type": ["number", "null"],
            "description": "0.0 to 1.0 score comparing the two photos (or comparing the owner's description/marks against the CSA photo when no owner photo exists). Null if no CSA item photo was provided.",
        },
        "same_physical_item": {
            "type": "boolean",
            "description": "True only when the visual evidence strongly indicates the exact same physical item (not merely a look-alike of the same category).",
        },
        "summary": {
            "type": "string",
            "description": "One or two short plain-English sentences for CSA staff explaining what matched or differed. Never claim ownership is proven.",
        },
    },
    "required": ["description_similarity", "photo_similarity", "same_physical_item", "summary"],
}

VALID_CATEGORIES = (
    "id", "phone", "wallets", "keys", "cards", "cash", "watch", "glasses", "jewelry",
    "bags", "clothing", "shoes", "uniform", "accessories", "laptop", "earphones",
    "charger", "usb", "calculator", "electronics", "books", "documents", "umbrella",
    "bottle", "sports", "medicine", "other",
)
VALID_COLORS = (
    "Black", "Blue", "Brown", "Gray", "Green", "Orange", "Pink",
    "Purple", "Red", "White", "Yellow", "Gold", "Silver", "Multicolor",
)

DESCRIBE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": list(VALID_CATEGORIES),
            "description": "Best matching LyFind item category code.",
        },
        "color": {
            "type": "string",
            "enum": list(VALID_COLORS),
            "description": "Main visible color of the item.",
        },
        "brand": {
            "type": "string",
            "description": "Clearly visible brand name on the item (e.g. Herschel, Nike, Apple), or empty string if not clearly visible.",
        },
        "description": {
            "type": "string",
            "description": "One short plain-English sentence describing what the item looks like. Never include personal names, ID numbers, or sensitive numbers.",
        },
    },
    "required": ["category", "color", "brand", "description"],
}

DESCRIBE_INSTRUCTION = (
    "You help fill out a campus Lost and Found form from one item photo. "
    "Identify the best matching category, main color, clearly visible brand (or empty string if unsure), "
    "and write one short plain-English sentence describing the visible object. "
    "Never transcribe personal names, student ID numbers, credit card numbers, or passwords. "
    "Return valid JSON strictly matching the schema."
)

SYSTEM_INSTRUCTION = (
    "You assist campus Lost and Found (CSA) staff in comparing one lost-item report against one found item in office inventory. "
    "Be careful and conservative: a score is only a similarity hint, never proof of ownership. "
    "Two items of the same category (such as two different black backpacks or two different phones) must NOT get a high photo_similarity or same_physical_item=true unless distinctive details, wear, stickers, logos, colors, or markings clearly match. "
    "Pay close attention to owner-only identifying marks compared against CSA private details. "
    "Return valid JSON strictly matching the schema."
)


def resolve_gemini_model(value=None):
    raw = str(value if value is not None else os.environ.get("GEMINI_MODEL", "")).strip()
    if not raw or any(raw.lower().startswith(prefix) for prefix in _DEPRECATED_PREFIXES):
        return DEFAULT_GEMINI_MODEL
    return raw


def _sniff_mime(raw):
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(raw) >= 12 and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _prepare_image_bytes(raw, max_side=1024):
    """Resize raw image bytes into an inline base64 image block for Gemini."""
    mime = _sniff_mime(raw)
    try:
        from PIL import Image

        with Image.open(io.BytesIO(raw)) as img:
            rgb = img.convert("RGB")
            if max(rgb.size) > max_side:
                rgb.thumbnail((max_side, max_side))
            buf = io.BytesIO()
            rgb.save(buf, format="JPEG", quality=85)
            raw = buf.getvalue()
            mime = "image/jpeg"
    except Exception:
        pass
    return {
        "type": "image",
        "data": base64.b64encode(raw).decode("ascii"),
        "mime_type": mime,
    }


def _prepare_image_part(path, max_side=1024):
    """Read and optionally resize a local photo into an inline base64 image block for Gemini."""
    return _prepare_image_bytes(Path(path).read_bytes(), max_side=max_side)


def _clamp01(value):
    num = float(value)
    if not isfinite(num):
        raise ValueError("Gemini returned a non-finite similarity score.")
    return max(0.0, min(1.0, num))


class GeminiClientAdapter:
    """Thin OOP adapter around the official google-genai Interactions API."""

    matching_method = "gemini_ai"

    def __init__(self, api_key=None, model=None, client=None):
        self.api_key = (api_key if api_key is not None else os.environ.get("GEMINI_API_KEY", "")).strip()
        self.model = resolve_gemini_model(model)
        self._lock = RLock()
        if client is not None:
            self._client = client
        else:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is required for Gemini matching.")
            from google import genai

            self._client = genai.Client(
                api_key=self.api_key,
                http_options={
                    "timeout": 15000,
                    "retry_options": {
                        "attempts": 1,
                    },
                },
            )

    def compare_pair(self, report, item):
        owner_photo = report.get("photo_path") if report.get("photo_path") and Path(report["photo_path"]).is_file() else None
        item_photo = item.get("photo_path") if item.get("photo_path") and Path(item["photo_path"]).is_file() else None

        prompt_lines = [
            "Compare this Lost Report and Found Item (same category):",
            f"Category: {report.get('category', '')}",
            "",
            "[LOST REPORT]",
            f"- Description: {report.get('description', '')}",
            f"- Owner-only identifying marks: {report.get('identifying_marks', '') or '(none provided)'}",
            f"- Color: {report.get('color', '') or '(not stated)'}",
            f"- Brand: {report.get('brand', '') or '(unknown)'}",
            f"- Place lost: {report.get('place', '') or '(not stated)'}",
            f"- Date lost: {report.get('date_lost', '')}",
            "",
            "[FOUND ITEM AT CSA]",
            f"- Description: {item.get('description', '')}",
            f"- CSA private details: {item.get('private_details', '') or '(none provided)'}",
            f"- Color: {item.get('color', '') or '(not stated)'}",
            f"- Brand: {item.get('brand', '') or '(unknown)'}",
            f"- Place found: {item.get('place', '') or '(not stated)'}",
            f"- Date found: {item.get('date_found', '')}",
        ]
        if owner_photo and item_photo:
            prompt_lines.append("\nTwo photos follow: FIRST is the owner's photo, SECOND is the CSA office photo of the found item.")
        elif item_photo:
            prompt_lines.append("\nOne photo follows: the CSA office photo of the found item. Compare the owner's written description and marks against this photo.")
        else:
            prompt_lines.append("\nNo photos are attached. Set photo_similarity to null and same_physical_item to false.")

        inputs = [{"type": "text", "text": "\n".join(prompt_lines)}]
        if owner_photo and item_photo:
            inputs.append(_prepare_image_part(owner_photo))
            inputs.append(_prepare_image_part(item_photo))
        elif item_photo:
            inputs.append(_prepare_image_part(item_photo))

        models_to_try = [self.model] + [m for m in FALLBACK_GEMINI_MODELS if m != self.model]
        interaction = None
        last_error = None
        with self._lock:
            for candidate_model in models_to_try:
                try:
                    interaction = self._client.interactions.create(
                        model=candidate_model,
                        system_instruction=SYSTEM_INSTRUCTION,
                        input=inputs,
                        response_format={
                            "type": "text",
                            "mime_type": "application/json",
                            "schema": MATCH_RESPONSE_SCHEMA,
                        },
                        store=False,
                        timeout=15.0,
                    )
                    self.last_model = candidate_model
                    break
                except Exception as error:
                    last_error = error
                    msg = str(error).lower()
                    if any(code in msg for code in ("503", "high demand", "unavailable", "overloaded", "not found", "404", "429", "quota", "timeout", "timed out")):
                        continue
                    raise
        if interaction is None:
            raise last_error or RuntimeError("Gemini could not complete the comparison.")

        raw_text = (getattr(interaction, "output_text", None) or "").strip()
        if not raw_text:
            raise RuntimeError("Gemini returned an empty response.")
        parsed = json.loads(raw_text)
        desc = _clamp01(parsed.get("description_similarity", 0.0))
        photo_raw = parsed.get("photo_similarity")
        photo = _clamp01(photo_raw) if (item_photo and photo_raw is not None) else None
        same_item = bool(parsed.get("same_physical_item", False)) if (owner_photo and item_photo) else False
        summary = " ".join(str(parsed.get("summary") or "").split())[:400]
        return {
            "description_similarity": desc,
            "photo_similarity": photo,
            "same_physical_item": same_item,
            "summary": summary,
        }

    def describe_photo_bytes(self, raw):
        inputs = [
            {"type": "text", "text": "Inspect this lost or found campus item photo and fill the form fields."},
            _prepare_image_bytes(raw),
        ]
        models_to_try = [self.model] + [m for m in FALLBACK_GEMINI_MODELS if m != self.model]
        interaction = None
        last_error = None
        with self._lock:
            for candidate_model in models_to_try:
                try:
                    interaction = self._client.interactions.create(
                        model=candidate_model,
                        system_instruction=DESCRIBE_INSTRUCTION,
                        input=inputs,
                        response_format={
                            "type": "text",
                            "mime_type": "application/json",
                            "schema": DESCRIBE_RESPONSE_SCHEMA,
                        },
                        store=False,
                        timeout=15.0,
                    )
                    self.last_model = candidate_model
                    break
                except Exception as error:
                    last_error = error
                    msg = str(error).lower()
                    if any(code in msg for code in ("503", "high demand", "unavailable", "overloaded", "not found", "404", "429", "quota", "timeout", "timed out")):
                        continue
                    raise
        if interaction is None:
            raise last_error or RuntimeError("Gemini could not read that photo right now.")
        raw_text = (getattr(interaction, "output_text", None) or "").strip()
        if not raw_text:
            raise RuntimeError("Gemini returned an empty response.")
        parsed = json.loads(raw_text)
        category = str(parsed.get("category") or "other").strip().lower()
        if category not in VALID_CATEGORIES:
            category = "other"
        color = str(parsed.get("color") or "").strip().title()
        if color not in VALID_COLORS:
            color = ""
        brand = " ".join(str(parsed.get("brand") or "").split())[:80]
        if brand.lower() in {"unknown", "none", "n/a", "unbranded", "not visible"}:
            brand = ""
        description = " ".join(str(parsed.get("description") or "").split())[:300]
        return {
            "category": category,
            "color": color,
            "brand": brand,
            "description": description,
            "model": getattr(self, "last_model", self.model),
        }


class GeminiMatchingService(MatchingService):
    """Proposal five-clue matcher backed by Google AI Studio (Gemini)."""

    method = "gemini_ai"
    STRONG_PHOTO_SIMILARITY = 0.78

    def __init__(self, adapter, weights=None):
        super().__init__(weights)
        self._adapter = adapter

    def compare(self, report, item):
        score, level, _ = self.evaluate(report, item)
        return score, level

    def evaluate(self, report, item):
        if str(report.get("category") or "").strip().casefold() != str(item.get("category") or "").strip().casefold():
            return 0.0, "hidden", {}
        details = self.explain(report, item)
        score, level = self._label(details["total"], details["strong_caveat"])
        return score, level, details

    def _strong_caveat(self, report, item, parts, photo_similarity, same_physical_item, has_owner_photo):
        if report["date_lost"] > item["date_found"]:
            return "The reported loss date is after the found date."
        typed_agreement = sum((parts[key] or 0) > 0 for key in ("color", "brand", "place"))
        description_agrees = self.weights.description > 0 and (parts["description"] or 0) >= self.weights.description / 2
        if has_owner_photo and photo_similarity is not None and self.weights.photo > 0:
            if not same_physical_item or photo_similarity < self.STRONG_PHOTO_SIMILARITY:
                return "Gemini judged that the owner and CSA photos do not agree closely enough for a Strong match."
            if not description_agrees and typed_agreement < 2:
                return "The photo needs support from the descriptions or at least two typed details."
        elif not description_agrees or typed_agreement < 2:
            return "Without an owner photo comparison, Strong needs agreeing descriptions and at least two of color, brand and place."
        return None

    def explain(self, report, item):
        has_owner_photo = bool(report.get("photo_path") and Path(report["photo_path"]).is_file())
        has_item_photo = bool(item.get("photo_path") and Path(item["photo_path"]).is_file())
        result = self._adapter.compare_pair(report, item)

        parts = self.typed_parts(report, item)
        parts["description"] = self.weights.description * result["description_similarity"]
        source = "owner_photo" if (has_owner_photo and has_item_photo) else ("owner_description" if has_item_photo else "not_used")
        parts["photo"] = (self.weights.photo * result["photo_similarity"]) if (has_item_photo and result["photo_similarity"] is not None) else None

        details = self.summarize(parts, source, report)
        used_model = getattr(self._adapter, "last_model", None) or self._adapter.model
        details["photo_model"] = f"Gemini ({used_model})" if parts["photo"] is not None else None
        typed_note = details["statement"]
        summary = result["summary"]
        details["statement"] = " ".join(part for part in (summary, typed_note) if part)
        details["strong_caveat"] = self._strong_caveat(
            report, item, parts, result["photo_similarity"], result["same_physical_item"], has_owner_photo
        )
        return details
