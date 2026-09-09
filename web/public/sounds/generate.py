#!/usr/bin/env python3
"""
Generate 4 short preset beep .wav files (mono, 22050 Hz, 16-bit PCM).
Stdlib only. Run from this directory: `python3 generate.py`.

Sounds are deliberately distinct so a user can tell them apart by ear.
"""

from __future__ import annotations

import math
import os
import struct
import wave

SAMPLE_RATE = 22050
DURATION_S = 0.25
N_SAMPLES = int(SAMPLE_RATE * DURATION_S)


def envelope_linear(t: float, total: float) -> float:
    """Linear 5 ms attack/decay, full sustain in the middle."""
    a = 0.005
    if t < a:
        return t / a
    if t > total - a:
        return max(0.0, (total - t) / a)
    return 1.0


def envelope_exp(t: float, total: float) -> float:
    """Exponential decay — bell-like."""
    if t < 0.001:
        return t / 0.001
    return math.exp(-6.0 * t / total)


def envelope_fast(t: float, total: float) -> float:
    """Fast attack, very fast decay — pop."""
    a = 0.003
    d = 0.08
    if t < a:
        return t / a
    if t > d:
        return max(0.0, 1.0 - (t - d) / (total - d))
    return 1.0


def envelope_blip(t: float, total: float) -> float:
    """Sharp attack, fast exponential decay — alert blip."""
    if t < 0.002:
        return t / 0.002
    return math.exp(-15.0 * t / total)


def render(name: str, freq: float, wave_fn, env_fn, amp: float = 0.6) -> None:
    total = DURATION_S
    samples: list[int] = []
    for i in range(N_SAMPLES):
        t = i / SAMPLE_RATE
        env = env_fn(t, total)
        s = wave_fn(2 * math.pi * freq * t) * env * amp
        samples.append(int(max(-1.0, min(1.0, s)) * 32767))
    path = os.path.join(os.path.dirname(__file__), f"{name}.wav")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    print(f"wrote {path} ({os.path.getsize(path)} bytes)")


def main() -> None:
    render("chime",  660, math.sin, envelope_linear)
    render("bell",   880, math.sin, envelope_exp)
    render("pop",    440, _triangle, envelope_fast)
    render("alert", 1040, _square, envelope_blip, amp=0.4)


def _triangle(phase: float) -> float:
    """Triangle wave in [-1, 1]."""
    x = (phase / (2 * math.pi)) % 1.0
    return 4 * abs(x - 0.5) - 1


def _square(phase: float) -> float:
    """Square wave in [-1, 1]."""
    return 1.0 if (phase / (2 * math.pi)) % 1.0 < 0.5 else -1.0


if __name__ == "__main__":
    main()
