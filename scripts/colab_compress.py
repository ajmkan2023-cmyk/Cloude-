# ── الصق هذه الخلية في colab.research.google.com وشغّلها ──
from google.colab import drive
drive.mount('/content/drive')

from pathlib import Path
from PIL import Image, ImageOps

SRC = Path('/content/drive/MyDrive/TikTok Content')   # عدّل المسار إن كان مختلفًا
OUT = SRC / '_previews'
OUT.mkdir(exist_ok=True)

n = 0
for p in sorted(SRC.iterdir()):
    if p.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp', '.heic'}:
        continue
    im = ImageOps.exif_transpose(Image.open(p)).convert('RGB')
    im.thumbnail((3200, 3200), Image.LANCZOS)
    dest = OUT / (p.stem + '.jpg')
    q = 85
    while True:
        im.save(dest, 'JPEG', quality=q, optimize=True)
        kb = dest.stat().st_size // 1024
        if kb <= 3000 or q <= 55:
            break
        q -= 8
    print(f'{dest.name}  {kb} KB')
    n += 1

print(f'\nتم ضغط {n} صورة في: {OUT}')
