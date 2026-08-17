"""المؤثرات البصرية: القصّ، التدرّج اللوني، الزجاج الضبابي، الحبيبات، الفينييت."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from .config import brand


# ---------------------------------------------------------------- القصّ
def cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """يملأ الإطار بالكامل مع الحفاظ على النِسَب (مثل background-size: cover)."""
    tw, th = size
    scale = max(tw / image.width, th / image.height)
    new = (max(tw, int(round(image.width * scale))), max(th, int(round(image.height * scale))))
    image = image.resize(new, Image.LANCZOS)
    left = (image.width - tw) // 2
    top = (image.height - th) // 2
    return image.crop((left, top, left + tw, top + th))


def smart_crop_bias(image: Image.Image) -> float:
    """يقدّر أين يقع «الاهتمام» رأسيًا (0=أعلى، 1=أسفل) من توزّع التباين.

    كافٍ عمليًا لصور السفر: يمنع قطع رؤوس الأشخاص أو حذف خطّ الأفق.
    """
    gray = np.asarray(image.convert("L").resize((64, 96), Image.BILINEAR), dtype=np.float32)
    energy = np.abs(np.diff(gray, axis=0)).sum(axis=1)
    if energy.sum() <= 0:
        return 0.5
    rows = np.arange(len(energy))
    center = float((rows * energy).sum() / energy.sum()) / max(1, len(energy) - 1)
    return min(0.75, max(0.25, center))


# ------------------------------------------------------------ التدرّج اللوني
def grade(image: Image.Image, strength: float = 1.0) -> Image.Image:
    """تدرّج لوني بهوية أجمكان: ظلال مائلة للأزرق العميق وإضاءات دافئة كالشمس."""
    if strength <= 0:
        return image
    arr = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0

    # منحنى تباين ناعم (S-curve)
    arr = np.clip(arr, 0, 1)
    arr = arr * arr * (3 - 2 * arr) * 0.35 + arr * 0.65

    lum = arr @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    shadows = np.clip(1.0 - lum * 1.9, 0, 1)[..., None]
    highs = np.clip((lum - 0.55) * 2.2, 0, 1)[..., None]

    cool = np.array([-0.030, 0.004, 0.070], dtype=np.float32)   # أزرق في الظلال
    warm = np.array([0.070, 0.032, -0.045], dtype=np.float32)   # ذهبي في الإضاءات
    arr = arr + (shadows * cool + highs * warm) * strength

    out = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8))
    out = ImageEnhance.Color(out).enhance(1.0 + 0.14 * strength)
    return out


def darken(image: Image.Image, amount: float) -> Image.Image:
    if amount <= 0:
        return image
    return ImageEnhance.Brightness(image).enhance(1.0 - amount)


# ------------------------------------------------------------ التدرّجات
@lru_cache(maxsize=32)
def linear_gradient(
    size: tuple[int, int],
    top: tuple,
    bottom: tuple,
    stops: tuple[float, ...] = (0.0, 1.0),
) -> Image.Image:
    """تدرّج رأسي RGBA بين لونين، مع إمكانية تحديد بداية/نهاية التدرّج."""
    w, h = size
    y = np.linspace(0, 1, h, dtype=np.float32)
    s0, s1 = stops
    t = np.clip((y - s0) / max(1e-6, s1 - s0), 0, 1)[:, None]
    top_arr = np.array(top, dtype=np.float32)
    bot_arr = np.array(bottom, dtype=np.float32)
    row = top_arr[None, :] * (1 - t) + bot_arr[None, :] * t
    arr = np.repeat(row[:, None, :], w, axis=1)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def scrim(size: tuple[int, int], top_alpha: int, mid_alpha: int, bottom_alpha: int) -> Image.Image:
    """طبقة تعتيم متدرّجة تُبقي النص مقروءًا فوق أي صورة."""
    ink = brand().color("ink")
    w, h = size
    upper = linear_gradient((w, h // 2), (*ink, top_alpha), (*ink, mid_alpha))
    lower = linear_gradient((w, h - h // 2), (*ink, mid_alpha), (*ink, bottom_alpha))
    out = Image.new("RGBA", size)
    out.paste(upper, (0, 0))
    out.paste(lower, (0, h // 2))
    return out


@lru_cache(maxsize=8)
def brand_backdrop(size: tuple[int, int]) -> Image.Image:
    """خلفية العلامة للأوترو: تدرّج بحري + وهج شمس + موجات ناعمة."""
    b = brand()
    w, h = size
    base = Image.new("RGBA", size, (*b.color("navy"), 255))

    diag = linear_gradient((w, h), (*b.color("ocean"), 235), (*b.color("ink"), 255))
    base.alpha_composite(diag)

    # وهج الشمس أعلى اليمين
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy, r = int(w * 0.78), int(h * 0.20), int(w * 0.46)
    gd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*b.color("sun"), 96))
    glow = glow.filter(ImageFilter.GaussianBlur(w * 0.16))
    base.alpha_composite(glow)

    # موجات مستوحاة من الشعار
    waves = Image.new("RGBA", size, (0, 0, 0, 0))
    wd = ImageDraw.Draw(waves)
    for i, (color, alpha, dy, thick) in enumerate(
        [(b.color("sky"), 70, 0, 26), (b.color("ocean"), 90, 78, 34), (b.color("sky"), 42, 168, 18)]
    ):
        top = int(h * 0.70) + dy
        wd.arc((-int(w * 0.35), top, int(w * 1.35), top + int(h * 0.42)),
               start=182, end=358, fill=(*color, alpha), width=thick)
    waves = waves.filter(ImageFilter.GaussianBlur(2.2))
    base.alpha_composite(waves)
    return base


# ------------------------------------------------------------ عناصر واجهة
def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    return mask


def glass_panel(
    backdrop: Image.Image,
    box: tuple[int, int, int, int],
    radius: int = 34,
    tint: tuple = (255, 255, 255, 26),
    blur: float = 26.0,
    border: tuple | None = (255, 255, 255, 58),
) -> Image.Image:
    """لوحة زجاجية شفافة: تضبيب ما خلفها + طبقة لون + حدّ رفيع.

    تُبنى مرة واحدة لكل مشهد ثم تُركّب في كل إطار — لهذا لا تُكلّف شيئًا.
    """
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    region = backdrop.convert("RGBA").crop(box).filter(ImageFilter.GaussianBlur(blur))
    region = ImageEnhance.Brightness(region).enhance(0.82)

    panel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    panel.alpha_composite(region)
    panel.alpha_composite(Image.new("RGBA", (w, h), tint))
    if border:
        ImageDraw.Draw(panel).rounded_rectangle((0, 0, w - 1, h - 1), radius, outline=border, width=2)

    panel.putalpha(Image.composite(panel.getchannel("A"), Image.new("L", (w, h), 0), rounded_mask((w, h), radius)))

    # ظل ناعم أسفل اللوحة
    shadow = Image.new("RGBA", (w + 80, h + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((40, 46, w + 40, h + 46), radius, fill=(0, 0, 0, 105))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    shadow.alpha_composite(panel, (40, 40))
    return shadow


def pill(text_layer: Image.Image, box: tuple[int, int, int, int], fill: tuple, radius: int | None = None):
    x0, y0, x1, y1 = box
    radius = radius if radius is not None else (y1 - y0) // 2
    ImageDraw.Draw(text_layer).rounded_rectangle(box, radius, fill=fill)


# ------------------------------------------------------------ لمسات نهائية
@lru_cache(maxsize=4)
def vignette(size: tuple[int, int], strength: float = 0.42) -> Image.Image:
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx - w / 2) / (w / 2)
    ny = (yy - h / 2) / (h / 2)
    r = np.sqrt(nx**2 + (ny * 0.72) ** 2)
    alpha = np.clip((r - 0.62) / 0.75, 0, 1) ** 1.7 * (255 * strength)
    layer = np.zeros((h, w, 4), dtype=np.uint8)
    layer[..., :3] = np.array(brand().color("ink"), dtype=np.uint8)
    layer[..., 3] = alpha.astype(np.uint8)
    return Image.fromarray(layer, "RGBA")


@lru_cache(maxsize=1)
def _grain_bank(size: tuple[int, int], frames: int = 8) -> tuple[Image.Image, ...]:
    rng = np.random.default_rng(7)
    w, h = size
    bank = []
    for _ in range(frames):
        noise = rng.normal(0, 1, (h // 2, w // 2)).astype(np.float32)
        noise = np.clip(noise * 26 + 128, 0, 255).astype(np.uint8)
        img = Image.fromarray(noise, "L").resize(size, Image.BILINEAR)
        rgba = Image.merge("RGBA", (img, img, img, Image.new("L", size, 16)))
        bank.append(rgba)
    return tuple(bank)


def grain(size: tuple[int, int], frame_index: int) -> Image.Image:
    bank = _grain_bank(size)
    return bank[frame_index % len(bank)]


def finish(frame: Image.Image, frame_index: int, grain_on: bool = True) -> Image.Image:
    """اللمسة الأخيرة على كل إطار: فينييت + حبيبات فيلمية خفيفة."""
    frame.alpha_composite(vignette(frame.size))
    if grain_on:
        frame = Image.blend(frame, Image.alpha_composite(frame, grain(frame.size, frame_index)), 0.5)
    return frame
