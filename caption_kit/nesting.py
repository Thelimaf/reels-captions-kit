"""
caption_kit/nesting.py — Motor de Aninhamento Real por Geometria de Glifos (Lockup)

Como funciona:
  1. Procura a fonte .woff2 primeiro na pasta local `legendas_dinamicas_kit/fonts/<familia>/`,
     depois em `~/.cache/hyperframes/fonts/<familia>/`, e se não existir localmente,
     baixa automaticamente do Google Fonts!
  2. Rasteriza a palavra principal (gigante) e as linhas de apoio (acima/abaixo) com Pillow.
  3. Mede coluna a coluna o contorno real da tinta (ascendentes, descendentes, altura-x).
  4. Calcula a posição (x, y) exata para encaixar as palavras menores nos vãos da palavra gigante
     sem nunca colidir (respeitando a folga `clear`).
"""
import glob
import io
import math
import os
import re
import urllib.parse
import urllib.request

import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

KIT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_FONT_ROOT = os.path.join(KIT_ROOT, "fonts")
HF_CACHE_FONT_ROOT = os.path.join(os.path.expanduser("~"), ".cache", "hyperframes", "fonts")

_faces = {}


class FontMissing(RuntimeError):
    pass


def _slug(family: str) -> str:
    return family.strip().lower().replace(" ", "-")


def _try_download_google_font(family: str, target_dir: str, weight=None, style="normal"):
    """Baixa automaticamente os arquivos .woff2 do Google Fonts caso a fonte ainda não esteja na pasta local.
    Com `weight`, baixa só aquele peso/estilo (ex.: 500 ou 600, que o pacote padrão não traz)."""
    os.makedirs(target_dir, exist_ok=True)
    q = urllib.parse.quote(family)
    if weight:
        it = 1 if style == "italic" else 0
        urls = [f"https://fonts.googleapis.com/css2?family={q}:ital,wght@{it},{int(weight)}&display=swap"]
    else:
        urls = [
            f"https://fonts.googleapis.com/css2?family={q}:ital,wght@0,400;0,700;0,800;0,900;1,400;1,700&display=swap",
            f"https://fonts.googleapis.com/css2?family={q}:wght@400;700;800;900&display=swap",
            f"https://fonts.googleapis.com/css2?family={q}&display=swap",
        ]
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    css_text = ""
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=15) as resp:
                css_text = resp.read().decode("utf-8", errors="ignore")
            if "font-face" in css_text:
                break
        except Exception:
            continue

    if not css_text:
        return

    blocks = re.findall(r"@font-face\s*\{([^}]+)\}", css_text)
    for idx, blk in enumerate(blocks):
        st_m = re.search(r"font-style:\s*(\w+)", blk)
        wt_m = re.search(r"font-weight:\s*(\d+)", blk)
        u_m = re.search(r"url\((https://[^)]+\.woff2)\)", blk)
        if not u_m:
            continue
        style = st_m.group(1) if st_m else "normal"
        weight = int(wt_m.group(1)) if wt_m else 400
        woff_url = u_m.group(1)
        out_file = os.path.join(target_dir, f"{weight}-{style}-{idx:02d}.woff2")
        if not os.path.exists(out_file):
            try:
                req = urllib.request.Request(woff_url, headers={"User-Agent": ua})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    with open(out_file, "wb") as f:
                        f.write(resp.read())
            except Exception:
                pass


class Face:
    """Fonte real (family/weight/style) que cobre os caracteres necessários."""

    def __init__(self, family, weight, style, chars):
        # Sanitiza pontuações especiais para nunca falhar na busca do cmap
        clean_chars = "".join(c for c in chars if ord(c) < 0x2000 and c not in "¿¡«»“”‘’…—–")
        if not clean_chars.strip():
            clean_chars = "A"

        slug = _slug(family)
        search_dirs = [
            os.path.join(LOCAL_FONT_ROOT, slug),
            os.path.join(HF_CACHE_FONT_ROOT, slug),
        ]

        woff_files = []
        chosen_dir = search_dirs[0]
        for d in search_dirs:
            found = glob.glob(os.path.join(d, "*.woff2"))
            if found:
                woff_files = found
                chosen_dir = d
                break

        if not woff_files:
            _try_download_google_font(family, search_dirs[0])
            chosen_dir = search_dirs[0]
            woff_files = glob.glob(os.path.join(chosen_dir, "*.woff2"))

        if not woff_files:
            raise FontMissing(
                f"Fonte '{family}' não encontrada em {LOCAL_FONT_ROOT}/{slug} nem pôde ser baixada automaticamente."
            )

        # Peso pedido ainda não baixado (ex.: 600): tenta buscar só ele antes de cair no mais próximo
        if not glob.glob(os.path.join(chosen_dir, f"{int(weight)}-{style}-*.woff2")):
            try:
                _try_download_google_font(family, chosen_dir, weight, style)
                woff_files = glob.glob(os.path.join(chosen_dir, "*.woff2"))
            except Exception:
                pass

        need = {ord(c) for c in clean_chars if not c.isspace()}
        weights = sorted({int(os.path.basename(p).split("-")[0]) for p in woff_files if os.path.basename(p).split("-")[0].isdigit()})
        weights.sort(key=lambda w: abs(w - weight))

        # Tenta primeiro com os caracteres pedidos; se falhar, faz fallback para 'A'
        for target_need in (need, {ord("A")}):
            for w in weights:
                candidates = sorted(glob.glob(os.path.join(chosen_dir, f"{w}-{style}-*.woff2")))
                if not candidates:
                    candidates = sorted(glob.glob(os.path.join(chosen_dir, f"{w}-*.woff2")))
                for p in candidates:
                    try:
                        tt = TTFont(p)
                        cmap = tt.getBestCmap() or {}
                        if target_need <= set(cmap):
                            buf = io.BytesIO()
                            tt.flavor = None
                            tt.save(buf)
                            self.data = buf.getvalue()
                            self.upm = tt["head"].unitsPerEm
                            self.asc = tt["hhea"].ascent
                            self.desc = -tt["hhea"].descent
                            self.weight = weight
                            self.variable = "fvar" in tt
                            self.path = p
                            return
                    except Exception:
                        continue

        raise FontMissing(f"Nenhum arquivo da fonte '{family}' ({style}) pôde ser carregado.")

    def font(self, px):
        f = ImageFont.truetype(io.BytesIO(self.data), size=max(8, int(round(px))))
        if self.variable:
            try:
                vals = [self.weight if "eight" in str(a.get("name")) else a["default"] for a in f.get_variation_axes()]
                f.set_variation_by_axes(vals)
            except Exception:
                pass
        return f


def face(family, weight, style, chars):
    key = (family, weight, style, "".join(sorted(set(chars))))
    if key not in _faces:
        _faces[key] = Face(family, weight, style, chars)
    return _faces[key]


def layout(fc, text, px, track_em):
    """Posições x de cada caractere + largura da caixa (tracking incluso, igual ao Chromium)."""
    f = fc.font(px)
    track = track_em * px
    xs, x = [], 0.0
    for ch in text:
        xs.append(x)
        x += f.getlength(ch) + track
    return {"xs": xs, "width": max(1.0, x), "font": f}


def baseline_in_box(fc, px, line_h):
    a, d = fc.asc * px / fc.upm, fc.desc * px / fc.upm
    return (line_h - (a + d)) / 2.0 + a


def shelf_height(fc, text, px):
    """Altura (px, acima da linha de base) da 'prateleira' onde o texto de cima se apoia."""
    f = fc.font(px)
    probe = "x" if any(c.islower() for c in text) else "H"
    l, t, r, b = f.getbbox(probe, anchor="ls")
    return float(-t)


def ink(fc, text, px, track_em, pad_px, line_h, rot=0.0):
    """Máscara de tinta do texto dentro da sua caixa de linha."""
    lay = layout(fc, text, px, track_em)
    box_w = lay["width"] + 2 * pad_px
    bib = baseline_in_box(fc, px, line_h)
    padx, pady = int(0.35 * px) + 2, int(0.7 * px) + 2
    W, H = int(math.ceil(box_w)) + 2 * padx, int(math.ceil(line_h)) + 2 * pady
    base_row = pady + bib
    img = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(img)
    for ch, x in zip(text, lay["xs"]):
        dr.text((padx + pad_px + x, base_row), ch, font=lay["font"], fill=255, anchor="ls")
    if rot:
        img = img.rotate(-rot, resample=Image.BICUBIC, center=(W / 2.0, H / 2.0))
    m = np.asarray(img) > 96
    has = m.any(axis=0)
    top = np.where(has, m.argmax(axis=0), 0).astype(float)
    bot = np.where(has, H - m[::-1].argmax(axis=0), 0).astype(float)
    return {
        "has": has, "top": top, "bot": bot, "W": W, "H": H,
        "padx": padx, "base_row": base_row, "box_w": box_w, "line_h": line_h, "bib": bib,
    }


def main_profile(mi):
    """Perfil da palavra principal em coordenadas relativas à linha de base."""
    n = mi["W"]
    O = n + 64
    L = n + 2 * O
    mt = np.full(L, np.inf)
    mb = np.full(L, -np.inf)
    cols = np.nonzero(mi["has"])[0]
    xb = cols - mi["padx"]
    mt[O + xb] = mi["top"][cols] - mi["base_row"]
    mb[O + xb] = mi["bot"][cols] - mi["base_row"]
    return {
        "mt": mt, "mb": mb, "O": O,
        "xmin": float(xb.min()), "xmax": float(xb.max()) + 1,
        "ytop": float(mt[np.isfinite(mt)].min()), "ybot": float(mb[np.isfinite(mb)].max()),
    }


def place(mp, wm, si, role, M, clear, shelf=None, lam=0.08, ov_frac=0.02, gain_cap=0.30):
    """Calcula a melhor posição (xc, yc) da linha pequena em relação à palavra principal."""
    ws = si["box_w"]
    ov = ov_frac * wm
    x_lo, x_hi = ws / 2.0 - ov, wm - ws / 2.0 + ov
    if x_lo > x_hi:
        x_lo = x_hi = wm / 2.0
    cand = np.arange(math.floor(x_lo), math.ceil(x_hi) + 1, 2.0)

    cols = np.nonzero(si["has"])[0]
    u = np.rint(cols - si["W"] / 2.0).astype(int)
    v_top = si["top"][cols] - si["H"] / 2.0
    v_bot = si["bot"][cols] - si["H"] / 2.0
    idx = mp["O"] + np.rint(cand)[:, None].astype(int) + u[None, :]
    idx = np.clip(idx, 0, len(mp["mt"]) - 1)
    cap = gain_cap * M

    if role == "above":
        tops = mp["mt"][idx]
        yc = np.min(tops - v_bot[None, :], axis=1) - clear
        y_loose = mp["ytop"] - clear - v_bot.max()
        yc = np.where(np.isfinite(yc), yc, y_loose)
        if shelf is not None:
            v_base = si["base_row"] - si["H"] / 2.0
            yc = np.minimum(yc, -shelf - clear - v_base)
        else:
            yc = np.minimum(yc, -clear - v_bot.max())
        yc = np.minimum(yc, y_loose + cap)
        gain = yc - y_loose
        x_pref = wm / 2.0
    else:
        bots = mp["mb"][idx]
        yc = np.max(bots - v_top[None, :], axis=1) + clear
        y_loose = mp["ybot"] + clear - v_top.min()
        yc = np.where(np.isfinite(yc), yc, y_loose)
        yc = np.maximum(yc, clear - v_top.min())
        yc = np.maximum(yc, y_loose - cap)
        gain = y_loose - yc
        x_pref = wm / 2.0

    score = gain - lam * np.abs(cand - x_pref)
    k = int(np.argmax(score))
    g = float(gain[k])
    q = "tucked" if g >= 0.08 * M else "tight" if g >= 0.03 * M else "loose"
    if q == "loose":
        if role == "below" and mp["ybot"] < 0.10 * M:
            q = "flush"
        elif role == "above" and shelf is not None and mp["ytop"] > -(shelf + 0.10 * M):
            q = "flush"
    return {
        "xc": float(cand[k]), "yc": float(yc[k]), "gain": g, "quality": q,
        "ink": (float(u.min()), float(u.max()) + 1, float(v_top.min()), float(v_bot.max())),
    }

