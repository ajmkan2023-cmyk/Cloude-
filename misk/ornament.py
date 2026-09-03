"""الزخرفة: خطوط فاصلة، أركان عربسك، إكليل، وإطار الصفحة.

كل شكل يُرسم على قناع رمادي مكبّر ثلاث مرّات ثم يُصغَّر — لأن ‎ImageDraw‎
لا تنعّم الحواف، والحواف الخشنة أوّل ما يفضح التصميم. الأشكال تُخزَّن
لأن الزخرفة ثابتة عبر الإطارات؛ الحركة تأتي من *كشفها* لا من إعادة رسمها.
"""

from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from .paint import mask_supersample

SS = 3  # معامل التكبير قبل التصغير


# ── هندسة ─────────────────────────────────────────────────────────────
def bezier(p0, p1, p2, p3, steps: int = 56) -> list[tuple[float, float]]:
    """منحنى بيزييه تكعيبي كسلسلة نقاط."""
    out = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0])
        y = (u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])
        out.append((x, y))
    return out


def bezier_at(p0, p1, p2, p3, t: float) -> tuple[float, float]:
    u = 1 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])


def _leaf(draw: ImageDraw.ImageDraw, cx: float, cy: float, length: float,
          width: float, angle: float, fill: int = 255) -> None:
    """ورقة على شكل دمعة: قوسان متقابلان من القاعدة إلى الطرف."""
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)

    def place(u, v):
        return (cx + u * ca - v * sa, cy + u * sa + v * ca)

    tip, base = place(length, 0), place(0, 0)
    side_a = bezier(base, place(length * 0.18, width), place(length * 0.62, width * 0.86), tip, 22)
    side_b = bezier(tip, place(length * 0.62, -width * 0.5), place(length * 0.20, -width * 0.36), base, 22)
    draw.polygon(side_a + side_b, fill=fill)


def _dot(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill: int = 255) -> None:
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill)


# ── عناصر ─────────────────────────────────────────────────────────────
@lru_cache(maxsize=32)
def rule(width: int, thickness: int = 2, diamond: int = 9,
         taper: float = 0.34, pips: bool = True) -> Image.Image:
    """خطّ فاصل يتلاشى طرفاه، وفي وسطه معيّن صغير ونقطتان.

    التلاشي عند الطرفين هو ما يجعله يبدو منقوشًا لا مرسومًا بمسطرة.
    """
    span = max(width, 40)
    height = max(diamond * 2 + 16, thickness * 6 + 16)
    big, down = mask_supersample((span, height), SS)
    d = ImageDraw.Draw(big)
    cy = height * SS / 2
    half = thickness * SS / 2

    d.rectangle((0, cy - half, span * SS, cy + half), fill=255)
    if diamond:
        r = diamond * SS
        d.polygon([(span * SS / 2, cy - r), (span * SS / 2 + r * 0.72, cy),
                   (span * SS / 2, cy + r), (span * SS / 2 - r * 0.72, cy)], fill=255)
        if pips:
            for side in (-1, 1):
                _dot(d, span * SS / 2 + side * r * 3.1, cy, thickness * SS * 0.9)
                _dot(d, span * SS / 2 + side * r * 4.4, cy, thickness * SS * 0.55)

    mask = down()

    # تلاشٍ خطّي عند الطرفين
    fade = Image.linear_gradient("L").resize((span, height))
    ramp = int(span * taper / 2) or 1
    left = fade.crop((0, 0, 1, height)).resize((ramp, height))
    for x in range(ramp):
        k = x / max(1, ramp - 1)
        col = mask.crop((x, 0, x + 1, height)).point(lambda p, k=k: int(p * k))
        mask.paste(col, (x, 0))
        col = mask.crop((span - 1 - x, 0, span - x, height)).point(lambda p, k=k: int(p * k))
        mask.paste(col, (span - 1 - x, 0))
    del left, fade
    return mask


@lru_cache(maxsize=16)
def corner(size: int = 190, stroke: int = 3) -> Image.Image:
    """ركن عربسك: كرمة تلتفّ حول الزاوية وتتفرّع منها ثلاث ورقات.

    الشكل مرسوم لركن **أعلى-يسار**؛ تُقلب أو تُدار للأركان الأخرى.
    """
    big, down = mask_supersample((size, size), SS)
    d = ImageDraw.Draw(big)
    S = size * SS
    w = max(1, stroke * SS)

    # الكرمة الرئيسية — ربع دوران يعانق الزاوية
    p0, p1 = (S * 0.97, S * 0.11), (S * 0.40, S * 0.02)
    p2, p3 = (S * 0.02, S * 0.40), (S * 0.11, S * 0.97)
    d.line(bezier(p0, p1, p2, p3), fill=255, width=w, joint="curve")

    # كرمة داخلية أقصر تنتهي بلفّة
    q0, q1 = (S * 0.62, S * 0.20), (S * 0.34, S * 0.19)
    q2, q3 = (S * 0.19, S * 0.34), (S * 0.20, S * 0.62)
    d.line(bezier(q0, q1, q2, q3), fill=255, width=max(1, int(w * 0.62)), joint="curve")

    # لفّة صغيرة عند طرف الكرمة الداخلية
    c0, c1 = (S * 0.20, S * 0.62), (S * 0.28, S * 0.74)
    c2, c3 = (S * 0.40, S * 0.70), (S * 0.34, S * 0.60)
    d.line(bezier(c0, c1, c2, c3), fill=255, width=max(1, int(w * 0.55)), joint="curve")

    # ورقات تتفرّع للخارج من الكرمة الرئيسية
    for t, length, wide, tilt in ((0.20, 0.20, 0.052, 62),
                                  (0.50, 0.26, 0.062, 135),
                                  (0.80, 0.20, 0.052, 208)):
        x, y = bezier_at(p0, p1, p2, p3, t)
        _leaf(d, x, y, S * length, S * wide, tilt)

    # نقاط تُنهي الأطراف
    _dot(d, *p0, w * 1.5)
    _dot(d, *p3, w * 1.5)
    _dot(d, S * 0.50, S * 0.50, w * 1.1)

    return down()


@lru_cache(maxsize=8)
def wreath(diameter: int = 620, stroke: int = 3, leaves: int = 11) -> Image.Image:
    """إكليل: قوسان من الورق يلتقيان، بفجوة أعلى وأسفل — يحيط بالاسم."""
    big, down = mask_supersample((diameter, diameter), SS)
    d = ImageDraw.Draw(big)
    D = diameter * SS
    r = D * 0.44
    cx = cy = D / 2
    w = max(1, stroke * SS)

    for side in (-1, 1):                      # يمين ويسار
        start, end = 16, 164                  # درجات — الفجوة أعلى وأسفل
        pts = []
        for i in range(49):
            a = math.radians(start + (end - start) * i / 48)
            pts.append((cx + side * r * math.sin(a), cy - r * math.cos(a)))
        d.line(pts, fill=255, width=w, joint="curve")

        for i in range(leaves):
            u = (i + 0.5) / leaves
            a = math.radians(start + (end - start) * u)
            x = cx + side * r * math.sin(a)
            y = cy - r * math.cos(a)
            outward = math.degrees(math.atan2(y - cy, x - cx))
            size = D * (0.052 + 0.018 * math.sin(math.pi * u))
            _leaf(d, x, y, size, size * 0.30, outward - side * 26)
            _leaf(d, x, y, size * 0.74, size * 0.24, outward + side * 30)

        for a_deg, rad in ((start, r), (end, r)):
            a = math.radians(a_deg)
            _dot(d, cx + side * rad * math.sin(a), cy - rad * math.cos(a), w * 1.6)

    # معيّن صغير أعلى وأسفل يسدّ الفجوة بلطف
    for sign in (-1, 1):
        y = cy + sign * r
        s = D * 0.016
        d.polygon([(cx, y - s), (cx + s * 0.7, y), (cx, y + s), (cx - s * 0.7, y)], fill=255)

    return down()


@lru_cache(maxsize=8)
def sprig(width: int = 300, stroke: int = 2, leaves: int = 5) -> Image.Image:
    """غصن صغير مورق — فاصل رقيق تحت العناوين."""
    big, down = mask_supersample((width, width // 3), SS)
    d = ImageDraw.Draw(big)
    W, H = width * SS, (width // 3) * SS
    w = max(1, stroke * SS)
    p0, p1 = (W * 0.04, H * 0.62), (W * 0.32, H * 0.20)
    p2, p3 = (W * 0.68, H * 0.20), (W * 0.96, H * 0.62)
    d.line(bezier(p0, p1, p2, p3), fill=255, width=w, joint="curve")
    for i in range(leaves):
        t = (i + 0.5) / leaves
        x, y = bezier_at(p0, p1, p2, p3, t)
        tilt = -70 + 140 * t
        _leaf(d, x, y, W * 0.10, W * 0.028, tilt - 90)
        _leaf(d, x, y, W * 0.08, W * 0.024, tilt + 90)
    _dot(d, *p0, w * 1.4)
    _dot(d, *p3, w * 1.4)
    return down()


@lru_cache(maxsize=4)
def page_frame(size: tuple[int, int], inset: int = 64, corner_size: int = 190,
               stroke: int = 2) -> Image.Image:
    """إطار الصفحة: مستطيلان رفيعان وأربعة أركان عربسك."""
    w, h = size
    big, down = mask_supersample(size, SS)
    d = ImageDraw.Draw(big)
    i0, i1 = inset * SS, (inset + 13) * SS
    d.rectangle((i0, i0, w * SS - i0, h * SS - i0), outline=255, width=stroke * SS)
    d.rectangle((i1, i1, w * SS - i1, h * SS - i1), outline=255, width=max(SS, SS))
    mask = down()

    c = corner(corner_size, stroke + 1)
    mask.paste(c, (inset - 6, inset - 6), c)
    cr = c.transpose(Image.FLIP_LEFT_RIGHT)
    mask.paste(cr, (w - inset - corner_size + 6, inset - 6), cr)
    cb = c.transpose(Image.FLIP_TOP_BOTTOM)
    mask.paste(cb, (inset - 6, h - inset - corner_size + 6), cb)
    cbr = c.transpose(Image.ROTATE_180)
    mask.paste(cbr, (w - inset - corner_size + 6, h - inset - corner_size + 6), cbr)
    return mask


@lru_cache(maxsize=8)
def arch_mask(size: tuple[int, int], radius: float = 0.5, feather: float = 2.0) -> Image.Image:
    """قناع بقوس علوي (شكل المحراب) — لتأطير الصور بأناقة."""
    w, h = size
    big, down = mask_supersample(size, SS)
    d = ImageDraw.Draw(big)
    W, H = w * SS, h * SS
    r = min(W / 2, H * radius)
    d.rectangle((0, r, W, H), fill=255)
    d.ellipse((W / 2 - r, 0, W / 2 + r, 2 * r), fill=255)
    if W > 2 * r:
        d.rectangle((0, r, W, H), fill=255)
        d.pieslice((0, 0, 2 * r, 2 * r), 180, 270, fill=255)
        d.pieslice((W - 2 * r, 0, W, 2 * r), 270, 360, fill=255)
        d.rectangle((r, 0, W - r, r), fill=255)
    mask = down()
    return mask.filter(ImageFilter.GaussianBlur(feather)) if feather else mask


# ── كشف تدريجي ────────────────────────────────────────────────────────
def reveal_center(mask: Image.Image, progress: float) -> Image.Image:
    """يكشف قناعًا من مركزه نحو الطرفين (للخطوط الفاصلة)."""
    if progress >= 0.999:
        return mask
    w, h = mask.size
    keep = int(w * max(0.0, progress))
    if keep <= 0:
        return Image.new("L", mask.size, 0)
    out = Image.new("L", mask.size, 0)
    x0 = (w - keep) // 2
    out.paste(mask.crop((x0, 0, x0 + keep, h)), (x0, 0))
    return out


def reveal_sweep(mask: Image.Image, progress: float, softness: int = 90,
                 direction: str = "down") -> Image.Image:
    """يكشف قناعًا بمسح ناعم — للإطار والإكليل."""
    if progress >= 0.999:
        return mask
    w, h = mask.size
    if progress <= 0.001:
        return Image.new("L", mask.size, 0)
    span = h if direction in ("down", "up") else w
    edge = int(span * progress)
    gate = Image.new("L", mask.size, 0)
    g = ImageDraw.Draw(gate)
    if direction == "down":
        g.rectangle((0, 0, w, edge), fill=255)
    elif direction == "up":
        g.rectangle((0, h - edge, w, h), fill=255)
    elif direction == "right":
        g.rectangle((0, 0, edge, h), fill=255)
    else:
        g.rectangle((w - edge, 0, w, h), fill=255)
    if softness:
        gate = gate.filter(ImageFilter.GaussianBlur(softness))
    out = mask.copy()
    out.paste(0, (0, 0), gate.point(lambda p: 255 - p))
    return out
