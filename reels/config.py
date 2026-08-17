"""تحميل الهوية البصرية والإعدادات العامة."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND_FILE = ROOT / "brand" / "brand.json"


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


@dataclass(frozen=True)
class Video:
    width: int
    height: int
    fps: int
    safe_top: int
    safe_bottom: int
    safe_side: int


class Brand:
    def __init__(self, data: dict):
        self._data = data
        self.name_ar: str = data["name_ar"]
        self.name_en: str = data["name_en"]
        self.handle: str = data["handle"]
        self.tagline_ar: str = data["tagline_ar"]
        self.contact_phone: str = data.get("contact_phone", "")
        self.contact_label_ar: str = data.get("contact_label_ar", "للحجز والاستفسار")
        self.location: dict = data.get("location", {})
        self.voice: dict = data["voice"]
        self.video = Video(**data["video"])
        self._colors = {k: hex_to_rgb(v) for k, v in data["colors"].items()}
        self._fonts = {k: ROOT / v for k, v in data["fonts"].items()}
        self.logo_mark = ROOT / data["logo"]["mark"]
        self.wordmark_text: str = data["logo"]["wordmark_text"]

    @property
    def location_line(self) -> str:
        return self.location.get("line_ar", "")

    # ألوان -------------------------------------------------------------
    def color(self, name: str, alpha: int | None = None):
        rgb = self._colors[name]
        return rgb if alpha is None else (*rgb, alpha)

    @property
    def colors(self) -> dict[str, tuple[int, int, int]]:
        return dict(self._colors)

    # خطوط -------------------------------------------------------------
    def font_path(self, role: str) -> Path:
        path = self._fonts[role]
        if not path.exists():  # احتياط: خط عربي من النظام
            for candidate in (
                Path("/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf"),
                Path("/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"),
                Path("/usr/share/fonts/truetype/freefont/FreeSerif.ttf"),
            ):
                if candidate.exists():
                    return candidate
            raise FileNotFoundError(f"خط مفقود: {path}")
        return path


@lru_cache(maxsize=1)
def brand() -> Brand:
    return Brand(json.loads(BRAND_FILE.read_text(encoding="utf-8")))
