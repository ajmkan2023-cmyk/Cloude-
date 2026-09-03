"""منحنيات الحركة والتوقيت.

كل حركة في هذا الفيديو بطيئة ومريحة: تبدأ سريعًا قليلًا ثم تستقرّ
(‎ease-out‎)، ولا شيء يرتدّ أو يقفز. الدوالّ هنا تأخذ ‎t‎ بين ٠ و١
وتعيد قيمة بين ٠ و١.
"""

from __future__ import annotations

import math

__all__ = [
    "clamp", "linear", "ease_out_cubic", "ease_out_quint", "ease_out_expo",
    "ease_in_out_sine", "ease_in_out_cubic", "ease_in_cubic", "smoothstep",
    "seg", "fade_in_out", "breathe", "drift", "lerp",
]


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


# ── منحنيات ───────────────────────────────────────────────────────────
def linear(t: float) -> float:
    return clamp(t)


def ease_out_cubic(t: float) -> float:
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_out_quint(t: float) -> float:
    t = clamp(t)
    return 1 - (1 - t) ** 5


def ease_out_expo(t: float) -> float:
    t = clamp(t)
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def ease_in_cubic(t: float) -> float:
    return clamp(t) ** 3


def ease_in_out_sine(t: float) -> float:
    return -(math.cos(math.pi * clamp(t)) - 1) / 2


def ease_in_out_cubic(t: float) -> float:
    t = clamp(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def smoothstep(t: float) -> float:
    t = clamp(t)
    return t * t * (3 - 2 * t)


# ── توقيت ─────────────────────────────────────────────────────────────
def seg(t: float, start: float, duration: float, ease=ease_out_cubic) -> float:
    """تقدّم مقطع زمني يبدأ عند ‎start‎ ويستمرّ ‎duration‎ ثانية."""
    if duration <= 0:
        return 1.0 if t >= start else 0.0
    return ease((t - start) / duration)


def fade_in_out(t: float, total: float, fade_in: float = 0.9,
                fade_out: float = 0.9, hold_ease=ease_in_out_sine) -> float:
    """شفافية عنصر يظهر ويختفي داخل مشهد طوله ‎total‎."""
    a = hold_ease(t / fade_in) if fade_in > 0 else 1.0
    remaining = total - t
    b = hold_ease(remaining / fade_out) if fade_out > 0 else 1.0
    return clamp(min(a, b))


def breathe(t: float, period: float = 9.0, amount: float = 1.0) -> float:
    """تذبذب لطيف بين ‎-amount‎ و‎+amount‎ — للحياة الخفيفة في الخلفية."""
    return math.sin(2 * math.pi * t / period) * amount


def drift(t: float, distance: float, duration: float, start: float = 0.0,
          ease=ease_out_expo) -> float:
    """إزاحة تبدأ من ‎distance‎ وتنتهي عند صفر."""
    return distance * (1 - seg(t, start, duration, ease))
