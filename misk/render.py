"""التصدير إلى MP4 — بلا مسار صوتي، كما هو مطلوب."""

from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg

from .config import VIDEO
from .timeline import Timeline


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def render(timeline: Timeline, out_path: str | Path, *, crf: int = 17,
           fps: int | None = None, progress_every: int = 30) -> Path:
    """يرسم كل إطار في بايثون ويمرّره خامًا إلى ffmpeg."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    timeline.prepare()
    fps = fps or VIDEO.fps
    w, h = VIDEO.width, VIDEO.height
    total = max(1, int(round(timeline.duration * fps)))

    cmd = [
        ffmpeg_exe(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
        "-i", "pipe:0",
        "-an",                                   # صامت — لا مسار صوت إطلاقًا
        "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
        "-movflags", "+faststart", "-r", str(fps),
        str(out_path),
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for i in range(total):
            frame = timeline.frame(i / fps).convert("RGB")
            proc.stdin.write(frame.tobytes())
            if progress_every and i % progress_every == 0:
                print(f"  إطار {i:4d}/{total}  ({100 * i / total:5.1f}%)", flush=True)
    finally:
        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
        code = proc.wait()

    if code != 0:
        raise RuntimeError(f"فشل ffmpeg (رمز {code}):\n{err[-3000:]}")
    print(f"✔ {out_path}  —  {total} إطار / {timeline.duration:.1f} ثانية / بلا صوت")
    return out_path


def poster(timeline: Timeline, out_path: str | Path, at: float) -> Path:
    """يصدّر إطارًا واحدًا كصورة غلاف."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    timeline.prepare()
    timeline.frame(at).convert("RGB").save(out_path, quality=95)
    print(f"✔ {out_path}  (عند {at:.1f}s)")
    return out_path


def contact_sheet(timeline: Timeline, out_dir: str | Path, times: list[float]) -> list[Path]:
    """يصدّر لقطات عند لحظات محدّدة — للمراجعة السريعة قبل الإخراج الكامل."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timeline.prepare()
    paths = []
    for t in times:
        p = out_dir / f"t{t:06.2f}.jpg".replace(".", "_", 1)
        timeline.frame(t).convert("RGB").save(p, quality=92)
        paths.append(p)
        print(f"  · {p.name}")
    return paths
