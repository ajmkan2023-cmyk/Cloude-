"""سجلّ الحلقات — الذاكرة التي تمنع تكرار الكلام أو الشكل.

القوالب في `concepts.py` *أشكال استرشادية* لا نصوص نهائية. هذا الملف يقارن
كل حلقة جديدة بما سبقها ويصرخ عند أي تكرار: عنوان مُعاد، عبارة افتتاح
مكرّرة، عنوان لقطة سبق استخدامه، أو تصميم لم يتغيّر بما يكفي.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

HISTORY_PATH = Path("plans/history.json")

# كم مفتاح تصميم يجب أن يختلف عن أي حلقة سابقة
MIN_DESIGN_DIFF = 3
# نسبة التشابه النصّي التي تُعدّ تكرارًا
SIMILAR = 0.72


def normalize(text: str) -> str:
    """يوحّد النص لمقارنة عادلة: بلا تشكيل ولا تطويل ولا فروق ألف/همزة."""
    text = re.sub(r"[ً-ْـ]", "", text or "")
    text = re.sub(r"[إأآٱ]", "ا", text)
    text = re.sub(r"[ىي]", "ي", text).replace("ة", "ه")
    return re.sub(r"\s+", " ", text).strip()


def similar(a: str, b: str) -> float:
    a, b = normalize(a), normalize(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


@dataclass
class History:
    cycles: list[dict] = field(default_factory=list)
    note: str = "سجلّ الحلقات — تقرأه مهارة التصميم لتتجنّب تكرار الفكرة أو الشكل أو الكلام"

    # ------------------------------------------------------------------
    @classmethod
    def load(cls, path: str | Path = HISTORY_PATH) -> "History":
        path = Path(path)
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(cycles=data.get("cycles", []), note=data.get("note", cls.note))

    def save(self, path: str | Path = HISTORY_PATH) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"note": self.note, "cycles": self.cycles}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def previous(self, cycle: int) -> list[dict]:
        return [c for c in self.cycles if c.get("cycle") != cycle]

    # ------------------------------------------------------------------
    def echoes(self, plan) -> list[str]:
        """يعيد كل ما يتكرّر في هذه الحلقة مقارنةً بالسجلّ."""
        past = self.previous(plan.cycle)
        if not past:
            return []

        found: list[str] = []

        for old in past:
            n = old.get("cycle", "?")

            if similar(plan.headline, old.get("headline", "")) >= SIMILAR:
                found.append(f"العنوان يشبه عنوان الحلقة {n}: «{old.get('headline','')}»")

            opener = (plan.caption or "").split("\n")[0]
            old_opener = (old.get("caption_opener") or "").split("\n")[0]
            if similar(opener, old_opener) >= SIMILAR:
                found.append(f"افتتاحية المنشور تشبه الحلقة {n}: «{old_opener}»")

            old_titles = old.get("shot_titles", [])
            for shot in plan.shots:
                for old_title in old_titles:
                    if similar(shot.title, old_title) >= SIMILAR:
                        found.append(
                            f"عنوان اللقطة «{shot.title}» يشبه «{old_title}» من الحلقة {n}"
                        )

        # الفكرة نفسها في آخر ثلاث دورات
        recent = sorted(past, key=lambda c: c.get("cycle", 0))[-3:]
        if any(c.get("concept") == plan.concept for c in recent):
            found.append(f"الفكرة «{plan.concept}» استُخدمت في آخر ٣ دورات")

        found += self._design_echoes(plan, past)
        return list(dict.fromkeys(found))

    def _design_echoes(self, plan, past: list[dict]) -> list[str]:
        current = self._design_signature(plan)
        out = []
        for old in sorted(past, key=lambda c: c.get("cycle", 0))[-4:]:
            old_design = old.get("design", {})
            if not old_design:
                continue
            differing = sum(
                1 for key, value in current.items() if old_design.get(key) != value
            )
            if differing < MIN_DESIGN_DIFF:
                out.append(
                    f"التصميم يختلف عن الحلقة {old.get('cycle','?')} في {differing} مفاتيح فقط "
                    f"(المطلوب {MIN_DESIGN_DIFF} على الأقل)"
                )
        return out

    @staticmethod
    def _design_signature(plan) -> dict:
        st = plan.style_obj
        return {
            "caption": st.caption,
            "title_layout": st.title_layout,
            "number": st.number,
            "accent": st.accent,
            "outro_bg": st.outro_bg,
            "progress": st.progress,
            "watermark": st.watermark,
            "transition": st.transition,
        }

    # ------------------------------------------------------------------
    def record(self, plan) -> None:
        """يسجّل الحلقة — يستبدل أي تسجيل سابق لنفس رقم الدورة."""
        entry = {
            "cycle": plan.cycle,
            "concept": plan.concept,
            "topic": plan.topic,
            "headline": plan.headline,
            "caption_opener": (plan.caption or "").split("\n")[0],
            "shot_titles": [s.title for s in plan.shots],
            "photos": [Path(s.photo).name for s in plan.shots]
            + ([Path(plan.hero_photo).name] if plan.hero_photo else []),
            "design": self._design_signature(plan),
            "design_note": plan.design_note,
            "created": plan.created,
        }
        self.cycles = [c for c in self.cycles if c.get("cycle") != plan.cycle]
        self.cycles.append(entry)
        self.cycles.sort(key=lambda c: c.get("cycle", 0))
