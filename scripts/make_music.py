"""واجهة سطر أوامر لتوليد موسيقى أجمكان — المحرّك في `reels/music.py`.

عادةً لا تحتاج تشغيله يدويًا: `python3 -m reels build` يولّد المقطع بطول
الريلز تلقائيًا حسب `music_mood` في الخطة.

    python scripts/make_music.py --cycle 2 --seconds 26
    python scripts/make_music.py --mood night --seconds 8 --out /tmp/x.m4a
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reels.music import MOOD_KEYS, MOODS, next_mood, write_track

OUT = Path("assets/audio/track.m4a")


def main() -> None:
    ap = argparse.ArgumentParser(description="توليد موسيقى أجمكان")
    ap.add_argument("--seconds", type=float, default=26.0)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--mood", choices=MOOD_KEYS, help="المزاج؛ يُشتقّ من الدورة إن أُهمل")
    ap.add_argument("--cycle", type=int, default=1)
    args = ap.parse_args()

    mood = args.mood or next_mood(args.cycle)
    out = write_track(args.out, args.seconds, mood)
    print(f"✔ {out}  مزاج «{MOODS[mood]['name_ar']}» ({mood})، "
          f"{out.stat().st_size // 1024} كيلوبايت، {args.seconds:.1f} ثانية")


if __name__ == "__main__":
    main()
