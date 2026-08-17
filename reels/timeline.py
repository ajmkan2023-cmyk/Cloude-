"""يربط المشاهد ببعضها: الانتقالات، شريط التقدّم، وعلامة العلامة التجارية."""

from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image, ImageDraw

from . import imagefx as fx
from . import motion as mo
from . import typography as ty
from .config import brand
from .scenes import Scene, paste_alpha
from .styles import Style

B = brand()
W, H = B.video.width, B.video.height
TOP = B.video.safe_top


@dataclass
class Timeline:
    scenes: list[Scene]
    style: Style = field(default_factory=Style)
    watermark_from: int = 1          # أول مشهد تظهر فيه العلامة الصغيرة

    _starts: list[float] = field(default_factory=list, repr=False)
    _mark: Image.Image = field(default=None, repr=False)
    _handle: Image.Image = field(default=None, repr=False)

    @property
    def transition(self) -> float:
        return self.style.transition_seconds

    @property
    def grain(self) -> bool:
        return self.style.grain

    # ------------------------------------------------------------ التحضير
    def prepare(self) -> None:
        for scene in self.scenes:
            scene.prepare()

        t = 0.0
        self._starts = []
        for i, scene in enumerate(self.scenes):
            self._starts.append(t)
            t += scene.duration - (self.transition if i < len(self.scenes) - 1 else 0)

        mark = Image.open(B.logo_mark).convert("RGBA")
        h = 78
        self._mark = mark.resize((int(mark.width * h / mark.height), h), Image.LANCZOS)

        handle_block = ty.wrap(
            B.handle,
            ty.TextStyle(role="latin", size=30, align="right", tracking=1,
                         direction="ltr", language="en",
                         fill=(*B.color("white"), 215), shadow=(0, 0, 0, 130), shadow_blur=8),
        )
        layer = ty.render_block(handle_block, (W, H), (W, 0))
        box = layer.getbbox()
        self._handle = layer.crop(box) if box else layer

    @property
    def duration(self) -> float:
        if not self._starts:
            self.prepare()
        return self._starts[-1] + self.scenes[-1].duration

    # ------------------------------------------------------------ الإطارات
    def _active(self, t: float) -> list[tuple[int, float]]:
        """يعيد المشاهد الحيّة في لحظة ما مع زمنها المحلي."""
        out = []
        for i, scene in enumerate(self.scenes):
            start = self._starts[i]
            if start - 1e-6 <= t < start + scene.duration:
                out.append((i, t - start))
        return out or [(len(self.scenes) - 1, self.scenes[-1].duration - 1e-3)]

    def frame(self, t: float, index: int) -> Image.Image:
        active = self._active(t)

        i0, lt0 = active[0]
        img = self.scenes[i0].frame(lt0)

        if len(active) > 1:
            i1, lt1 = active[1]
            progress = mo.ease_in_out(lt1 / max(1e-6, self.transition))
            nxt = self.scenes[i1].frame(lt1)
            img = self._blend(img, nxt, progress, i1)

        self._furniture(img, t, i0)
        return fx.finish(img, index, grain_on=self.grain)

    def _blend(self, cur: Image.Image, nxt: Image.Image, progress: float, index: int) -> Image.Image:
        """الانتقال بين مشهدين حسب النمط المطلوب."""
        kind = self.style.transition

        if kind == "slide":
            # المشهد الجديد يدخل من اليمين مع اتجاه القراءة العربي
            offset = int(W * (1 - progress))
            out = cur.copy()
            out.alpha_composite(nxt.crop((0, 0, W - offset, H)), (offset, 0))
            return out

        if kind == "zoom":
            # المشهد الجديد يبدأ مكبّرًا ثم يستقرّ — انتقال «سينمائي»
            if progress < 0.999:
                scale = 1.0 + 0.08 * (1 - progress)
                zw, zh = int(W * scale), int(H * scale)
                nxt = nxt.resize((zw, zh), Image.BILINEAR).crop(
                    ((zw - W) // 2, (zh - H) // 2, (zw - W) // 2 + W, (zh - H) // 2 + H)
                )
            return Image.blend(cur, nxt, progress)

        # fade: مزج بسيط مع تقريب طفيف جدًا
        if progress < 0.999:
            scale = 1.0 + 0.035 * (1 - progress)
            zw, zh = int(W * scale), int(H * scale)
            nxt = nxt.resize((zw, zh), Image.BILINEAR).crop(
                ((zw - W) // 2, (zh - H) // 2, (zw - W) // 2 + W, (zh - H) // 2 + H)
            )
        return Image.blend(cur, nxt, progress)

    def _furniture(self, img: Image.Image, t: float, scene_index: int) -> None:
        """العناصر الثابتة فوق كل المشاهد: شريط التقدّم + العلامة الصغيرة."""
        total = self.duration
        last = len(self.scenes) - 1
        accent = B.color(self.style.accent)
        draw = ImageDraw.Draw(img)

        if scene_index != last and self.style.progress == "bar":
            bar_y = TOP - 34
            draw.rounded_rectangle((84, bar_y, W - 84, bar_y + 5), 3, fill=(255, 255, 255, 55))
            width = int((W - 168) * mo.clamp01(t / total))
            if width > 6:
                draw.rounded_rectangle((84, bar_y, 84 + width, bar_y + 5), 3, fill=(*accent, 235))

        elif scene_index != last and self.style.progress == "dots":
            # نقطة لكل مشهد صورة، تُملأ عند بلوغه
            photo_scenes = max(1, last - 1)
            cy, gap, r = TOP - 30, 26, 6
            start_x = W // 2 - (photo_scenes - 1) * gap // 2
            for i in range(photo_scenes):
                filled = scene_index >= i + 1
                cx = start_x + i * gap
                draw.ellipse((cx - r, cy - r, cx + r, cy + r),
                             fill=(*accent, 240) if filled else (255, 255, 255, 70))

        if self.style.watermark != "none" and self.watermark_from <= scene_index < last:
            a = mo.ease_out_cubic(mo.window(t, self._starts[self.watermark_from], 0.6)) * 0.92
            if self.style.watermark == "top_left":
                mark_x, handle_x = 84, 84
            else:
                mark_x = W - 84 - self._mark.width
                handle_x = W - 84 - self._handle.width
            paste_alpha(img, self._mark, (mark_x, TOP - 6), a)
            paste_alpha(img, self._handle, (handle_x, TOP + self._mark.height + 2), a * 0.9)
