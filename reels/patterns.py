"""أنماط التحرير — *نحو* المونتاج لا ثوبه.

المشكلة التي يحلّها هذا الملف: كانت كل حلقة تُبنى بالتتابع نفسه (عنوان ثم
صور ملء الشاشة واحدة تلو الأخرى ثم ختام) بالإيقاع نفسه، فتبدو الحلقات
متشابهة مهما تغيّر لونها وشكل بطاقاتها. `styles.py` يغيّر *الثوب*، وهذا
الملف يغيّر *البنية*: أي أنواع مشاهد تتوالى، وكم تدوم، وكم صورة تستهلك.

النمط قائمة «خانات» (Slot)، كل خانة نوع مشهد ومدّته وعدد الصور التي يأخذها.
"""

from __future__ import annotations

from dataclasses import dataclass

# أنواع المشاهد المتاحة
KINDS = ("title", "photo", "grid", "flash", "text", "inset", "outro",
         # مشاهد المناسبات (اليوم الوطني) — انظر `national.py`
         "national_title", "split", "emblem", "national_outro")

# أول خانة وآخر خانة: افتتاح وختام، أيًّا كان طرازهما
OPENERS = ("title", "national_title")
CLOSERS = ("outro", "national_outro")


@dataclass(frozen=True)
class Slot:
    kind: str
    seconds: float
    photos: int = 1        # كم صورة تستهلك هذه الخانة (0 لبطاقة النص)


@dataclass(frozen=True)
class Pattern:
    key: str
    name_ar: str
    slots: tuple[Slot, ...]
    note: str              # ما الذي يميّز إيقاع هذا النمط
    skin: str = "brand"    # brand = أزرق أجمكان، national = أخضر المناسبة

    @property
    def photo_count(self) -> int:
        """عدد الصور المطلوبة عدا صورة الافتتاح."""
        return sum(s.photos for s in self.slots
                   if s.kind not in OPENERS + CLOSERS)

    @property
    def text_count(self) -> int:
        return sum(1 for s in self.slots if s.kind in ("text", "emblem"))

    @property
    def total_seconds(self) -> float:
        return sum(s.seconds for s in self.slots)

    def validate(self) -> None:
        for s in self.slots:
            if s.kind not in KINDS:
                raise ValueError(f"نوع مشهد غير معروف: {s.kind}")
            if not 0.8 <= s.seconds <= 6.0:
                raise ValueError(f"مدّة خانة خارج المدى (٠٫٨–٦): {s.seconds}")
        if self.slots[0].kind not in OPENERS or self.slots[-1].kind not in CLOSERS:
            raise ValueError("كل نمط يبدأ بمشهد افتتاح وينتهي بمشهد ختام")


PATTERNS: tuple[Pattern, ...] = (
    Pattern(
        key="classic",
        name_ar="الكلاسيكي",
        note="إيقاع متّزن: لقطة كاملة لكل فكرة، مساحة للنظر والقراءة",
        slots=(
            Slot("title", 3.2, 1),
            Slot("photo", 3.4), Slot("photo", 3.4), Slot("photo", 3.4),
            Slot("photo", 3.4), Slot("photo", 3.4),
            Slot("outro", 3.6, 0),
        ),
    ),
    Pattern(
        key="hook",
        name_ar="الخطّاف",
        note="يبدأ بقطع سريع يشدّ الانتباه في أول ثانيتين ثم يهدأ، وينتهي بشبكة",
        slots=(
            Slot("title", 2.8, 1),
            Slot("flash", 2.4, 5),
            Slot("photo", 3.2), Slot("photo", 3.2), Slot("photo", 3.2),
            Slot("grid", 3.4, 4),
            Slot("outro", 3.4, 0),
        ),
    ),
    Pattern(
        key="chapters",
        name_ar="الفصول",
        note="بطاقات نصّية تفصل بين اللقطات كفصول قصيرة — يمنح النص وزنًا",
        slots=(
            Slot("title", 3.2, 1),
            Slot("photo", 3.2), Slot("text", 2.2, 0),
            Slot("photo", 3.2), Slot("photo", 3.2),
            Slot("text", 2.2, 0), Slot("photo", 3.2),
            Slot("outro", 3.4, 0),
        ),
    ),
    Pattern(
        key="mosaic",
        name_ar="الفسيفساء",
        note="شبكات تعرض أربع لقطات معًا — يوصل «سعة المكان» في لمحة",
        slots=(
            Slot("title", 3.0, 1),
            Slot("grid", 3.6, 4),
            Slot("photo", 3.2), Slot("photo", 3.2),
            Slot("grid", 3.6, 4),
            Slot("outro", 3.4, 0),
        ),
    ),
    Pattern(
        key="gallery",
        name_ar="المعرض",
        note="الصور داخل إطار بهامش العلامة لا ملء الشاشة — إحساس مطبوع أنيق",
        slots=(
            Slot("title", 3.2, 1),
            Slot("inset", 3.0), Slot("inset", 3.0),
            Slot("inset", 3.0), Slot("inset", 3.0),
            Slot("photo", 3.4),
            Slot("outro", 3.4, 0),
        ),
    ),
    Pattern(
        key="pulse",
        name_ar="النبض",
        note="أسرع الأنماط: دفعتا قطع سريع ولقطات قصيرة — طاقة عالية للعروض",
        slots=(
            Slot("title", 2.6, 1),
            Slot("flash", 2.6, 6),
            Slot("photo", 2.4), Slot("photo", 2.4),
            Slot("flash", 1.8, 4),
            Slot("photo", 2.6), Slot("text", 2.0, 0),
            Slot("outro", 3.4, 0),
        ),
    ),
)


# أنماط المناسبات — خارج الدوران الدوري لأنها تخصّ تاريخًا بعينه، ولا يصحّ
# أن تظهر في حلقة عادية في منتصف الشتاء.
OCCASIONS: tuple[Pattern, ...] = (
    Pattern(
        key="national",
        name_ar="الوطني",
        skin="national",
        note=(
            "إعلان مناسبة: ستارة خضراء تنفتح عن الصورة، انقسامات قطرية بحافّة "
            "ذهبية، بطاقة رقم اليوم الوطني، ثم ختام بتهنئة"
        ),
        slots=(
            Slot("national_title", 3.8, 1),
            Slot("flash", 2.2, 4),
            Slot("split", 3.4),
            Slot("emblem", 3.0, 0),
            Slot("split", 3.4),
            Slot("photo", 2.8),
            Slot("grid", 3.2, 4),
            Slot("national_outro", 4.4, 0),
        ),
    ),
)


PATTERN_BY_KEY = {p.key: p for p in PATTERNS + OCCASIONS}
for _p in PATTERNS + OCCASIONS:
    _p.validate()


def next_pattern(cycle: int) -> Pattern:
    """احتياطي: يدور بست خطوات حين لا تختار المهارة نمطًا صريحًا."""
    return PATTERNS[(cycle - 1) % len(PATTERNS)]
