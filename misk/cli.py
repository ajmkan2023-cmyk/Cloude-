"""واجهة الأوامر: عرض المواقيت، لقطات مراجعة، وإخراج الفيديو."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import story
from .config import PRESETS, VIDEO, use_preset
from .render import contact_sheet, poster, render


def _plan(args) -> dict:
    return story.load(args.plan)


def cmd_outline(args) -> int:
    print(story.outline(_plan(args)))
    return 0


def cmd_shots(args) -> int:
    plan = _plan(args)
    tl = story.build_timeline(plan)
    if args.at:
        times = args.at
    else:  # منتصف كل مشهد — لقطة تمثّله بعد استقرار عناصره
        tl.prepare()
        times = [round(c.start + min(c.duration - 0.6, c.fade_in + 2.6), 2) for c in tl.cues]
    print(f"لقطات مراجعة ← {args.out}")
    contact_sheet(tl, args.out, times)
    return 0


def cmd_poster(args) -> int:
    tl = story.build_timeline(_plan(args))
    poster(tl, args.out, args.at)
    return 0


def cmd_build(args) -> int:
    plan = _plan(args)
    tl = story.build_timeline(plan)
    print(story.outline(plan), end="\n\n")
    out = Path(args.out)
    render(tl, out, crf=args.crf, fps=args.fps)
    if args.poster:
        poster(tl, out.with_suffix(".jpg"), args.poster_at)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="misk", description="محرّك فيديو بشارة المولودة — صامت وأنيق")
    ap.add_argument("--size", choices=sorted(PRESETS), default="vertical",
                    help="مقاس الفيديو (افتراضي: vertical ١٠٨٠×١٩٢٠)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_plan(p):
        p.add_argument("plan", nargs="?", default="plans/misk.json")
        return p

    add_plan(sub.add_parser("outline", help="جدول المشاهد والمواقيت")).set_defaults(fn=cmd_outline)

    s = add_plan(sub.add_parser("shots", help="لقطات ثابتة لمراجعة التصميم"))
    s.add_argument("--out", default="out/shots")
    s.add_argument("--at", type=float, nargs="*", help="لحظات محدّدة بالثواني")
    s.set_defaults(fn=cmd_shots)

    p = add_plan(sub.add_parser("poster", help="صورة غلاف واحدة"))
    p.add_argument("--out", default="out/misk.jpg")
    p.add_argument("--at", type=float, default=25.0)
    p.set_defaults(fn=cmd_poster)

    b = add_plan(sub.add_parser("build", help="إخراج ملفّ MP4 كامل"))
    b.add_argument("--out", default="out/misk.mp4")
    b.add_argument("--crf", type=int, default=17)
    b.add_argument("--fps", type=int, default=None)
    b.add_argument("--poster", action="store_true", help="أخرِج صورة غلاف أيضًا")
    b.add_argument("--poster-at", type=float, default=25.0)
    b.set_defaults(fn=cmd_build)

    args = ap.parse_args(argv)
    use_preset(args.size)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
