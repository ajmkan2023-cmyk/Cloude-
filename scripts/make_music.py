"""يولّد مقطعًا موسيقيًا أصليًا بهوية أجمكان — هادئ ودافئ كغروب على البحر.

لماذا التوليد بدل التنزيل: الموسيقى التجارية بلا ترخيص تُعرّض الفيديو للكتم
أو الحذف على تيك توك. هذا المقطع مُولَّد بالكامل هنا، فلا حقوق على أحد.

الشكل: وسادة هارمونية دافئة (pad) + أربيجيو ناعم + نبض خفيف، على تتابع
F – C – Dm – B♭ بإيقاع ٧٦ نبضة، مع صدى وترشيح يمنعان الحدّة الرقمية.

    python scripts/make_music.py --cycle 2 --seconds 26
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np

SR = 44100
OUT = Path("assets/audio/track.m4a")

# نصف نغمة = النسبة ٢^(١/١٢) — تُستخدم لبناء التآلفات من نغمة الأساس
SEMI = 2 ** (1 / 12)


def chord(root: float, kind: str) -> tuple[float, float, float]:
    """تآلف ثلاثي من نغمة أساس: كبير (مبتهج) أو صغير (حنون)."""
    third = 4 if kind == "maj" else 3
    return root, root * SEMI**third, root * SEMI**7


# أمزجة موسيقية — لكل حلقة مزاج مختلف، كما يختلف تصميمها
MOODS: dict[str, dict] = {
    "warm": {   # دافئ متفائل — مناسب لجولة أو دعوة
        "name_ar": "دافئ",
        "bpm": 76,
        "roots": [(349.23, "maj"), (261.63, "maj"), (293.66, "min"), (233.08, "maj")],
        "pad_cut": 1500, "arp_cut": 3200, "pulse": True,
        "arp_gain": 0.085, "pad_gain": 0.20, "reverb": 0.34, "detune": 0.0016,
    },
    "night": {  # ليلي هادئ — للمسبح والإضاءة المسائية
        "name_ar": "ليلي",
        "bpm": 66,
        "roots": [(220.00, "min"), (174.61, "maj"), (261.63, "maj"), (196.00, "maj")],
        "pad_cut": 1050, "arp_cut": 2400, "pulse": False,
        "arp_gain": 0.070, "pad_gain": 0.23, "reverb": 0.46, "detune": 0.0022,
    },
    "bright": {  # نهاري نشِط — لإيقاع سريع
        "name_ar": "نهاري",
        "bpm": 94,
        "roots": [(261.63, "maj"), (196.00, "maj"), (220.00, "min"), (174.61, "maj")],
        "pad_cut": 1900, "arp_cut": 4200, "pulse": True,
        "arp_gain": 0.105, "pad_gain": 0.17, "reverb": 0.26, "detune": 0.0012,
    },
    "sunset": {  # غروب حنون — نبرة شاعرية
        "name_ar": "غروب",
        "bpm": 70,
        "roots": [(233.08, "maj"), (174.61, "maj"), (196.00, "min"), (155.56, "maj")],
        "pad_cut": 1250, "arp_cut": 2800, "pulse": False,
        "arp_gain": 0.078, "pad_gain": 0.22, "reverb": 0.42, "detune": 0.0020,
    },
    "breeze": {  # نسيم خفيف — أجواء عائلية
        "name_ar": "نسيم",
        "bpm": 84,
        "roots": [(196.00, "maj"), (293.66, "maj"), (246.94, "min"), (261.63, "maj")],
        "pad_cut": 1700, "arp_cut": 3600, "pulse": True,
        "arp_gain": 0.092, "pad_gain": 0.18, "reverb": 0.30, "detune": 0.0014,
    },
    "cinematic": {  # سينمائي واسع — للافتتاحيات القوية
        "name_ar": "سينمائي",
        "bpm": 72,
        "roots": [(293.66, "min"), (233.08, "maj"), (349.23, "maj"), (261.63, "maj")],
        "pad_cut": 1350, "arp_cut": 2600, "pulse": True,
        "arp_gain": 0.068, "pad_gain": 0.25, "reverb": 0.50, "detune": 0.0024,
    },
}

MOOD_KEYS = tuple(MOODS)


def next_mood(cycle: int) -> str:
    """المزاج يدور بست خطوات، فلا يتكرّر قبل ١٨ يومًا."""
    return MOOD_KEYS[(cycle - 1) % len(MOOD_KEYS)]


def adsr(n: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
    """مغلّف صوتي يمنع النقر الرقمي عند بداية النغمة ونهايتها."""
    a, d, r = int(n * attack), int(n * decay), int(n * release)
    s = max(0, n - a - d - r)
    return np.concatenate([
        np.linspace(0, 1, a, endpoint=False),
        np.linspace(1, sustain, d, endpoint=False),
        np.full(s, sustain),
        np.linspace(sustain, 0, r),
    ])[:n]


def voice(freq: float, n: int, harmonics: tuple[float, ...], detune: float = 0.0) -> np.ndarray:
    """نغمة مركّبة من توافقيات — التوافقيات هي ما يعطي الدفء بدل الصفير."""
    t = np.arange(n) / SR
    out = np.zeros(n, dtype=np.float32)
    for k, amp in enumerate(harmonics, start=1):
        f = freq * k
        if f > SR / 2.2:
            break
        out += amp * np.sin(2 * np.pi * f * t)
        if detune:
            out += amp * 0.55 * np.sin(2 * np.pi * f * (1 + detune) * t)
    return out


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    """ترشيح بسيط يزيل الحوافّ الحادّة (مرشّح أُسّي أحادي القطب)."""
    alpha = np.exp(-2 * np.pi * cutoff / SR)
    out = np.empty_like(x)
    acc = 0.0
    for i, sample in enumerate(x):
        acc = (1 - alpha) * sample + alpha * acc
        out[i] = acc
    return out


def reverb(x: np.ndarray, decay: float = 0.34, taps: int = 5, gap_ms: float = 71) -> np.ndarray:
    """صدى تقريبي بتكرارات متباعدة — يعطي إحساس المساحة."""
    out = x.copy()
    gap = int(SR * gap_ms / 1000)
    for i in range(1, taps + 1):
        shift = gap * i
        out[shift:] += x[:-shift] * (decay**i)
    return out


def build(seconds: float, mood: str) -> np.ndarray:
    m = MOODS[mood]
    progression = [chord(root, kind) for root, kind in m["roots"]]
    beat = 60 / m["bpm"]
    bar = beat * 4
    n_total = int(seconds * SR)
    mix = np.zeros(n_total, dtype=np.float32)

    bar_n = int(bar * SR)
    bars = int(np.ceil(seconds / bar))

    for b in range(bars):
        start = b * bar_n
        if start >= n_total:
            break
        notes = progression[b % len(progression)]
        length = min(bar_n, n_total - start)

        # وسادة هارمونية: أساس المزاج
        pad = np.zeros(length, dtype=np.float32)
        for f in notes:
            tone = voice(f / 2, length, (1.0, 0.42, 0.18, 0.08), detune=m["detune"])
            pad += tone * adsr(length, 0.22, 0.18, 0.72, 0.34)
        mix[start:start + length] += lowpass(pad, m["pad_cut"]) * m["pad_gain"]

        # أربيجيو: حركة خفيفة تمنع الرتابة
        step = int(beat * SR / 2)
        for k in range(8):
            s0 = start + k * step
            if s0 >= n_total:
                break
            ln = min(step * 2, n_total - s0)
            if ln <= 0:
                break
            f = notes[k % 3] * (2 if k % 4 >= 2 else 1)
            note = voice(f, ln, (1.0, 0.30, 0.10)) * adsr(ln, 0.01, 0.30, 0.16, 0.55)
            mix[s0:s0 + ln] += lowpass(note, m["arp_cut"]) * m["arp_gain"]

        # نبض منخفض هادئ (بعض الأمزجة بلا إيقاع)
        if m["pulse"]:
            for k in (0, 2):
                s0 = start + int(k * beat * SR)
                ln = min(int(0.22 * SR), n_total - s0)
                if ln <= 0:
                    continue
                t = np.arange(ln) / SR
                sweep = np.sin(2 * np.pi * (110 * np.exp(-t * 22)) * t)
                mix[s0:s0 + ln] += (sweep * np.exp(-t * 16) * 0.16).astype(np.float32)

    mix = reverb(mix, decay=m["reverb"])

    # دخول وخروج ناعمان
    fade = int(1.6 * SR)
    mix[:fade] *= np.linspace(0, 1, fade)
    mix[-fade:] *= np.linspace(1, 0, fade)

    peak = np.max(np.abs(mix)) or 1.0
    return (mix / peak * 0.82).astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser(description="توليد موسيقى أجمكان")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--mood", choices=MOOD_KEYS, help="المزاج؛ يُشتقّ من الدورة إن أُهمل")
    ap.add_argument("--cycle", type=int, default=1)
    args = ap.parse_args()

    mood = args.mood or next_mood(args.cycle)
    audio = build(args.seconds, mood)
    stereo = np.stack([audio, np.roll(audio, 220)], axis=1)   # اتساع استريو خفيف
    pcm = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    import imageio_ffmpeg

    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
        "-f", "s16le", "-ar", str(SR), "-ac", "2", "-i", "pipe:0",
        "-c:a", "aac", "-b:a", "192k", str(out),
    ]
    proc = subprocess.run(cmd, input=pcm.tobytes(), capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.decode("utf-8", "replace")[-2000:])

    print(f"✔ {out}  مزاج «{MOODS[mood]['name_ar']}» ({mood})، "
          f"{out.stat().st_size // 1024} كيلوبايت، {args.seconds:.0f} ثانية)")


if __name__ == "__main__":
    main()
