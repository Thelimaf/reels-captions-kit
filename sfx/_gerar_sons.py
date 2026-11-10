"""Gera os efeitos sonoros do kit (sintetizados, originais, domínio público).

Rodar: python sfx/_gerar_sons.py   (precisa de numpy e ffmpeg para os .mp3)
Substitua qualquer arquivo por um som seu mantendo o nome.
"""
import os, subprocess, wave
import numpy as np

SR = 48000
HERE = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(7)


def _save_wav(name, mono, level=1.0):
    mono = np.clip(mono * level, -1, 1)
    st = np.stack([mono, mono], axis=1)
    with wave.open(os.path.join(HERE, name), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())


def _click(dur, f0, decay, noise=0.6, gain=0.9):
    """Tique curto: seno que cai rápido + um pouco de ruído."""
    n = int(SR * dur); t = np.arange(n) / SR
    env = np.exp(-t * decay)
    tone = np.sin(2 * np.pi * f0 * t) * env
    nz = rng.standard_normal(n) * np.exp(-t * decay * 1.6) * noise
    x = (tone + nz)
    x[: int(0.0008 * SR)] *= np.linspace(0, 1, int(0.0008 * SR))
    return x / (np.max(np.abs(x)) + 1e-9) * gain


def _place(buf, clip, at):
    i = int(at * SR); buf[i:i + len(clip)] += clip[: len(buf) - i]


# tiques suaves (0,14 s)
for k, f in enumerate([1500, 1800, 2100, 2400, 2700, 3000], start=1):
    x = np.zeros(int(SR * 0.14)); _place(x, _click(0.14, f, 55, noise=0.35, gain=0.75), 0)
    _save_wav(f"tick_{k}.wav", x, 0.45)

# digitação: sequência de teclas em ritmo irregular
for name, dur, n_keys, seed in [("typing_a.wav", 1.3, 9, 1), ("typing_b.wav", 1.4, 10, 2), ("typing_c.wav", 1.2, 8, 3)]:
    r = np.random.default_rng(seed); x = np.zeros(int(SR * dur))
    t = 0.04
    for _ in range(n_keys):
        _place(x, _click(0.07, r.uniform(900, 1700), 70, noise=0.8, gain=r.uniform(0.45, 0.8)), t)
        t += r.uniform(0.08, 0.16)
        if t > dur - 0.08: break
    _save_wav(name, x, 0.32)

# mouse: clique "down" + "up"
for name, dur, gap in [("mouse_1.wav", 0.12, 0.07), ("mouse_2.wav", 0.13, 0.075)]:
    x = np.zeros(int(SR * dur))
    _place(x, _click(0.05, 1100, 90, noise=0.9, gain=0.9), 0.0)
    _place(x, _click(0.04, 1500, 110, noise=0.7, gain=0.55), gap)
    _save_wav(name, x, 0.38)

# whoosh suave (ruído filtrado com envelope), codificado em mp3
for name, seed, lo in [("whoosh_soft_a", 11, 0.18), ("whoosh_soft_b", 12, 0.12)]:
    r = np.random.default_rng(seed); n = int(SR * 1.0); t = np.arange(n) / SR
    nz = r.standard_normal(n)
    k = np.ones(int(SR * lo)) / int(SR * lo)       # passa-baixa por média móvel
    nz = np.convolve(nz, k, mode="same")
    env = np.sin(np.pi * np.clip(t / 1.0, 0, 1)) ** 2
    x = nz * env; x = x / (np.max(np.abs(x)) + 1e-9) * 0.6
    wav = os.path.join(HERE, name + "_tmp.wav")
    _save_wav(name + "_tmp.wav", x)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-ar", "44100", "-codec:a", "libmp3lame", "-q:a", "4",
                    os.path.join(HERE, name + ".mp3")], check=True)
    os.remove(wav)
print("ok")
