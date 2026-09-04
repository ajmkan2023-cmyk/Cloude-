"""بناء الفيلم المصوّر: أربع عشرة لقطة، ثلاثة فصول، ونصّ يجلس في فراغ كل صورة.

التنوّع هنا مقصود ومحسوب لا عشوائي. ثلاثة محاور تتغيّر من لقطة لأخرى:
موضع النصّ في الإطار، واتجاه حركة الكاميرا، ومزاج الصورة (فاتح/داكن).
والفصل الثاني ينقلب إلى الظلمة عمدًا، لأن الذهب لا يلمع إلا هناك — وهذا
ما يعطي كشف الاسم وزنه.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import VIDEO, color
from .scenes import (BODY, CLOSING, KICKER, LEAD, NOTE, VERSE,
                     ImagePanel, NameReveal, Stack)
from .timeline import Timeline

ASSETS = Path("assets/misk")


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _shot(plan: dict, key: str) -> dict:
    return plan.get("shots", {}).get(key, {})


def _img(name: str) -> Path:
    return ASSETS / name


def build_scenes(plan: dict) -> list:
    d = plan.get("durations", {})
    omit = set(plan.get("omit", []))
    S = lambda k: _shot(plan, k)                                   # noqa: E731
    scenes: list = []

    def panel(image, key, build=None, **kw):
        """يعيد ‎None‎ للقطة مُسقَطة — الإسقاط من الخطّة لا من الكود،
        فتُستعاد اللقطة بحذف اسمها من ‎omit‎ دون لمس شيء."""
        if key in omit:
            return None
        return ImagePanel(_img(image), build, name=key,
                          duration=d.get(key, 5.4), **kw)

    def add(scene) -> None:
        if scene is not None:
            scenes.append(scene)

    # ── الفصل الأول: الضوء ──────────────────────────────────────────
    # ١ البسملة — نصّ في وسط الستارة المضيئة، والكاميرا تقترب ببطء
    def bismillah(s: Stack, ink, txt=S("bismillah")):
        s.text(txt.get("text", ""), VERSE, ink["soft"], delay=0.5, max_lines=2)
        s.gap(46)
        s.rule(400, delay=1.6, thickness=2, diamond=7, fill=ink["rule"])
    add(panel("01-dawn.jpg", "bismillah", bismillah,
                        zone="center", move="in", tone="light", scrim_strength=0.42))

    # ٢ فاصل حرير — بلا نصّ، تمرير أفقي يفتح النَّفَس
    add(panel("13-silk.jpg", "silk", None, zone="center", move="right",
                        tone="light", zoom=0.14))

    # ٣ الحمد — النصّ أعلى الكتّان، والكاميرا تصعد
    def praise(s: Stack, ink, txt=S("praise")):
        s.sprig(360, delay=0.3, fill=ink["rule"])
        s.gap(44)
        s.text(txt.get("text", ""), LEAD, ink["body"], delay=0.8, max_lines=3)
    add(panel("02-linen.jpg", "praise", praise,
                        zone="top", move="up", tone="light", scrim_strength=0.50))

    # ٤ الآية — وسط السماء، والكاميرا تبتعد فتتّسع الصورة
    def ayah(s: Stack, ink, txt=S("verse")):
        if txt.get("kicker"):
            s.text(txt["kicker"], KICKER, ink["kicker"], delay=0.4, max_lines=1)
            s.gap(38)
        s.text(txt.get("text", ""), VERSE, ink["body"], delay=0.85, max_lines=3)
        s.gap(40)
        s.rule(360, delay=2.1, thickness=2, diamond=6, fill=ink["rule"])
        s.gap(26)
        if txt.get("note"):
            s.text(txt["note"], NOTE, ink["faint"], delay=2.4, max_lines=1, shade=False)
    add(panel("03-sky.jpg", "verse", ayah,
                        zone="center", move="out", tone="light", scrim_strength=0.46))

    # ٥ البشرى — النصّ أعلى الزهر، اقتراب هادئ
    def bushra(s: Stack, ink, txt=S("news")):
        if txt.get("kicker"):
            s.text(txt["kicker"], KICKER, ink["accent"], delay=0.35, max_lines=1)
            s.gap(34)
        s.text(txt.get("text", ""), LEAD, ink["body"], delay=0.75, max_lines=3)
    add(panel("04-blossom.jpg", "news", bushra,
                        zone="top", move="in", tone="light", scrim_strength=0.48))

    # ٦ فاصل بتلات — بلا نصّ، هبوط. آخر ما يُرى قبل الظلمة
    add(panel("14-petals.jpg", "petals", None, zone="center", move="down",
                        tone="light", zoom=0.13))

    # ── الفصل الثاني: الاسم ─────────────────────────────────────────
    # ٧ كشف الاسم فوق الحرير الداكن — الذروة
    scenes.append(NameReveal(
        name_text=plan["name_ar"],
        kicker=plan.get("name_kicker", ""),
        subtitle=plan.get("kinship_ar", ""),
        latin=plan.get("name_latin", ""),
        duration=d.get("name", 9.2),
        image=_img("06-silk-gold.jpg"), tone="dark", move="in",
        zoom=0.09, scrim_strength=0.40,
    ))

    # ٨ الحديث — النصّ في الظلمة فوق قارورة الطيب
    def athar(s: Stack, ink, txt=S("hadith")):
        if txt.get("kicker"):
            s.text(txt["kicker"], KICKER, ink["kicker"], delay=0.4, max_lines=1)
            s.gap(36)
        s.text(txt.get("text", ""), LEAD, ink["body"], delay=0.85, max_lines=2)
        s.gap(38)
        s.rule(340, delay=2.0, thickness=2, diamond=6, fill=ink["rule"])
        s.gap(24)
        if txt.get("note"):
            s.text(txt["note"], NOTE, ink["faint"], delay=2.3, max_lines=1, shade=False)
    add(panel("07-musk.jpg", "hadith", athar,
                        zone="top", move="in", tone="dark", scrim_strength=0.44))

    # ── الفصل الثالث: البيت ─────────────────────────────────────────
    # ٩ اليد الصغيرة — نصّ قصير أعلى البطّانية
    def hand(s: Stack, ink, txt=S("hand")):
        s.text(txt.get("text", ""), LEAD, ink["body"], delay=0.6, max_lines=2)
    add(panel("05-hand.jpg", "hand", hand,
                        zone="top", move="in", tone="light", scrim_strength=0.52))

    # ١٠ المهد — ابتعاد يكشف الغرفة كلّها
    def crib(s: Stack, ink, txt=S("crib")):
        s.text(txt.get("text", ""), LEAD, ink["body"], delay=0.6, max_lines=2)
    add(panel("08-crib.jpg", "crib", crib,
                        zone="top", move="out", tone="light", scrim_strength=0.52))

    # ١١ الحذاء — التكوين إلى اليمين والنصّ إلى اليسار، تمرير أفقي
    def booties(s: Stack, ink, txt=S("booties")):
        s.text(txt.get("text", ""), LEAD, ink["body"], delay=0.6, max_lines=3)
    add(panel("09-booties.jpg", "booties", booties,
                        zone="left", move="right", tone="light",
                        scrim_strength=0.52, text_width=0.54))

    # ١٢ الدعاء — أطول مشهد، الأسطر تتوالى في الظلمة
    def prayer(s: Stack, ink, txt=S("dua")):
        if txt.get("kicker"):
            s.text(txt["kicker"], KICKER, ink["kicker"], delay=0.3, max_lines=1)
            s.gap(40)
        s.text(txt.get("text", ""), BODY, ink["body"], delay=0.75,
               stagger=0.46, max_lines=6)
    add(panel("10-candle.jpg", "dua", prayer,
                        zone="top", move="in", tone="dark", scrim_strength=0.40))

    # ١٣ الختام — الاسم كاملًا على الجدار المضيء
    fin = plan.get("finale", {})

    def closing(s: Stack, ink, f=fin):
        # حبر داكن لا ذهب: الذهب استُهلك في كشف الاسم، وتكراره على خلفية
        # دافئة يُذهب أثره ويُذهب معه القراءة.
        s.text(f.get("name", ""), CLOSING, ink["body"], delay=0.5, max_lines=1)
        s.gap(40)
        s.rule(420, delay=1.2, thickness=2, diamond=8, fill=ink["rule"])
        if f.get("date"):
            s.gap(34)
            s.text(f["date"], NOTE, ink["faint"], delay=1.5, max_lines=1, shade=False)
        if f.get("blessing"):
            s.gap(52)
            s.text(f["blessing"], BODY, ink["soft"], delay=1.9, max_lines=3)
        if f.get("family"):
            s.gap(46)
            s.text(f["family"], NOTE, ink["faint"], delay=2.6, max_lines=2, shade=False)
    # ١٣ فاصل الجدار — صامت. ظلال الأوراق جميلة لكنها تقطع أي نصّ فوقها
    add(panel("11-wall.jpg", "wall", None, zone="center", move="left",
                        tone="light", zoom=0.13))

    # ١٤ الختام — على البوكيه: خلفية موحّدة بلا تفاصيل تنازع الاسم
    add(panel("12-bokeh.jpg", "finale", closing,
                        zone="center", move="in", tone="light",
                        scrim_strength=0.58, zoom=0.14, text_width=0.74))

    return scenes


def build_timeline(plan: dict) -> Timeline:
    scenes = build_scenes(plan)
    tl = Timeline(
        scenes,
        crossfade=plan.get("crossfade", 0.9),
        atmosphere=False,                       # الجسيمات كانت تعوّض عن فقر الخلفية
        show_frame=plan.get("frame", True),
        frame_alpha=plan.get("frame_alpha", 105),
    )
    # وميض ذهبي عند الدخول إلى كشف الاسم — الانتقال الوحيد المسموح له أن يُرى
    for cue in tl.cues:
        if cue.scene.name == "name":
            cue.flash = plan.get("name_flash", 0.55)
    return tl


def outline(plan: dict) -> str:
    tl = build_timeline(plan)
    rows = [f"{'المشهد':<12}{'يبدأ':>8}{'ينتهي':>8}{'المدّة':>8}   الصورة"]
    for cue in tl.cues:
        sc = cue.scene
        src = getattr(getattr(sc, "plate", None), "path", None)
        rows.append(f"{sc.name:<12}{cue.start:>8.1f}{cue.end:>8.1f}{cue.duration:>8.1f}"
                    f"   {src.name if src else '—'}")
    rows.append(f"\nالمجموع: {tl.duration:.1f} ثانية  ·  {VIDEO.width}×{VIDEO.height}"
                f"  ·  {VIDEO.fps}fps  ·  بلا صوت")
    return "\n".join(rows)
