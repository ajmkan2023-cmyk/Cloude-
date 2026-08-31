"""المشاهد: مشهد الافتتاح، مشاهد الصور، ومشهد الختام.

كل مشهد يجهّز طبقاته الثقيلة مرّة واحدة في `prepare()` ثم يرسم إطارًا في
`frame(t)` — لهذا يبقى الإخراج سريعًا رغم أن كل بكسل مرسوم في بايثون.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import imagefx as fx
from . import motion as mo
from . import typography as ty
from .config import brand
from .styles import STYLES, Style

B = brand()
W, H = B.video.width, B.video.height
SIDE = B.video.safe_side
BOTTOM = B.video.safe_bottom
TOP = B.video.safe_top

ZMAX = 1.20


# ------------------------------------------------------------------ أدوات
def paste_alpha(dst: Image.Image, src: Image.Image, pos: tuple[int, int], alpha: float) -> None:
    """يركّب طبقة بشفافية إضافية دون تعديل الأصل."""
    if alpha <= 0.003:
        return
    if alpha < 0.997:
        layer = src.copy()
        layer.putalpha(layer.getchannel("A").point(lambda a: int(a * alpha)))
    else:
        layer = src
    dst.alpha_composite(layer, pos)


def tight_lines(block: ty.TextBlock, origin: tuple[int, int]) -> list[tuple[Image.Image, tuple[int, int]]]:
    """يرسم كل سطر في طبقة مقصوصة على حدوده — لتحريك الأسطر كلٌّ على حدة."""
    out: list[tuple[Image.Image, tuple[int, int]]] = []
    line_h = block.line_height
    for i, line in enumerate(block.lines):
        if not line:
            continue
        single = ty.TextBlock(lines=[line], style=block.style, line_boxes=[block.line_boxes[i]])
        layer = ty.render_block(single, (W, H), (origin[0], origin[1] + i * line_h))
        box = layer.getbbox()
        if not box:
            continue
        out.append((layer.crop(box), (box[0], box[1])))
    return out


def load_photo(path: str | Path) -> Image.Image:
    """يحمّل صورة، يصحّح دورانها، ويجهّزها بمقاس عمودي مع هامش للحركة."""
    img = Image.open(path)
    try:  # احترام معلومات EXIF للاتجاه
        from PIL import ImageOps

        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    img = img.convert("RGB")
    return fx.cover(img, (int(W * ZMAX), int(H * ZMAX)))


def ken_burns(base: Image.Image, t: float, duration: float, move: str, bias: float = 0.5) -> Image.Image:
    """نافذة متحرّكة على الصورة — تكبير/تصغير/انتقال أفقي بحركة منعّمة."""
    p = mo.ease_in_out(mo.window(t, 0, duration))

    if move == "zoom_out":
        z = mo.lerp(ZMAX, 1.02, p)
    elif move in ("pan_left", "pan_right"):
        z = mo.lerp(1.09, 1.15, p)
    elif move == "rise":
        z = mo.lerp(1.04, ZMAX, p)
    else:  # zoom_in
        z = mo.lerp(1.02, ZMAX, p)

    win_w = min(base.width, max(W, int(round(W * ZMAX / z))))
    win_h = min(base.height, max(H, int(round(H * ZMAX / z))))

    slack_x = base.width - win_w
    slack_y = base.height - win_h

    if move == "pan_left":
        fx_ = mo.lerp(0.92, 0.08, p)
    elif move == "pan_right":
        fx_ = mo.lerp(0.08, 0.92, p)
    else:
        fx_ = 0.5

    if move == "rise":
        fy = mo.lerp(0.86, 0.16, p)
    else:
        fy = bias

    left = int(slack_x * fx_)
    top = int(slack_y * fy)
    window = base.crop((left, top, left + win_w, top + win_h))
    return window.resize((W, H), Image.BICUBIC)


# ------------------------------------------------------------------ الأساس
@dataclass
class Scene:
    duration: float = 4.0

    # خطّافات الجلد: الافتراضي هوية أجمكان الزرقاء، وحزمة المناسبة
    # (`national.py`) تستبدلها بالأخضر دون نسخ المشاهد كلها.
    grade_fn = staticmethod(fx.grade)
    scrim_fn = staticmethod(fx.scrim)
    bg_color = "ink"

    def prepare(self) -> None:  # pragma: no cover - يُنفَّذ في الأبناء
        ...

    def frame(self, t: float) -> Image.Image:  # pragma: no cover
        raise NotImplementedError


# ------------------------------------------------------------ مشهد الافتتاح
@dataclass
class TitleScene(Scene):
    photo: str = ""
    kicker: str = ""
    headline: str = ""
    subline: str = ""
    duration: float = 3.4
    style: Style = field(default_factory=lambda: STYLES[0])

    _base: Image.Image = field(default=None, repr=False)
    _bias: float = 0.5
    _scrim: Image.Image = field(default=None, repr=False)
    _kicker: list = field(default_factory=list, repr=False)
    _head: list = field(default_factory=list, repr=False)
    _sub: list = field(default_factory=list, repr=False)
    _rule: Image.Image = field(default=None, repr=False)
    _logo: Image.Image = field(default=None, repr=False)

    def prepare(self) -> None:
        st = self.style
        centered = st.title_layout == "center"
        accent = B.color(st.accent)

        self._base = load_photo(self.photo)
        self._bias = fx.smart_crop_bias(self._base)
        self._scrim = fx.scrim((W, H), *st.scrim_title)

        align = "center" if centered else "right"
        anchor_x = W // 2 if centered else W - SIDE
        max_w = W - SIDE * 2

        head_style = ty.fit_size(
            self.headline,
            ty.TextStyle(role="display", size=st.title_size, max_width=max_w, align=align,
                         line_spacing=1.22, shadow=(0, 0, 0, 165), shadow_offset=(0, 6),
                         shadow_blur=16, fill=(*B.color("white"), 255)),
            max_lines=3,
        )
        head_block = ty.wrap(self.headline, head_style)

        sub_style = ty.TextStyle(role="body", size=40, align=align, line_spacing=1.30,
                                 max_width=int(max_w * 0.92), fill=(*B.color("sand"), 240),
                                 shadow=(0, 0, 0, 130), shadow_blur=12)
        sub_block = ty.wrap(self.subline, sub_style) if self.subline else None
        sub_h = sub_block.height if sub_block else 0

        if centered or st.title_layout == "upper":
            # كتلة واحدة: متمركزة بصريًا، أو مرفوعة إلى أعلى الشاشة
            block_h = 86 + head_block.height + (66 + sub_h if sub_block else 0)
            top = int(H * 0.46) - block_h // 2 if centered else int(H * 0.20)
            kick_top = top
            head_top = kick_top + 86
            sub_top = head_top + head_block.height + 66
        else:
            # التكوين من الأسفل إلى الأعلى ليبقى النص داخل المنطقة الآمنة
            sub_top = H - BOTTOM - 40 - sub_h
            head_top = sub_top - (66 if sub_block else 0) - head_block.height
            kick_top = head_top - 86

        self._head = tight_lines(head_block, (anchor_x, head_top))
        self._sub = tight_lines(sub_block, (anchor_x, sub_top)) if sub_block else []

        kick_style = ty.TextStyle(role="body_bold", size=38, align=align,
                                  fill=(*accent, 255), shadow=(0, 0, 0, 140),
                                  shadow_blur=10, max_width=max_w)
        kick_block = ty.wrap(self.kicker, kick_style)
        kick_anchor = anchor_x if centered else anchor_x - 74
        self._kicker = tight_lines(kick_block, (kick_anchor, kick_top))
        self._centered = centered

        # خط قصير بلون التمييز بجوار السطر التمهيدي (في التكوين اليميني فقط)
        rule = Image.new("RGBA", (54, 6), (0, 0, 0, 0))
        ImageDraw.Draw(rule).rounded_rectangle((0, 0, 53, 5), 3, fill=(*accent, 255))
        self._rule = rule

        logo = Image.open(B.logo_mark).convert("RGBA")
        target_h = 168
        self._logo = logo.resize((int(logo.width * target_h / logo.height), target_h), Image.LANCZOS)

    def frame(self, t: float) -> Image.Image:
        img = ken_burns(self._base, t, self.duration, "zoom_in", self._bias)
        img = fx.grade(img, self.style.grade).convert("RGBA")
        img.alpha_composite(self._scrim)

        # الشعار يهبط بلطف من الأعلى
        p_logo = mo.ease_out_cubic(mo.window(t, 0.10, 0.7))
        lx = (W - self._logo.width) // 2
        paste_alpha(img, self._logo, (lx, int(TOP + 30 - 26 * (1 - p_logo))), p_logo)

        for i, (layer, (x, y)) in enumerate(self._kicker):
            p = mo.ease_out_cubic(mo.window(t, 0.55 + i * 0.08, 0.55))
            slide = 0 if self._centered else int(34 * (1 - p))
            paste_alpha(img, layer, (x + slide, y), p)
        if self._kicker and not self._centered:
            _, (kx, ky) = self._kicker[0]
            p = mo.ease_out_cubic(mo.window(t, 0.62, 0.5))
            grown = max(1, int(54 * p))          # ينمو من اليمين لليسار مع اتجاه القراءة
            rule = self._rule.crop((54 - grown, 0, 54, 6))
            rule_right = kx + self._kicker[0][0].width + 22 + 54
            paste_alpha(img, rule, (rule_right - grown, ky + 16), p)

        for i, (layer, (x, y)) in enumerate(self._head):
            p = mo.ease_out_quint(mo.window(t, 0.80 + i * 0.15, 0.85))
            paste_alpha(img, layer, (x, y + int(52 * (1 - p))), p)

        for i, (layer, (x, y)) in enumerate(self._sub):
            p = mo.ease_out_cubic(mo.window(t, 1.45 + i * 0.10, 0.7))
            paste_alpha(img, layer, (x, y + int(26 * (1 - p))), p)

        return img


# --------------------------------------------------------------- مشهد صورة
@dataclass
class PhotoScene(Scene):
    photo: str = ""
    title: str = ""
    body: str = ""
    index: int = 1
    total: int = 1
    move: str = "zoom_in"
    duration: float = 3.8
    style: Style = field(default_factory=lambda: STYLES[0])

    _base: Image.Image = field(default=None, repr=False)
    _bias: float = 0.5
    _scrim: Image.Image = field(default=None, repr=False)
    _panels: list = field(default_factory=list, repr=False)
    _title: list = field(default_factory=list, repr=False)
    _body: list = field(default_factory=list, repr=False)
    _number: Image.Image = field(default=None, repr=False)
    _number_pos: tuple[int, int] = (0, 0)
    _card_origin: tuple[int, int] = (0, 0)

    def prepare(self) -> None:
        st = self.style
        self._base = load_photo(self.photo)
        self._bias = fx.smart_crop_bias(self._base)
        self._scrim = self.scrim_fn((W, H), *st.scrim_photo)
        accent = B.color(st.accent)

        mid = ken_burns(self._base, self.duration / 2, self.duration, self.move, self._bias)
        mid = self.grade_fn(mid, st.grade).convert("RGBA")

        max_w = W - SIDE * 2
        # «bare» بلا لوحة فيتنفّس النص أكثر؛ الباقي داخل لوحة لها حشوة
        pad = 0 if st.caption == "bare" else 44
        reserve = 96 if st.number == "chip" else 0     # مكان الشارة داخل اللوحة

        title_style = ty.fit_size(
            self.title,
            ty.TextStyle(role="headline", size=st.caption_title_size, align="right",
                         line_spacing=1.18, max_width=max_w - pad * 2 - reserve,
                         fill=(*B.color("white"), 255),
                         shadow=(0, 0, 0, 120), shadow_blur=8, shadow_offset=(0, 3)),
            max_lines=2,
        )
        title_block = ty.wrap(self.title, title_style)

        body_style = ty.TextStyle(role="body", size=st.body_size, align="right",
                                  line_spacing=1.30,
                                  max_width=max_w - pad * 2 - (40 if st.caption == "bare" else 0),
                                  fill=(*B.color("sand"), 235),
                                  shadow=(0, 0, 0, 110), shadow_blur=8)
        body_block = ty.wrap(self.body, body_style) if self.body else None

        text_h = title_block.height + (body_block.height + 16 if body_block else 0)
        card_h = pad * 2 + text_h
        card_x, card_w = SIDE, max_w
        card_y = H - BOTTOM - card_h - 20

        self._panels = []      # طبقات تُرسم خلف النص: (طبقة، موضع)
        right = card_x + card_w - pad
        text_top = card_y + pad

        if st.caption == "glass":
            panel = fx.glass_panel(mid, (card_x, card_y, card_x + card_w, card_y + card_h),
                                   radius=st.radius)
            self._panels.append((panel, (card_x - 40, card_y - 40)))   # اللوحة تحمل ظلًا بهامش ٤٠

        elif st.caption == "ribbon":
            # لوحة ضيّقة تحتضن النص فقط، بحافّة ملوّنة على يمينها
            text_w = max(title_block.width, body_block.width if body_block else 0)
            rib_w = min(max_w, text_w + pad * 2 + reserve)
            rib_x = W - SIDE - rib_w
            panel = fx.glass_panel(mid, (rib_x, card_y, rib_x + rib_w, card_y + card_h),
                                   radius=st.radius)
            edge = Image.new("RGBA", (10, card_h), (0, 0, 0, 0))
            ImageDraw.Draw(edge).rounded_rectangle((0, 0, 9, card_h - 1), 5, fill=(*accent, 255))
            self._panels.append((panel, (rib_x - 40, card_y - 40)))
            self._panels.append((edge, (W - SIDE - 10, card_y)))
            right = W - SIDE - pad
            card_x, card_w = rib_x, rib_w

        elif st.caption == "band":
            band_h = card_h + 36
            band_y = H - BOTTOM - band_h + 10
            band = Image.new("RGBA", (W, band_h + 30), (0, 0, 0, 0))
            bd = ImageDraw.Draw(band)
            bd.rectangle((0, 6, W, band_h), fill=(*B.color("navy"), 232))
            bd.rectangle((0, 0, W, 6), fill=(*accent, 255))
            self._panels.append((band, (0, band_y)))
            right = W - SIDE
            text_top = band_y + 34
            card_y = band_y

        elif st.caption == "bare":
            # بلا لوحة: شريط رأسي رفيع يمين النص
            rule_h = text_h + 10
            rule = Image.new("RGBA", (8, rule_h), (0, 0, 0, 0))
            ImageDraw.Draw(rule).rounded_rectangle((0, 0, 7, rule_h - 1), 4, fill=(*accent, 255))
            self._panels.append((rule, (W - SIDE - 8, card_y - 4)))
            right = W - SIDE - 34

        elif st.caption == "corner":
            # النص أعلى الشاشة بدل أسفلها — يقلب التكوين رأسًا على عقب
            card_y = TOP + 150
            text_top = card_y + pad
            panel = fx.glass_panel(mid, (card_x, card_y, card_x + card_w, card_y + card_h),
                                   radius=st.radius)
            self._panels.append((panel, (card_x - 40, card_y - 40)))

        self._title = tight_lines(title_block, (right, text_top))
        self._body = (
            tight_lines(body_block, (right, text_top + title_block.height + 16))
            if body_block else []
        )

        self._number, self._number_pos = self._build_number(st, card_x, card_y, card_h, pad)

    def _build_number(self, st, card_x: int, card_y: int, card_h: int, pad: int):
        """شكل الترقيم يتبع النمط: شارة دائرية، رقم ضخم شبحي، أو رقم صغير."""
        if st.number == "none":
            return None, (0, 0)

        num = f"{self.index}"
        accent = B.color(st.accent)

        if st.number == "chip":
            chip = Image.new("RGBA", (84, 84), (0, 0, 0, 0))
            cd = ImageDraw.Draw(chip)
            cd.ellipse((0, 0, 83, 83), fill=(*accent, 255))
            cd.text((42, 44), num, font=ty.font("body_bold", 42),
                    fill=(*B.color("ink"), 255), anchor="mm")
            return chip, (card_x + pad - 8, card_y + pad - 4)

        if st.number == "big":
            f = ty.font("display", 150)
            layer = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
            ImageDraw.Draw(layer).text(
                (100, 100), num, font=f, fill=(*accent, 60), anchor="mm",
                stroke_width=4, stroke_fill=(*accent, 190),
            )
            return layer, (SIDE - 20, card_y + card_h // 2 - 100 + 18)

        # text: ترقيم صغير مثل «٠١ / ٠٥» — أسفل البطاقة إن كانت أعلى الشاشة
        f = ty.font("body_bold", 30)
        label = f"{self.index:02d} / {self.total:02d}"
        layer = Image.new("RGBA", (240, 60), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((239, 30), label, font=f, fill=(*accent, 240),
                                   anchor="rm", direction="ltr")
        at_top = card_y < H // 2
        y = card_y + card_h + 18 if at_top else card_y - 58
        return layer, (W - SIDE - 34 - 239, y)

    def frame(self, t: float) -> Image.Image:
        img = ken_burns(self._base, t, self.duration, self.move, self._bias)
        img = self.grade_fn(img, self.style.grade).convert("RGBA")
        img.alpha_composite(self._scrim)

        a = mo.inout_alpha(t, self.duration, fade_in=0.55, fade_out=0.35)
        rise = mo.ease_out_quint(mo.window(t, 0.0, 0.75))
        dy = int(70 * (1 - rise))

        for panel, (px, py) in self._panels:
            paste_alpha(img, panel, (px, py + dy), a)
        if self._number is not None:
            paste_alpha(img, self._number, (self._number_pos[0], self._number_pos[1] + dy), a)

        for i, (layer, (x, y)) in enumerate(self._title):
            p = mo.ease_out_cubic(mo.window(t, 0.18 + i * 0.09, 0.6))
            paste_alpha(img, layer, (x, y + dy + int(18 * (1 - p))), min(a, p))
        for i, (layer, (x, y)) in enumerate(self._body):
            p = mo.ease_out_cubic(mo.window(t, 0.34 + i * 0.07, 0.6))
            paste_alpha(img, layer, (x, y + dy + int(14 * (1 - p))), min(a, p))

        return img


# ---------------------------------------------------------------- الختام
@dataclass
class OutroScene(Scene):
    cta: str = "احجز رحلتك الآن"
    duration: float = 3.6
    style: Style = field(default_factory=lambda: STYLES[0])
    photo: str = ""            # تُستخدم كخلفية حين يطلب النمط ذلك

    _bg: Image.Image = field(default=None, repr=False)
    _logo: Image.Image = field(default=None, repr=False)
    _word: Image.Image = field(default=None, repr=False)
    _tag: Image.Image = field(default=None, repr=False)
    _cta_layer: Image.Image = field(default=None, repr=False)
    _phone: Image.Image = field(default=None, repr=False)
    _handle: Image.Image = field(default=None, repr=False)

    def prepare(self) -> None:
        self._bg = fx.brand_backdrop((W, H))
        if self.style.outro_bg == "photo" and self.photo:
            # صورة مضبّبة بعمق خلف تدرّج العلامة — تربط الختام ببقية الحلقة
            base = load_photo(self.photo)
            blurred = fx.grade(fx.cover(base, (W, H)), self.style.grade)
            blurred = blurred.filter(ImageFilter.GaussianBlur(38)).convert("RGBA")
            veil = self._bg.copy()
            veil.putalpha(veil.getchannel("A").point(lambda a: int(a * 0.82)))
            blurred.alpha_composite(veil)
            self._bg = blurred

        logo = Image.open(B.logo_mark).convert("RGBA")
        target_h = 470
        self._logo = logo.resize((int(logo.width * target_h / logo.height), target_h), Image.LANCZOS)

        def centered(text: str, style: ty.TextStyle) -> Image.Image:
            block = ty.wrap(text, style)
            layer = ty.render_block(block, (W, H), (W // 2, 0))
            box = layer.getbbox()
            return layer.crop(box) if box else layer

        self._word = centered(
            B.wordmark_text,
            ty.TextStyle(role="display", size=112, align="center", tracking=4,
                         fill=(*B.color("white"), 255), shadow=(0, 0, 0, 120), shadow_blur=18),
        )
        self._tag = centered(
            B.tagline_ar,
            ty.TextStyle(role="body", size=40, align="center",
                         fill=(*B.color("sand"), 235), shadow=(0, 0, 0, 90), shadow_blur=10),
        )
        self._place = centered(
            B.location_line,
            ty.TextStyle(role="body", size=32, align="center",
                         fill=(*B.color("sky"), 225), shadow=(0, 0, 0, 80), shadow_blur=8),
        ) if B.location_line else None

        # زر الدعوة لاتخاذ إجراء
        cta_style = ty.TextStyle(role="body_bold", size=44, align="center")
        cta_font = ty.font(cta_style.role, cta_style.size)
        cta_text = ty.shape(self.cta)
        tw = ty.measure(cta_text, cta_style)[0]
        pw, ph = int(tw) + 108, 106
        btn = Image.new("RGBA", (pw + 60, ph + 60), (0, 0, 0, 0))
        shadow = Image.new("RGBA", (pw + 60, ph + 60), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((30, 38, 30 + pw, 38 + ph), ph // 2, fill=(0, 0, 0, 120))
        btn.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
        bd = ImageDraw.Draw(btn)
        bd.rounded_rectangle((30, 30, 30 + pw, 30 + ph), ph // 2, fill=(*B.color("sun"), 255))
        bd.text((30 + pw / 2, 30 + ph / 2), cta_text, font=cta_font,
                fill=(*B.color("ink"), 255), anchor="mm", **cta_style._draw_kwargs)
        self._cta_layer = btn

        phone_text = f"{B.contact_label_ar}  ·  {B.contact_phone}" if B.contact_phone else B.contact_label_ar
        self._phone = centered(
            phone_text,
            ty.TextStyle(role="body_bold", size=44, align="center", tracking=1,
                         fill=(*B.color("white"), 255), shadow=(0, 0, 0, 110), shadow_blur=12),
        )
        self._handle = centered(
            B.handle,
            ty.TextStyle(role="latin", size=36, align="center", tracking=2,
                         direction="ltr", language="en",
                         fill=(*B.color("sky"), 235), shadow=None),
        )

    def frame(self, t: float) -> Image.Image:
        img = self._bg.copy()

        # الشعار يكبر بلطف مع تنفّس خفيف
        p = mo.ease_out_back(mo.window(t, 0.05, 0.9), overshoot=0.9)
        scale = 0.86 + 0.14 * p + 0.006 * mo.breathe(t, period=4.0)
        lw = max(2, int(self._logo.width * scale))
        lh = max(2, int(self._logo.height * scale))
        logo = self._logo.resize((lw, lh), Image.BICUBIC)
        logo_y = int(H * 0.17)
        paste_alpha(img, logo, ((W - lw) // 2, logo_y), mo.ease_out_cubic(mo.window(t, 0.0, 0.5)))

        y = logo_y + int(self._logo.height * 0.96)
        p_word = mo.ease_out_cubic(mo.window(t, 0.55, 0.6))
        paste_alpha(img, self._word, ((W - self._word.width) // 2, y + int(26 * (1 - p_word))), p_word)

        y += self._word.height + 30
        p_tag = mo.ease_out_cubic(mo.window(t, 0.85, 0.6))
        paste_alpha(img, self._tag, ((W - self._tag.width) // 2, y + int(18 * (1 - p_tag))), p_tag)

        if self._place is not None:
            y += self._tag.height + 18
            p_place = mo.ease_out_cubic(mo.window(t, 1.00, 0.6))
            paste_alpha(img, self._place,
                        ((W - self._place.width) // 2, y + int(14 * (1 - p_place))), p_place)
            y += self._place.height + 72
        else:
            y += self._tag.height + 78

        p_cta = mo.ease_out_cubic(mo.window(t, 1.20, 0.5))
        cw = self._cta_layer.width
        back = mo.ease_out_back(mo.window(t, 1.20, 0.7), overshoot=1.1)
        paste_alpha(img, self._cta_layer, ((W - cw) // 2, y + int(30 * (1 - back))), p_cta)

        y += self._cta_layer.height + 4
        p_phone = mo.ease_out_cubic(mo.window(t, 1.60, 0.6))
        paste_alpha(img, self._phone, ((W - self._phone.width) // 2, y + int(18 * (1 - p_phone))), p_phone)

        y += self._phone.height + 54
        p_handle = mo.ease_out_cubic(mo.window(t, 1.90, 0.6))
        paste_alpha(img, self._handle, ((W - self._handle.width) // 2, min(y, H - BOTTOM)), p_handle)

        return img


# ------------------------------------------------------- مشاهد المونتاج
# الأنواع التالية هي ما يكسر رتابة «صورة كاملة لكل مشهد». يختار نمط التحرير
# (`patterns.py`) أيّها يظهر ومتى، فيتغيّر إحساس الفيديو لا لونه فقط.


@dataclass
class GridScene(Scene):
    """أربع لقطات (أو ثلاث/اثنتان) في إطار واحد — توصل سعة المكان في لمحة."""

    photos: tuple = ()
    title: str = ""
    body: str = ""
    duration: float = 3.6
    style: Style = field(default_factory=lambda: STYLES[0])

    _cells: list = field(default_factory=list, repr=False)
    _boxes: list = field(default_factory=list, repr=False)
    _bg: Image.Image = field(default=None, repr=False)
    _title: list = field(default_factory=list, repr=False)
    _body: list = field(default_factory=list, repr=False)

    def prepare(self) -> None:
        st = self.style
        gap, edge = 10, 0
        n = len(self.photos)

        # التخطيط يتبع عدد الصور: ٤ شبكة، ٣ كبيرة فوق واثنتان تحت، ٢ مكدّستان
        top = TOP + 40
        bottom = H - BOTTOM + 120
        area_h = bottom - top
        if n >= 4:
            cw, ch = (W - gap) // 2, (area_h - gap) // 2
            self._boxes = [(edge, top), (edge + cw + gap, top),
                           (edge, top + ch + gap), (edge + cw + gap, top + ch + gap)]
            sizes = [(cw, ch)] * 4
        elif n == 3:
            big_h = int(area_h * 0.52)
            cw = (W - gap) // 2
            self._boxes = [(edge, top), (edge, top + big_h + gap), (edge + cw + gap, top + big_h + gap)]
            sizes = [(W, big_h), (cw, area_h - big_h - gap), (cw, area_h - big_h - gap)]
        else:
            ch = (area_h - gap) // 2
            self._boxes = [(edge, top), (edge, top + ch + gap)]
            sizes = [(W, ch)] * 2

        self._cells = []
        for path, size in zip(self.photos[: len(self._boxes)], sizes):
            img = fx.cover(load_photo(path), size)
            self._cells.append(self.grade_fn(img, st.grade).convert("RGBA"))

        self._bg = Image.new("RGBA", (W, H), (*B.color(self.bg_color), 255))

        max_w = W - SIDE * 2
        accent = B.color(st.accent)
        t_style = ty.fit_size(
            self.title,
            ty.TextStyle(role="headline", size=st.caption_title_size, align="center",
                         line_spacing=1.18, max_width=max_w, fill=(*B.color("white"), 255),
                         shadow=(0, 0, 0, 150), shadow_blur=10),
            max_lines=2,
        )
        t_block = ty.wrap(self.title, t_style)
        self._title = tight_lines(t_block, (W // 2, TOP - 40 if False else H - BOTTOM + 140))

        if self.body:
            b_style = ty.TextStyle(role="body", size=st.body_size, align="center",
                                   line_spacing=1.30, max_width=max_w,
                                   fill=(*accent, 240), shadow=(0, 0, 0, 130), shadow_blur=8)
            b_block = ty.wrap(self.body, b_style)
            self._body = tight_lines(b_block, (W // 2, H - BOTTOM + 140 + t_block.height + 14))

    def frame(self, t: float) -> Image.Image:
        img = self._bg.copy()
        for i, (cell, (x, y)) in enumerate(zip(self._cells, self._boxes)):
            p = mo.ease_out_cubic(mo.window(t, 0.08 * i, 0.55))
            # كل خليّة تكبر قليلًا بمرور الوقت فلا تبدو الشبكة جامدة
            z = 1.0 + 0.05 * mo.ease_in_out(mo.window(t, 0, self.duration))
            zw, zh = int(cell.width * z), int(cell.height * z)
            grown = cell.resize((zw, zh), Image.BILINEAR)
            grown = grown.crop(((zw - cell.width) // 2, (zh - cell.height) // 2,
                                (zw - cell.width) // 2 + cell.width,
                                (zh - cell.height) // 2 + cell.height))
            paste_alpha(img, grown, (x, y + int(24 * (1 - p))), p)

        a = mo.inout_alpha(t, self.duration, fade_in=0.5, fade_out=0.3)
        for layer, (x, y) in self._title:
            paste_alpha(img, layer, (x, y), a)
        for layer, (x, y) in self._body:
            paste_alpha(img, layer, (x, y), a)
        return img


@dataclass
class FlashScene(Scene):
    """قطع سريع: عدّة لقطات بأقل من نصف ثانية — يشدّ الانتباه في الافتتاح."""

    photos: tuple = ()
    kicker: str = ""
    duration: float = 2.4
    style: Style = field(default_factory=lambda: STYLES[0])

    _frames: list = field(default_factory=list, repr=False)
    _kicker: list = field(default_factory=list, repr=False)

    def prepare(self) -> None:
        st = self.style
        self._frames = [
            self.grade_fn(fx.cover(load_photo(p), (W, H)), st.grade).convert("RGBA")
            for p in self.photos
        ]
        if self.kicker:
            style = ty.TextStyle(role="display", size=72, align="center",
                                 fill=(*B.color("white"), 255), max_width=W - SIDE * 2,
                                 shadow=(0, 0, 0, 170), shadow_blur=18)
            block = ty.wrap(self.kicker, style)
            self._kicker = tight_lines(block, (W // 2, int(H * 0.46)))

    def frame(self, t: float) -> Image.Image:
        n = max(1, len(self._frames))
        per = self.duration / n
        i = min(n - 1, int(t / per))
        local = (t - i * per) / per

        # نبضة تكبير قصيرة في بداية كل قطع تعطي إحساس الضربة
        z = 1.10 - 0.10 * mo.ease_out_quint(min(1.0, local * 2.2))
        base = self._frames[i]
        zw, zh = int(W * z), int(H * z)
        img = base.resize((zw, zh), Image.BILINEAR).crop(
            ((zw - W) // 2, (zh - H) // 2, (zw - W) // 2 + W, (zh - H) // 2 + H)
        )
        img.alpha_composite(self.scrim_fn((W, H), 90, 30, 150))

        for layer, (x, y) in self._kicker:
            paste_alpha(img, layer, (x, y), mo.inout_alpha(t, self.duration, 0.35, 0.3))
        return img


@dataclass
class TextCardScene(Scene):
    """بطاقة نصّية بلا صورة — تفصل بين اللقطات وتمنح الجملة وزنًا."""

    line: str = ""
    duration: float = 2.2
    style: Style = field(default_factory=lambda: STYLES[0])

    _bg: Image.Image = field(default=None, repr=False)
    _lines: list = field(default_factory=list, repr=False)
    _rule: Image.Image = field(default=None, repr=False)

    def prepare(self) -> None:
        st = self.style
        accent = B.color(st.accent)
        self._bg = fx.brand_backdrop((W, H))

        style = ty.fit_size(
            self.line,
            ty.TextStyle(role="display", size=84, align="center", line_spacing=1.22,
                         max_width=W - SIDE * 2, fill=(*B.color("white"), 255),
                         shadow=(0, 0, 0, 130), shadow_blur=16),
            max_lines=3,
        )
        block = ty.wrap(self.line, style)
        self._lines = tight_lines(block, (W // 2, int(H * 0.44) - block.height // 2))

        rule = Image.new("RGBA", (120, 6), (0, 0, 0, 0))
        ImageDraw.Draw(rule).rounded_rectangle((0, 0, 119, 5), 3, fill=(*accent, 255))
        self._rule = rule

    def frame(self, t: float) -> Image.Image:
        img = self._bg.copy()
        for i, (layer, (x, y)) in enumerate(self._lines):
            p = mo.ease_out_quint(mo.window(t, 0.12 + i * 0.12, 0.7))
            paste_alpha(img, layer, (x, y + int(34 * (1 - p))), p)
        p = mo.ease_out_cubic(mo.window(t, 0.10, 0.55))
        grown = self._rule.crop((0, 0, max(2, int(120 * p)), 6))
        paste_alpha(img, grown, ((W - grown.width) // 2, int(H * 0.44) + 130), p)
        return img


@dataclass
class InsetScene(Scene):
    """الصورة داخل إطار بهامش العلامة لا ملء الشاشة — إحساس مطبوع أنيق."""

    photo: str = ""
    title: str = ""
    body: str = ""
    index: int = 1
    total: int = 1
    move: str = "zoom_in"
    duration: float = 3.0
    style: Style = field(default_factory=lambda: STYLES[0])

    _base: Image.Image = field(default=None, repr=False)
    _bias: float = 0.5
    _bg: Image.Image = field(default=None, repr=False)
    _box: tuple = (0, 0, 0, 0)
    _mask: Image.Image = field(default=None, repr=False)
    _title: list = field(default_factory=list, repr=False)
    _body: list = field(default_factory=list, repr=False)

    def prepare(self) -> None:
        st = self.style
        margin_x, top, height = 74, TOP + 130, int(H * 0.52)
        self._box = (margin_x, top, W - margin_x, top + height)
        bw, bh = self._box[2] - self._box[0], height

        img = load_photo(self.photo)
        self._bias = fx.smart_crop_bias(img)
        self._base = fx.cover(img, (int(bw * 1.16), int(bh * 1.16)))
        self._bg = fx.brand_backdrop((W, H))
        self._mask = fx.rounded_mask((bw, bh), st.radius or 18)

        accent = B.color(st.accent)
        max_w = W - margin_x * 2
        t_style = ty.fit_size(
            self.title,
            ty.TextStyle(role="headline", size=st.caption_title_size, align="right",
                         line_spacing=1.18, max_width=max_w, fill=(*B.color("white"), 255),
                         shadow=(0, 0, 0, 110), shadow_blur=8),
            max_lines=2,
        )
        t_block = ty.wrap(self.title, t_style)
        text_top = top + height + 54
        self._title = tight_lines(t_block, (W - margin_x, text_top))

        if self.body:
            b_style = ty.TextStyle(role="body", size=st.body_size, align="right",
                                   line_spacing=1.30, max_width=max_w,
                                   fill=(*accent, 235), shadow=(0, 0, 0, 100), shadow_blur=8)
            b_block = ty.wrap(self.body, b_style)
            self._body = tight_lines(b_block, (W - margin_x, text_top + t_block.height + 16))

    def frame(self, t: float) -> Image.Image:
        img = self._bg.copy()
        x0, y0, x1, y1 = self._box
        bw, bh = x1 - x0, y1 - y0

        p = mo.ease_in_out(mo.window(t, 0, self.duration))
        z = mo.lerp(1.16, 1.02, p) if self.move == "zoom_out" else mo.lerp(1.02, 1.16, p)
        win_w = min(self._base.width, max(bw, int(round(bw * 1.16 / z))))
        win_h = min(self._base.height, max(bh, int(round(bh * 1.16 / z))))
        left = int((self._base.width - win_w) * 0.5)
        topc = int((self._base.height - win_h) * self._bias)
        cell = self._base.crop((left, topc, left + win_w, topc + win_h)).resize((bw, bh), Image.BICUBIC)
        cell = cell.convert("RGBA")
        cell.putalpha(self._mask)

        rise = mo.ease_out_quint(mo.window(t, 0.0, 0.7))
        a = mo.inout_alpha(t, self.duration, 0.45, 0.3)
        paste_alpha(img, cell, (x0, y0 + int(30 * (1 - rise))), a)

        for i, (layer, (lx, ly)) in enumerate(self._title):
            q = mo.ease_out_cubic(mo.window(t, 0.20 + i * 0.08, 0.6))
            paste_alpha(img, layer, (lx, ly + int(16 * (1 - q))), min(a, q))
        for i, (layer, (lx, ly)) in enumerate(self._body):
            q = mo.ease_out_cubic(mo.window(t, 0.34 + i * 0.07, 0.6))
            paste_alpha(img, layer, (lx, ly + int(12 * (1 - q))), min(a, q))
        return img
