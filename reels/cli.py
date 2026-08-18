"""واجهة الأوامر.

    python -m reels build plans/cycle-001.json          # إخراج الريلز
    python -m reels check plans/cycle-001.json          # فحص الخطة فقط
    python -m reels preview plans/cycle-001.json 2.4    # لقطة واحدة للمعاينة
    python -m reels scaffold 1 countdown "العلا"        # هيكل خطة جديدة
    python -m reels demo                                # عيّنة باستخدام صور تجريبية
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from .concepts import CONCEPT_BY_KEY, next_concept, hashtag_line
from .plan import Plan, Shot, build_timeline
from .render import render, render_poster


def _fail(message: str) -> None:
    print(f"✖ {message}", file=sys.stderr)
    raise SystemExit(1)


def _load(path: str) -> Plan:
    plan = Plan.load(path)
    problems = plan.validate()
    if problems:
        for p in problems:
            print(f"  • {p}", file=sys.stderr)
        _fail("الخطة غير صالحة")
    return plan


def cmd_check(path: str) -> None:
    plan = _load(path)
    c, st = plan.concept_obj, plan.style_obj
    print(f"✔ الخطة صالحة — فكرة «{c.name_ar}» بنمط «{st.name_ar}»، "
          f"{len(plan.shots)} لقطات، ~{c.total_seconds:.0f} ثانية")
    notes = plan.review()
    if notes:
        print("\n--- ملاحظات للمراجعة ---")
        for n in notes:
            print(f"  • {n}")
    print("\n--- نص المنشور ---")
    print(plan.full_caption())


def cmd_build(path: str, out: str | None = None) -> None:
    plan = _load(path)
    stem = Path(path).stem
    out_path = Path(out) if out else Path("out") / f"{stem}.mp4"
    timeline = build_timeline(plan)
    render(timeline, out_path, audio=plan.audio or None)
    render_poster(timeline, out_path.with_suffix(".jpg"), at=plan.concept_obj.title_scene_seconds * 0.75)
    caption_file = out_path.with_suffix(".txt")
    caption_file.write_text(plan.full_caption(), encoding="utf-8")
    print(f"✔ نص المنشور: {caption_file}")


def cmd_preview(path: str, at: str = "2.0") -> None:
    plan = _load(path)
    timeline = build_timeline(plan)
    out = Path("out") / f"{Path(path).stem}-preview-{at}.jpg"
    render_poster(timeline, out, at=float(at))


def cmd_scaffold(cycle: str, concept_key: str | None = None, topic: str = "وجهتك") -> None:
    n = int(cycle)
    concept = CONCEPT_BY_KEY[concept_key] if concept_key else next_concept(n - 1)
    headline = concept.headline_template.format(n=concept.scene_count, topic=topic)
    plan = Plan(
        cycle=n,
        concept=concept.key,
        topic=topic,
        headline=headline,
        kicker=concept.kicker,
        subline="",
        cta="احجز رحلتك الآن",
        hero_photo="assets/incoming/hero.jpg",
        shots=[
            Shot(photo=f"assets/incoming/shot{i+1}.jpg", title="", body="")
            for i in range(concept.scene_count)
        ],
        caption=concept.caption_opener.format(n=concept.scene_count, topic=topic),
        hashtags=hashtag_line(concept),
        audio="assets/audio/track.mp3" if Path("assets/audio/track.mp3").exists() else "",
        created=date.today().isoformat(),
    )
    path = plan.save(Path("plans") / f"cycle-{n:03d}.json")
    print(f"✔ هيكل الخطة: {path}")
    print(f"  الفكرة: {concept.name_ar} — {concept.guidance}")


def cmd_demo() -> None:
    from scripts.make_demo_assets import main as make_assets

    make_assets()
    cmd_scaffold("999", "reasons", "أجمكان")
    plan = Plan.load("plans/cycle-999.json")
    plan.hero_photo = "assets/incoming/demo/hero.jpg"
    plan.headline = "٥ أسباب\nتخليك تجي أجمكان"
    plan.subline = "على بحر الخبر — قريب منك أكثر مما تتخيّل"
    plan.cta = "احجز جلستك الآن"
    # النصوص مطابقة لما في الصور التجريبية فعلًا (انظر DEMO_INDEX)
    demo_shots = [
        ("ظلّ ونخيل", "سماء مفتوحة وهدوء يمتدّ"),
        ("سماء الليل", "نجوم أقرب مما تتخيّل"),
        ("زُرقة تمتدّ", "ماء صافٍ وأفق بلا نهاية"),
        ("ضوء ذهبي", "لون لا يتكرّر ولا يحتاج فلتر"),
        ("خليج هادئ", "شاطئ يبدأ حيث ينتهي الزحام"),
    ]
    plan.shots = [
        Shot(photo=f"assets/incoming/demo/shot{i+1}.jpg", title=t, body=b)
        for i, (t, b) in enumerate(demo_shots)
    ]
    plan.caption = ("٥ أسباب تخليك تختار أجمكان على بحر الخبر 🌴\n"
                    "للحجز والاستفسار: 0535516054")
    plan.save("plans/cycle-999.json")
    cmd_build("plans/cycle-999.json")


def cmd_record(path: str) -> None:
    """يسجّل الحلقة في السجلّ بعد اعتمادها — لتتجنّبها الدورات القادمة."""
    from .history import History

    plan = Plan.load(path)
    history = History.load()
    history.record(plan)
    out = history.save()
    print(f"✔ سُجّلت الدورة {plan.cycle} في {out} ({len(history.cycles)} حلقة في السجلّ)")


COMMANDS = {
    "check": cmd_check,
    "record": cmd_record,
    "build": cmd_build,
    "preview": cmd_preview,
    "scaffold": cmd_scaffold,
    "demo": cmd_demo,
}


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        raise SystemExit(0 if not argv else 1)
    COMMANDS[argv[0]](*argv[1:])


if __name__ == "__main__":
    main()
