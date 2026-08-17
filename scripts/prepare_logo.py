"""يحضّر علامة أجمكان (النخيل + الشمس + الموجة) كملف PNG شفاف عالي الدقة.

المصدر `brand/logo/ajmkan_logo_src.png` نسخة صغيرة وبها تلف في الجزء السفلي
(كلمة "أجمكان")، لذلك نقتطع الرمز فقط ونكتب الاسم لاحقًا بخط عربي حقيقي.

    python scripts/prepare_logo.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFile, ImageFilter

ImageFile.LOAD_TRUNCATED_IMAGES = True

SRC = Path("brand/logo/ajmkan_logo_src.png")
DST = Path("brand/logo/ajmkan_mark.png")

# الجزء السليم من الصورة المصدر (الرمز بدون الكلمة التالفة)
MARK_BOTTOM_RATIO = 0.79
UPSCALE = 5
WHITE_CUTOFF = 232


def main() -> None:
    src = Image.open(SRC).convert("RGBA")
    mark = src.crop((0, 0, src.width, int(src.height * MARK_BOTTOM_RATIO)))

    # تفريغ الخلفية البيضاء إلى شفافة مع تدرّج ناعم على الحواف
    px = mark.load()
    for y in range(mark.height):
        for x in range(mark.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            lightness = (r + g + b) / 3
            if lightness >= 250:
                px[x, y] = (r, g, b, 0)
            elif lightness > WHITE_CUTOFF:
                fade = (250 - lightness) / (250 - WHITE_CUTOFF)
                px[x, y] = (r, g, b, int(a * fade))

    mark = mark.crop(mark.getbbox())
    mark = mark.resize(
        (mark.width * UPSCALE, mark.height * UPSCALE), Image.LANCZOS
    )
    # تنعيم درجات التكبير ثم استرجاع الحدّة
    mark = mark.filter(ImageFilter.GaussianBlur(1.1))
    mark = mark.filter(ImageFilter.UnsharpMask(radius=3, percent=140, threshold=2))

    DST.parent.mkdir(parents=True, exist_ok=True)
    mark.save(DST)
    print(f"تم: {DST}  {mark.size}")


if __name__ == "__main__":
    main()
