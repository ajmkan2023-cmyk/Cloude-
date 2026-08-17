"""تنضيد النص العربي.

إذا كانت Pillow مبنية مع Raqm (وهو الوضع المعتاد) فهي تتولّى تشكيل الحروف
واتجاه النص بنفسها عبر HarfBuzz — وهذا أدقّ بكثير من التشكيل اليدوي لأنه
يستخدم جداول OpenType الحقيقية في الخط. عند غياب Raqm نرجع تلقائيًا إلى
`arabic-reshaper` + `python-bidi`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

from .config import brand

HAS_RAQM: bool = bool(features.check("raqm"))

# أوزان الخطوط المتغيّرة (variable fonts) لكل دور
_WEIGHTS = {"display": 800, "latin": 700}


def shape(text: str) -> str:
    """يعيد النص جاهزًا للرسم.

    مع Raqm يبقى النص كما هو (Pillow تشكّله)، وبدونه نشكّله يدويًا.
    """
    if not text:
        return ""
    if HAS_RAQM:
        return text
    import arabic_reshaper
    from bidi.algorithm import get_display

    return get_display(arabic_reshaper.reshape(text))


@lru_cache(maxsize=96)
def font(role: str, size: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(brand().font_path(role)), size)
    weight = _WEIGHTS.get(role)
    if weight is not None:
        try:  # خط متغيّر: نثبّت الوزن المطلوب
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


@dataclass
class TextStyle:
    role: str = "headline"
    size: int = 56
    fill: tuple = (255, 255, 255, 255)
    line_spacing: float = 1.25
    align: str = "right"              # right | center | left
    direction: str = "rtl"            # rtl | ltr
    language: str = "ar"
    shadow: tuple | None = (0, 0, 0, 150)
    shadow_offset: tuple[int, int] = (0, 4)
    shadow_blur: float = 10.0
    glow: tuple | None = None
    glow_blur: float = 26.0
    max_width: int | None = None
    tracking: int = 0                 # تباعد الحروف — للنص اللاتيني فقط

    @property
    def _draw_kwargs(self) -> dict:
        if not HAS_RAQM:
            return {}
        return {"direction": self.direction, "language": self.language}

    @property
    def _can_track(self) -> bool:
        """تباعد الحروف يكسر وصل الحروف العربية، فنسمح به للاتيني فقط."""
        return self.tracking != 0 and self.direction == "ltr"


@dataclass
class TextBlock:
    lines: list[str]
    style: TextStyle
    line_boxes: list[tuple[int, int]] = field(default_factory=list)
    width: int = 0
    height: int = 0

    @property
    def line_height(self) -> int:
        """ارتفاع السطر مقيسًا من امتداد الحروف الفعلي.

        مقاييس ascent/descent المعلنة في الخطوط العربية غير متّسقة (الكوفي
        يعلن ١٩١ بكسل لحجم ١٠٠ بينما ارتفاع الحروف الحقيقي ١٤٦)، لذلك نقيس
        الرسم نفسه. هكذا يبقى `line_spacing` معناه واحدًا مهما تغيّر الخط:
        ١٫٠ = ملاصق، ١٫٢ = مريح.
        """
        heights = [h for _, h in self.line_boxes if h]
        base = max(heights) if heights else int(self.style.size * 1.25)
        return int(base * self.style.line_spacing)


_SCRATCH = ImageDraw.Draw(Image.new("RGBA", (8, 8)))


def measure(text: str, style: TextStyle) -> tuple[int, int]:
    if not text:
        return 0, 0
    f = font(style.role, style.size)
    box = _SCRATCH.textbbox((0, 0), text, font=f, **style._draw_kwargs)
    w = box[2] - box[0]
    if style._can_track:
        w += style.tracking * max(0, len(text) - 1)
    return w, box[3] - box[1]


def wrap(text: str, style: TextStyle) -> TextBlock:
    """يلفّ النص على أسطر ضمن `max_width` مع احترام فواصل الأسطر اليدوية."""
    limit = style.max_width or 10**6
    lines: list[str] = []

    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current: list[str] = []
        for word in words:
            trial = " ".join(current + [word])
            if not current or measure(shape(trial), style)[0] <= limit:
                current.append(word)
            else:
                lines.append(" ".join(current))
                current = [word]
        lines.append(" ".join(current))

    visual = [shape(line) for line in lines]
    boxes = [measure(line, style) for line in visual]

    block = TextBlock(lines=visual, style=style, line_boxes=boxes)
    block.width = max((w for w, _ in boxes), default=0)
    block.height = block.line_height * len(visual)
    return block


def _draw_line(draw: ImageDraw.ImageDraw, xy, text: str, style: TextStyle, fill) -> None:
    f = font(style.role, style.size)
    anchor_x = {"right": "r", "center": "m", "left": "l"}[style.align]
    x, y = xy

    if not style._can_track:
        draw.text((x, y), text, font=f, fill=fill, anchor=f"{anchor_x}a", **style._draw_kwargs)
        return

    total = measure(text, style)[0]
    cursor = x - total if anchor_x == "r" else x - total / 2 if anchor_x == "m" else x
    for ch in text:
        draw.text((cursor, y), ch, font=f, fill=fill, anchor="la", **style._draw_kwargs)
        cursor += draw.textlength(ch, font=f, **style._draw_kwargs) + style.tracking


def _stamp(canvas_size, block: TextBlock, origin, fill) -> Image.Image:
    layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    ox, oy = origin
    lh = block.line_height
    for i, line in enumerate(block.lines):
        if line:
            _draw_line(draw, (ox, oy + i * lh), line, block.style, fill)
    return layer


def render_block(block: TextBlock, canvas_size: tuple[int, int], origin: tuple[int, int]) -> Image.Image:
    """يرسم كتلة نص (مع التوهّج والظل) على طبقة شفافة بحجم `canvas_size`.

    `origin` هو نقطة الارتساء الأفقية حسب المحاذاة، و`y` أعلى الكتلة.
    """
    style = block.style
    layer = _stamp(canvas_size, block, origin, style.fill)

    if style.glow:
        glow = _stamp(canvas_size, block, origin, style.glow)
        glow = glow.filter(ImageFilter.GaussianBlur(style.glow_blur))
        glow.alpha_composite(layer)
        layer = glow

    if style.shadow:
        dx, dy = style.shadow_offset
        shadow = _stamp(canvas_size, block, (origin[0] + dx, origin[1] + dy), style.shadow)
        shadow = shadow.filter(ImageFilter.GaussianBlur(style.shadow_blur))
        shadow.alpha_composite(layer)
        layer = shadow

    return layer


def fit_size(text: str, style: TextStyle, max_lines: int, min_size: int = 28) -> TextStyle:
    """يقلّص حجم الخط تدريجيًا حتى يتّسع النص في عدد الأسطر المطلوب."""
    size = style.size
    while size > min_size:
        trial = replace(style, size=size)
        if len(wrap(text, trial).lines) <= max_lines:
            return trial
        size -= 3
    return replace(style, size=min_size)
