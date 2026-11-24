"""Matching accuracy check on a labelled, generated image set.

    .venv/bin/python scripts/eval_matching.py                 # held-out seeds 11,12,13 with the shipped settings
    .venv/bin/python scripts/eval_matching.py --seeds 1 --tune  # try weight/calibration presets on a tuning seed

The images are drawn with Pillow (12 object types, each in lookalike variants, shown on different backgrounds
and positions). They are synthetic: the numbers show how the signals behave together, not field accuracy.
See docs/MATCHING_ACCURACY.md.
"""
import argparse
import itertools
import random
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

from lyfind.matching import AIMatchingService, Calibration, AMBIGUITY_MARGIN, ScoreWeights, TypedDetailsMatchingService, settle_ambiguity  # noqa: E402

RGB = {"black": (35, 35, 38), "white": (238, 238, 232), "red": (196, 40, 45), "blue": (40, 80, 190), "green": (40, 125, 70),
       "brown": (120, 78, 45), "gray": (130, 132, 138), "pink": (230, 130, 170), "yellow": (232, 196, 50), "orange": (235, 125, 35),
       "purple": (115, 65, 160)}
# type: (category, nouns for the owner, nouns for the office, brands, colours to draw)
TYPES = {
    "wallet": ("wallets", ["wallet", "leather wallet", "billfold"], ["wallet", "folding wallet"], ["Fossil", "Levi's", "Coach", "Tommy"], ["black", "brown", "red", "blue", "gray"]),
    "phone": ("electronics", ["phone", "smartphone", "mobile phone"], ["smartphone", "mobile phone"], ["Samsung", "Apple", "Xiaomi", "Oppo"], ["black", "white", "blue", "red", "green"]),
    "earphones": ("electronics", ["earbuds", "earphones", "wireless earbuds"], ["earbuds with charging case", "wireless earphones"], ["Sony", "JBL", "Apple", "Anker"], ["white", "black", "pink", "blue", "gray"]),
    "keys": ("keys", ["keys", "key ring", "keychain with keys"], ["set of keys on a ring", "keys with a fob"], ["", "", "", ""], ["red", "blue", "green", "yellow", "black"]),
    "bottle": ("other", ["water bottle", "bottle", "tumbler"], ["water bottle", "drinking bottle"], ["Hydro Flask", "Nalgene", "Contigo", "Owala"], ["blue", "black", "pink", "green", "gray"]),
    "umbrella": ("other", ["umbrella", "folding umbrella"], ["umbrella", "compact umbrella"], ["", "", "", ""], ["black", "red", "blue", "green", "yellow"]),
    "backpack": ("bags", ["backpack", "school bag", "rucksack"], ["backpack", "canvas backpack"], ["Jansport", "Nike", "Herschel", "Adidas"], ["black", "blue", "green", "red", "gray"]),
    "id_card": ("documents", ["ID card", "student ID", "school ID"], ["identification card", "ID card in a holder"], ["", "", "", ""], ["white", "blue", "yellow", "green", "pink"]),
    "glasses": ("accessories", ["glasses", "eyeglasses", "spectacles"], ["pair of eyeglasses", "glasses"], ["Ray-Ban", "", "Oakley", ""], ["black", "brown", "red", "blue", "gray"]),
    "watch": ("accessories", ["watch", "wristwatch"], ["wristwatch", "watch with strap"], ["Casio", "Fossil", "Timex", "Seiko"], ["black", "brown", "red", "blue", "gray"]),
    "cap": ("clothing", ["cap", "baseball cap", "hat"], ["baseball cap", "cap"], ["Nike", "New Era", "Adidas", ""], ["black", "blue", "red", "green", "white"]),
    "notebook": ("documents", ["notebook", "spiral notebook", "journal"], ["spiral notebook", "notebook"], ["", "", "", ""], ["red", "blue", "green", "yellow", "purple"]),
}
PLACES = ["Jose P. Laurel (JPL) Building", "Sotero H. Laurel (SHL) Building", "Freedom Park", "Gymnasium",
          "Canteen / Food park", "Academic Resource Center (Library)", "Campus parking", "CSA Office"]
NEAR = {"Jose P. Laurel (JPL) Building": "JPL lobby", "Sotero H. Laurel (SHL) Building": "SHL hallway",
        "Freedom Park": "Freedom Park benches", "Gymnasium": "Gym lockers",
        "Canteen / Food park": "Food park", "Academic Resource Center (Library)": "Library tables",
        "Campus parking": "Parking near Gate 1", "CSA Office": "Administration Building"}
MARKS = [("sticker", "round {c} sticker"), ("tape", "strip of {c} tape"), ("initials", "initials {i} written on it")]
MARK_COLORS = ["red", "yellow", "blue", "white", "green", "orange"]


def shade(rgb, k):
    return tuple(max(0, min(255, int(v * k))) for v in rgb)


def draw_object(kind, d, cx, cy, s, rgb, mark, rng):
    """Draw one object centred at (cx, cy), about s pixels across."""
    dark, light = shade(rgb, 0.65), shade(rgb, 1.25)
    rr = lambda box, r, **kw: d.rounded_rectangle(box, radius=r, **kw)
    if kind == "wallet":
        w, h = s * .8, s * .55
        box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        rr(box, s * .06, fill=rgb, outline=dark, width=3)
        d.line((cx - w / 2 + 8, cy - h / 2 + 12, cx + w / 2 - 8, cy - h / 2 + 12), fill=dark, width=2)
        rr((cx + w * .22, cy - h * .12, cx + w / 2 + 6, cy + h * .12), 6, fill=light, outline=dark, width=2)
        for x in range(int(cx - w / 2 + 14), int(cx + w / 2 - 10), 12):
            d.line((x, cy + h / 2 - 12, x + 6, cy + h / 2 - 12), fill=dark, width=2)
        body = box
    elif kind == "phone":
        w, h = s * .42, s * .82
        box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        rr(box, s * .06, fill=rgb, outline=dark, width=3)
        rr((cx - w / 2 + 7, cy - h / 2 + 12, cx + w / 2 - 7, cy + h / 2 - 12), 8, fill=(20, 24, 40))
        d.ellipse((cx - w / 2 + 12, cy - h / 2 + 18, cx - w / 2 + 24, cy - h / 2 + 30), fill=(70, 70, 80))
        d.ellipse((cx - 6, cy + h / 2 - 22, cx + 6, cy + h / 2 - 10), outline=(160, 160, 170), width=2)
        body = box
    elif kind == "earphones":
        w, h = s * .62, s * .42
        box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        rr(box, s * .12, fill=rgb, outline=dark, width=3)
        d.line((cx - w / 2, cy - h * .1, cx + w / 2, cy - h * .1), fill=dark, width=2)
        d.ellipse((cx - 8, cy + 4, cx + 8, cy + 20), fill=shade(rgb, 1.4), outline=dark)
        for sx in (-1, 1):
            d.ellipse((cx + sx * w * .62 - 12, cy + h * .35, cx + sx * w * .62 + 12, cy + h * .35 + 26), fill=light, outline=dark, width=2)
            xa, xb = sorted((cx + sx * w * .25, cx + sx * w * .65))
            d.arc((xa, cy + h * .3, xb, cy + h * .9), 20, 160, fill=dark, width=2)
        body = box
    elif kind == "keys":
        d.ellipse((cx - s * .3, cy - s * .38, cx + s * .1, cy + s * .02), outline=(170, 170, 178), width=5)
        for i, ang in enumerate((-25, 15, 55)):
            x0, y0 = cx - s * .1, cy - s * .1
            kx, ky = x0 + (i - 1) * s * .12, y0 + s * .25 + i * 4
            rr((kx - 7, y0 + 12, kx + 7, ky + s * .3), 6, fill=(190, 190, 198), outline=(110, 110, 120), width=2)
            for t in range(3):
                d.rectangle((kx + 7, ky + s * .12 + t * 14, kx + 17, ky + s * .12 + t * 14 + 7), fill=(150, 150, 158))
        rr((cx + s * .1, cy - s * .15, cx + s * .36, cy + s * .2), 12, fill=rgb, outline=dark, width=3)
        body = (cx + s * .1, cy - s * .15, cx + s * .36, cy + s * .2)
    elif kind == "bottle":
        w, h = s * .32, s * .85
        box = (cx - w / 2, cy - h * .3, cx + w / 2, cy + h / 2)
        rr(box, s * .08, fill=rgb, outline=dark, width=3)
        rr((cx - w * .3, cy - h * .45, cx + w * .3, cy - h * .28), 6, fill=rgb, outline=dark, width=3)
        rr((cx - w * .34, cy - h * .52, cx + w * .34, cy - h * .43), 5, fill=shade(rgb, .5), outline=dark, width=2)
        d.rectangle((cx - w / 2 + 3, cy + h * .02, cx + w / 2 - 3, cy + h * .22), fill=shade(rgb, 1.5))
        body = box
    elif kind == "umbrella":
        w = s * .95
        d.pieslice((cx - w / 2, cy - s * .55, cx + w / 2, cy + s * .25), 180, 360, fill=rgb, outline=dark, width=3)
        for i in range(1, 4):
            x = cx - w / 2 + i * w / 4
            d.line((cx, cy - s * .3, x, cy - s * .15), fill=dark, width=2)
        d.line((cx, cy - s * .15, cx, cy + s * .42), fill=(70, 70, 75), width=5)
        d.arc((cx - 24, cy + s * .3, cx, cy + s * .55), 0, 180, fill=(70, 70, 75), width=5)
        body = (cx - w * .3, cy - s * .45, cx + w * .3, cy - s * .2)
    elif kind == "backpack":
        w, h = s * .62, s * .8
        box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        d.arc((cx - w * .2, cy - h * .62, cx + w * .2, cy - h * .38), 180, 360, fill=dark, width=5)
        rr(box, s * .16, fill=rgb, outline=dark, width=3)
        rr((cx - w * .38, cy + h * .02, cx + w * .38, cy + h * .38), 12, fill=light, outline=dark, width=3)
        d.line((cx - w * .38, cy + h * .1, cx + w * .38, cy + h * .1), fill=dark, width=2)
        d.line((cx - w * .3, cy - h * .3, cx + w * .3, cy - h * .3), fill=dark, width=3)
        body = (cx - w * .38, cy + h * .02, cx + w * .38, cy + h * .38)
    elif kind == "id_card":
        w, h = s * .85, s * .55
        box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        rr(box, 10, fill=rgb, outline=dark, width=3)
        rr((cx - w * .42, cy - h * .3, cx - w * .08, cy + h * .25), 5, fill=(215, 215, 220), outline=dark)
        d.ellipse((cx - w * .32, cy - h * .22, cx - w * .18, cy - h * .06), fill=(150, 150, 160))
        for i in range(4):
            d.line((cx, cy - h * .25 + i * h * .15, cx + w * .38 - (i % 2) * 20, cy - h * .25 + i * h * .15), fill=dark, width=3)
        d.rectangle((cx - w / 2 + 3, cy + h * .33, cx + w / 2 - 3, cy + h * .45), fill=dark)
        body = box
    elif kind == "glasses":
        r = s * .17
        for sx in (-1, 1):
            d.ellipse((cx + sx * s * .22 - r, cy - r, cx + sx * s * .22 + r, cy + r), outline=rgb, width=7, fill=(205, 225, 235))
        d.arc((cx - 14, cy - 14, cx + 14, cy + 6), 200, 340, fill=rgb, width=6)
        for sx in (-1, 1):
            d.line((cx + sx * (s * .22 + r), cy - 4, cx + sx * (s * .5), cy + s * .12), fill=rgb, width=6)
        body = (cx - s * .4, cy - r, cx + s * .4, cy + r)
    elif kind == "watch":
        d.rectangle((cx - s * .1, cy - s * .5, cx + s * .1, cy + s * .5), fill=rgb, outline=dark, width=3)
        for i in range(-3, 4):
            d.ellipse((cx - 3, cy + i * 10 + 20 - 3, cx + 3, cy + i * 10 + 20 + 3), fill=dark)
        d.ellipse((cx - s * .24, cy - s * .24, cx + s * .24, cy + s * .24), fill=(200, 200, 205), outline=(90, 90, 100), width=5)
        d.ellipse((cx - s * .19, cy - s * .19, cx + s * .19, cy + s * .19), fill=(245, 245, 240))
        d.line((cx, cy, cx, cy - s * .15), fill=(30, 30, 30), width=3)
        d.line((cx, cy, cx + s * .1, cy + s * .04), fill=(30, 30, 30), width=3)
        body = (cx - s * .1, cy + s * .26, cx + s * .1, cy + s * .45)
    elif kind == "cap":
        w = s * .8
        d.pieslice((cx - w / 2, cy - s * .45, cx + w / 2, cy + s * .35), 180, 360, fill=rgb, outline=dark, width=3)
        d.ellipse((cx - w * .1, cy + s * .02, cx + w * .72, cy + s * .24), fill=dark, outline=dark)
        d.ellipse((cx - 5, cy - s * .45 - 4, cx + 5, cy - s * .45 + 6), fill=dark)
        for i in (-1, 0, 1):
            d.arc((cx - w * .3 + i * 20, cy - s * .45, cx + w * .3 + i * 20, cy + s * .3), 200, 340, fill=dark, width=2)
        body = (cx - w * .25, cy - s * .25, cx + w * .1, cy - s * .05)
    else:  # notebook
        w, h = s * .62, s * .8
        box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        rr(box, 8, fill=rgb, outline=dark, width=3)
        for y in range(int(cy - h / 2 + 14), int(cy + h / 2 - 8), 20):
            d.ellipse((cx - w / 2 - 6, y, cx - w / 2 + 8, y + 12), fill=(210, 210, 215), outline=(90, 90, 95))
        rr((cx - w * .3, cy - h * .3, cx + w * .38, cy - h * .05), 5, fill=(240, 240, 235), outline=dark)
        body = (cx - w * .3, cy + h * .05, cx + w * .38, cy + h * .35)
    # the owner's distinctive mark, drawn on the item
    kindm, mcolor, initials = mark
    mx = body[0] + (body[2] - body[0]) * (.25 + .5 * rng.random())
    my = body[1] + (body[3] - body[1]) * (.25 + .5 * rng.random())
    if kindm == "sticker":
        d.ellipse((mx - 11, my - 11, mx + 11, my + 11), fill=RGB[mcolor], outline=(30, 30, 30), width=1)
    elif kindm == "tape":
        d.rectangle((body[0] + 6, my - 4, body[2] - 6, my + 4), fill=RGB[mcolor])
    else:
        d.text((mx - 10, my - 6), initials, fill=RGB["white"] if rgb[0] + rgb[1] + rgb[2] < 400 else RGB["black"])


def background(rng, size=224):
    base = rng.choice([(222, 214, 200), (190, 190, 195), (160, 130, 100), (235, 235, 235), (120, 140, 125), (70, 72, 80)])
    img = Image.new("RGB", (size * 2, size * 2), base)
    d = ImageDraw.Draw(img)
    for _ in range(rng.randint(2, 5)):
        x, y = rng.randint(0, size * 2), rng.randint(0, size * 2)
        d.ellipse((x, y, x + rng.randint(40, 240), y + rng.randint(40, 240)), fill=shade(base, rng.uniform(.88, 1.12)))
    return img


def render(kind, color, mark, rng, size=224):
    img = background(rng, size)
    d = ImageDraw.Draw(img)
    s = rng.uniform(.62, .85) * size * 2
    cx, cy = size + rng.randint(-24, 24), size + rng.randint(-24, 24)
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((cx - s * .4, cy + s * .35, cx + s * .4, cy + s * .5), fill=(0, 0, 0, 70))
    img.paste(shadow.filter(ImageFilter.GaussianBlur(10)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(10)))
    state = rng.getstate()
    draw_object(kind, d, cx, cy, s, shade(RGB[color], rng.uniform(.9, 1.1)), mark, rng)
    rng.setstate(state)
    img = img.rotate(rng.uniform(-18, 18), resample=Image.BICUBIC, fillcolor=(200, 200, 200))
    return img.resize((size, size), Image.LANCZOS)


def make_dataset(seed, folder):
    """Returns (found_items, lost_reports). Each lost report has `true` = index of its item, or None for no-match reports."""
    rng = random.Random(seed)
    items, losts = [], []
    folder = Path(folder)
    counter = itertools.count()
    base_day = 100

    def day(n):
        return (date(2026, 1, 1) + timedelta(days=n)).isoformat()

    def new_mark():
        kind, tmpl = rng.choice(MARKS)
        color, initials = rng.choice(MARK_COLORS), "".join(rng.choice("ABCDEFGHJKLMNPRSTW") for _ in range(2))
        return (kind, color, initials), tmpl.format(c=color, i=initials)

    def save(img):
        path = folder / f"{next(counter):04d}.jpg"
        img.save(path, quality=88)
        return str(path)

    def write(kind, color, brand, mark, mark_text, place, date_n, has_photo_lost=True, matched=True):
        category, owner_nouns, office_nouns, _, _ = TYPES[kind]
        owner_color = color if rng.random() > .08 else ""
        shade_word = rng.choice(["", "", "dark ", "light "])
        item = dict(category=category, description=f"{color.title()} {rng.choice(office_nouns)}" + (f" with a {brand} logo" if brand and rng.random() < .6 else ""),
                    color=color.title(), brand=brand if (brand and rng.random() < .7) else rng.choice(["", "unknown"]),
                    place=place, date_found=day(date_n + rng.randint(0, 3)),
                    private_details=(mark_text + ". " if rng.random() < .6 else "") + rng.choice(["Found on a table", "Handed in by a student", "Left on a bench"]),
                    photo_path=save(render(kind, color, mark, rng)), kind=kind)
        lost_place = place if rng.random() < .6 else NEAR[place] if rng.random() < .5 else rng.choice(PLACES)
        lost = dict(category=category, description=f"{rng.choice(['My', 'I lost my', 'Lost'])} {shade_word}{color} {rng.choice(owner_nouns)}" + (f" by {brand}" if brand and rng.random() < .5 else ""),
                    color=owner_color.title() if owner_color else "", brand=brand if (brand and rng.random() < .5) else rng.choice(["", "unknown"]),
                    place=lost_place, date_lost=day(date_n), identifying_marks=mark_text if rng.random() < .55 else "",
                    kind=kind, true=None)
        if has_photo_lost:
            lost["photo_path"] = save(render(kind, color, mark, rng))
        return item, lost

    for kind, (category, _, _, brands, colors) in TYPES.items():
        # four instances per type: two share a colour (the hard lookalike case), two differ
        palette = [colors[0], colors[0], colors[1], colors[2]]
        first = {}
        for n in range(4):
            mark, text = new_mark()
            place, when, brand = rng.choice(PLACES), base_day + rng.randint(0, 25), brands[n]
            if n == 1 and rng.random() < .7:  # the lookalike: same colour, brand, and often the same place and week
                brand = first["brand"]
                place = first["place"] if rng.random() < .6 else place
                when = first["when"] + rng.randint(0, 3) if rng.random() < .6 else when
            if n == 0:
                first = dict(brand=brand, place=place, when=when)
            item, lost = write(kind, palette[n], brand, mark, text, place, when, has_photo_lost=rng.random() < .75)
            lost["true"] = len(items)
            items.append(item)
            losts.append(lost)
        # one lost report with no matching item in the office: same type and often the same colour as an item that is there
        mark, text = new_mark()
        _, ghost = write(kind, colors[0] if rng.random() < .6 else colors[4], rng.choice(brands), mark, text, rng.choice(PLACES), base_day + rng.randint(0, 25), has_photo_lost=rng.random() < .75)
        losts.append(ghost)
    return items, losts


def degrade(losts, seed):
    """Text-poor regime: half of the owners write only a short generic line (no colour, brand, marks, or the right place)."""
    rng = random.Random(seed * 7919)
    out = []
    for lost in losts:
        lost = dict(lost)
        if rng.random() < .5:
            noun = lost["description"].split()[-1]
            lost.update(description=f"Lost {noun}", color="", brand="", identifying_marks="", place=rng.choice(PLACES))
        out.append(lost)
    return out


def evaluate(items, losts, matcher, margin=AMBIGUITY_MARGIN):
    """Rank every same-category item for every lost report. Returns metrics."""
    top1 = top3 = with_true = 0
    strong_pairs = strong_true = strong_false = 0
    ghost_with_strong = ghosts = 0
    possible_false = possible_true = shown_true = 0
    entries = []
    for li, lost in enumerate(losts):
        for index, item in enumerate(items):
            info = matcher.evaluate(lost, item)
            if info["level"] == "hidden" and not info["contributions"]:
                continue  # different category or impossible dates
            entries.append((li, index, info))
    settle_ambiguity([(li, index, info) for li, index, info in entries], margin=margin)
    for li, lost in enumerate(losts):
        scored = sorted(((info["total"], index, info["level"]) for l, index, info in entries if l == li), key=lambda t: -t[0])
        order = [i for _, i, _ in scored]
        if lost["true"] is None:
            ghosts += 1
            if any(level == "strong" for _, _, level in scored):
                ghost_with_strong += 1
        else:
            with_true += 1
            top1 += bool(order and order[0] == lost["true"])
            top3 += lost["true"] in order[:3]
        for score, index, level in scored:
            correct = index == lost["true"]
            if level == "strong":
                shown_true += correct
                strong_pairs += 1
                strong_true += correct
                strong_false += not correct
            elif level == "possible":
                shown_true += correct
                possible_true += correct
                possible_false += not correct
    return dict(reports=with_true, ghosts=ghosts, top1=top1 / with_true, top3=top3 / with_true,
                strong_pairs=strong_pairs, strong_precision=strong_true / strong_pairs if strong_pairs else 1.0,
                strong_false=strong_false, false_positive_rate=strong_false / strong_pairs if strong_pairs else 0.0,
                strong_recall=strong_true / with_true, shown_recall=shown_true / with_true, possible_true=possible_true, possible_false=possible_false,
                ghost_with_strong=ghost_with_strong, ghost_rate=ghost_with_strong / ghosts if ghosts else 0.0)


def build_adapter():
    from lyfind.ai_runtime import LocalAI
    ai = LocalAI()
    adapter = ai.prepare()
    if adapter is None:
        raise SystemExit("Local matching models are not available: " + ai.reason)
    return adapter


def combine(rows):
    keys = rows[0].keys()
    return {k: sum(r[k] for r in rows) / len(rows) for k in keys}


def show(title, m):
    print(f"{title:<34} top-1 {m['top1']*100:5.1f}%  top-3 {m['top3']*100:5.1f}%  strong precision {m['strong_precision']*100:5.1f}%  "
          f"false-strong {m['false_positive_rate']*100:4.1f}% ({m['strong_false']:.1f} pairs)  strong recall {m['strong_recall']*100:5.1f}%  shown(strong+possible) {m['shown_recall']*100:5.1f}%  "
          f"no-match reports shown Strong {m['ghost_rate']*100:4.1f}%")


def zero_shot(adapter, items):
    """Does CLIP itself recognise the drawn objects? A sanity check on how realistic the images are."""
    from lyfind.matching import clip_image_vec, cosine
    if adapter.embed_text("a photo of a backpack") is None:
        return 0.0
    names = list(TYPES)
    texts = {k: adapter.embed_text("a photo of a " + k.replace("_", " ")) for k in names}
    right = sum(max(names, key=lambda k: cosine(texts[k], clip_image_vec(adapter, i["photo_path"]))) == i["kind"] for i in items)
    return right / len(items)


def main():
    print('EXPERIMENTAL EIGHT-CLUE BENCHMARK ONLY. The website uses the five proposal clues through ProposalMatcher; these are not live website accuracy figures.')
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="11,12,13")
    parser.add_argument("--tune", action="store_true")
    args = parser.parse_args()
    adapter = build_adapter()
    started = time.time()
    sets = []
    with tempfile.TemporaryDirectory() as tmp:
        for seed in [int(s) for s in args.seeds.split(",")]:
            folder = Path(tmp) / str(seed)
            folder.mkdir()
            items, losts = make_dataset(seed, folder)
            sets.append((seed, items, losts))
        print(f"{sum(len(i) for _, i, _ in sets)} found items, {sum(len(l) for _, _, l in sets)} lost reports in {len(sets)} sets "
              f"({sum(1 for _, _, l in sets for x in l if x['true'] is None)} have no item in the office)")
        print(f"CLIP names the drawn object type correctly for {zero_shot(adapter, [i for _, items, _ in sets for i in items]) * 100:.0f}% of the photos")

        def run(label, matcher, regime=None):
            result = combine([evaluate(i, regime(l, seed) if regime else l, matcher) for seed, i, l in sets])
            show(label, result)
            return result

        base = ScoreWeights()
        if args.tune:
            wide = Calibration(photo_low=.65, photo_high=.92)
            presets = {
                "shipped": (base, Calibration()),
                "photo-heavy": (ScoreWeights(photo=36, text_image=14, description=14, category=4, color=8, brand=6, place=10, date=8), Calibration()),
                "typed-heavy": (ScoreWeights(photo=20, text_image=10, description=20, category=5, color=12, brand=10, place=13, date=10), Calibration()),
                "tight photo scale": (base, Calibration(photo_low=.88, photo_high=.96)),
                "wide photo scale": (base, Calibration(photo_low=.60, photo_high=.90)),
                "text 0.17-0.28": (base, Calibration(text_low=.17, text_high=.28)),
            }
            for label, (weights, cal) in presets.items():
                run(label, AIMatchingService(adapter, weights, cal))
                run("   text-poor: " + label, AIMatchingService(adapter, weights, cal), degrade)
        else:
            photo_only = ScoreWeights(photo=60, text_image=0, description=0, category=0, color=0, brand=0, place=0, date=40)
            for title, regime in (("Typed details are rich (colour, brand, marks, place)", None), ("Text-poor (half the owners write one generic line)", degrade)):
                print("\n" + title)
                run("DINOv2 + CLIP + typed (shipped)", AIMatchingService(adapter, base, Calibration()), regime)
                run("Typed details only (AI off)", TypedDetailsMatchingService(base, Calibration()), regime)
                run("Photo similarity only", AIMatchingService(adapter, photo_only, Calibration()), regime)
        print(f"Elapsed {time.time() - started:.1f}s")


if __name__ == "__main__":
    main()
