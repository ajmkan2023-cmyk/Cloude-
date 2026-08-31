"""خطة الريلز: بنية JSON واحدة تصف الفيديو كاملًا ونصّ المنشور.

كلود يكتب هذا الملف في كل دورة، والمحرّك ينفّذه حرفيًا — فصل النصّ الإبداعي
عن الرسم يجعل المراجعة والتعديل سهلين دون لمس الكود.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .catalog import Catalog
from .concepts import CONCEPT_BY_KEY, Concept, hashtag_line
from .patterns import PATTERN_BY_KEY, Pattern, next_pattern
from .styles import STYLE_BY_KEY, Style, next_style


@dataclass
class Shot:
    photo: str            # مسار الصورة داخل assets/incoming
    title: str            # عنوان قصير جدًا (٢-٥ كلمات)
    body: str = ""        # سطر وصفي واحد
    move: str = ""        # فارغ = يختاره المحرّك من الفكرة


@dataclass
class Plan:
    cycle: int
    concept: str
    topic: str
    headline: str
    kicker: str
    subline: str
    cta: str
    pattern: str = ""             # نمط التحرير — بنية المونتاج
    text_cards: list = field(default_factory=list)  # جُمل البطاقات النصّية
    style: str = ""               # نقطة انطلاق جاهزة (اختيارية)
    design: dict = field(default_factory=dict)   # مفاتيح التصميم التي تبتكرها المهارة
    design_note: str = ""         # لماذا هذا التصميم لهذه الحلقة — للسجلّ والمراجعة
    shots: list[Shot] = field(default_factory=list)
    caption: str = ""
    hashtags: str = ""
    hero_photo: str = ""          # صورة مشهد الافتتاح
    audio: str = ""               # مسار موسيقى اختياري
    music_mood: str = ""          # مزاج الموسيقى المولّدة لهذه الحلقة
    voice: str = ""               # مسار تعليق صوتي — تنخفض الموسيقى تحته
    voice_delay: float = 0.0      # إزاحة بالثواني لضبط الجمل على المشاهد
    created: str = ""

    # ----------------------------------------------------------------
    @property
    def concept_obj(self) -> Concept:
        return CONCEPT_BY_KEY[self.concept]

    @property
    def pattern_obj(self) -> Pattern:
        return PATTERN_BY_KEY[self.pattern] if self.pattern else next_pattern(self.cycle)

    @property
    def style_obj(self) -> Style:
        """التصميم النهائي: نقطة انطلاق (إن وُجدت) + ما ابتكرته المهارة فوقها."""
        base = STYLE_BY_KEY[self.style] if self.style else next_style(self.cycle - 1)
        return base.merged(self.design) if self.design else base

    def validate(self) -> list[str]:
        """أخطاء تمنع الإخراج."""
        problems: list[str] = []
        if self.concept not in CONCEPT_BY_KEY:
            problems.append(f"فكرة غير معروفة: {self.concept}")
            return problems
        if self.style and self.style not in STYLE_BY_KEY:
            problems.append(f"نقطة انطلاق غير معروفة: {self.style}")
        else:
            try:
                self.style_obj.validate()
            except ValueError as exc:
                problems.append(f"التصميم: {exc}")

        if self.pattern and self.pattern not in PATTERN_BY_KEY:
            problems.append(f"نمط تحرير غير معروف: {self.pattern}")
            return problems
        pat = self.pattern_obj

        if not self.hero_photo:
            problems.append("لا توجد صورة افتتاح (hero_photo)")
        if not self.shots:
            problems.append("لا توجد لقطات")
        if len(self.shots) != pat.photo_count:
            problems.append(
                f"عدد اللقطات {len(self.shots)} لا يطابق نمط «{pat.name_ar}» "
                f"({pat.photo_count} صورة)"
            )
        if len(self.text_cards) != pat.text_count:
            problems.append(
                f"عدد البطاقات النصّية {len(self.text_cards)} لا يطابق نمط "
                f"«{pat.name_ar}» ({pat.text_count})"
            )

        used: set[str] = set()
        for i, shot in enumerate(self.shots, 1):
            if not Path(shot.photo).exists():
                problems.append(f"اللقطة {i}: الصورة غير موجودة — {shot.photo}")
            if not shot.title:
                problems.append(f"اللقطة {i}: بلا عنوان")
            if shot.photo in used:
                problems.append(f"اللقطة {i}: الصورة مكرّرة داخل الحلقة — {Path(shot.photo).name}")
            used.add(shot.photo)

        if self.hero_photo and not Path(self.hero_photo).exists():
            problems.append(f"صورة الافتتاح غير موجودة — {self.hero_photo}")

        # الصورة غير المفهرسة خطأ: بلا فهرس لا سبيل للتأكّد أن النص يصفها
        catalog = Catalog.load()
        checks = [("صورة الافتتاح", self.hero_photo, (self.headline, self.subline))]
        checks += [
            (f"اللقطة {i}", shot.photo, (shot.title, shot.body))
            for i, shot in enumerate(self.shots, 1)
        ]
        for label, photo, texts in checks:
            if not photo:
                continue
            if catalog.for_photo(photo) is None:
                problems.append(
                    f"{label}: «{Path(photo).name}» غير مفهرسة — افهرسها قبل كتابة نص يصفها"
                )
                continue
            problems += [f"{label}: {w}" for w in catalog.hard_conflicts(photo, *texts)]
        return problems

    def review(self) -> list[str]:
        """ملاحظات لا تمنع الإخراج لكن يُستحسن مراجعتها."""
        from .history import History

        notes: list[str] = History.load().echoes(self)

        catalog = Catalog.load()
        if not catalog.entries:
            notes.append("لا يوجد فهرس صور — شغّل خطوة الفهرسة أولًا لضمان تطابق النص مع الصور")
            return notes

        notes += [
            f"صورة الافتتاح: {w}"
            for w in catalog.check_text(self.hero_photo, self.headline, self.subline)
            if not w.startswith("تناقض")
        ]
        for i, shot in enumerate(self.shots, 1):
            notes += [
                f"اللقطة {i}: {w}"
                for w in catalog.check_text(shot.photo, shot.title, shot.body)
                if not w.startswith("تناقض")
            ]
        return notes

    def full_caption(self) -> str:
        tags = self.hashtags or hashtag_line(self.concept_obj)
        return f"{self.caption.strip()}\n\n{tags}".strip()

    # ----------------------------------------------------------------
    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    @classmethod
    def load(cls, path: str | Path) -> "Plan":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        shots = [Shot(**s) for s in data.pop("shots", [])]
        return cls(shots=shots, **data)


def build_timeline(plan: Plan):
    """يبني الخط الزمني بالسير على خانات نمط التحرير.

    النمط يحدّد *بنية* المونتاج (أي أنواع المشاهد تتوالى وكم تدوم)، والفكرة
    تحدّد النبرة وحركة الكاميرا، والتصميم يحدّد الشكل. الثلاثة مستقلّة، فلا
    تتكرّر حلقة بعينها.
    """
    from .national import (EmblemScene, NationalOutroScene, NationalTitleScene,
                           SplitScene)
    from .scenes import (FlashScene, GridScene, InsetScene, OutroScene,
                         PhotoScene, TextCardScene, TitleScene)
    from .timeline import Timeline

    if plan.pattern_obj.skin == "national":
        from . import national as nat
        FlashScene, PhotoScene, GridScene = (nat.NationalFlashScene,
                                             nat.NationalPhotoScene,
                                             nat.NationalGridScene)

    c, st, pat = plan.concept_obj, plan.style_obj, plan.pattern_obj
    shots, cards = list(plan.shots), list(plan.text_cards)
    scenes, si, ci, mi = [], 0, 0, 0
    numbered = sum(1 for s in pat.slots if s.kind in ("photo", "inset"))
    index = 0

    for slot in pat.slots:
        if slot.kind == "title":
            scenes.append(TitleScene(
                photo=plan.hero_photo, kicker=plan.kicker or c.kicker,
                headline=plan.headline, subline=plan.subline,
                duration=slot.seconds, style=st))

        elif slot.kind == "outro":
            scenes.append(OutroScene(cta=plan.cta, duration=slot.seconds,
                                     style=st, photo=plan.hero_photo))

        elif slot.kind == "national_title":
            scenes.append(NationalTitleScene(
                photo=plan.hero_photo, kicker=plan.kicker or c.kicker,
                headline=plan.headline, subline=plan.subline,
                number=plan.topic, duration=slot.seconds, style=st))

        elif slot.kind == "national_outro":
            scenes.append(NationalOutroScene(cta=plan.cta, duration=slot.seconds, style=st))

        elif slot.kind == "emblem":
            line = cards[ci] if ci < len(cards) else plan.subline
            ci += 1
            scenes.append(EmblemScene(number=plan.topic, line=line,
                                      duration=slot.seconds, style=st))

        elif slot.kind == "split":
            shot = shots[si] if si < len(shots) else shots[-1]
            si += 1
            move = shot.move or c.moves[mi % len(c.moves)]
            mi += 1
            scenes.append(SplitScene(
                photo=shot.photo, title=shot.title, body=shot.body, move=move,
                flip=bool(len([s for s in scenes if isinstance(s, SplitScene)]) % 2),
                duration=slot.seconds, style=st))

        elif slot.kind == "text":
            line = cards[ci] if ci < len(cards) else plan.subline
            ci += 1
            scenes.append(TextCardScene(line=line, duration=slot.seconds, style=st))

        elif slot.kind == "flash":
            group = shots[si:si + slot.photos]
            si += slot.photos
            scenes.append(FlashScene(
                photos=tuple(g.photo for g in group),
                kicker=group[0].title if group else "",
                duration=slot.seconds, style=st))

        elif slot.kind == "grid":
            group = shots[si:si + slot.photos]
            si += slot.photos
            scenes.append(GridScene(
                photos=tuple(g.photo for g in group),
                title=group[0].title if group else "",
                body=group[0].body if group else "",
                duration=slot.seconds, style=st))

        else:  # photo | inset
            shot = shots[si] if si < len(shots) else shots[-1]
            si += 1
            index += 1
            move = shot.move or c.moves[mi % len(c.moves)]
            mi += 1
            cls = InsetScene if slot.kind == "inset" else PhotoScene
            scenes.append(cls(
                photo=shot.photo, title=shot.title, body=shot.body,
                index=index, total=numbered, move=move,
                duration=slot.seconds, style=st))

    return Timeline(scenes=scenes, style=st)
