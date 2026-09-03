"""المشاهد ونظام التنضيد الرأسي.

`Stack` هو العمود الفقري: كل مشهد نصّيّ عبارة عن كومة عناصر (عنوان صغير،
سطر كبير، خطّ فاصل، غصن، إسناد) تُحسب مواضعها مرّة واحدة عند التحضير، ثم
تدخل عنصرًا بعد عنصر — كل واحد بتأخيره وانزلاقه الخاص. الدخول المتتابع هو
ما يفرّق بين نصّ *يتحرّك* ونصّ *يُلصَق*.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

from . import motion as M
from . import ornament as orn
from . import paint
from .config import VIDEO, color
from .typography import Style, fit, layout

# ── سلّم الخطوط ───────────────────────────────────────────────────────
# مقاسات معايَرة على مشاهدة الجوّال: السطر الرئيسي يملأ نحو ثلاثة أرباع
# عرض الإطار، لأن النصّ الأنيق الصغير يضيع على شاشة صغيرة.
KICKER = Style(role="kufi", size=52, line_spacing=1.5, pad=44)
VERSE = Style(role="naskh", size=108, line_spacing=1.58, pad=72)
LEAD = Style(role="naskh_bold", size=126, line_spacing=1.50, pad=80)
BODY = Style(role="naskh", size=86, line_spacing=1.64, pad=60)
NOTE = Style(role="kufi", size=38, line_spacing=1.5, pad=40)
NAME = Style(role="ruqaa_bold", size=600, line_spacing=1.1, pad=150)
CLOSING = Style(role="ruqaa_bold", size=230, line_spacing=1.2, pad=90)
SUBNAME = Style(role="naskh", size=92, line_spacing=1.4, pad=64)
LATIN = Style(role="latin", size=60, direction="ltr", language="en",
              tracking=22, line_spacing=1.4, pad=48)


# ── عنصر مرسوم داخل الكومة ────────────────────────────────────────────
@dataclass
class Piece:
    layer: Image.Image      # RGBA جاهزة للتركيب
    dx: int                 # نسبةً إلى مركز الكومة أفقيًا
    dy: int                 # نسبةً إلى أعلى الكومة
    delay: float = 0.0
    rise: float = 26.0
    grow: float = 1.0       # مدّة الدخول


def _ink(mask: Image.Image, fill, *, gold: bool = False, glow_fill=None,
         glow_blur: float = 26.0, glow_gain: float = 1.0,
         shade: bool = True) -> Image.Image:
    """يحوّل قناع نص إلى طبقة نهائية: ظلّ + توهّج + حبر (ذهبي أو صلب)."""
    out = paint.blank(mask.size)
    if shade:
        paint.stamp(out, paint.shadow(mask, 9.0, (74, 52, 44, 46)), (0, 5))
    if glow_fill is not None:
        paint.stamp(out, paint.glow(mask, glow_blur, glow_fill, glow_gain))
    if gold:
        sheet = paint.gold_sheet(mask.size, 92)
        paint.stamp(out, paint.tint_sheet(mask, sheet, (0, 0)))
    else:
        paint.stamp(out, paint.tint(mask, fill))
    return out


class Stack:
    """كومة عناصر متمركزة أفقيًا، تُبنى مرّة وتُرسم كثيرًا."""

    def __init__(self, width: int):
        self.width = width
        self.pieces: list[Piece] = []
        self._cursor = 0
        self._delay = 0.0

    # -- بناء -----------------------------------------------------------
    def gap(self, height: int) -> "Stack":
        self._cursor += height
        return self

    def text(self, text: str, style: Style, fill=None, *, gold: bool = False,
             delay: float | None = None, stagger: float = 0.16,
             rise: float = 26.0, grow: float = 1.15, max_lines: int = 4,
             glow_fill=None, glow_blur: float = 26.0, glow_gain: float = 1.0,
             shade: bool = True, width: int | None = None) -> "Stack":
        if not text:
            return self
        style = fit(text, style.__class__(**{**style.__dict__,
                                             "max_width": width or self.width}),
                    max_lines=max_lines)
        block = layout(text, style)
        base_delay = self._delay if delay is None else delay
        for i, line in enumerate(block.lines):
            self.pieces.append(Piece(
                layer=_ink(line.mask, fill or color("ink"), gold=gold,
                           glow_fill=glow_fill, glow_blur=glow_blur,
                           glow_gain=glow_gain, shade=shade),
                dx=line.dx, dy=self._cursor + line.dy,
                delay=base_delay + i * stagger, rise=rise, grow=grow,
            ))
        self._cursor += block.height
        self._delay = base_delay + max(0, len(block.lines) - 1) * stagger + 0.34
        return self

    def rule(self, width: int = 420, *, fill=None, thickness: int = 2,
             diamond: int = 8, delay: float | None = None, grow: float = 1.4,
             pips: bool = True) -> "Stack":
        mask = orn.rule(width, thickness, diamond, pips=pips)
        layer = paint.tint(mask, fill or color("gold", 220))
        self.pieces.append(Piece(layer=layer, dx=-mask.width // 2, dy=self._cursor,
                                 delay=self._delay if delay is None else delay,
                                 rise=0.0, grow=grow))
        self._cursor += mask.height
        self._delay = (self._delay if delay is None else delay) + 0.22
        return self

    def sprig(self, width: int = 300, *, fill=None, delay: float | None = None) -> "Stack":
        mask = orn.sprig(width, 2)
        layer = paint.tint(mask, fill or color("gold", 190))
        self.pieces.append(Piece(layer=layer, dx=-mask.width // 2, dy=self._cursor,
                                 delay=self._delay if delay is None else delay,
                                 rise=10.0, grow=1.3))
        self._cursor += mask.height
        self._delay = (self._delay if delay is None else delay) + 0.24
        return self

    def image(self, layer: Image.Image, *, delay: float | None = None,
              rise: float = 20.0, grow: float = 1.3) -> "Stack":
        self.pieces.append(Piece(layer=layer, dx=-layer.width // 2, dy=self._cursor,
                                 delay=self._delay if delay is None else delay,
                                 rise=rise, grow=grow))
        self._cursor += layer.height
        self._delay = (self._delay if delay is None else delay) + 0.26
        return self

    # -- قياس ورسم -------------------------------------------------------
    @property
    def height(self) -> int:
        return self._cursor

    @property
    def settle(self) -> float:
        """اللحظة التي يستقرّ عندها آخر عنصر."""
        return max((p.delay + p.grow for p in self.pieces), default=0.0)

    def draw(self, base: Image.Image, t: float, center: tuple[int, int],
             opacity: float = 1.0) -> Image.Image:
        if opacity <= 0.01:
            return base
        cx, top = center[0], center[1] - self.height // 2
        for p in self.pieces:
            local = t - p.delay
            if local <= 0:
                continue
            a = M.ease_out_cubic(local / p.grow)
            dy = p.rise * (1 - M.ease_out_expo(local / p.grow))
            paint.stamp(base, p.layer, (cx + p.dx, top + p.dy + dy), opacity * a)
        return base


# ── قاعدة المشهد ──────────────────────────────────────────────────────
class Scene:
    duration: float = 6.0
    name: str = "scene"

    def prepare(self) -> None:  # pragma: no cover - يُعاد تعريفه
        pass

    def draw(self, base: Image.Image, t: float) -> Image.Image:
        raise NotImplementedError


@dataclass
class Panel(Scene):
    """مشهد نصّيّ عام: كومة متمركزة في الإطار."""
    build: object                       # دالّة تستقبل Stack وتملؤه
    duration: float = 6.0
    name: str = "panel"
    anchor: float = 0.5                 # موضع مركز الكومة من الارتفاع
    exit_lift: float = 18.0             # انزلاق لطيف عند الخروج
    stack: Stack = field(init=False, default=None)

    def prepare(self) -> None:
        self.stack = Stack(VIDEO.content_width)
        self.build(self.stack)

    def draw(self, base: Image.Image, t: float) -> Image.Image:
        cy = int(VIDEO.height * self.anchor)
        tail = M.clamp((t - (self.duration - 1.0)) / 1.0)
        lift = -self.exit_lift * M.ease_in_out_sine(tail)
        self.stack.draw(base, t, (VIDEO.width // 2, int(cy + lift)))
        return base


# ── مشهد كشف الاسم ────────────────────────────────────────────────────
class NameReveal(Scene):
    """ذروة الفيديو: الإكليل يُرسم، والاسم يظهر ويمرّ عليه بريق ذهبي."""

    name = "name"

    def __init__(self, name_text: str, kicker: str = "", subtitle: str = "",
                 latin: str = "", duration: float = 10.0):
        self.name_text = name_text
        self.kicker = kicker
        self.subtitle = subtitle
        self.latin = latin
        self.duration = duration

    def prepare(self) -> None:
        style = fit(self.name_text, Style(**{**NAME.__dict__,
                                             "max_width": VIDEO.content_width}), max_lines=1)
        block = layout(self.name_text, style)
        line = block.lines[0]
        self.mask = line.mask
        self.name_layer = _ink(self.mask, color("ink"), gold=True,
                               glow_fill=color("gold_light", 120), glow_blur=42,
                               glow_gain=1.15)
        self.name_dx = line.dx
        self.name_h = block.height

        # صفيحة البريق: شريط مضيء يُمرَّر أفقيًا عبر القناع
        w, h = self.mask.size
        self.sweep_sheet = paint.gradient(
            (w * 2, h),
            [(0.00, color("gold_light", 0)), (0.44, color("gold_light", 0)),
             (0.50, (255, 250, 236, 235)), (0.56, color("gold_light", 0)),
             (1.00, color("gold_light", 0))], angle=0)

        diameter = min(int(VIDEO.width * 0.86), int(VIDEO.height * 0.46))
        self.wreath_mask = orn.wreath(diameter, 3, 11)
        self.wreath_layer = paint.tint(self.wreath_mask, color("gold", 165))
        self.diameter = diameter

        self.above = Stack(VIDEO.content_width)
        if self.kicker:
            self.above.text(self.kicker, KICKER, color("gold_deep", 230), delay=0.15)

        self.below = Stack(VIDEO.content_width)
        if self.subtitle:
            self.below.rule(420, delay=2.5, thickness=2, diamond=8)
            self.below.gap(38)
            self.below.text(self.subtitle, SUBNAME, color("ink_soft"), delay=2.95,
                            max_lines=1)
        if self.latin:
            self.below.gap(40)
            self.below.text(self.latin, LATIN, color("ink_faint"), delay=3.4,
                            max_lines=1, shade=False)

    def draw(self, base: Image.Image, t: float) -> Image.Image:
        cx, cy = VIDEO.width // 2, int(VIDEO.height * 0.5)

        # الإكليل يُرسم من الأعلى نزولًا
        grow = M.seg(t, 0.35, 2.4, M.ease_out_cubic)
        if grow > 0.01:
            revealed = orn.reveal_sweep(self.wreath_mask, grow, softness=110, direction="down")
            paint.stamp_mask(base, revealed, color("gold", 165),
                             (cx - self.diameter // 2, cy - self.diameter // 2))

        # الاسم: يظهر مع اتّساع طفيف
        appear = M.seg(t, 0.95, 1.5, M.ease_out_quint)
        if appear > 0.01:
            mw, mh = self.mask.size
            x = cx + self.name_dx
            y = cy - self.name_h // 2 - (mh - self.name_h) // 2
            rise = 22 * (1 - appear)
            paint.stamp(base, self.name_layer, (x, y + rise), appear)

            # بريق يمرّ مرّة واحدة بعد استقرار الاسم
            sweep = M.seg(t, 2.15, 1.5, M.ease_in_out_sine)
            if 0.01 < sweep < 0.995:
                offset = int((mw * 2 - mw) * sweep)
                band = self.sweep_sheet.crop((mw - offset, 0, 2 * mw - offset, mh))
                shine = band.copy()
                shine.putalpha(ImageChops.multiply(shine.getchannel("A"), self.mask))
                paint.stamp(base, shine, (x, y + rise), 0.9)

        self.above.draw(base, t, (cx, cy - self.diameter // 2 - 86))
        self.below.draw(base, t, (cx, cy + self.diameter // 2 + 96))
        return base


# ── مشهد الصورة ───────────────────────────────────────────────────────
class PhotoPanel(Scene):
    """صورة داخل قوس مذهّب، بحركة تقريب بطيئة وتعليق تحتها."""

    name = "photo"

    def __init__(self, path: str | Path, caption: str = "", duration: float = 7.0,
                 zoom: float = 0.10, drift: tuple[float, float] = (0.0, -0.02)):
        self.path = Path(path)
        self.caption = caption
        self.duration = duration
        self.zoom = zoom
        self.drift = drift

    def prepare(self) -> None:
        w = int(VIDEO.width * 0.74)
        h = int(w * 1.24)
        self.box = (w, h)
        self.pos = ((VIDEO.width - w) // 2, int(VIDEO.height * 0.40) - h // 2)

        self.arch = orn.arch_mask((w, h), 0.5, 1.6)
        inner = orn.arch_mask((w - 14, h - 14), 0.5, 1.2)
        outline = self.arch.copy()
        hole = Image.new("L", (w, h), 0)
        hole.paste(inner, (7, 7))
        self.outline = ImageChops.subtract(outline, hole)

        over = 1.0 + self.zoom
        src = Image.open(self.path).convert("RGB")
        tw, th = int(w * over), int(h * over)
        ratio = max(tw / src.width, th / src.height)
        src = src.resize((max(1, int(src.width * ratio)), max(1, int(src.height * ratio))),
                         Image.LANCZOS)
        left = (src.width - tw) // 2
        top = (src.height - th) // 2
        self.plate = src.crop((left, top, left + tw, top + th)).convert("RGBA")

        self.shadow = paint.tint(self.arch.filter(ImageFilter.GaussianBlur(26)),
                                 (86, 60, 50, 92))

        self.cap = Stack(int(VIDEO.width * 0.78))
        if self.caption:
            self.cap.rule(300, delay=1.5, thickness=2, diamond=7)
            self.cap.gap(26)
            self.cap.text(self.caption, BODY, color("ink_soft"), delay=1.85, max_lines=2)

    def draw(self, base: Image.Image, t: float) -> Image.Image:
        w, h = self.box
        appear = M.seg(t, 0.2, 1.6, M.ease_out_quint)
        if appear > 0.01:
            k = M.ease_in_out_sine(M.clamp(t / max(0.1, self.duration)))
            scale = 1.0 + self.zoom * (1 - k)
            cw, ch = int(w * scale), int(h * scale)
            px = (self.plate.width - cw) // 2 + int(self.drift[0] * w * k)
            py = (self.plate.height - ch) // 2 + int(self.drift[1] * h * k)
            px = max(0, min(self.plate.width - cw, px))
            py = max(0, min(self.plate.height - ch, py))
            view = self.plate.crop((px, py, px + cw, py + ch)).resize((w, h), Image.LANCZOS)
            view.putalpha(self.arch)

            rise = int(24 * (1 - appear))
            x, y = self.pos[0], self.pos[1] + rise
            paint.stamp(base, self.shadow, (x, y + 18), appear * 0.9)
            paint.stamp(base, view, (x, y), appear)
            paint.stamp_mask(base, self.outline, color("gold", 210), (x, y), appear)

        self.cap.draw(base, t, (VIDEO.width // 2,
                                self.pos[1] + h + 40 + self.cap.height // 2))
        return base
