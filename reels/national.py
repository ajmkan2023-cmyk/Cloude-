"""حزمة اليوم الوطني السعودي — نظام بصري مستقل لإعلان المناسبة.

لماذا ملف مستقل: هوية أجمكان بحريّة زرقاء، وهوية اليوم الوطني خضراء. بدل
حشو فضاء التصميم العام بمفاتيح تخصّ مناسبة واحدة في السنة، جُمع هنا كل ما
يخصّها: اللون الرسمي، ونقش السدو المرسوم برمجيًا، والمشاهد الخاصة.

قرار مقصود: لا يُرسم العلم السعودي ولا شعار الدولة (السيفان والنخلة) في أي
مشهد. العلم يحمل الشهادة وله نظام يحكم استعماله، فالاحترافي — وما تفعله
العلامات الكبيرة فعلًا — هو الاكتفاء بالأخضر الرسمي وبنقوش السدو التراثية.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from . import imagefx as fx
from . import motion as mo
from . import typography as ty
from .config import brand
from .scenes import (BOTTOM, SIDE, TOP, H, W, FlashScene, GridScene, PhotoScene,
                     Scene, ken_burns, load_photo, open_photo, paste_alpha,
                     tight_lines)
from .styles import STYLES, Style

B = brand()

# اليوم الوطني السعودي مثبّت على ٢٣ سبتمبر ميلاديًا
NATIONAL_DATE_AR = "٢٣ سبتمبر"
NATIONAL_LABEL_AR = "اليوم الوطني السعودي"


# ------------------------------------------------------------------ اللون
def national_grade(image: Image.Image, strength: float = 0.55) -> Image.Image:
    """تدرّج لوني للمناسبة: ظلال تميل للأخضر وإضاءات دافئة ذهبية.

    ليس فلترًا أخضر فوق الصورة — الصورة تبقى طبيعية، لكن ظلالها تُسحب نحو
    الأخضر فتتناغم مع اللوحات الخضراء بدل أن تصطدم بها.
    """
    if strength <= 0:
        return image
    arr = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    arr = arr * arr * (3 - 2 * arr) * 0.46 + arr * 0.54        # تباين أوضح

    lum = arr @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    shadows = np.clip(1.0 - lum * 1.8, 0, 1)[..., None]
    highs = np.clip((lum - 0.52) * 2.1, 0, 1)[..., None]

    # الظلال تُسحب نحو الأخضر بلطف، والإضاءات تُدفّأ قليلًا فقط. الأرقام
    # منخفضة عمدًا: الصبغة القوية تحوّل الصور الليلية الزرقاء إلى بنفسجي.
    green = np.array([-0.034, 0.026, -0.020], dtype=np.float32)
    gold = np.array([0.026, 0.020, -0.024], dtype=np.float32)
    arr = np.clip(arr + (shadows * green + highs * gold) * strength, 0, 1)

    out = Image.fromarray((arr * 255).astype(np.uint8))
    return ImageEnhance.Color(out).enhance(1.0 + 0.04 * strength)


def green_scrim(size: tuple[int, int], top_a: int, mid_a: int, bot_a: int) -> Image.Image:
    """طبقة تعتيم خضراء — نظير `fx.scrim` لكن بالأخضر العميق بدل الحبر."""
    g = B.color("green_deep")
    w, h = size
    upper = fx.linear_gradient((w, h // 2), (*g, top_a), (*g, mid_a))
    lower = fx.linear_gradient((w, h - h // 2), (*g, mid_a), (*g, bot_a))
    out = Image.new("RGBA", size)
    out.paste(upper, (0, 0))
    out.paste(lower, (0, h // 2))
    return out


@lru_cache(maxsize=8)
def national_backdrop(size: tuple[int, int]) -> Image.Image:
    """خلفية المناسبة: أخضر عميق بتدرّج قطري ووهج ذهبي خافت."""
    w, h = size
    base = Image.new("RGBA", size, (*B.color("green_deep"), 255))
    base.alpha_composite(fx.linear_gradient((w, h), (*B.color("green"), 225),
                                            (*B.color("green_deep"), 255)))

    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy, r = int(w * 0.24), int(h * 0.24), int(w * 0.52)
    gd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*B.color("gold"), 62))
    cx2, cy2, r2 = int(w * 0.86), int(h * 0.80), int(w * 0.44)
    gd.ellipse((cx2 - r2, cy2 - r2, cx2 + r2, cy2 + r2), fill=(*B.color("green"), 120))
    base.alpha_composite(glow.filter(ImageFilter.GaussianBlur(w * 0.17)))
    return base


# ------------------------------------------------------------------ السدو
# نقش السدو نسيج بدوي سعودي: صفوف أفقية متراصّة من وحدات هندسية بسيطة
# (مثلثات، معيّنات، أمشاط، عيون). نرسمه برمجيًا فيخرج نظيفًا بأي مقاس،
# ويتبدّل تركيبه بتبدّل البذرة فلا يتكرّر شريطان متطابقان في الفيديو نفسه.

_ROW_KINDS = ("solid", "hairline", "triangles", "diamonds", "combs", "eyes", "zigzag")


def _row_solid(d: ImageDraw.ImageDraw, y: int, rh: int, w: int, ink, alt) -> None:
    d.rectangle((0, y, w, y + rh), fill=ink)


def _row_hairline(d: ImageDraw.ImageDraw, y: int, rh: int, w: int, ink, alt) -> None:
    mid = y + rh // 2
    t = max(1, rh // 4)
    d.rectangle((0, mid - t // 2, w, mid + t // 2 + t % 2), fill=ink)


def _row_triangles(d: ImageDraw.ImageDraw, y: int, rh: int, w: int, ink, alt) -> None:
    unit = max(8, rh)
    for i in range(0, w + unit, unit):
        up = (i // unit) % 2 == 0
        if up:
            d.polygon([(i, y + rh), (i + unit / 2, y), (i + unit, y + rh)], fill=ink)
        else:
            d.polygon([(i, y), (i + unit / 2, y + rh), (i + unit, y)], fill=alt)


def _row_diamonds(d: ImageDraw.ImageDraw, y: int, rh: int, w: int, ink, alt) -> None:
    unit = max(10, int(rh * 1.15))
    cy = y + rh / 2
    for i in range(0, w + unit, unit):
        cx = i + unit / 2
        d.polygon([(cx, y), (cx + unit / 2, cy), (cx, y + rh), (cx - unit / 2, cy)], fill=ink)
        k = 0.42
        d.polygon([(cx, y + rh * (0.5 - k)), (cx + unit * k / 2, cy),
                   (cx, y + rh * (0.5 + k)), (cx - unit * k / 2, cy)], fill=alt)


def _row_combs(d: ImageDraw.ImageDraw, y: int, rh: int, w: int, ink, alt) -> None:
    unit = max(8, rh)
    tooth = max(2, unit // 3)
    for i in range(0, w + unit, unit):
        d.rectangle((i, y, i + tooth, y + rh), fill=ink)
        d.rectangle((i + tooth, y + rh // 2, i + unit, y + rh), fill=alt)


def _row_eyes(d: ImageDraw.ImageDraw, y: int, rh: int, w: int, ink, alt) -> None:
    unit = max(10, int(rh * 1.4))
    pad = max(1, rh // 5)
    for i in range(0, w + unit, unit):
        d.rectangle((i + pad, y + pad, i + unit - pad, y + rh - pad), fill=ink)
        d.rectangle((i + pad * 2, y + pad * 2, i + unit - pad * 2, y + rh - pad * 2), fill=alt)


def _row_zigzag(d: ImageDraw.ImageDraw, y: int, rh: int, w: int, ink, alt) -> None:
    unit = max(10, rh)
    t = max(2, rh // 4)
    pts = []
    for i in range(0, w + unit * 2, unit):
        pts.append((i, y + (t if (i // unit) % 2 == 0 else rh - t)))
    d.line(pts, fill=ink, width=t, joint="curve")


_ROW_FN = {
    "solid": _row_solid, "hairline": _row_hairline, "triangles": _row_triangles,
    "diamonds": _row_diamonds, "combs": _row_combs, "eyes": _row_eyes,
    "zigzag": _row_zigzag,
}


@lru_cache(maxsize=32)
def sadu_band(width: int, height: int, seed: int = 0, on_dark: bool = True) -> Image.Image:
    """شريط سدو مرسوم برمجيًا — تركيب الصفوف يتبدّل مع البذرة."""
    rng = random.Random(seed)
    white = (*B.color("white"), 255)
    green = (*B.color("green"), 255)
    gold = (*B.color("gold"), 255)
    deep = (*B.color("green_deep"), 255)

    band = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(band)
    d.rectangle((0, 0, width, height), fill=deep if on_dark else white)

    # تركيب الصفوف: صفّان زخرفيان كبيران بينهما فواصل رفيعة
    plan = ["hairline", rng.choice(("triangles", "diamonds", "eyes")), "hairline",
            rng.choice(("combs", "zigzag", "triangles")), "hairline"]
    weights = [0.10, 0.34, 0.08, 0.34, 0.10]

    inks = [gold, white, gold, green if on_dark else green, gold]
    alts = [gold, green, gold, white, gold]
    if not on_dark:
        inks = [green, green, gold, green, green]
        alts = [green, white, gold, gold, green]

    y = 0
    for kind, wgt, ink, alt in zip(plan, weights, inks, alts):
        rh = max(2, int(height * wgt))
        _ROW_FN[kind](d, y, rh, width, ink, alt)
        y += rh
    return band


# ------------------------------------------------------------------ اللمعة
def shine(layer: Image.Image, p: float, band: float = 0.30,
          strength: int = 190, slant: float = 0.55) -> Image.Image:
    """شعاع ضوء يعبر النص — يُقصّ بشفافية النص نفسه فلا يخرج عن حروفه."""
    w, h = layer.size
    if w < 2 or h < 2:
        return Image.new("RGBA", layer.size, (0, 0, 0, 0))
    xs = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    ys = np.linspace(-0.5, 0.5, h, dtype=np.float32)[:, None]
    dist = np.abs(xs + slant * ys - p)
    mask = np.clip(1.0 - dist / band, 0, 1) ** 2

    alpha = np.asarray(layer.getchannel("A"), dtype=np.float32) / 255.0
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., :3] = 255
    out[..., 3] = (mask * alpha * strength).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def _numeral(text: str, size: int, fill, stroke, stroke_width: int) -> Image.Image:
    """رقم ضخم بحدّ ملوّن — يُقصّ على حدوده ليسهل توسيطه وتحريكه."""
    f = ty.font("display", size)
    pad = size
    layer = Image.new("RGBA", (size * 4 + pad, size * 2 + pad), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(
        (layer.width // 2, layer.height // 2), text, font=f, fill=fill, anchor="mm",
        stroke_width=stroke_width, stroke_fill=stroke, direction="rtl", language="ar",
    )
    box = layer.getbbox()
    return layer.crop(box) if box else layer


def _centered(text: str, style: ty.TextStyle) -> Image.Image:
    block = ty.wrap(text, style)
    layer = ty.render_block(block, (W, H), (W // 2, 0))
    box = layer.getbbox()
    return layer.crop(box) if box else layer


# ================================================================ المشاهد
@dataclass
class NationalTitleScene(Scene):
    """افتتاح المناسبة: ستارة خضراء تنفتح عن الصورة، ورقم العام خلف العنوان."""

    photo: str = ""
    kicker: str = NATIONAL_LABEL_AR
    headline: str = ""
    subline: str = ""
    number: str = "٩٦"
    duration: float = 3.6
    style: Style = field(default_factory=lambda: STYLES[0])

    _base: Image.Image = field(default=None, repr=False)
    _bias: float = 0.5
    _scrim: Image.Image = field(default=None, repr=False)
    _ghost: Image.Image = field(default=None, repr=False)
    _ghost_pos: tuple = (0, 0)
    _band: Image.Image = field(default=None, repr=False)
    _band_y: int = 0
    _kicker: list = field(default_factory=list, repr=False)
    _head: list = field(default_factory=list, repr=False)
    _sub: list = field(default_factory=list, repr=False)
    _rule: Image.Image = field(default=None, repr=False)
    _logo: Image.Image = field(default=None, repr=False)
    _head_shine: list = field(default_factory=list, repr=False)

    def prepare(self) -> None:
        gold = B.color("gold")
        self._base = load_photo(self.photo)
        self._bias = fx.smart_crop_bias(self._base)
        self._scrim = green_scrim((W, H), 175, 95, 250)

        self._band = sadu_band(W, 46, seed=1)
        self._band_y = TOP + 96

        # رقم العام خلف النص — حضور بلا ضجيج
        self._ghost = _numeral(self.number, 400, (*B.color("white"), 44),
                               (*gold, 175), 8)
        self._ghost_pos = ((W - self._ghost.width) // 2, int(H * 0.205))

        max_w = W - SIDE * 2
        anchor_x = W - SIDE

        head_style = ty.fit_size(
            self.headline,
            ty.TextStyle(role="display", size=98, max_width=max_w, align="right",
                         line_spacing=1.20, shadow=(0, 0, 0, 170), shadow_offset=(0, 6),
                         shadow_blur=18, fill=(*B.color("white"), 255)),
            max_lines=3,
        )
        head_block = ty.wrap(self.headline, head_style)

        sub_style = ty.TextStyle(role="body", size=40, align="right", line_spacing=1.30,
                                 max_width=int(max_w * 0.92), fill=(*B.color("sand"), 242),
                                 shadow=(0, 0, 0, 140), shadow_blur=12)
        sub_block = ty.wrap(self.subline, sub_style) if self.subline else None
        sub_h = sub_block.height if sub_block else 0

        sub_top = H - BOTTOM - 30 - sub_h
        head_top = sub_top - (60 if sub_block else 0) - head_block.height
        kick_top = head_top - 92

        self._head = tight_lines(head_block, (anchor_x, head_top))
        self._head_shine = [(layer, pos) for layer, pos in self._head]
        self._sub = tight_lines(sub_block, (anchor_x, sub_top)) if sub_block else []

        kick_style = ty.TextStyle(role="body_bold", size=40, align="right",
                                  fill=(*gold, 255), shadow=(0, 0, 0, 150),
                                  shadow_blur=10, max_width=max_w)
        self._kicker = tight_lines(ty.wrap(self.kicker, kick_style), (anchor_x - 78, kick_top))

        rule = Image.new("RGBA", (58, 6), (0, 0, 0, 0))
        ImageDraw.Draw(rule).rounded_rectangle((0, 0, 57, 5), 3, fill=(*gold, 255))
        self._rule = rule

        logo = Image.open(B.logo_mark).convert("RGBA")
        target_h = 150
        self._logo = logo.resize((int(logo.width * target_h / logo.height), target_h), Image.LANCZOS)

    def frame(self, t: float) -> Image.Image:
        img = ken_burns(self._base, t, self.duration, "zoom_in", self._bias)
        img = national_grade(img, 0.72).convert("RGBA")
        img.alpha_composite(self._scrim)

        # شريط السدو ينفتح من المنتصف إلى الطرفين
        p_band = mo.ease_out_quint(mo.window(t, 0.35, 0.85))
        bw = max(2, int(W * p_band))
        band = self._band.crop(((W - bw) // 2, 0, (W - bw) // 2 + bw, self._band.height))
        paste_alpha(img, band, ((W - bw) // 2, self._band_y), min(1.0, p_band * 1.6))

        p_ghost = mo.ease_out_cubic(mo.window(t, 0.55, 1.1))
        paste_alpha(img, self._ghost,
                    (self._ghost_pos[0], self._ghost_pos[1] + int(30 * (1 - p_ghost))),
                    p_ghost * 0.95)

        p_logo = mo.ease_out_cubic(mo.window(t, 0.20, 0.7))
        paste_alpha(img, self._logo, ((W - self._logo.width) // 2,
                                      int(TOP - 40 + 24 * (1 - p_logo))), p_logo)

        for i, (layer, (x, y)) in enumerate(self._kicker):
            p = mo.ease_out_cubic(mo.window(t, 0.70 + i * 0.08, 0.55))
            paste_alpha(img, layer, (x + int(36 * (1 - p)), y), p)
        if self._kicker:
            _, (kx, ky) = self._kicker[0]
            p = mo.ease_out_cubic(mo.window(t, 0.78, 0.5))
            grown = max(1, int(58 * p))
            rule_right = kx + self._kicker[0][0].width + 24 + 58
            paste_alpha(img, self._rule.crop((58 - grown, 0, 58, 6)),
                        (rule_right - grown, ky + 18), p)

        for i, (layer, (x, y)) in enumerate(self._head):
            p = mo.ease_out_quint(mo.window(t, 0.95 + i * 0.16, 0.85))
            paste_alpha(img, layer, (x, y + int(58 * (1 - p))), p)

        # اللمعة تمرّ على العنوان مرّة واحدة بعد اكتماله
        sweep = mo.window(t, 1.85, 0.95)
        if 0 < sweep < 1:
            pos = mo.lerp(-0.35, 1.35, sweep)
            for layer, (x, y) in self._head_shine:
                img.alpha_composite(shine(layer, pos), (x, y))

        for i, (layer, (x, y)) in enumerate(self._sub):
            p = mo.ease_out_cubic(mo.window(t, 1.60 + i * 0.10, 0.7))
            paste_alpha(img, layer, (x, y + int(26 * (1 - p))), p)

        # الستارة الخضراء تنفتح من المنتصف في أول لحظة
        p_open = mo.ease_out_quint(mo.window(t, 0.0, 0.9))
        if p_open < 0.999:
            off = int(H / 2 * p_open)
            shutter = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            sd = ImageDraw.Draw(shutter)
            sd.rectangle((0, 0, W, H // 2 - off), fill=(*B.color("green_deep"), 255))
            sd.rectangle((0, H // 2 + off, W, H), fill=(*B.color("green_deep"), 255))
            edge = int(220 * (1 - p_open) + 60)
            sd.rectangle((0, H // 2 - off - 4, W, H // 2 - off), fill=(*B.color("gold"), edge))
            sd.rectangle((0, H // 2 + off, W, H // 2 + off + 4), fill=(*B.color("gold"), edge))
            img.alpha_composite(shutter)

        return img


@dataclass
class SplitScene(Scene):
    """انقسام قطري: الصورة في الأعلى بحافّة مائلة، والنص على حقل أخضر تحتها."""

    photo: str = ""
    title: str = ""
    body: str = ""
    move: str = "zoom_in"
    flip: bool = False           # يقلب ميل الحافّة فلا يتكرّر التكوين
    duration: float = 3.2
    style: Style = field(default_factory=lambda: STYLES[0])

    _base: Image.Image = field(default=None, repr=False)
    _region_h: int = 0
    _bg: Image.Image = field(default=None, repr=False)
    _mask: Image.Image = field(default=None, repr=False)
    _edge: Image.Image = field(default=None, repr=False)
    _band: Image.Image = field(default=None, repr=False)
    _band_y: int = 0
    _title: list = field(default_factory=list, repr=False)
    _body: list = field(default_factory=list, repr=False)
    _text_rule: Image.Image = field(default=None, repr=False)
    _rule_pos: tuple = (0, 0)

    def prepare(self) -> None:
        gold = B.color("gold")
        self._bg = national_backdrop((W, H))

        y_hi, y_lo = int(H * 0.55), int(H * 0.64)
        left, right = (y_lo, y_hi) if not self.flip else (y_hi, y_lo)
        poly = [(0, 0), (W, 0), (W, right), (0, left)]

        # الصورة تُقصّ على مقاس *منطقة الانقسام* (١٠٨٠×١٢٢٩ تقريبًا) لا على
        # مقاس الإطار الكامل: قصّ إطار عمودي كامل ثم إخفاء نصفه يعني أننا
        # نعرض أعلى الصورة فقط — وهو غالبًا السماء أو الجدار لا الموضوع.
        self._region_h = max(left, right)
        self._base = fx.cover(open_photo(self.photo),
                              (int(W * 1.16), int(self._region_h * 1.16)))

        self._mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(self._mask).polygon(poly, fill=255)

        self._edge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(self._edge).line([(0, left), (W, right)], fill=(*gold, 235), width=6)

        self._band = sadu_band(W, 40, seed=3)
        self._band_y = H - BOTTOM + 96

        text_top = max(left, right) + 88
        max_w = W - SIDE * 2 - 46
        t_style = ty.fit_size(
            self.title,
            ty.TextStyle(role="headline", size=self.style.caption_title_size + 16,
                         align="right", line_spacing=1.18, max_width=max_w,
                         fill=(*B.color("white"), 255), shadow=(0, 0, 0, 120), shadow_blur=10),
            max_lines=2,
        )
        t_block = ty.wrap(self.title, t_style)
        self._title = tight_lines(t_block, (W - SIDE - 38, text_top))

        body_h = 0
        if self.body:
            b_style = ty.TextStyle(role="body", size=self.style.body_size + 4, align="right",
                                   line_spacing=1.34, max_width=max_w,
                                   fill=(*B.color("sand"), 238), shadow=(0, 0, 0, 110),
                                   shadow_blur=8)
            b_block = ty.wrap(self.body, b_style)
            body_h = b_block.height + 22
            self._body = tight_lines(b_block, (W - SIDE - 38, text_top + t_block.height + 22))

        # خيط ذهبي رأسي يمين الكتلة — يربط النص بحافّة الانقسام
        rule_h = t_block.height + body_h + 8
        self._text_rule = Image.new("RGBA", (8, rule_h), (0, 0, 0, 0))
        ImageDraw.Draw(self._text_rule).rounded_rectangle((0, 0, 7, rule_h - 1), 4,
                                                          fill=(*gold, 255))
        self._rule_pos = (W - SIDE - 8, text_top - 6)

    def _window(self, t: float) -> Image.Image:
        """نافذة كِن بيرنز داخل منطقة الانقسام وحدها."""
        bw, bh = W, self._region_h
        p = mo.ease_in_out(mo.window(t, 0, self.duration))
        z = mo.lerp(1.16, 1.02, p) if self.move == "zoom_out" else mo.lerp(1.02, 1.16, p)
        win_w = min(self._base.width, max(bw, int(round(bw * 1.16 / z))))
        win_h = min(self._base.height, max(bh, int(round(bh * 1.16 / z))))

        if self.move == "pan_left":
            fx_ = mo.lerp(0.88, 0.12, p)
        elif self.move == "pan_right":
            fx_ = mo.lerp(0.12, 0.88, p)
        else:
            fx_ = 0.5
        x0 = int((self._base.width - win_w) * fx_)
        y0 = int((self._base.height - win_h) * 0.5)
        return self._base.crop((x0, y0, x0 + win_w, y0 + win_h)).resize((bw, bh), Image.BICUBIC)

    def frame(self, t: float) -> Image.Image:
        img = self._bg.copy()

        photo = national_grade(self._window(t), 0.40).convert("RGBA")
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        layer.paste(photo, (0, 0))
        layer.putalpha(self._mask)
        photo = layer

        # الكشف يمشي من اليمين لليسار مع اتجاه القراءة، وعلى حافّته خيط ذهبي
        p = mo.ease_out_quint(mo.window(t, 0.0, 0.75))
        vis = max(2, int(W * p))
        img.alpha_composite(photo.crop((W - vis, 0, W, H)), (W - vis, 0))
        if p < 0.999:
            glow = Image.new("RGBA", (10, H), (*B.color("gold"), 210))
            paste_alpha(img, glow, (max(0, W - vis - 5), 0), 1.0 - p * 0.3)

        a = mo.inout_alpha(t, self.duration, 0.5, 0.3)
        paste_alpha(img, self._edge, (0, 0), min(a, mo.ease_out_cubic(mo.window(t, 0.35, 0.6))))

        p_band = mo.ease_out_cubic(mo.window(t, 0.45, 0.7))
        bw = max(2, int(W * p_band))
        paste_alpha(img, self._band.crop((0, 0, bw, self._band.height)),
                    (W - bw, self._band_y), min(a, p_band))

        p_rule = mo.ease_out_cubic(mo.window(t, 0.40, 0.55))
        grown = max(2, int(self._text_rule.height * p_rule))
        paste_alpha(img, self._text_rule.crop((0, 0, 8, grown)), self._rule_pos, min(a, p_rule))

        for i, (layer, (x, y)) in enumerate(self._title):
            q = mo.ease_out_quint(mo.window(t, 0.42 + i * 0.10, 0.7))
            paste_alpha(img, layer, (x + int(40 * (1 - q)), y), min(a, q))
        for i, (layer, (x, y)) in enumerate(self._body):
            q = mo.ease_out_cubic(mo.window(t, 0.62 + i * 0.08, 0.6))
            paste_alpha(img, layer, (x + int(26 * (1 - q)), y), min(a, q))
        return img


@dataclass
class EmblemScene(Scene):
    """بطاقة المناسبة: الرقم والتاريخ وجملة التهنئة على حقل أخضر بنقش سدو."""

    number: str = "٩٦"
    date: str = NATIONAL_DATE_AR
    label: str = NATIONAL_LABEL_AR
    line: str = ""
    duration: float = 2.6
    style: Style = field(default_factory=lambda: STYLES[0])

    _bg: Image.Image = field(default=None, repr=False)
    _num: Image.Image = field(default=None, repr=False)
    _label: Image.Image = field(default=None, repr=False)
    _date: Image.Image = field(default=None, repr=False)
    _line: list = field(default_factory=list, repr=False)
    _rule: Image.Image = field(default=None, repr=False)

    def prepare(self) -> None:
        gold = B.color("gold")
        bg = national_backdrop((W, H)).copy()
        top_band = sadu_band(W, 54, seed=5)
        bot_band = sadu_band(W, 54, seed=9)
        bg.alpha_composite(top_band, (0, TOP + 40))
        bg.alpha_composite(bot_band, (0, H - BOTTOM + 60))
        self._bg = bg

        self._num = _numeral(self.number, 420, (*B.color("white"), 255), (*gold, 255), 8)
        self._label = _centered(self.label, ty.TextStyle(
            role="body_bold", size=44, align="center", fill=(*gold, 255),
            shadow=(0, 0, 0, 110), shadow_blur=10))
        self._date = _centered(self.date, ty.TextStyle(
            role="body", size=38, align="center", fill=(*B.color("sand"), 235),
            shadow=(0, 0, 0, 90), shadow_blur=8))

        if self.line:
            style = ty.fit_size(self.line, ty.TextStyle(
                role="display", size=68, align="center", line_spacing=1.22,
                max_width=W - SIDE * 2, fill=(*B.color("white"), 255),
                shadow=(0, 0, 0, 130), shadow_blur=14), max_lines=2)
            block = ty.wrap(self.line, style)
            self._line = tight_lines(block, (W // 2, int(H * 0.70)))

        rule = Image.new("RGBA", (200, 5), (0, 0, 0, 0))
        ImageDraw.Draw(rule).rounded_rectangle((0, 0, 199, 4), 2, fill=(*gold, 255))
        self._rule = rule

    def frame(self, t: float) -> Image.Image:
        img = self._bg.copy()

        p_label = mo.ease_out_cubic(mo.window(t, 0.05, 0.5))
        paste_alpha(img, self._label, ((W - self._label.width) // 2,
                                       int(H * 0.30) + int(18 * (1 - p_label))), p_label)

        p = mo.ease_out_back(mo.window(t, 0.18, 0.8), overshoot=0.7)
        scale = 0.80 + 0.20 * p
        nw, nh = max(2, int(self._num.width * scale)), max(2, int(self._num.height * scale))
        num = self._num.resize((nw, nh), Image.BICUBIC)
        nx, ny = (W - nw) // 2, int(H * 0.36)
        paste_alpha(img, num, (nx, ny), mo.ease_out_cubic(mo.window(t, 0.18, 0.4)))

        sweep = mo.window(t, 0.85, 0.85)
        if 0 < sweep < 1:
            img.alpha_composite(shine(num, mo.lerp(-0.35, 1.35, sweep), strength=215), (nx, ny))

        y = ny + nh + 26
        p_rule = mo.ease_out_cubic(mo.window(t, 0.60, 0.5))
        grown = max(2, int(200 * p_rule))
        paste_alpha(img, self._rule.crop((0, 0, grown, 5)), ((W - grown) // 2, y), p_rule)

        p_date = mo.ease_out_cubic(mo.window(t, 0.72, 0.5))
        paste_alpha(img, self._date, ((W - self._date.width) // 2,
                                      y + 26 + int(14 * (1 - p_date))), p_date)

        for i, (layer, (x, yy)) in enumerate(self._line):
            q = mo.ease_out_quint(mo.window(t, 0.95 + i * 0.12, 0.7))
            paste_alpha(img, layer, (x, yy + int(30 * (1 - q))), q)
        return img


@dataclass
class NationalOutroScene(Scene):
    """ختام المناسبة: تهنئة، ثم الشعار والدعوة للحجز على حقل أخضر."""

    cta: str = "احجز شاليهك"
    greeting: str = "كل عام ووطننا بخير"
    duration: float = 4.2
    style: Style = field(default_factory=lambda: STYLES[0])

    _bg: Image.Image = field(default=None, repr=False)
    _logo: Image.Image = field(default=None, repr=False)
    _word: Image.Image = field(default=None, repr=False)
    _tag: Image.Image = field(default=None, repr=False)
    _place: Image.Image = field(default=None, repr=False)
    _greet: Image.Image = field(default=None, repr=False)
    _cta: Image.Image = field(default=None, repr=False)
    _phone: Image.Image = field(default=None, repr=False)
    _handle: Image.Image = field(default=None, repr=False)

    def prepare(self) -> None:
        gold = B.color("gold")
        bg = national_backdrop((W, H)).copy()
        bg.alpha_composite(sadu_band(W, 48, seed=7), (0, TOP - 20))
        bg.alpha_composite(sadu_band(W, 48, seed=11), (0, H - 150))
        self._bg = bg

        logo = Image.open(B.logo_mark).convert("RGBA")
        target_h = 300
        self._logo = logo.resize((int(logo.width * target_h / logo.height), target_h),
                                 Image.LANCZOS)

        self._greet = _centered(self.greeting, ty.TextStyle(
            role="display", size=64, align="center", fill=(*B.color("white"), 255),
            shadow=(0, 0, 0, 120), shadow_blur=14))
        self._word = _centered(B.wordmark_text, ty.TextStyle(
            role="display", size=88, align="center", fill=(*B.color("white"), 255),
            shadow=(0, 0, 0, 120), shadow_blur=16))
        self._tag = _centered(B.tagline_ar, ty.TextStyle(
            role="body", size=36, align="center", fill=(*B.color("sand"), 235),
            shadow=(0, 0, 0, 90), shadow_blur=10))
        self._place = _centered(B.location_line, ty.TextStyle(
            role="body", size=30, align="center", fill=(*gold, 235),
            shadow=(0, 0, 0, 80), shadow_blur=8)) if B.location_line else None

        cta_style = ty.TextStyle(role="body_bold", size=44, align="center")
        cta_font = ty.font(cta_style.role, cta_style.size)
        cta_text = ty.shape(self.cta)
        pw = int(ty.measure(cta_text, cta_style)[0]) + 108
        ph = 104
        btn = Image.new("RGBA", (pw + 60, ph + 60), (0, 0, 0, 0))
        shadow = Image.new("RGBA", (pw + 60, ph + 60), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((30, 40, 30 + pw, 40 + ph), ph // 2,
                                                 fill=(0, 0, 0, 130))
        btn.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
        bd = ImageDraw.Draw(btn)
        bd.rounded_rectangle((30, 30, 30 + pw, 30 + ph), ph // 2, fill=(*B.color("white"), 255))
        bd.rounded_rectangle((30, 30, 30 + pw, 30 + ph), ph // 2,
                             outline=(*gold, 255), width=3)
        bd.text((30 + pw / 2, 30 + ph / 2), cta_text, font=cta_font,
                fill=(*B.color("green_deep"), 255), anchor="mm", **cta_style._draw_kwargs)
        self._cta = btn

        phone_text = (f"{B.contact_label_ar}  ·  {B.contact_phone}"
                      if B.contact_phone else B.contact_label_ar)
        self._phone = _centered(phone_text, ty.TextStyle(
            role="body_bold", size=42, align="center", fill=(*B.color("white"), 255),
            shadow=(0, 0, 0, 110), shadow_blur=12))
        self._handle = _centered(B.handle, ty.TextStyle(
            role="latin", size=34, align="center", tracking=2, direction="ltr",
            language="en", fill=(*gold, 240), shadow=None))

    def frame(self, t: float) -> Image.Image:
        img = self._bg.copy()

        p_greet = mo.ease_out_quint(mo.window(t, 0.05, 0.75))
        gy = int(H * 0.155)
        paste_alpha(img, self._greet, ((W - self._greet.width) // 2,
                                       gy + int(30 * (1 - p_greet))), p_greet)
        sweep = mo.window(t, 0.70, 0.9)
        if 0 < sweep < 1:
            img.alpha_composite(shine(self._greet, mo.lerp(-0.35, 1.35, sweep)),
                                ((W - self._greet.width) // 2, gy))

        p = mo.ease_out_back(mo.window(t, 0.40, 0.9), overshoot=0.8)
        scale = 0.88 + 0.12 * p + 0.005 * mo.breathe(t, period=4.0)
        lw, lh = max(2, int(self._logo.width * scale)), max(2, int(self._logo.height * scale))
        logo = self._logo.resize((lw, lh), Image.BICUBIC)
        ly = gy + self._greet.height + 46
        paste_alpha(img, logo, ((W - lw) // 2, ly),
                    mo.ease_out_cubic(mo.window(t, 0.40, 0.5)))

        y = ly + int(self._logo.height * 0.94)
        p_word = mo.ease_out_cubic(mo.window(t, 0.85, 0.6))
        paste_alpha(img, self._word, ((W - self._word.width) // 2,
                                      y + int(24 * (1 - p_word))), p_word)

        y += self._word.height + 24
        p_tag = mo.ease_out_cubic(mo.window(t, 1.05, 0.6))
        paste_alpha(img, self._tag, ((W - self._tag.width) // 2,
                                     y + int(16 * (1 - p_tag))), p_tag)

        if self._place is not None:
            y += self._tag.height + 14
            p_place = mo.ease_out_cubic(mo.window(t, 1.20, 0.6))
            paste_alpha(img, self._place, ((W - self._place.width) // 2,
                                           y + int(12 * (1 - p_place))), p_place)
            y += self._place.height + 54
        else:
            y += self._tag.height + 60

        p_cta = mo.ease_out_cubic(mo.window(t, 1.45, 0.5))
        back = mo.ease_out_back(mo.window(t, 1.45, 0.7), overshoot=1.05)
        paste_alpha(img, self._cta, ((W - self._cta.width) // 2,
                                     y + int(28 * (1 - back))), p_cta)

        y += self._cta.height + 2
        p_phone = mo.ease_out_cubic(mo.window(t, 1.85, 0.6))
        paste_alpha(img, self._phone, ((W - self._phone.width) // 2,
                                       y + int(16 * (1 - p_phone))), p_phone)

        y += self._phone.height + 40
        p_handle = mo.ease_out_cubic(mo.window(t, 2.10, 0.6))
        paste_alpha(img, self._handle, ((W - self._handle.width) // 2,
                                        min(y, H - 210)), p_handle)
        return img


# --------------------------------------------------- جلد المناسبة للمشاهد العامة
# مشاهد `scenes.py` مبنيّة على أزرق أجمكان. بدل نسخها كاملة نستبدل خطّافاتها
# الثلاثة فقط، فتخرج بالأخضر نفسه دون أي تكرار للكود.

def _occasion_grade(image: Image.Image, strength: float = 1.0) -> Image.Image:
    return national_grade(image, 0.42 * max(0.6, min(1.4, strength)))


class _NationalSkin:
    grade_fn = staticmethod(_occasion_grade)
    scrim_fn = staticmethod(green_scrim)
    bg_color = "green_deep"


class NationalPhotoScene(_NationalSkin, PhotoScene):
    """مشهد صورة كامل بجلد المناسبة."""


class NationalFlashScene(_NationalSkin, FlashScene):
    """قطع سريع بجلد المناسبة."""


class NationalGridScene(_NationalSkin, GridScene):
    """شبكة لقطات بجلد المناسبة."""
