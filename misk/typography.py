"""التنضيد العربي: تشكيل الحروف، لفّ الأسطر، وإخراج كل سطر كطبقة مستقلة.

كل سطر يخرج **مقصوصًا على حدوده الفعلية** مع هامش للتوهّج، ومعه موضعه
النسبي داخل الكتلة. هذا يسمح بدخول الأسطر متتابعةً (سطر بعد سطر) بدل
ظهور الكتلة دفعةً واحدة — وهو الفرق بين نصّ يتحرّك ونصّ «يُلصَق».

Pillow هنا مبنيّة مع Raqm، فالتشكيل والاتجاه يمرّان عبر HarfBuzz وجداول
OpenType الحقيقية. عند غيابها نرجع إلى ‎arabic-reshaper + python-bidi‎.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont, features

from .config import font_path

HAS_RAQM: bool = bool(features.check("raqm"))


def shape(text: str) -> str:
    """يعيد النص جاهزًا للرسم (مع Raqm يبقى كما هو)."""
    if not text:
        return ""
    if HAS_RAQM:
        return text
    import arabic_reshaper
    from bidi.algorithm import get_display
    return get_display(arabic_reshaper.reshape(text))


@lru_cache(maxsize=128)
def font(role: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path(role)), size)


@dataclass(frozen=True)
class Style:
    """وصف كامل لمظهر النص. غيّر منه بـ ‎dataclasses.replace‎."""
    role: str = "naskh"
    size: int = 56
    align: str = "center"          # right | center | left
    direction: str = "rtl"         # rtl | ltr
    language: str = "ar"
    line_spacing: float = 1.42
    tracking: int = 0              # تباعد الحروف — لاتيني فقط (يكسر الوصل العربي)
    max_width: int | None = None
    pad: int = 48                  # هامش حول كل سطر ليتّسع التوهّج والظل

    @property
    def draw_kwargs(self) -> dict:
        return {"direction": self.direction, "language": self.language} if HAS_RAQM else {}

    @property
    def can_track(self) -> bool:
        return self.tracking != 0 and self.direction == "ltr"


@dataclass
class Line:
    """سطر واحد مرسومًا كقناع رمادي مقصوص على حدوده."""
    text: str
    mask: Image.Image              # وضع "L" — ٢٥٥ حيث الحبر
    dx: int                        # موضع يسار القناع نسبةً إلى نقطة ارتساء الكتلة
    dy: int                        # موضع أعلى القناع نسبةً إلى أعلى الكتلة
    pad: int

    @property
    def size(self) -> tuple[int, int]:
        return self.mask.size


@dataclass
class Block:
    lines: list[Line] = field(default_factory=list)
    style: Style = field(default_factory=Style)
    width: int = 0                 # عرض أوسع سطر (بلا الهامش)
    height: int = 0                # من أعلى أوّل سطر إلى أسفل آخر سطر
    line_height: int = 0

    def __bool__(self) -> bool:
        return bool(self.lines)


_SCRATCH = ImageDraw.Draw(Image.new("L", (8, 8)))


def measure(text: str, style: Style) -> tuple[int, int]:
    if not text:
        return 0, 0
    f = font(style.role, style.size)
    box = _SCRATCH.textbbox((0, 0), text, font=f, **style.draw_kwargs)
    w = box[2] - box[0]
    if style.can_track:
        w += style.tracking * max(0, len(text) - 1)
    return w, box[3] - box[1]


def _draw_line(draw: ImageDraw.ImageDraw, xy, text: str, style: Style) -> None:
    """يرسم سطرًا بحبر أبيض كامل على قناع. ‎xy‎ عند خطّ الصاعد (anchor 'a')."""
    f = font(style.role, style.size)
    anchor_x = {"right": "r", "center": "m", "left": "l"}[style.align]
    x, y = xy

    if not style.can_track:
        draw.text((x, y), text, font=f, fill=255, anchor=f"{anchor_x}a", **style.draw_kwargs)
        return

    total = measure(text, style)[0]
    cursor = {"r": x - total, "m": x - total / 2, "l": x}[anchor_x]
    for ch in text:
        draw.text((cursor, y), ch, font=f, fill=255, anchor="la", **style.draw_kwargs)
        cursor += draw.textlength(ch, font=f, **style.draw_kwargs) + style.tracking


def _split(text: str, style: Style) -> list[str]:
    """يلفّ النص ضمن ‎max_width‎ مع احترام فواصل الأسطر اليدوية."""
    limit = style.max_width or 10 ** 7
    out: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            out.append("")
            continue
        current: list[str] = []
        for word in words:
            trial = " ".join(current + [word])
            if not current or measure(shape(trial), style)[0] <= limit:
                current.append(word)
            else:
                out.append(" ".join(current))
                current = [word]
        out.append(" ".join(current))
    return out


def layout(text: str, style: Style) -> Block:
    """يبني كتلة نص: كل سطر قناعٌ مقصوص وموضعٌ نسبي.

    نقطة الارتساء الأفقية (‎dx = 0‎) تتبع المحاذاة: يمين الكتلة عند
    ‎align="right"‎، ومنتصفها عند ‎"center"‎. عموديًا ‎dy = 0‎ هو أعلى
    حبر أوّل سطر.
    """
    raw = _split(text, style)
    visual = [shape(line) for line in raw]
    sizes = [measure(line, style) for line in visual]

    ink_heights = [h for _, h in sizes if h]
    base = max(ink_heights) if ink_heights else int(style.size * 1.2)
    line_height = int(round(base * style.line_spacing))

    pad = style.pad
    span_w = max((w for w, _ in sizes), default=0)
    # لوح مؤقّت واسع بما يكفي لأطول سطر مهما امتدّت الحركات والمدود
    plate_w = span_w + 4 * pad + style.size * 2
    plate_h = line_height + 4 * pad + style.size * 2
    anchor_x = {"right": plate_w - pad * 2, "center": plate_w // 2, "left": pad * 2}[style.align]
    anchor_y = pad * 2

    lines: list[Line] = []
    top_offsets: list[int] = []
    for i, visual_line in enumerate(visual):
        if not visual_line:
            continue
        plate = Image.new("L", (plate_w, plate_h), 0)
        _draw_line(ImageDraw.Draw(plate), (anchor_x, anchor_y), visual_line, style)
        box = plate.getbbox()
        if box is None:
            continue
        x0, y0, x1, y1 = box
        crop = (max(0, x0 - pad), max(0, y0 - pad),
                min(plate_w, x1 + pad), min(plate_h, y1 + pad))
        mask = plate.crop(crop)
        lines.append(Line(
            text=visual_line,
            mask=mask,
            dx=crop[0] - anchor_x,
            dy=crop[1] - anchor_y + i * line_height,
            pad=pad,
        ))
        top_offsets.append(y0 - anchor_y + i * line_height)

    block = Block(lines=lines, style=style, line_height=line_height)
    if lines:
        # نُعيد الضبط بحيث ‎dy = 0‎ عند أعلى حبر في الكتلة كلّها
        shift = min(top_offsets)
        for line in lines:
            line.dy -= shift
        # ‎dy‎ يقيس أعلى *القناع* (وفيه الهامش)، فحدّ الحبر السفلي
        # هو ‎dy + ارتفاع القناع − هامش واحد‎ لا هامشين.
        block.width = max(line.size[0] - 2 * pad for line in lines)
        block.height = max(line.dy + line.size[1] - pad for line in lines)
    return block


def fit(text: str, style: Style, max_lines: int = 3, min_size: int = 24,
        step: int = 4) -> Style:
    """يصغّر حجم الخط حتى يتّسع النصّ عددًا للأسطر **وعرضًا**.

    شرط العرض ليس زائدًا: كلمة واحدة طويلة (اسم مثلًا) لا يمكن لفّها،
    فتتجاوز الحدّ مهما كبرت ولا يوقفها شرط عدد الأسطر وحده.
    """
    limit = style.max_width or 10 ** 7
    size = style.size
    while size > min_size:
        trial = replace(style, size=size)
        lines = _split(text, trial)
        widest = max((measure(shape(line), trial)[0] for line in lines), default=0)
        if len(lines) <= max_lines and widest <= limit:
            return trial
        size -= step
    return replace(style, size=min_size)
