"""فهرس الصور — ما الذي *في* كل صورة فعلًا.

المشكلة التي يحلّها هذا الملف: لا يجوز أن يقول النص «البحر قدّامك» فوق صورة
غرفة نوم. لذلك قبل كتابة أي خطة يقرأ كلود محتوى كل صورة من درايف ويسجّله
هنا، ثم يتحقّق المحرّك آليًا من تطابق النص مع الصورة ويرفض الخطة عند التناقض.

بنية `assets/catalog.json`:

```jsonc
{
  "DSC03144.JPG": {
    "path": "assets/incoming/DSC03144.JPG",
    "tags": ["بحر", "شاطئ", "غروب"],
    "description": "شاطئ رملي وقت الغروب مع موج هادئ",
    "people": false,
    "time": "غروب",          // صباح | نهار | غروب | ليل
    "quality": "جيدة",        // جيدة | متوسطة | ضعيفة
    "vertical_ok": true        // هل تصلح للقصّ العمودي دون فقد الموضوع
  }
}
```
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

CATALOG_PATH = Path("assets/catalog.json")

# مفردات الوسوم المعتمدة — كل وسم يقابل كلمات قد ترد في النص
TAG_VOCABULARY: dict[str, tuple[str, ...]] = {
    "بحر":     ("بحر", "موج", "شاطئ", "رمل", "بحري", "الخليج"),
    "شاطئ":    ("شاطئ", "رمل", "رملي", "كورنيش"),
    "غروب":    ("غروب", "الغروب", "شفق", "برتقالي", "ذهبي", "المغيب"),
    "شروق":    ("شروق", "الشروق", "فجر", "الصباح", "صباح"),
    "ليل":     ("ليل", "ليلي", "نجوم", "قمر", "مساء"),
    "نخيل":    ("نخيل", "نخلة", "سعف"),
    "مسبح":    ("مسبح", "سباحة", "بركة"),
    "جلسة":    ("جلسة", "جلسات", "كنب", "مقاعد", "طاولة", "جلوس"),
    "غرفة":    ("غرفة", "نوم", "سرير", "داخلي", "الداخل", "غرف"),
    "مطعم":    ("مطعم", "طعام", "قهوة", "إفطار", "عشاء", "وجبة", "مشويات"),
    "عائلة":   ("عائلة", "عائلي", "أطفال", "أطفالك", "لمّة", "أصدقاء"),
    "مبنى":    ("مبنى", "فيلا", "استراحة", "واجهة"),
    "طبيعة":   ("طبيعة", "خضرة", "أشجار", "حديقة", "زرع"),
    "سماء":    ("سماء", "غيوم", "أفق"),
    "صالة":    ("صالة", "مجلس", "جلوس", "تلفزيون", "أريكة"),
    "مطبخ":    ("مطبخ", "طبخ"),
    "حمام":    ("حمام", "دورة مياه", "مغسلة"),
    "إطلالة":  ("إطلالة", "نافذة", "شرفة", "بلكونة", "تطل"),
}

# وسوم متنافرة: وجود اليمين في الصورة يمنع كلمات اليسار في النص
CONFLICTS: tuple[tuple[str, str], ...] = (
    ("غرفة", "بحر"),
    ("غرفة", "شاطئ"),
    ("مطعم", "بحر"),
    ("ليل", "شروق"),
    ("ليل", "غروب"),
)


@dataclass
class Entry:
    path: str
    tags: list[str] = field(default_factory=list)
    description: str = ""
    people: bool = False
    time: str = ""
    quality: str = "جيدة"
    vertical_ok: bool = True

    @property
    def name(self) -> str:
        return Path(self.path).name


class Catalog:
    def __init__(self, entries: dict[str, Entry]):
        self.entries = entries

    # ----------------------------------------------------------------
    @classmethod
    def load(cls, path: str | Path = CATALOG_PATH) -> "Catalog":
        path = Path(path)
        if not path.exists():
            return cls({})
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls({k: Entry(**v) for k, v in raw.items()})

    def save(self, path: str | Path = CATALOG_PATH) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: vars(v) for k, v in self.entries.items()}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def for_photo(self, photo_path: str) -> Entry | None:
        name = Path(photo_path).name
        return self.entries.get(name)

    def with_tag(self, tag: str) -> list[Entry]:
        return [e for e in self.entries.values() if tag in e.tags]

    # ----------------------------------------------------------------
    def check_text(self, photo_path: str, *texts: str) -> list[str]:
        """يتحقّق أن ما يقوله النص موجود فعلًا في الصورة.

        يعيد قائمة تحذيرات فارغة إذا كان كل شيء متطابقًا.
        """
        entry = self.for_photo(photo_path)
        if entry is None:
            return [f"«{Path(photo_path).name}» غير مفهرسة — لا يمكن التحقّق من مطابقة النص"]

        blob = " ".join(t for t in texts if t)
        if not blob.strip():
            return []

        warnings: list[str] = []
        mentioned = {
            tag for tag, words in TAG_VOCABULARY.items()
            if any(word in blob for word in words)
        }

        for tag in mentioned:
            if tag in entry.tags:
                continue
            # التناقض الصريح خطأ، والغياب البسيط تحذير
            hard = any(
                present in entry.tags and forbidden == tag
                for present, forbidden in CONFLICTS
            )
            level = "تناقض" if hard else "غير مؤكّد"
            warnings.append(
                f"{level}: النص يذكر «{tag}» بينما الصورة «{entry.name}» "
                f"موسومة بـ [{'، '.join(entry.tags) or 'بلا وسوم'}]"
            )

        if entry.quality == "ضعيفة":
            warnings.append(f"جودة «{entry.name}» ضعيفة — يُفضّل استبدالها")
        if not entry.vertical_ok:
            warnings.append(f"«{entry.name}» لا تصلح للقصّ العمودي — الموضوع سيُقطع")
        return warnings

    def hard_conflicts(self, photo_path: str, *texts: str) -> list[str]:
        return [w for w in self.check_text(photo_path, *texts) if w.startswith("تناقض")]
