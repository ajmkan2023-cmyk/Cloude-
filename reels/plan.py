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
    style: str = ""               # نقطة انطلاق جاهزة (اختيارية)
    design: dict = field(default_factory=dict)   # مفاتيح التصميم التي تبتكرها المهارة
    design_note: str = ""         # لماذا هذا التصميم لهذه الحلقة — للسجلّ والمراجعة
    shots: list[Shot] = field(default_factory=list)
    caption: str = ""
    hashtags: str = ""
    hero_photo: str = ""          # صورة مشهد الافتتاح
    audio: str = ""               # مسار موسيقى اختياري
    created: str = ""

    # ----------------------------------------------------------------
    @property
    def concept_obj(self) -> Concept:
        return CONCEPT_BY_KEY[self.concept]

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

        c = self.concept_obj
        if not self.hero_photo:
            problems.append("لا توجد صورة افتتاح (hero_photo)")
        if not self.shots:
            problems.append("لا توجد لقطات")
        if len(self.shots) != c.scene_count:
            problems.append(
                f"عدد اللقطات {len(self.shots)} لا يطابق فكرة «{c.name_ar}» ({c.scene_count})"
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
    """يحوّل الخطة إلى خط زمني جاهز للإخراج."""
    from .scenes import OutroScene, PhotoScene, TitleScene
    from .timeline import Timeline

    c = plan.concept_obj
    st = plan.style_obj
    scenes = [
        TitleScene(
            photo=plan.hero_photo,
            kicker=plan.kicker or c.kicker,
            headline=plan.headline,
            subline=plan.subline,
            duration=c.title_scene_seconds,
            style=st,
        )
    ]
    total = len(plan.shots)
    for i, shot in enumerate(plan.shots):
        scenes.append(
            PhotoScene(
                photo=shot.photo,
                title=shot.title,
                body=shot.body,
                index=i + 1,
                total=total,
                move=shot.move or c.moves[i % len(c.moves)],
                duration=c.photo_scene_seconds,
                style=st,
            )
        )
    scenes.append(
        OutroScene(cta=plan.cta, duration=c.outro_seconds, style=st, photo=plan.hero_photo)
    )
    return Timeline(scenes=scenes, style=st)
