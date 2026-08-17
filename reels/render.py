"""تصدير الإطارات إلى ملف MP4 جاهز لتيك توك عبر ffmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg

from .config import brand
from .timeline import Timeline

B = brand()


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def render(
    timeline: Timeline,
    out_path: str | Path,
    audio: str | Path | None = None,
    crf: int = 18,
    progress_every: int = 30,
) -> Path:
    """يرسم كل إطار في بايثون ويمرّره خامًا إلى ffmpeg."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    timeline.prepare()
    fps = B.video.fps
    w, h = B.video.width, B.video.height
    total_frames = max(1, int(round(timeline.duration * fps)))

    cmd = [
        ffmpeg_exe(), "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{w}x{h}", "-r", str(fps), "-i", "pipe:0",
    ]
    if audio:
        cmd += ["-i", str(audio), "-shortest", "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    cmd += [
        "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
        "-movflags", "+faststart", "-r", str(fps),
        str(out_path),
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE)
    assert proc.stdin is not None

    try:
        for i in range(total_frames):
            t = i / fps
            frame = timeline.frame(t, i).convert("RGB")
            proc.stdin.write(frame.tobytes())
            if progress_every and i % progress_every == 0:
                pct = 100 * i / total_frames
                print(f"  إطار {i:4d}/{total_frames}  ({pct:5.1f}%)", flush=True)
    finally:
        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
        code = proc.wait()

    if code != 0:
        raise RuntimeError(f"فشل ffmpeg (رمز {code}):\n{err[-3000:]}")

    print(f"✔ تم الإخراج: {out_path}  ({total_frames} إطار / {timeline.duration:.1f} ثانية)")
    return out_path


def render_poster(timeline: Timeline, out_path: str | Path, at: float = 1.6) -> Path:
    """يصدّر صورة غلاف (ثامبنيل) من لحظة محدّدة."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    timeline.prepare()
    frame = timeline.frame(min(at, timeline.duration - 0.05), int(at * B.video.fps))
    frame.convert("RGB").save(out_path, quality=95)
    print(f"✔ صورة الغلاف: {out_path}")
    return out_path
