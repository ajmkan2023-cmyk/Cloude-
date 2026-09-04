"""الخطّ الزمني: يرتّب المشاهد، ويذيب بينها، ويضيف الطبقات الثابتة.

الذوبان هنا حقيقي لا تراكميّ: المشهد الخارج يُرسم كاملًا، والداخل فوقه
بشفافية متصاعدة. لو رُسم الاثنان بشفافية جزئية لتسرّبت الخلفية بينهما
وشحبت اللقطات الداكنة عند كل انتقال.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image

from . import motion as M
from . import ornament as orn
from . import paint
from .atmosphere import Atmosphere
from .config import VIDEO, color
from .scenes import Scene


def _bump(t: float, center: float, width: float) -> float:
    """نتوء ناعم يبلغ ١ عند المركز ويعود إلى صفر عند حافّتي العرض."""
    u = abs(t - center) / max(1e-6, width / 2)
    return 0.0 if u >= 1 else (math.cos(math.pi * u) + 1) / 2


@dataclass
class Cue:
    scene: Scene
    start: float
    fade_in: float = 0.9
    flash: float = 0.0          # وميض ذهبي عند الدخول — للحظة واحدة في الفيلم

    @property
    def duration(self) -> float:
        return self.scene.duration

    @property
    def end(self) -> float:
        return self.start + self.duration

    def rise(self, t: float) -> float:
        """تصاعد الظهور: صفر قبل البداية، وواحد بعد اكتمال الذوبان."""
        if self.fade_in <= 0:
            return 1.0 if t >= self.start else 0.0
        return M.clamp(M.ease_in_out_sine((t - self.start) / self.fade_in))


class Timeline:
    """يجمع المشاهد ويخرج إطارًا جاهزًا عند أي لحظة."""

    def __init__(self, scenes: list[Scene], *, crossfade: float = 0.9,
                 frame_fade_in: float = 2.6, open_fade: float = 1.2,
                 close_fade: float = 2.0, atmosphere: bool = True,
                 show_frame: bool = True, frame_alpha: int = 130,
                 tail: float = 0.5):
        self.crossfade = crossfade
        self.frame_fade_in = frame_fade_in
        self.open_fade = open_fade
        self.close_fade = close_fade
        self.show_frame = show_frame
        self.frame_alpha = frame_alpha
        self.tail = tail
        self.atmos = Atmosphere(VIDEO.size) if atmosphere else None

        self.cues: list[Cue] = []
        clock = 0.0
        for i, scene in enumerate(scenes):
            self.cues.append(Cue(
                scene=scene, start=clock,
                fade_in=(min(crossfade, scene.duration / 2) if i else open_fade),
            ))
            clock += scene.duration - crossfade
        self.duration = (self.cues[-1].end + tail) if self.cues else 0.0
        self._ready = False

    # ------------------------------------------------------------------
    def prepare(self) -> None:
        if self._ready:
            return
        for cue in self.cues:
            cue.scene.prepare()
        self._paper = paint.paper(VIDEO.size)
        self._frame_mask = orn.page_frame(VIDEO.size, VIDEO.frame_inset, 190, 2)
        self._vignette = paint.vignette(VIDEO.size, 44)
        self._grain = paint.grain(VIDEO.size, 3, 23)
        halo = int(min(VIDEO.size) * 1.5)
        self._halo = paint.radial((halo, halo), (halo / 2, halo / 2), halo / 2,
                                  (*color("paper_cool"), 92), (*color("paper_cool"), 0), 1.5)
        self._flash = paint.solid(VIDEO.size, color("gold_light"))
        self._ready = True

    def _visible(self, t: float) -> list[tuple[int, Cue]]:
        """المشاهد التي تُرسم فعلًا: نُسقط ما غطّاه مشهدٌ لاحق تمامًا."""
        active = [(i, c) for i, c in enumerate(self.cues)
                  if c.start - 0.05 <= t <= c.end + 0.05]
        out: list[tuple[int, Cue]] = []
        for j, (i, cue) in enumerate(active):
            if any(later.rise(t) >= 0.999 for _, later in active[j + 1:]):
                continue
            out.append((i, cue))
        return out

    def frame(self, t: float) -> Image.Image:
        """يبني الإطار عند اللحظة ‎t‎ (بالثواني) ويعيده RGBA."""
        self.prepare()
        base = self._paper.copy()

        if self.atmos:
            hx = VIDEO.width * (0.5 + 0.20 * M.breathe(t, 26.0))
            hy = VIDEO.height * (0.34 + 0.09 * M.breathe(t + 7, 19.0))
            paint.stamp(base, self._halo,
                        (hx - self._halo.width / 2, hy - self._halo.height / 2))
            self.atmos.draw(base, t)

        visible = self._visible(t)
        for j, (i, cue) in enumerate(visible):
            # الخارج يُرسم كاملًا؛ الداخل فوقه بشفافية متصاعدة
            a = cue.rise(t) if (j > 0 or i == 0) else 1.0
            if a <= 0.004:
                continue
            content = paint.blank(VIDEO.size)
            cue.scene.draw(content, t - cue.start)
            paint.stamp(base, content, (0, 0), a)

        if self.show_frame:
            fa = M.seg(t, 0.4, self.frame_fade_in, M.ease_in_out_sine)
            close = M.clamp((self.duration - t) / max(0.1, self.close_fade))
            paint.stamp_mask(base, self._frame_mask, color("gold", self.frame_alpha),
                             (0, 0), fa * M.ease_in_out_sine(close))

        paint.stamp(base, self._vignette)
        paint.stamp(base, self._grain, (0, 0), 0.75)

        # وميض ذهبي عابر عند الدخول إلى المشهد المعلَّم به
        for cue in self.cues:
            if cue.flash <= 0:
                continue
            spike = _bump(t, cue.start + cue.fade_in * 0.42, 1.0)
            if spike > 0.004:
                paint.stamp(base, self._flash, (0, 0), cue.flash * spike)

        # فتح من بياض الورق وإغلاق إليه
        veil = 0.0
        if t < self.open_fade:
            veil = 1 - M.ease_in_out_sine(t / self.open_fade)
        tail_start = self.duration - self.close_fade
        if t > tail_start:
            veil = max(veil, M.ease_in_out_sine((t - tail_start) / self.close_fade))
        if veil > 0.002:
            paint.stamp(base, paint.solid(VIDEO.size, color("paper_cool")), (0, 0), veil)

        return base
