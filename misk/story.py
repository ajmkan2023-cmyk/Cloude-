"""تحويل ملفّ الخطّة (JSON) إلى سلسلة مشاهد.

كل الكلام في الخطّة، ولا كلمة منه في الكود — حتى يُعدَّل النصّ أو تُبدَّل
الصور دون المساس بالتصميم.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import VIDEO, color
from .scenes import (BODY, CLOSING, KICKER, LEAD, NOTE, SUBNAME, VERSE,
                     NameReveal, Panel, PhotoPanel, Stack)
from .timeline import Timeline

DEFAULT_DURATIONS = {
    "opening": 4.6, "praise": 6.0, "verse": 7.6, "news": 6.4,
    "name": 10.5, "hadith": 6.4, "photo": 7.0, "dua": 8.4, "finale": 7.6,
}


def load(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data.setdefault("durations", {})
    for key, value in DEFAULT_DURATIONS.items():
        data["durations"].setdefault(key, value)
    return data


def _panel(build, duration: float, name: str, anchor: float = 0.48) -> Panel:
    return Panel(build=build, duration=duration, name=name, anchor=anchor)


def build_scenes(plan: dict) -> list:
    d = plan["durations"]
    scenes: list = []

    # ١ — البسملة
    if plan.get("opening"):
        def opening(s: Stack, text=plan["opening"]):
            s.text(text, VERSE, color("ink_soft"), delay=0.3, max_lines=2)
            s.gap(46)
            s.rule(420, delay=1.5, thickness=2, diamond=7, fill=color("gold", 200))
        scenes.append(_panel(opening, d["opening"], "opening"))

    # ٢ — الحمد
    if plan.get("praise"):
        def praise(s: Stack, text=plan["praise"]):
            s.sprig(380, delay=0.25, fill=color("gold", 175))
            s.gap(44)
            s.text(text, LEAD, color("ink"), delay=0.7, max_lines=3,
                   glow_fill=color("paper_cool", 90), glow_blur=34)
        scenes.append(_panel(praise, d["praise"], "praise"))

    # ٣ — الآية
    verse = plan.get("verse") or {}
    if verse.get("text"):
        def ayah(s: Stack, v=verse):
            if v.get("kicker"):
                s.text(v["kicker"], KICKER, color("gold_deep", 235), delay=0.25, max_lines=1)
                s.gap(38)
            s.text(v["text"], VERSE, color("ink"), delay=0.7, max_lines=3)
            s.gap(40)
            s.rule(380, delay=1.9, thickness=2, diamond=6)
            s.gap(26)
            if v.get("note"):
                s.text(v["note"], NOTE, color("ink_faint"), delay=2.2, max_lines=1, shade=False)
        scenes.append(_panel(ayah, d["verse"], "verse"))

    # ٤ — البشرى
    news = plan.get("news") or {}
    if news.get("text"):
        def bushra(s: Stack, n=news):
            if n.get("kicker"):
                s.text(n["kicker"], KICKER, color("rose_deep", 240), delay=0.25, max_lines=1)
                s.gap(34)
            s.text(n["text"], LEAD, color("ink"), delay=0.65, max_lines=3,
                   glow_fill=color("rose", 70), glow_blur=40)
        scenes.append(_panel(bushra, d["news"], "news"))

    # ٥ — كشف الاسم
    scenes.append(NameReveal(
        name_text=plan["name_ar"],
        kicker=plan.get("name_kicker", ""),
        subtitle=plan.get("kinship_ar", ""),
        latin=plan.get("name_latin", ""),
        duration=d["name"],
    ))

    # ٦ — الحديث في معنى الاسم
    hadith = plan.get("hadith") or {}
    if hadith.get("text"):
        def athar(s: Stack, hd=hadith):
            if hd.get("kicker"):
                s.text(hd["kicker"], KICKER, color("gold_deep", 235), delay=0.25, max_lines=1)
                s.gap(36)
            s.text(hd["text"], LEAD, color("ink"), delay=0.7, max_lines=2, gold=False)
            s.gap(38)
            s.rule(380, delay=1.8, thickness=2, diamond=6)
            s.gap(24)
            if hd.get("note"):
                s.text(hd["note"], NOTE, color("ink_faint"), delay=2.1, max_lines=1, shade=False)
        scenes.append(_panel(athar, d["hadith"], "hadith"))

    # ٧ — الصور (اختيارية)
    for shot in plan.get("photos") or []:
        path = Path(shot["path"])
        if not path.exists():
            print(f"  ⚠ صورة مفقودة، تُتخطّى: {path}")
            continue
        scenes.append(PhotoPanel(
            path=path,
            caption=shot.get("caption", ""),
            duration=shot.get("duration", d["photo"]),
            zoom=shot.get("zoom", 0.10),
            drift=tuple(shot.get("drift", (0.0, -0.02))),
        ))

    # ٨ — الدعاء
    dua = plan.get("dua") or {}
    if dua.get("text"):
        def prayer(s: Stack, p=dua):
            if p.get("kicker"):
                s.text(p["kicker"], KICKER, color("gold_deep", 235), delay=0.2, max_lines=1)
                s.gap(40)
            s.text(p["text"], BODY, color("ink"), delay=0.6, stagger=0.42, max_lines=6)
            if p.get("note"):
                s.gap(38)
                s.rule(340, thickness=2, diamond=7)
                s.gap(22)
                s.text(p["note"], NOTE, color("ink_faint"), max_lines=1, shade=False)
        scenes.append(_panel(prayer, d["dua"], "dua"))

    # ٩ — الختام
    fin = plan.get("finale") or {}
    if fin.get("name"):
        def closing(s: Stack, f=fin):
            s.text(f["name"], CLOSING, color("ink"), delay=0.4, max_lines=1, gold=True)
            s.gap(40)
            s.rule(460, delay=1.0, thickness=2, diamond=8)
            if f.get("date"):
                s.gap(34)
                s.text(f["date"], NOTE, color("ink_faint"), delay=1.35, max_lines=1, shade=False)
            if f.get("blessing"):
                s.gap(56)
                s.text(f["blessing"], BODY, color("ink_soft"), delay=1.7, max_lines=3)
            if f.get("family"):
                s.gap(52)
                s.sprig(340, fill=color("rose_deep", 170))
                s.gap(34)
                s.text(f["family"], NOTE, color("ink_faint"), max_lines=2, shade=False)
        scenes.append(_panel(closing, d["finale"], "finale"))

    return scenes


def build_timeline(plan: dict) -> Timeline:
    return Timeline(
        build_scenes(plan),
        crossfade=plan.get("crossfade", 1.1),
        atmosphere=plan.get("atmosphere", True),
        show_frame=plan.get("frame", True),
    )


def outline(plan: dict) -> str:
    """جدول المشاهد ومواقيتها — للمراجعة قبل الإخراج."""
    tl = build_timeline(plan)
    rows = [f"{'المشهد':<12}{'يبدأ':>9}{'ينتهي':>9}{'المدّة':>9}"]
    for cue in tl.cues:
        rows.append(f"{cue.scene.name:<12}{cue.start:>9.1f}{cue.end:>9.1f}"
                    f"{cue.duration:>9.1f}")
    rows.append(f"\nالمجموع: {tl.duration:.1f} ثانية  ·  {VIDEO.width}×{VIDEO.height}"
                f"  ·  {VIDEO.fps}fps  ·  بلا صوت")
    return "\n".join(rows)
