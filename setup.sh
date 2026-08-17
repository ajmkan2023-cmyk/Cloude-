#!/usr/bin/env bash
# تجهيز البيئة لتشغيل محرّك أجمكان — يعمل على أي جهاز أو Colab أو جلسة جديدة.
set -euo pipefail

echo "▸ تثبيت مكتبات بايثون…"
pip install --quiet --upgrade -r requirements.txt

echo "▸ التأكد من ffmpeg…"
python3 - <<'PY'
import imageio_ffmpeg
print("  ffmpeg:", imageio_ffmpeg.get_ffmpeg_exe())
PY

echo "▸ التأكد من دعم النص العربي في Pillow…"
python3 - <<'PY'
from PIL import features
if features.check("raqm"):
    print("  Raqm متوفّر — تشكيل عربي كامل عبر HarfBuzz")
else:
    print("  تنبيه: Raqm غير متوفّر — سيُستخدم التشكيل الاحتياطي")
PY

echo "▸ التأكد من الخطوط…"
python3 - <<'PY'
from pathlib import Path
missing = [f.name for f in [
    Path("brand/fonts/NotoKufiArabic-var.ttf"),
    Path("brand/fonts/Almarai-ExtraBold.ttf"),
    Path("brand/fonts/Tajawal-Medium.ttf"),
    Path("brand/fonts/Tajawal-ExtraBold.ttf"),
    Path("brand/fonts/Cairo-var.ttf"),
] if not f.exists()]
print("  ناقص:", ", ".join(missing) if missing else "لا شيء — كل الخطوط موجودة")
PY

if [ ! -f brand/logo/ajmkan_mark.png ]; then
  echo "▸ تحضير الشعار…"
  python3 scripts/prepare_logo.py
fi

echo "✔ جاهز.  جرّب:  python3 -m reels demo"
