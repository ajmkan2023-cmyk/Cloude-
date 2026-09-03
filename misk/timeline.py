"""الخطّ الزمني: يرتّب المشاهد، ويذيب بينها، ويضيف الطبقات الثابتة.

كل مشهد يرسم على طبقة شفّافة مستقلّة، فيصبح المزج بين مشهدين مسألة
شفافية لا أكثر — وهذا ما يسمح بالذوبان المتقاطع الهادئ بدل القطع الحادّ.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from . import motion as M
from . import ornament as orn
from . import paint
from .atmosphere import Atmosphere
from .config import VIDEO, color
from .scenes import Scene


@dataclass
class Cue:
    scene: Scene
    start: float
    fade_in: float = 1.0
    fade_out: float = 1.0

    @property
    def duration(self) -> float:
        return self.scene.duration

    @property
    def end(self) -> float:
        return self.start + self.duration

    def opacity(self, t: float) -> float:
        local = t - self.start
        if local < -0.05 or local > self.duration + 0.05:
            return 0.0
        rise = M.ease_in_out_sine(local / self.fade_in) if self.fade_in > 0 else 1.0
        fall = (M.ease_in_out_sine((self.duration - local) / self.fade_out)
                if self.fade_out > 0 else 1.0)
        return M.clamp(min(rise, fall))


class Timeline:
    """يجمع المشاهد ويخرج إطارًا جاهزًا عند أي لحظة."""

    def __init__(self, scenes: list[Scene], *, crossfade: float = 1.1,
                 frame_fade_in: float = 2.6, open_fade: float = 1.2,
                 close_fade: float = 2.0, atmosphere: bool = True,
                 show_frame: bool = True, tail: float = 0.6):
        self.crossfade = crossfade
        self.frame_fade_in = frame_fade_in
        self.open_fade = open_fade
        self.close_fade = close_fade
        self.show_frame = show_frame
        self.tail = tail
        self.atmos = Atmosphere(VIDEO.size) if atmosphere else None

        self.cues: list[Cue] = []
        clock = 0.0
        for i, scene in enumerate(scenes):
            self.cues.append(Cue(
                scene=scene,
                start=clock,
                fade_in=min(crossfade, scene.duration / 2) if i else open_fade,
                fade_out=min(crossfade, scene.duration / 2),
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
        self._ready = True

    def frame(self, t: float) -> Image.Image:
        """يبني الإطار عند اللحظة ‎t‎ (بالثواني) ويعيده RGBA."""
        self.prepare()
        base = self._paper.copy()

        # ضوء واسع يتنقّل ببطء شديد — يمنع سكون الخلفية التام
        hx = VIDEO.width * (0.5 + 0.20 * M.breathe(t, 26.0))
        hy = VIDEO.height * (0.34 + 0.09 * M.breathe(t + 7, 19.0))
        paint.stamp(base, self._halo, (hx - self._halo.width / 2, hy - self._halo.height / 2))

        if self.atmos:
            self.atmos.draw(base, t)

        for cue in self.cues:
            a = cue.opacity(t)
            if a <= 0.01:
                continue
            content = paint.blank(VIDEO.size)
            cue.scene.draw(content, t - cue.start)
            paint.stamp(base, content, (0, 0), a)

        if self.show_frame:
            fa = M.seg(t, 0.4, self.frame_fade_in, M.ease_in_out_sine)
            close = M.clamp((self.duration - t) / max(0.1, self.close_fade))
            paint.stamp_mask(base, self._frame_mask, color("gold", 150), (0, 0),
                             fa * M.ease_in_out_sine(close))

        paint.stamp(base, self._vignette)
        paint.stamp(base, self._grain, (0, 0), 0.75)

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
