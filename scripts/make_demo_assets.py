"""يولّد صورًا تجريبية (سماء، كثبان، بحر، نخيل) لاختبار المحرّك بلا صور حقيقية.

ليست بديلًا عن صور أجمكان — الغرض منها فحص التكوين والخطوط والحركة فقط.

    python scripts/make_demo_assets.py
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path("assets/incoming/demo")
SIZE = (1400, 2100)

PALETTES = [
    # (سماء علوية، سماء سفلية، أرض قريبة، أرض بعيدة)
    ((28, 44, 92), (240, 148, 74), (78, 48, 42), (152, 96, 66)),      # غروب صحراوي
    ((120, 190, 232), (238, 232, 206), (198, 160, 108), (222, 196, 150)),  # كثبان نهارية
    ((10, 18, 46), (44, 70, 128), (12, 22, 48), (26, 44, 84)),        # ليل ونجوم
    ((132, 205, 236), (226, 244, 250), (28, 122, 168), (86, 178, 208)),  # بحر
    ((246, 196, 120), (250, 232, 200), (140, 108, 78), (190, 156, 116)),  # ضوء ذهبي
    ((60, 120, 180), (200, 226, 240), (36, 86, 120), (74, 140, 176)),  # خليج
]


def _vertical(size, top, bottom) -> np.ndarray:
    h, w = size[1], size[0]
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    col = np.array(top, np.float32)[None, :] * (1 - t) + np.array(bottom, np.float32)[None, :] * t
    return np.repeat(col[:, None, :], w, axis=1)


def _terrain(size, horizon: float, near, far, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    w, h = size
    x = np.arange(w)
    ridge = np.zeros(w, np.float32)
    for freq, amp in ((1.7, 46), (3.3, 24), (7.1, 12), (13.0, 6)):
        ridge += np.sin(x / w * freq * 2 * math.pi + rng.uniform(0, 6.28)) * amp
    base = int(h * horizon)
    yy = np.arange(h)[:, None]
    mask = (yy >= (base + ridge)[None, :]).astype(np.float32)
    depth = np.clip((yy - base) / max(1, h - base), 0, 1)
    col = np.array(far, np.float32)[None, None, :] * (1 - depth[..., None]) + \
        np.array(near, np.float32)[None, None, :] * depth[..., None]
    return col, mask


def _palm(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float, color) -> None:
    """نخلة بسيطة كظلّ في المقدّمة."""
    trunk_h = int(340 * scale)
    draw.line([(x, y), (x - int(18 * scale), y - trunk_h)], fill=color, width=max(3, int(14 * scale)))
    top = (x - int(18 * scale), y - trunk_h)
    for angle in range(-165, -14, 30):
        rad = math.radians(angle)
        length = 150 * scale
        ex = top[0] + math.cos(rad) * length
        ey = top[1] + math.sin(rad) * length * 0.72
        draw.line([top, (ex, ey)], fill=color, width=max(2, int(9 * scale)))
        for f in (0.45, 0.7, 0.9):
            px = top[0] + (ex - top[0]) * f
            py = top[1] + (ey - top[1]) * f
            draw.line([(px, py), (px + math.cos(rad + 1.1) * 34 * scale,
                                  py + math.sin(rad + 1.1) * 30 * scale)],
                      fill=color, width=max(1, int(5 * scale)))


def make_image(index: int, path: Path) -> None:
    sky_top, sky_bottom, near, far = PALETTES[index % len(PALETTES)]
    rng = np.random.default_rng(100 + index)

    arr = _vertical(SIZE, sky_top, sky_bottom)
    horizon = 0.52 + 0.08 * math.sin(index)
    ground, mask = _terrain(SIZE, horizon, near, far, seed=index)
    arr = arr * (1 - mask[..., None]) + ground * mask[..., None]

    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    # شمس أو قمر
    glow = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    sx, sy = int(SIZE[0] * (0.28 + 0.4 * ((index * 7) % 5) / 5)), int(SIZE[1] * (horizon - 0.10))
    r = 120 if index != 2 else 54
    gd.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(255, 232, 186, 235))
    gd.ellipse((sx - r * 3, sy - r * 3, sx + r * 3, sy + r * 3), fill=(255, 200, 130, 46))
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(28)))

    if index == 2:  # نجوم
        sd = ImageDraw.Draw(img)
        for _ in range(420):
            x, y = rng.integers(0, SIZE[0]), rng.integers(0, int(SIZE[1] * horizon))
            s = rng.integers(1, 3)
            sd.ellipse((x, y, x + s, y + s), fill=(255, 255, 255, int(rng.integers(90, 255))))

    # نخيل في المقدّمة
    fg = ImageDraw.Draw(img)
    for k in range(1 + index % 3):
        _palm(fg, int(SIZE[0] * (0.12 + 0.34 * k)), int(SIZE[1] * (0.90 + 0.03 * k)),
              0.9 + 0.25 * k, (18, 26, 38, 225))

    # ضوضاء خفيفة تعطي إحساسًا فوتوغرافيًا
    noise = rng.normal(0, 6, (SIZE[1], SIZE[0], 1)).astype(np.float32)
    out = np.clip(np.asarray(img.convert("RGB"), np.float32) + noise, 0, 255).astype(np.uint8)
    final = Image.fromarray(out).filter(ImageFilter.GaussianBlur(0.4))

    path.parent.mkdir(parents=True, exist_ok=True)
    final.save(path, quality=92)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    make_image(0, OUT / "hero.jpg")
    for i in range(1, 6):
        make_image(i, OUT / f"shot{i}.jpg")
    print(f"✔ صور تجريبية في {OUT}")


if __name__ == "__main__":
    main()
