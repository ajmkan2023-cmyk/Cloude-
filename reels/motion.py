"""دوال التنعيم والحركة — كل حركة في الريلز تمرّ من هنا."""

from __future__ import annotations

import math


def clamp01(t: float) -> float:
    return 0.0 if t < 0 else 1.0 if t > 1 else t


def linear(t: float) -> float:
    return clamp01(t)


def ease_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 1 - (1 - t) ** 3


def ease_out_quint(t: float) -> float:
    t = clamp01(t)
    return 1 - (1 - t) ** 5


def ease_in_out(t: float) -> float:
    t = clamp01(t)
    return 3 * t * t - 2 * t * t * t


def ease_out_back(t: float, overshoot: float = 1.25) -> float:
    t = clamp01(t)
    c3 = overshoot + 1
    return 1 + c3 * (t - 1) ** 3 + overshoot * (t - 1) ** 2


def breathe(t: float, period: float = 6.0, amount: float = 1.0) -> float:
    """تذبذب لطيف حول الصفر — يُستخدم للتوهجات والحركات الحيّة."""
    return math.sin(2 * math.pi * t / period) * amount


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def window(t: float, start: float, duration: float) -> float:
    """يحوّل الزمن المطلق إلى تقدّم 0..1 داخل نافذة زمنية."""
    if duration <= 0:
        return 1.0
    return clamp01((t - start) / duration)


def inout_alpha(t: float, duration: float, fade_in: float = 0.5, fade_out: float = 0.4) -> float:
    """شفافية تدخل وتخرج: تظهر في البداية وتختفي قرب نهاية المشهد."""
    a = ease_out_cubic(window(t, 0.0, fade_in))
    b = 1.0 - ease_out_cubic(window(t, duration - fade_out, fade_out))
    return min(a, b)
