"""مكتبة الأفكار الإبداعية — تدور كل ٣ أيام فلا يتكرّر الشكل ولا الأسلوب.

أجمكان وجهة على البحر في الخبر، لذلك كل فكرة هنا مبنية على البحر والغروب
والأجواء لا على «وجهات سفر» عامة. كل فكرة تحدّد الإيقاع وأسلوب الحركة
وصياغة العنوان وقالب نص المنشور؛ أما النصّ النهائي فيُكتب في كل دورة بناءً
على الصور الفعلية، وهذه القوالب هي الإطار الذي يحفظ ثبات الهوية.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Concept:
    key: str
    name_ar: str
    kicker: str
    # ⚠ قالب استرشادي لا نصّ نهائي: يبيّن *شكل* العنوان فقط، وعلى المهارة أن
    # تكتب عنوانًا جديدًا كل دورة. تسليم القالب كما هو يُرصد في `history.py`.
    headline_template: str        # {n} عدد اللقطات، {topic} زاوية الحلقة
    scene_count: int
    title_scene_seconds: float
    photo_scene_seconds: float
    outro_seconds: float
    moves: tuple[str, ...]
    caption_opener: str           # استرشادي كذلك — تُعاد صياغته كل دورة
    hashtags: tuple[str, ...]
    guidance: str                 # توجيه لكلود عند كتابة النصوص
    topic_hint: str = ""          # اقتراح لزاوية الحلقة

    @property
    def total_seconds(self) -> float:
        return (
            self.title_scene_seconds
            + self.scene_count * self.photo_scene_seconds
            + self.outro_seconds
        )


BASE_TAGS = ("أجمكان", "الخبر", "المنطقة_الشرقية", "الدمام", "شاطئ", "البحر")


CONCEPTS: tuple[Concept, ...] = (
    Concept(
        key="reasons",
        name_ar="الأسباب",
        kicker="لماذا أجمكان",
        headline_template="{n} أسباب\nتخليك تجي {topic}",
        scene_count=5,
        title_scene_seconds=3.2,
        photo_scene_seconds=3.4,
        outro_seconds=3.6,
        moves=("zoom_in", "pan_left", "rise", "pan_right", "zoom_out"),
        caption_opener="{n} أسباب تخليك تختار أجمكان في الخبر 🌴",
        hashtags=BASE_TAGS + ("وجهات_الشرقية", "اكتشف_الخبر"),
        guidance=(
            "قائمة مرقّمة. كل لقطة سبب واحد ملموس (الموقع، الغروب، الجلسات، "
            "الهدوء، القرب من المدينة). العنوان ٢-٤ كلمات، والسطر يصف الإحساس "
            "لا المواصفات. اجعل السبب الأخير أقواها."
        ),
        topic_hint="أجمكان",
    ),
    Concept(
        key="day_by_sea",
        name_ar="يوم على البحر",
        kicker="من الصباح للغروب",
        headline_template="يوم كامل\nعلى بحر {topic}",
        scene_count=5,
        title_scene_seconds=3.4,
        photo_scene_seconds=3.6,
        outro_seconds=3.6,
        moves=("rise", "zoom_in", "pan_right", "pan_left", "zoom_out"),
        caption_opener="من أول ضوء إلى آخر غروب… هكذا يمرّ اليوم على بحر الخبر",
        hashtags=BASE_TAGS + ("يوم_على_البحر", "اجازة"),
        guidance=(
            "تسلسل زمني: صباح هادئ، ضحى، ظهيرة، عصر، غروب. العناوين قصيرة "
            "كأنها ساعات من اليوم، والأسطر تصف اللحظة لا الخدمة."
        ),
        topic_hint="الخبر",
    ),
    Concept(
        key="sunset",
        name_ar="الغروب",
        kicker="خذ نفسًا",
        headline_template="غروب {topic}\nكما لم تره",
        scene_count=4,
        title_scene_seconds=3.6,
        photo_scene_seconds=4.0,
        outro_seconds=3.6,
        moves=("zoom_out", "pan_left", "rise", "zoom_in"),
        caption_opener="أجمل ما في اليوم لحظة يلامس فيها الضوء البحر 🌅",
        hashtags=BASE_TAGS + ("غروب", "هدوء"),
        guidance=(
            "نبرة شاعرية هادئة وإيقاع أبطأ. العناوين ٢-٣ كلمات، والأسطر "
            "إحساس خالص. لا أرقام ولا عروض في هذه الحلقة."
        ),
        topic_hint="الخبر",
    ),
    Concept(
        key="family",
        name_ar="أجواء العائلة",
        kicker="لمّة العائلة",
        headline_template="مكانك المفضّل\nمع {topic}",
        scene_count=5,
        title_scene_seconds=3.2,
        photo_scene_seconds=3.4,
        outro_seconds=3.6,
        moves=("zoom_in", "rise", "pan_right", "pan_left", "zoom_in"),
        caption_opener="أجواء عائلية على البحر في الخبر — احجز جلستك 👨‍👩‍👧",
        hashtags=BASE_TAGS + ("عائلات", "جلسات_خارجية"),
        guidance=(
            "دفء وبساطة. كل لقطة لحظة مشتركة (جلسة، مشي على الرمل، ضحك، "
            "شواء، صورة جماعية). العنوان اسم اللحظة والسطر شعورها."
        ),
        topic_hint="العائلة",
    ),
    Concept(
        key="guide",
        name_ar="الدليل السريع",
        kicker="قبل ما تجي",
        headline_template="دليلك السريع\nقبل زيارة {topic}",
        scene_count=5,
        title_scene_seconds=3.2,
        photo_scene_seconds=3.4,
        outro_seconds=3.6,
        moves=("zoom_in", "pan_left", "rise", "pan_right", "zoom_out"),
        caption_opener="دليل سريع قبل زيارتك لأجمكان — احفظه لزيارتك القادمة 📌",
        hashtags=BASE_TAGS + ("نصائح", "دليل"),
        guidance=(
            "كل لقطة نصيحة عملية: أفضل وقت للزيارة، ماذا تحضر، أين تصوّر، "
            "كيف تحجز. العنوان فعل أمر قصير، والسطر تفصيل مفيد فعلًا."
        ),
        topic_hint="أجمكان",
    ),
    Concept(
        key="invitation",
        name_ar="الدعوة",
        kicker="إجازتك القادمة",
        headline_template="جاهز لـ{topic}؟",
        scene_count=5,
        title_scene_seconds=3.0,
        photo_scene_seconds=3.2,
        outro_seconds=4.0,
        moves=("zoom_in", "pan_right", "zoom_out", "pan_left", "rise"),
        caption_opener="إجازتك على البحر تبدأ برسالة واحدة ✈️",
        hashtags=BASE_TAGS + ("احجز_الآن", "عروض"),
        guidance=(
            "إيقاع سريع وطاقة عالية. العناوين وعود قصيرة (إقامة، غروب، "
            "هدوء، بحر)، والختام يركّز على الحجز والرقم."
        ),
        topic_hint="إجازة على البحر",
    ),
)


CONCEPT_BY_KEY = {c.key: c for c in CONCEPTS}


def next_concept(cycle: int) -> Concept:
    """يختار الفكرة بالتناوب حسب رقم الدورة — لا تكرار قبل ٦ دورات (١٨ يومًا)."""
    return CONCEPTS[cycle % len(CONCEPTS)]


def hashtag_line(concept: Concept, extra: tuple[str, ...] = ()) -> str:
    tags = list(dict.fromkeys(concept.hashtags + extra))
    return " ".join(f"#{t}" for t in tags)
