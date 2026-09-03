"""الجوّ: هالات ضوئية غير محدّدة المعالم وذرّات مِسك تسبح ببطء.

الفكرة أن الإطار لا يسكن أبدًا حتى وهو صامت — شيء لطيف يطفو دائمًا في
الخلفية. الأداء محفوظ لأن كل جسيم صورة صغيرة مُعدّة مسبقًا؛ الإطار لا
يرسم شيئًا، إنما يلصق سبرايتات في مواضع محسوبة.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from PIL import Image

from .config import PALETTE
from .paint import radial, stamp


@lru_cache(maxsize=64)
def _orb(diameter: int, rgb: tuple[int, int, int], core: int, edge: int = 0,
         ring: float = 0.0) -> Image.Image:
    """قرص ضوئي ناعم، مع إمكان إبراز حافّته كبوكيه عدسة."""
    img = radial((diameter, diameter), (diameter / 2, diameter / 2), diameter / 2,
                 (*rgb, core), (*rgb, edge), falloff=1.9 if ring < 0.01 else 3.2)
    if ring > 0.01:
        halo = radial((diameter, diameter), (diameter / 2, diameter / 2), diameter / 2,
                      (*rgb, 0), (*rgb, int(core * ring)), falloff=7.0)
        arr = np.asarray(halo).copy()
        d = np.linalg.norm(
            np.stack(np.meshgrid(np.arange(diameter) - diameter / 2,
                                 np.arange(diameter) - diameter / 2), -1), axis=-1)
        arr[..., 3] = np.where(d > diameter / 2, 0, arr[..., 3])
        img.alpha_composite(Image.fromarray(arr, "RGBA"))
    return img


@dataclass(frozen=True)
class Particle:
    x: float          # ٠..١ من العرض
    y: float          # ٠..١ من الارتفاع، تتناقص مع الزمن
    diameter: int
    rgb: tuple[int, int, int]
    alpha: int
    speed: float      # جزء من الارتفاع في الثانية
    sway: float       # سعة التمايل الأفقي بالبكسل
    period: float
    phase: float
    ring: float


def _field(size: tuple[int, int], count: int, seed: int, kind: str) -> list[Particle]:
    rng = np.random.default_rng(seed)
    w, h = size
    out: list[Particle] = []
    for _ in range(count):
        if kind == "bokeh":
            diameter = int(rng.integers(int(w * 0.06), int(w * 0.26)))
            rgb = PALETTE[str(rng.choice(["gold_light", "rose", "paper_cool", "gold"]))]
            alpha = int(rng.integers(14, 40))
            speed = float(rng.uniform(0.006, 0.018))
            sway = float(rng.uniform(10, 34))
            ring = float(rng.uniform(0.0, 0.5))
        else:                                   # ذرّات
            diameter = int(rng.integers(6, 20))
            rgb = PALETTE[str(rng.choice(["gold_light", "paper_cool", "gold"]))]
            alpha = int(rng.integers(90, 190))
            speed = float(rng.uniform(0.012, 0.040))
            sway = float(rng.uniform(14, 46))
            ring = 0.0
        out.append(Particle(
            x=float(rng.uniform(-0.06, 1.06)),
            y=float(rng.uniform(-0.12, 1.12)),
            diameter=diameter, rgb=rgb, alpha=alpha, speed=speed, sway=sway,
            period=float(rng.uniform(5.0, 13.0)),
            phase=float(rng.uniform(0, math.tau)),
            ring=ring,
        ))
    return out


class Atmosphere:
    """طبقة الجسيمات فوق الخلفية: هالات كبيرة + ذرّات صغيرة."""

    def __init__(self, size: tuple[int, int], bokeh: int = 13, motes: int = 46,
                 seed: int = 2024):
        self.size = size
        self.particles = (_field(size, bokeh, seed, "bokeh")
                          + _field(size, motes, seed + 1, "motes"))

    def draw(self, base: Image.Image, t: float, opacity: float = 1.0) -> Image.Image:
        if opacity <= 0.01:
            return base
        w, h = self.size
        for p in self.particles:
            y = (p.y - p.speed * t) % 1.24 - 0.12
            x = p.x + p.sway * math.sin(math.tau * t / p.period + p.phase) / w
            pulse = 0.72 + 0.28 * math.sin(math.tau * t / (p.period * 0.7) + p.phase * 1.7)
            sprite = _orb(p.diameter, p.rgb, p.alpha, 0, p.ring)
            stamp(base, sprite,
                  (x * w - p.diameter / 2, y * h - p.diameter / 2),
                  opacity * pulse)
        return base
