"""
caption_kit/placement.py — Posição vertical automática por contraste (sem sombra extra)

Para cada legenda, olha os quadros do vídeo durante o tempo em que ela fica na tela e escolhe a
altura (dentro de uma faixa segura do Reels) onde o fundo dá mais leitura para a cor do texto:
texto claro vai para áreas escuras e lisas, texto escuro para áreas claras. Evita áreas com muito
branco estourado (ex.: roupa clara) e não fica pulando de altura entre legendas seguidas.
"""
import subprocess

import numpy as np

SAMPLE_FPS = 4
SW, SH = 108, 192  # resolução de análise (proporção 9:16)


def _luminance(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def load_frames(video):
    """Quadros em tons de cinza (0..1), SAMPLE_FPS por segundo, em baixa resolução."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", video, "-vf", f"fps={SAMPLE_FPS},scale={SW}:{SH},format=gray",
         "-f", "rawvideo", "-"],
        capture_output=True, check=True,
    ).stdout
    n = len(raw) // (SW * SH)
    return np.frombuffer(raw[: n * SW * SH], np.uint8).reshape(n, SH, SW).astype(np.float32) / 255.0


def auto_place(groups, video, text_color="#ffffff", y_lockup=0.74, y_plain=0.75,
               band=(0.62, 0.78), step=0.01, keep_margin=0.06, mode="uniform"):
    """
    Define `g["y"]` em cada grupo. `band` é a faixa permitida (fração da altura; o padrão fica
    abaixo do rosto numa pessoa falando e acima da legenda/botões do Reels, que ocupam os ~20% de baixo).
    `mode="uniform"` (padrão): uma altura só para o vídeo inteiro, a que dá melhor leitura na média
    (legenda parada no mesmo lugar, mais limpa). `mode="per_block"`: cada legenda na sua melhor altura.
    `keep_margin`: no modo por bloco, só muda de altura se o ganho de leitura passar disso.
    Retorna a lista de (y, nota) escolhida por grupo, para conferência.
    """
    frames = load_frames(video)
    light_text = _luminance(text_color) >= 0.5
    ys = np.arange(band[0], band[1] + 1e-6, step)
    chosen, prev, total = [], None, None
    for g in groups:
        i0 = int(g["t0"] * SAMPLE_FPS)
        i1 = max(i0 + 1, int(g["t1"] * SAMPLE_FPS))
        clip = frames[min(i0, len(frames) - 1): min(i1, len(frames))]
        if not len(clip):
            chosen.append((g.get("y"), None))
            continue
        lum = clip.mean(axis=0)              # média no tempo do bloco
        half = 0.075 if g["kind"] == "lockup" else 0.04
        pref = y_lockup if g["kind"] == "lockup" else y_plain
        x0, x1 = int(SW * 0.1), int(SW * 0.9)

        def score(y):
            r0, r1 = int(SH * (y - half)), int(SH * (y + half))
            reg = lum[max(0, r0): min(SH, r1), x0:x1]
            mean, std = float(reg.mean()), float(reg.std())
            if light_text:
                contrast = 1.0 - mean
                clash = float((reg > 0.72).mean())   # branco estourado atrás do texto claro
            else:
                contrast = mean
                clash = float((reg < 0.25).mean())
            return contrast - 1.6 * clash - 0.5 * std - 0.4 * abs(y - pref)

        scores = np.array([score(y) for y in ys])
        if mode == "uniform":
            total = scores if total is None else total + scores
            continue
        best_y, best_s = float(ys[scores.argmax()]), float(scores.max())
        if prev is not None:
            prev_s = score(prev)
            if prev_s >= best_s - keep_margin:
                best_y, best_s = prev, prev_s
        g["y"] = round(best_y, 3)
        prev = best_y
        chosen.append((g["y"], round(best_s, 3)))
    if mode == "uniform" and total is not None:
        y_all = round(float(ys[total.argmax()]), 3)
        for g in groups:
            g["y"] = y_all
        return [(y_all, None)] * len(groups)
    return chosen
