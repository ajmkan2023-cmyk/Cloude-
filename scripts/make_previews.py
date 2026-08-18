"""يولّد نسخًا مصغّرة من صور درايف ليستطيع كلود *رؤيتها* عند الفهرسة.

لماذا: أدوات درايف لا تصف الصور، والأصل (٤–١٠ ميجابايت) أكبر من أن يُنقل
إلى الجلسة. النسخة المصغّرة (~١٠٠ كيلوبايت) تُنقل بيسر، فيرى كلود الصورة
فعلًا ويفهرس محتواها بدل تخمينه.

يُشغَّل مرّة واحدة عند إضافة صور جديدة — من Colab مع درايف مركّب:

    !python scripts/make_previews.py --drive "/content/drive/MyDrive/TikTok Content"

أو محلّيًا على مجلّد ثم ارفع الناتج إلى درايف داخل مجلّد باسم `_previews`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageOps

MEDIA = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
LONG_EDGE = 3200      # يكفي للريلز العمودي 1080×1920 دون نعومة
QUALITY = 85
TARGET_KB = 3000      # حدّ ناقل درايف ~٥ ميجابايت


def make_preview(src: Path, dest: Path) -> int:
    img = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    img.thumbnail((LONG_EDGE, LONG_EDGE), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)

    quality = QUALITY
    while True:
        img.save(dest, "JPEG", quality=quality, optimize=True)
        size_kb = dest.stat().st_size // 1024
        if size_kb <= TARGET_KB or quality <= 55:
            return size_kb
        quality -= 8


def main() -> None:
    ap = argparse.ArgumentParser(description="توليد نسخ مصغّرة للفهرسة")
    ap.add_argument("--drive", required=True, help="مجلّد الصور (الأصول)")
    ap.add_argument("--out", default="", help="مجلّد الناتج (افتراضيًا _previews داخله)")
    args = ap.parse_args()

    src_dir = Path(args.drive).expanduser()
    if not src_dir.is_dir():
        raise SystemExit(f"✖ ليس مجلّدًا: {src_dir}")
    out_dir = Path(args.out).expanduser() if args.out else src_dir / "_previews"

    made = skipped = 0
    for path in sorted(src_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in MEDIA:
            continue
        dest = out_dir / (path.stem + ".jpg")
        if dest.exists() and dest.stat().st_mtime >= path.stat().st_mtime:
            skipped += 1
            continue
        size_kb = make_preview(path, dest)
        print(f"  ✓ {path.name} → {dest.name} ({size_kb} كيلوبايت)")
        made += 1

    print(f"\n✔ {made} نسخة جديدة، {skipped} موجودة مسبقًا")
    print(f"   المجلّد: {out_dir}")
    print("   ارفعه إلى درايف باسم «_previews» داخل مجلّد TikTok Content.")


if __name__ == "__main__":
    main()
