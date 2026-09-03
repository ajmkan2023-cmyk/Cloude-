"""أدوات الرسم: التدرّجات، الورق، الحبيبات، الفينييت، وتلوين الأقنعة.

كل ما يتكرّر في كل إطار مبنيّ ليكون رخيصًا: الطبقات الثابتة تُحسب مرّة
وتُخزَّن، والتركيب يتمّ على مستطيلات مقصوصة لا على اللوح كاملًا.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image, ImageFilter

from .config import PALETTE, color

Size = tuple[int, int]
RGBA = tuple[int, int, int, int]


# ── لبنات أساسية ──────────────────────────────────────────────────────
def blank(size: Size) -> Image.Image:
    return Image.new("RGBA", size, (0, 0, 0, 0))


def solid(size: Size, fill) -> Image.Image:
    return Image.new("RGBA", size, fill if len(fill) == 4 else (*fill, 255))


def _axis(size: Size, angle: float) -> np.ndarray:
    """قيمة بين ٠ و١ تتدرّج على امتداد الزاوية المعطاة (بالدرجات)."""
    w, h = size
    if angle % 180 == 90:
        t = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None] * np.ones((1, w), np.float32)
        return t if angle % 360 == 90 else 1.0 - t
    if angle % 180 == 0:
        t = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :] * np.ones((h, 1), np.float32)
        return t if angle % 360 == 0 else 1.0 - t
    rad = np.deg2rad(angle)
    xs = np.linspace(-0.5, 0.5, w, dtype=np.float32)[None, :]
    ys = np.linspace(-0.5, 0.5, h, dtype=np.float32)[:, None]
    proj = xs * np.cos(rad) + ys * np.sin(rad)
    return (proj - proj.min()) / max(1e-6, proj.max() - proj.min())


def gradient(size: Size, stops: list[tuple[float, tuple]], angle: float = 90) -> Image.Image:
    """تدرّج خطّي متعدّد المحطّات. كل محطّة ‎(موضع 0..1, لون RGB أو RGBA)‎."""
    stops = sorted(stops, key=lambda s: s[0])
    t = _axis(size, angle)
    positions = np.array([s[0] for s in stops], dtype=np.float32)
    colors = np.array([[*s[1], 255][:4] for s in stops], dtype=np.float32)
    out = np.empty((*t.shape, 4), dtype=np.float32)
    for c in range(4):
        out[..., c] = np.interp(t, positions, colors[:, c])
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def radial(size: Size, center: tuple[float, float], radius: float,
           inner: RGBA, outer: RGBA, falloff: float = 1.6) -> Image.Image:
    """هالة دائرية ناعمة — تُستعمل للإضاءة والتوهّج."""
    w, h = size
    cx, cy = center
    ys = np.arange(h, dtype=np.float32)[:, None] - cy
    xs = np.arange(w, dtype=np.float32)[None, :] - cx
    d = np.sqrt(xs * xs + ys * ys) / max(1.0, radius)
    t = np.clip(d, 0.0, 1.0) ** falloff
    inner_a = np.array(inner, dtype=np.float32)
    outer_a = np.array(outer, dtype=np.float32)
    out = inner_a[None, None, :] * (1 - t[..., None]) + outer_a[None, None, :] * t[..., None]
    return Image.fromarray(out.astype(np.uint8), "RGBA")


# ── نسيج ──────────────────────────────────────────────────────────────
@lru_cache(maxsize=4)
def grain(size: Size, amount: int = 3, seed: int = 7) -> Image.Image:
    """حبيبات ورق دقيقة — تكسر نظافة التدرّجات الرقمية.

    مقصودها أن تُحَسّ لا أن تُرى: سعة منخفضة وتمويه يكفي لإذابة النقاط
    المفردة، وإلا انقلب الورق إلى ورق صنفرة.
    """
    rng = np.random.default_rng(seed)
    w, h = size
    noise = rng.normal(0.0, 1.0, (h // 2, w // 2)).astype(np.float32)
    small = Image.fromarray(np.clip(128 + noise * amount * 2, 0, 255).astype(np.uint8), "L")
    full = small.resize(size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(0.9))
    arr = np.asarray(full, dtype=np.int16) - 128
    layer = np.zeros((h, w, 4), dtype=np.uint8)
    layer[..., 0] = layer[..., 1] = layer[..., 2] = np.where(arr > 0, 255, 40).astype(np.uint8)
    layer[..., 3] = np.clip(np.abs(arr), 0, 255).astype(np.uint8)
    return Image.fromarray(layer, "RGBA")


@lru_cache(maxsize=4)
def vignette(size: Size, strength: int = 46, tone: tuple = (72, 52, 44)) -> Image.Image:
    """تعتيم لطيف عند الأطراف يجمع العين نحو المركز."""
    w, h = size
    return radial(size, (w / 2, h / 2), max(w, h) * 0.62,
                  (*tone, 0), (*tone, strength), falloff=2.4)


@lru_cache(maxsize=4)
def paper(size: Size) -> Image.Image:
    """الخلفية الأساس: عاجيّ دافئ بإضاءة علوية ناعمة وحبيبات."""
    w, h = size
    base = gradient(size, [
        (0.00, PALETTE["paper_cool"]),
        (0.42, PALETTE["paper"]),
        (1.00, PALETTE["paper_warm"]),
    ], angle=90)
    glow = radial(size, (w * 0.5, h * 0.30), h * 0.52,
                  (*PALETTE["paper_cool"], 150), (*PALETTE["paper_cool"], 0), falloff=1.25)
    base.alpha_composite(glow)
    warm = radial(size, (w * 0.18, h * 0.86), h * 0.42,
                  (*PALETTE["rose"], 30), (*PALETTE["rose"], 0), falloff=1.5)
    base.alpha_composite(warm)
    base.alpha_composite(grain(size, 3, 11))
    return base


@lru_cache(maxsize=8)
def gold_sheet(size: Size, angle: float = 100) -> Image.Image:
    """صفيحة ذهب — تُمرَّر عبر قناع النص لتعطي حبرًا ذهبيًا متدرّجًا."""
    return gradient(size, [
        (0.00, PALETTE["gold"]),
        (0.16, PALETTE["gold_light"]),
        (0.38, PALETTE["gold"]),
        (0.56, PALETTE["gold_light"]),
        (0.80, PALETTE["gold"]),
        (1.00, PALETTE["gold_deep"]),
    ], angle=angle)


# ── تلوين الأقنعة ─────────────────────────────────────────────────────
def tint(mask: Image.Image, fill, opacity: float = 1.0) -> Image.Image:
    """يحوّل قناعًا رماديًا إلى طبقة ملوّنة."""
    rgb = fill[:3]
    a = fill[3] / 255 if len(fill) == 4 else 1.0
    layer = Image.new("RGBA", mask.size, (*rgb, 0))
    alpha = mask if a * opacity >= 0.999 else scale(mask, a * opacity)
    layer.putalpha(alpha)
    return layer


def tint_sheet(mask: Image.Image, sheet: Image.Image, at: tuple[int, int],
               opacity: float = 1.0) -> Image.Image:
    """يمرّر صفيحة (ذهب مثلًا) عبر قناع، مع أخذ موضع القناع في الاعتبار."""
    w, h = mask.size
    x, y = at
    crop = sheet.crop((x, y, x + w, y + h)).convert("RGBA")
    crop.putalpha(mask if opacity >= 0.999 else scale(mask, opacity))
    return crop


def scale(mask: Image.Image, k: float) -> Image.Image:
    """يضرب قناعًا رماديًا في معامل (لتخفيت الشفافية)."""
    k = max(0.0, min(1.0, k))
    if k >= 0.999:
        return mask
    if k <= 0.001:
        return Image.new("L", mask.size, 0)
    return mask.point(lambda p, k=k: int(p * k))


def glow(mask: Image.Image, blur: float, fill, gain: float = 1.0) -> Image.Image:
    """توهّج ناعم مبنيّ من القناع نفسه."""
    soft = mask.filter(ImageFilter.GaussianBlur(blur))
    if gain != 1.0:
        soft = soft.point(lambda p, g=gain: min(255, int(p * g)))
    return tint(soft, fill)


def shadow(mask: Image.Image, blur: float, fill=(60, 40, 34, 70)) -> Image.Image:
    return tint(mask.filter(ImageFilter.GaussianBlur(blur)), fill)


# ── تركيب ─────────────────────────────────────────────────────────────
def stamp(base: Image.Image, layer: Image.Image, at: tuple[int, int] = (0, 0),
          opacity: float = 1.0) -> Image.Image:
    """يركّب طبقة فوق اللوح عند موضع، مع قصّ ما يخرج عن الحدود.

    يعمل على المستطيل المتقاطع فقط — أرخص بكثير من بناء لوح كامل لكل عنصر.
    """
    if opacity <= 0.002:
        return base
    bw, bh = base.size
    lw, lh = layer.size
    x, y = int(round(at[0])), int(round(at[1]))

    sx, sy = max(0, -x), max(0, -y)
    dx, dy = max(0, x), max(0, y)
    cw, ch = min(lw - sx, bw - dx), min(lh - sy, bh - dy)
    if cw <= 0 or ch <= 0:
        return base

    piece = layer.crop((sx, sy, sx + cw, sy + ch)) if (sx, sy, cw, ch) != (0, 0, lw, lh) else layer
    if opacity < 0.998:
        piece = piece.copy()
        piece.putalpha(scale(piece.getchannel("A"), opacity))
    base.alpha_composite(piece, dest=(dx, dy))
    return base


def stamp_mask(base: Image.Image, mask: Image.Image, fill,
               at: tuple[int, int] = (0, 0), opacity: float = 1.0) -> Image.Image:
    return stamp(base, tint(mask, fill), at, opacity)


def supersample(size: Size, factor: int = 3):
    """يعيد ‎(لوح مكبّر, دالة تصغير)‎ لرسم أشكال ناعمة الحواف.

    ‎ImageDraw‎ لا تنعّم الحواف، فنرسم على ثلاثة أضعاف المقاس ثم نصغّر.
    """
    big = Image.new("RGBA", (size[0] * factor, size[1] * factor), (0, 0, 0, 0))

    def down(img: Image.Image = big) -> Image.Image:
        return img.resize(size, Image.LANCZOS)

    return big, down


def mask_supersample(size: Size, factor: int = 3):
    big = Image.new("L", (size[0] * factor, size[1] * factor), 0)

    def down(img: Image.Image = big) -> Image.Image:
        return img.resize(size, Image.LANCZOS)

    return big, down
