"""فضاء التصميم — المفاتيح التي يُركَّب منها شكل الحلقة.

هذا الملف لا يحوي «أربعة قوالب» بل *مساحة* من الخيارات. مهارة التصميم
(`.claude/skills/ajmkan-reel-design`) تؤلّف في كل دورة تركيبة جديدة من هذه
المفاتيح وتكتبها في الخطة تحت `design`، فيخرج شكل مختلف فعلًا لا مجرّد تدوير.

عدد التركيبات الممكنة يتجاوز عشرات الآلاف، لكن الحدود هنا هي ما يضمن أن
تبقى كل تركيبة *ضمن هوية أجمكان* مهما اختلفت.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace

# القيم المسموحة لكل مفتاح — المهارة تختار منها فقط
CHOICES: dict[str, tuple] = {
    "caption": ("glass", "band", "bare", "ribbon", "corner"),
    "title_layout": ("bottom", "center", "upper"),
    "number": ("chip", "big", "text", "none"),
    "accent": ("sun", "sky", "sand"),
    "outro_bg": ("brand", "photo"),
    "progress": ("bar", "dots", "none"),
    "watermark": ("top_right", "top_left", "none"),
    "transition": ("fade", "zoom", "slide"),
}


@dataclass(frozen=True)
class Style:
    key: str = "custom"
    name_ar: str = "تصميم مخصّص"

    # --- بنية الشاشة
    caption: str = "glass"          # معالجة نص اللقطة
    title_layout: str = "bottom"    # موضع عنوان الافتتاح
    number: str = "chip"            # شكل الترقيم
    outro_bg: str = "brand"         # خلفية الختام

    # --- اللون والضوء
    accent: str = "sun"             # لون التمييز من ألوان العلامة
    grade: float = 1.0              # قوّة التدرّج اللوني (0.6 – 1.3)
    scrim_photo: tuple[int, int, int] = (120, 40, 225)
    scrim_title: tuple[int, int, int] = (190, 70, 235)

    # --- التنضيد
    title_size: int = 100           # حجم عنوان الافتتاح
    caption_title_size: int = 58    # حجم عنوان اللقطة
    body_size: int = 36             # حجم السطر الوصفي
    radius: int = 34                # استدارة اللوحات

    # --- الحركة
    transition: str = "fade"
    transition_seconds: float = 0.45

    # --- عناصر ثابتة
    progress: str = "bar"
    watermark: str = "top_right"
    grain: bool = True

    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict) -> "Style":
        """يبني تصميمًا من قاموس جزئي — أي مفتاح غير مذكور يأخذ قيمته الافتراضية."""
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"مفاتيح تصميم غير معروفة: {'، '.join(sorted(unknown))}")
        clean = dict(data)
        for tuple_key in ("scrim_photo", "scrim_title"):
            if tuple_key in clean:
                clean[tuple_key] = tuple(clean[tuple_key])
        style = cls(**clean)
        style.validate()
        return style

    def merged(self, overrides: dict) -> "Style":
        base = {f.name: getattr(self, f.name) for f in fields(self)}
        base.update(overrides)
        return Style.from_dict(base)

    def validate(self) -> None:
        for key, allowed in CHOICES.items():
            value = getattr(self, key)
            if value not in allowed:
                raise ValueError(
                    f"قيمة غير مسموحة لـ«{key}»: {value} — المسموح: {'، '.join(allowed)}"
                )
        if not 0.6 <= self.grade <= 1.3:
            raise ValueError("grade يجب أن يكون بين 0.6 و 1.3")
        if not 0.25 <= self.transition_seconds <= 0.9:
            raise ValueError("transition_seconds يجب أن يكون بين 0.25 و 0.9")
        for name in ("title_size", "caption_title_size", "body_size"):
            value = getattr(self, name)
            if not 24 <= value <= 130:
                raise ValueError(f"{name} خارج المدى المعقول (24–130)")


# نقاط انطلاق جاهزة — المهارة تبدأ من إحداها ثم تغيّر ما تشاء،
# ولا يجوز تسليم تصميم مطابق تمامًا لأي منها.
PRESETS: tuple[Style, ...] = (
    Style(key="glass", name_ar="الزجاج", caption="glass", number="chip", accent="sun"),
    Style(key="band", name_ar="الشريط", caption="band", number="big", accent="sun",
          grade=1.1, scrim_photo=(100, 30, 200), transition="slide"),
    Style(key="editorial", name_ar="التحريري", caption="bare", title_layout="upper",
          number="text", accent="sky", outro_bg="photo", grade=0.9,
          scrim_photo=(140, 50, 245), scrim_title=(205, 80, 245), progress="dots"),
    Style(key="poster", name_ar="الملصق", caption="ribbon", title_layout="center",
          number="chip", accent="sky", outro_bg="photo", grade=1.05,
          scrim_title=(215, 120, 230), transition="zoom"),
)

STYLE_BY_KEY = {s.key: s for s in PRESETS}
STYLES = PRESETS   # توافق مع الاستيرادات القديمة


def next_style(cycle: int) -> Style:
    """احتياطي فقط: يُستخدم حين لا تكتب المهارة تصميمًا صريحًا."""
    return PRESETS[cycle % len(PRESETS)]
