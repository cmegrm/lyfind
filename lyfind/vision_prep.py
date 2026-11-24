"""Local subject isolation for photo matching. No cloud vision APIs.

Crops the likely item so DINOv2 compares the object, not the floor, hand, or office wall.
A dull owner photo is lifted before the crops, so it can meet a clear office photo.
Falls back to the original frame when the crop would throw the object away.
"""
import math

from PIL import Image, ImageFilter, ImageOps


def brightness(picture):
    """Average lightness from 0 to 1."""
    gray = picture.convert("L")
    hist = gray.histogram()
    total = sum(hist) or 1
    return sum(index * count for index, count in enumerate(hist)) / total / 255


def even_light(picture):
    """Lift a dull photo toward a clear one. A photo that is already bright is left alone."""
    rgb = picture.convert("RGB")
    mean = brightness(rgb)
    if mean < 0.38:
        gamma = max(0.45, math.log(0.42) / math.log(max(mean, 0.08)))
        rgb = rgb.point(lambda pixel: int(255 * ((pixel / 255) ** gamma)))
    return ImageOps.autocontrast(rgb, cutoff=1)


def photo_views(picture, size=256):
    """Full, center, lower, isolated subject, then a mirrored full frame.

    Worn items (a shoe on a foot) sit low in the frame. Office photos are often
    a hand-held close-up. Slot 3 is always the isolate so matching can compare it
    without treating a lucky center crop as proof. Slot 4 is a left-right flip.
    Lighting is evened first so a dim owner photo can match a bright office photo.
    """
    rgb = even_light(picture)
    width, height = rgb.size
    views = [rgb]
    views.append(rgb.crop((int(width * 0.25), int(height * 0.25), int(width * 0.75), int(height * 0.75))))
    views.append(rgb.crop((int(width * 0.08), int(height * 0.32), int(width * 0.92), height)))
    views.append(isolate_subject(rgb))
    views.append(ImageOps.mirror(rgb))
    return views


def isolate_subject(picture):
    """Trim pixels that look like the frame border so the item fills the crop."""
    rgb = picture.convert("RGB")
    width, height = rgb.size
    if width < 24 or height < 24:
        return rgb
    work = rgb.resize((96, 96), Image.BILINEAR).filter(ImageFilter.MedianFilter(3))
    pix = work.load()
    border = []
    for x in range(96):
        border.extend((pix[x, 0], pix[x, 95], pix[0, x], pix[95, x]))
    br = sum(p[0] for p in border) / len(border)
    bg = sum(p[1] for p in border) / len(border)
    bb = sum(p[2] for p in border) / len(border)
    scored = []
    for y in range(96):
        for x in range(96):
            r, g, b = pix[x, y]
            scored.append((abs(r - br) + abs(g - bg) + abs(b - bb), x, y))
    scored.sort(reverse=True)
    keep = scored[: max(40, int(0.28 * len(scored)))]
    cells = [(x, y) for _, x, y in keep]
    if len(cells) < 40:
        return rgb
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if (x1 - x0) < 12 or (y1 - y0) < 12:
        return rgb
    pad = 6
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(95, x1 + pad), min(95, y1 + pad)
    left = int(x0 / 96 * width)
    top = int(y0 / 96 * height)
    right = int((x1 + 1) / 96 * width)
    bottom = int((y1 + 1) / 96 * height)
    if right - left < 16 or bottom - top < 16:
        return rgb
    return rgb.crop((left, top, right, bottom))
