"""
caption_kit/renderer.py — Compilador Modular de Legendas Dinâmicas para HyperFrames

Descobre automaticamente todos os estilos dentro da pasta `styles/` (arquivos `.py` ou `.json`).
Para compartilhar ou adicionar um novo estilo, basta jogar 1 arquivo `.py` ou `.json` na pasta `styles/`!
"""
import glob
import html
import importlib.util
import json
import os
import re

from . import nesting as cn

KIT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STYLES_DIR = os.path.join(KIT_ROOT, "styles")


def load_styles(extra_styles_dir=None):
    """
    Carrega dinamicamente todos os módulos de estilo (.py ou .json) da pasta `styles/`.
    Ignora arquivos cujo nome começa com `_` (como `_TEMPLATE_NOVO_ESTILO.py`).
    """
    styles = {}
    dirs = [STYLES_DIR]
    if extra_styles_dir and os.path.isdir(extra_styles_dir):
        dirs.append(extra_styles_dir)

    for d in dirs:
        if not os.path.isdir(d):
            continue
        # 1. Arquivos .py
        for py_path in sorted(glob.glob(os.path.join(d, "*.py"))):
            fname = os.path.basename(py_path)
            if fname.startswith("_"):
                continue
            mod_name = os.path.splitext(fname)[0]
            try:
                spec = importlib.util.spec_from_file_location(f"caption_style_{mod_name}", py_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "STYLE") and isinstance(mod.STYLE, dict):
                    st = dict(mod.STYLE)
                    sid = st.get("id", mod_name)
                    st["id"] = sid
                    st["_source"] = py_path
                    styles[sid] = st
            except Exception as e:
                print(f"[AVISO] Erro ao carregar estilo {py_path}: {e}")

        # 2. Arquivos .json
        for js_path in sorted(glob.glob(os.path.join(d, "*.json"))):
            fname = os.path.basename(js_path)
            if fname.startswith("_"):
                continue
            mod_name = os.path.splitext(fname)[0]
            try:
                st = json.load(open(js_path, encoding="utf-8"))
                if isinstance(st, dict):
                    sid = st.get("id", mod_name)
                    st["id"] = sid
                    st["_source"] = js_path
                    styles[sid] = st
            except Exception as e:
                print(f"[AVISO] Erro ao carregar estilo JSON {js_path}: {e}")

    return styles


def esc(s):
    return html.escape(str(s), quote=True)


def apply_case(text, mode, keep=()):
    """`keep`: palavras que mantêm a grafia original (nomes próprios/marcas) mesmo em "lower"/"upper"."""
    if mode not in ("upper", "lower"):
        return text
    keep_set = {k.lower() for k in keep} if mode == "lower" else set()
    out = []
    for w in text.split(" "):
        core = re.sub(r"^\W+|\W+$", "", w).lower()
        out.append(w if core and core in keep_set else (w.upper() if mode == "upper" else w.lower()))
    return " ".join(out)


def groups_from_simple(items, start=0.0):
    """Converte lista simples (above/main/below ou text) em grupos internos."""
    out, t = [], start
    for it in items:
        t0 = float(it.get("t0", t))
        t1 = float(it.get("t1", t0 + float(it.get("dur", 1.6))))
        if it.get("kind", "lockup") == "lockup":
            if "lines" in it:
                out.append({"kind": "lockup", "t0": t0, "t1": t1, "lines": it["lines"]})
            else:
                lines = []
                for role in ("above", "main", "below"):
                    if it.get(role):
                        offset = 0.0 if role == "above" else (0.07 if role == "main" else 0.14)
                        lines.append({
                            "role": role,
                            "text": it[role],
                            "t0": round(t0 + offset, 3),
                            "accent": (role == "main" and bool(it.get("accent", True))),
                        })
                out.append({"kind": "lockup", "t0": t0, "t1": t1, "lines": lines})
        else:
            if "words" in it and isinstance(it["words"], list):
                out.append({"kind": "plain", "t0": t0, "t1": t1, "words": it["words"]})
            else:
                ws = it.get("text", "").split()
                n = max(1, len(ws))
                step = min(0.18, (t1 - t0) * 0.6 / n)
                words = [{"text": w, "t0": round(t0 + i * step, 3), "accent": False} for i, w in enumerate(ws)]
                out.append({"kind": "plain", "t0": t0, "t1": t1, "words": words})
        t = t1 + 0.05
    return out


def _inherit_color_css(st):
    """Cor definida na LINHA e herdada pelas letras/palavras. Assim, uma cor aplicada no Studio a uma
    linha (ou palavra) aparece de verdade. Estilos com texto em gradiente (background-clip) ficam como estão."""
    hexc = r"(?<![-\w])color:\s*(#[0-9a-fA-F]{3,8})"
    out = []
    mm = re.search(hexc, st.get("main_css", ""))
    if mm and "background-clip" not in st.get("main_css", ""):
        out.append(f".line.main{{color:{mm.group(1)};}}.line.main.acc{{color:{st['accent']};}}"
                   ".main .txt .ch,.main.acc .txt .ch{color:inherit;}")
    ms = re.search(hexc, st.get("small_css", ""))
    if ms:
        out.append(f".line.small{{color:{ms.group(1)};}}.small .txt{{color:inherit;}}")
    return "".join(out)


def _words_of(g):
    """Palavras com tempo de um grupo (do grouper, ou derivadas das linhas de um lockup simples)."""
    if g.get("words") and all("t0" in w for w in g["words"]):
        return [{"text": w["text"], "t0": float(w["t0"])} for w in g["words"]]
    out = []
    for ln in g.get("lines", []):
        for j, t in enumerate(ln["text"].split()):
            out.append({"text": t, "t0": round(float(ln["t0"]) + 0.1 * j, 3)})
    return out


def _main_word_of(g):
    if g.get("main_word"):
        return g["main_word"]
    m = next((l for l in g.get("lines", []) if l["role"] == "main"), None)
    return m["text"] if m else None


def build(
    groups,
    style_name="serif_clean",
    W=1080,
    H=1920,
    y_lockup=0.74,
    y_plain=0.75,
    bg="transparent",
    min_hold=0.42,
    video_src="",
    accent_override=None,
    extra_styles_dir=None,
    style_overrides=None,
):
    """
    Compila uma lista de grupos em documento HTML HyperFrames + relatório de encaixe.
    `style_overrides`: dicionário que sobrescreve chaves do estilo (ex.: {"main_font": "Bodoni Moda"}).
    """
    styles = load_styles(extra_styles_dir)
    if style_name not in styles:
        # Fallback amigável: se pediu 'bold', usa 'serif_clean'
        if style_name == "bold" and "serif_clean" in styles:
            style_name = "serif_clean"
        else:
            available = ", ".join(sorted(styles.keys()))
            raise KeyError(f"Estilo '{style_name}' não encontrado. Estilos disponíveis: {available}")

    st = dict(styles[style_name])
    st.update(style_overrides or {})
    if accent_override:
        st["accent"] = accent_override

    # Layouts alternativos ao lockup: convertem cada grupo antes de renderizar
    layout = st.get("layout", "lockup")
    if layout in ("plain", "accumulate", "stairs"):
        conv = []
        for g in groups:
            ws = _words_of(g)
            mw = _main_word_of(g)
            if layout == "stairs":
                conv.append({"kind": "stairs", "t0": g["t0"], "t1": g["t1"], "y": g.get("y"),
                             "words": ws, "main_word": mw})
            else:
                conv.append({"kind": "plain", "t0": g["t0"], "t1": g["t1"], "y": g.get("y"),
                             "words": [dict(w, accent=(w["text"].lower() == (mw or "").lower())) for w in ws]})
            if conv[-1]["y"] is None:
                conv[-1].pop("y")
        groups = conv

    # Legenda comum em pedaços curtos (referências: 1–3 palavras por tela, cada pedaço inteiro e centrado)
    pmax = int(st.get("plain_max_words", 0) or 0)
    if pmax > 0:
        split = []
        for g in groups:
            ws = g.get("words") if g["kind"] == "plain" else None
            if not ws or len(ws) <= pmax:
                split.append(g)
                continue
            k = -(-len(ws) // pmax)
            sizes = [len(ws) // k + (1 if j < len(ws) % k else 0) for j in range(k)]
            chunks, pos = [], 0
            for sz in sizes:
                chunks.append(ws[pos:pos + sz]); pos += sz
            # 1) pedaço só de conectivo ("e", "de", "a"...) nunca fica sozinho: junta com o seguinte
            conn = {"e", "o", "a", "os", "as", "de", "do", "da", "em", "no", "na", "que", "pra", "para",
                    "com", "um", "uma", "se", "eu", "me", "te", "é", "ao", "mas", "ou"}
            chunks = [list(c) for c in chunks]
            j = 0
            while j < len(chunks) and len(chunks) > 1:
                if all(w["text"].lower() in conn for w in chunks[j]):
                    if j + 1 < len(chunks):
                        chunks[j + 1] = chunks[j] + chunks[j + 1]
                    else:
                        chunks[j - 1] = chunks[j - 1] + chunks[j]
                    chunks.pop(j)
                    continue
                j += 1
            # 2) pedaço que ficaria menos de `plain_min_chunk` s na tela junta com o anterior (sem pisca)
            min_chunk = float(st.get("plain_min_chunk", 0.3))
            j = 0
            while j < len(chunks) and len(chunks) > 1:
                start = chunks[j][0]["t0"] if j else g["t0"]
                end = chunks[j + 1][0]["t0"] if j + 1 < len(chunks) else g["t1"]
                if end - start < min_chunk:
                    if j > 0:
                        chunks[j - 1] = chunks[j - 1] + chunks[j]
                    else:
                        chunks[j + 1] = chunks[j] + chunks[j + 1]
                    chunks.pop(j)
                    continue
                j += 1
            for j, ch in enumerate(chunks):
                c0 = g["t0"] if j == 0 else ch[0]["t0"]
                c1 = chunks[j + 1][0]["t0"] if j + 1 < len(chunks) else g["t1"]
                sub = dict(g, t0=round(c0, 3), t1=round(max(c1, c0 + 0.2), 3),
                           words=[dict(w, t0=round(c0, 3)) for w in ch])
                split.append(sub)
        groups = split

    S = W / 1080.0
    px = lambda v: round(v * S, 1)

    for i, g in enumerate(groups):
        nxt = groups[i + 1]["t0"] if i + 1 < len(groups) else None
        if g["t1"] - g["t0"] < min_hold:
            g["t1"] = g["t0"] + min_hold
        if nxt is not None and g["t1"] > nxt:
            g["t1"] = nxt if st.get("exit", "fade") == "cut" else max(g["t0"] + 0.25, nxt)

    body, js, report = [], [], []
    loose = 0
    # Velocidade das entradas: durações base já são "rápidas" (falas curtas de Reels);
    # cada estilo pode acelerar/desacelerar com "speed" (ex.: 1.3 mais rápido, 0.8 mais calmo)
    spd = max(0.3, float(st.get("speed", 1.0)))

    def d(x):
        return round(x / spd, 3)
    for i, g in enumerate(groups):
        gid, t0, t1 = f"g{i}", g["t0"], g["t1"]
        dur = round(t1 - t0, 3)
        exit_t = max(t0 + 0.2, t1 - 0.14)
        cut_exit = st.get("exit", "fade") == "cut"

        if g["kind"] == "plain":
            ws = g["words"]
            spans = []
            for k, w in enumerate(ws):
                txt = esc(apply_case(w["text"], st.get("plain_case", "none"), st.get("keep_case", ())))
                if st.get("plain_accent_kw_only"):
                    acc = re.sub(r"\W", "", w["text"]).lower() in {k.lower() for k in st.get("support_kw", ())}
                else:
                    acc = w.get("accent")
                cls = "w acc" if acc else "w"
                spans.append(f'<span id="{gid}-w{k}" class="{cls}">{txt}</span>')
            body.append(
                f'<div id="{gid}" class="clip grp" data-start="{t0:.3f}" data-duration="{dur:.3f}">'
                f'<div class="anchor" style="top:{H * g.get("y", y_plain):.1f}px"><div id="{gid}-box" class="plain-row">{" ".join(spans)}</div></div></div>'
            )
            plain_cut = st.get("plain_entry", "rise") == "cut"
            plain_blur = st.get("plain_entry") == "blurin"
            for k, w in enumerate(ws):
                at = max(t0, w["t0"])
                if plain_blur:
                    js.append(f'tl.fromTo(P("#{gid}-w{k}","#{gid}-box"),{{opacity:0,filter:"blur(6px)"}},{{opacity:1,filter:"blur(0px)",duration:{d(.1)},ease:"power2.out",overwrite:"auto"}},{at:.3f});')
                elif plain_cut:
                    js.append(f'tl.fromTo(P("#{gid}-w{k}","#{gid}-box"),{{opacity:0}},{{opacity:1,duration:.06,ease:"none",overwrite:"auto"}},{at:.3f});')
                else:
                    js.append(
                        f'tl.fromTo(P("#{gid}-w{k}","#{gid}-box"),{{opacity:0,y:{px(28)}}},{{opacity:1,y:0,duration:{d(.2)},ease:"power3.out",overwrite:"auto"}},{at:.3f});'
                    )
            if not cut_exit:
                js.append(f'tl.to("#{gid} .w",{{opacity:0,duration:.14,ease:"power1.in",overwrite:"auto"}},{exit_t:.3f});')
            report.append({
                "group": gid, "kind": "plain",
                "text": " ".join(w["text"] for w in ws), "t0": t0, "t1": t1,
            })
            continue

        if g["kind"] == "stairs":
            ws = g["words"]
            mw = (g.get("main_word") or "").lower()
            mi_ = next((k for k, w in enumerate(ws) if w["text"].lower() == mw), max(range(len(ws)), key=lambda k: len(ws[k]["text"])))
            per = int(st.get("stairs_words_per_line", 2))
            def _chunks(seq):
                return [seq[j:j + per] for j in range(0, len(seq), per)]
            rows = [(c, False) for c in _chunks(ws[:mi_])] + [([ws[mi_]], True)] + [(c, False) for c in _chunks(ws[mi_ + 1:])]
            off = px(st.get("stairs_offset", 70))
            shift = off * (len(rows) - 1) / 2.0
            html_rows = []
            for k, (row, is_main) in enumerate(rows):
                txt = " ".join(apply_case(w["text"], st.get("main_case" if is_main else "small_case", "none"), st.get("keep_case", ())) for w in row)
                cls = "st-line st-main" if is_main else "st-line"
                html_rows.append(f'<div id="{gid}-s{k}" class="{cls}" style="margin-left:{k * off:.1f}px">{esc(txt)}</div>')
                at = max(t0, row[0]["t0"])
                if is_main:
                    js.append(f'tl.fromTo("#{gid}-s{k}",{{opacity:0,scale:1.12,x:{px(-16)}}},{{opacity:1,scale:1,x:0,duration:{d(.22)},ease:"power3.out",overwrite:"auto"}},{at:.3f});')
                else:
                    js.append(f'tl.fromTo("#{gid}-s{k}",{{opacity:0,y:{px(22)}}},{{opacity:1,y:0,duration:{d(.18)},ease:"power3.out",overwrite:"auto"}},{at:.3f});')
                if not cut_exit:
                    js.append(f'tl.to("#{gid}-s{k}",{{opacity:0,duration:.14,ease:"power1.in",overwrite:"auto"}},{exit_t:.3f});')
            body.append(
                f'<div id="{gid}" class="clip grp" data-start="{t0:.3f}" data-duration="{dur:.3f}">'
                f'<div class="anchor" style="top:{H * g.get("y", y_lockup):.1f}px"><div id="{gid}-box" class="stairs" style="transform:translateX({-shift:.1f}px)">'
                f'{"".join(html_rows)}</div></div></div>'
            )
            report.append({"group": gid, "kind": "stairs", "main": ws[mi_]["text"], "t0": t0, "t1": t1})
            continue

        # Lockup (aninhamento por geometria real de glifos)
        main = next((l for l in g["lines"] if l["role"] == "main"), None)
        if not main:
            continue
        main_txt = apply_case(main["text"], st.get("main_case", "none"), st.get("keep_case", ()))
        PAD = 0.04
        mface = cn.face(st["main_font"], st["main_weight"], st.get("main_style", "normal"), main_txt)
        w100 = cn.layout(mface, main_txt, 100.0, st["main_track"])["width"] + 2 * PAD * 100.0
        main_px = max(px(110), min(px(st["max_px"]), (W * 0.76) / w100 * 100.0))
        Lm = st["main_lh"] * main_px
        mi = cn.ink(mface, main_txt, main_px, st["main_track"], PAD * main_px, Lm)
        wm = mi["box_w"]
        mp = cn.main_profile(mi)
        clear = max(px(6), st.get("clear", 0.03) * main_px)
        shelf = cn.shelf_height(mface, main_txt, main_px)

        placed, q = [], {}
        for k, ln in enumerate(g["lines"]):
            role = ln["role"]
            if role == "main":
                continue
            txt = apply_case(ln["text"], st.get("small_case", "none"), st.get("keep_case", ()))
            sface = cn.face(st["small_font"], st["small_weight"], st.get("small_style", "normal"), txt)
            rot = st.get("tilt", (0, 0))[0 if role == "above" else 1]
            spx0 = max(px(46), main_px * min(0.55, max(0.22, st.get("small_scale", 0.42))))
            best = None
            for f in (1.0, 0.9, 0.8, 0.72, 0.64, 0.56):
                spx = max(px(40), spx0 * f)
                sw = cn.layout(sface, txt, spx, st["small_track"])["width"]
                if sw > wm * 0.85:
                    spx *= wm * 0.85 / sw
                Ls = 1.05 * spx
                si = cn.ink(sface, txt, spx, st["small_track"], 0.0, Ls, rot)
                res = cn.place(mp, wm, si, role, main_px, clear, shelf)
                depth = mp["ybot"] if role == "below" else (-mp["ytop"] - shelf)
                fill = min(1.0, res["gain"] / depth) if depth > 0.06 * main_px else 1.0
                util = 0.65 * fill + 0.35 * (spx / spx0)
                if best is None or util > best[0]:
                    best = (util, spx, Ls, si, res)
                if fill >= 0.85 and f == 1.0:
                    break
            _, spx, Ls, si, res = best
            if st.get("small_layout") == "spread" and len(txt.split()) >= 2:
                # linha espalhada ocupa a largura toda da principal: empilha (sem encaixe nos vãos)
                gap = clear
                iy0, iy1 = res["ink"][2], res["ink"][3]
                if role == "above":
                    res["yc"] = mp["ytop"] - gap - iy1
                else:
                    res["yc"] = mp["ybot"] + gap - iy0
                res["xc"] = (mp["xmin"] + mp["xmax"]) / 2.0
                half = (mp["xmax"] - mp["xmin"]) / 2.0
                res["ink"] = (-half, half, iy0, iy1)
                res["quality"] = "stacked"
            if st.get("nest_mode") == "overlap":
                res["quality"] = "stacked"
            q[role] = res["quality"]
            if res["quality"] == "loose":
                loose += 1
            placed.append((k, ln, role, txt, spx, Ls, si, res))

        xs0, xs1, ys0, ys1 = [mp["xmin"]], [mp["xmax"]], [mp["ytop"]], [mp["ybot"]]
        for (_, _, _, _, _, _, si, res) in placed:
            xs0.append(res["xc"] + res["ink"][0]); xs1.append(res["xc"] + res["ink"][1])
            ys0.append(res["yc"] + res["ink"][2]); ys1.append(res["yc"] + res["ink"][3])
        minx, maxx, miny, maxy = min(xs0), max(xs1), min(ys0), max(ys1)

        cells, q_gain = [], {}
        mid_idx = next(k for k, l in enumerate(g["lines"]) if l["role"] == "main")
        cls = "line main acc" if main.get("accent") else "line main"
        chars = "".join(f'<span class="ch">{"&nbsp;" if c == " " else esc(c)}</span>' for c in main_txt)
        cells.append((
            1,
            f'<div class="cell" style="left:{-minx:.1f}px;top:{-mi["bib"] - miny:.1f}px;font-size:{main_px:.1f}px;line-height:{Lm:.1f}px">'
            f'<div id="{gid}-l{mid_idx}" class="{cls}"><span class="txt">{chars}</span>'
            f'<span id="{gid}-sh" class="shine" aria-hidden="true">{chars}</span></div></div>'
        ))
        # palavras com tempo do grupo (para entrada palavra a palavra nas linhas pequenas)
        gw = g.get("words") if g.get("words") and all("t0" in w for w in g["words"]) else None
        n_above = len(next((l["text"].split() for l in g["lines"] if l["role"] == "above"), []))
        support_kw = {w.lower() for w in st.get("support_kw", ())}
        for (k, ln, role, txt, spx, Ls, si, res) in placed:
            lid = f"{gid}-l{k}"
            ws = si["box_w"]
            words_txt = txt.split()
            # tempos de cada palavra da linha (acima = primeiras do bloco; abaixo = últimas)
            if gw and len(gw) >= n_above + 1 + (len(words_txt) if role == "below" else 0):
                wt = [w["t0"] for w in (gw[:n_above] if role == "above" else gw[n_above + 1:])][:len(words_txt)]
            else:
                wt = [ln["t0"]] * len(words_txt)
            while len(wt) < len(words_txt):
                wt.append(wt[-1] if wt else ln["t0"])
            spread = st.get("small_layout") == "spread" and len(words_txt) >= 2
            if spread and len(words_txt) > 2:
                # espalhado em 2 blocos (metade esquerda / metade direita), como na referência;
                # cada bloco entra no tempo da sua primeira palavra
                h = (len(words_txt) + 1) // 2
                words_txt = [" ".join(words_txt[:h]), " ".join(words_txt[h:])]
                wt = [wt[0], wt[h]]
            def _wspan(wd):
                kw = re.sub(r"\W", "", wd).lower() in support_kw or any(c.isdigit() for c in wd)
                return f'<span class="{"kw" if kw else "nk"}">{esc(wd)}</span>'
            spans = "".join(
                f'<span id="{lid}-w{j}" class="txt">{" ".join(_wspan(x) for x in wd.split())}</span>'
                + ("" if j == len(words_txt) - 1 else '<span class="sp"> </span>')
                for j, wd in enumerate(words_txt)
            )
            if spread:
                # espalhado: 1ª palavra na borda esquerda da principal, última na borda direita
                left, width = mp["xmin"] - minx, mp["xmax"] - mp["xmin"]
                cells.append((
                    0 if role == "above" else 2,
                    f'<div class="cell" style="left:{left:.1f}px;width:{width:.1f}px;top:{res["yc"] - Ls / 2.0 - miny:.1f}px;font-size:{spx:.1f}px;line-height:{Ls:.1f}px">'
                    f'<div id="{lid}" class="line small spread">{spans}</div></div>'
                ))
            else:
                cells.append((
                    0 if role == "above" else 2,
                    f'<div class="cell" style="left:{res["xc"] - ws / 2.0 - minx:.1f}px;top:{res["yc"] - Ls / 2.0 - miny:.1f}px;font-size:{spx:.1f}px;line-height:{Ls:.1f}px">'
                    f'<div id="{lid}" class="line small">{spans}</div></div>'
                ))
            q_gain[role] = {"quality": res["quality"], "tuck_px": round(res["gain"], 1), "small_px": round(spx, 1)}
            rot = st.get("tilt", (0, 0))[0 if role == "above" else 1]
            if st.get("small_entry") == "blurin":
                # palavra a palavra, opacidade + desfoque curtos (referência de mercado: ~0,1 s)
                if len(words_txt) == 1:
                    # linha de um bloco só: anima a própria LINHA (o Studio troca o conteúdo interno ao
                    # editar cor/texto, mas nunca a linha) — continua certo mesmo no meio da edição
                    js.append(f'tl.fromTo("#{lid}",{{opacity:0,filter:"blur(6px)"}},{{opacity:1,filter:"blur(0px)",duration:{d(.1)},ease:"power2.out",overwrite:"auto"}},{max(t0, wt[0]):.3f});')
                for j in range(len(words_txt) if len(words_txt) > 1 else 0):
                    js.append(f'tl.fromTo(P("#{lid}-w{j}","#{lid}"),{{opacity:0,filter:"blur(6px)"}},{{opacity:1,filter:"blur(0px)",duration:{d(.1)},ease:"power2.out",overwrite:"auto"}},{max(t0, wt[j]):.3f});')
            else:
                js.append(
                    f'tl.fromTo("#{lid}",{{opacity:0,y:{px(-18 if role == "above" else 18)},rotation:{rot * 2},filter:"blur(6px)"}},'
                    f'{{opacity:1,y:0,rotation:{rot},filter:"blur(0px)",duration:{d(.28)},ease:"power3.out",overwrite:"auto"}},{max(t0, ln["t0"]):.3f});'
                )
            if not cut_exit:
                js.append(
                    f'tl.to("#{lid}",{{opacity:0,y:{px(-10 if role == "above" else 10)},duration:.16,ease:"power1.in",overwrite:"auto"}},{exit_t:.3f});'
                )
        q = q_gain

        body.append(
            f'<div id="{gid}" class="clip grp" data-start="{t0:.3f}" data-duration="{dur:.3f}">'
            f'<div class="anchor" style="top:{H * g.get("y", y_lockup):.1f}px"><div id="{gid}-box" class="lockup" style="width:{maxx - minx:.1f}px;height:{maxy - miny:.1f}px">'
            f'{"".join(c for _, c in sorted(cells, key=lambda x: x[0]))}</div></div></div>'
        )

        variants = st.get("variants", ("slam", "letters", "rise"))
        v = variants[i % len(variants)]
        mid = f"{gid}-l{mid_idx}"
        at = max(t0, main["t0"])
        if v == "blur":
            js.append(f'tl.fromTo("#{mid}",{{opacity:0,scale:1.1,filter:"blur(14px)"}},{{opacity:1,scale:1,filter:"blur(0px)",duration:{d(.3)},ease:"power3.out",overwrite:"auto"}},{at:.3f});')
            settle = d(.3)
        elif v == "rise":
            js.append(f'tl.fromTo("#{mid}",{{opacity:0,y:{px(48)},scale:.96}},{{opacity:1,y:0,scale:1,duration:{d(.32)},ease:"power3.out",overwrite:"auto"}},{at:.3f});')
            settle = d(.32)
        elif v == "letters":
            n = max(1, len(main_txt))
            stg = d(min(0.025, 0.18 / n))
            js.append(f'tl.fromTo(P("#{mid} .txt .ch","#{mid}"),{{opacity:0,y:"0.28em",scale:.85,filter:"blur(8px)"}},{{opacity:1,y:0,scale:1,filter:"blur(0px)",duration:{d(.28)},ease:"power3.out",stagger:{stg:.3f}}},{at:.3f});')
            settle = d(.28) + stg * (n - 1)
        elif v == "blurin":
            # referência de mercado: opacidade + desfoque 10 px→0 em ~4 quadros, sem escala
            js.append(f'tl.fromTo("#{mid}",{{opacity:0,filter:"blur(10px)"}},{{opacity:1,filter:"blur(0px)",duration:{d(.13)},ease:"power2.out",overwrite:"auto"}},{at:.3f});')
            settle = d(.13)
        elif v == "typepop":
            # máquina de escrever com pop: 1 letra a cada ~0,035 s, cada uma cresce em 0,12 s
            n = max(1, len(main_txt))
            stg = d(min(0.035, 0.45 / n))
            js.append(f'tl.fromTo(P("#{mid} .txt .ch","#{mid}"),{{opacity:0,scale:.2,y:"0.12em"}},{{opacity:1,scale:1,y:0,duration:{d(.12)},ease:"back.out(2.2)",stagger:{stg:.3f}}},{at:.3f});')
            settle = d(.12) + stg * (n - 1)
        else:
            js.append(f'tl.fromTo("#{mid}",{{opacity:0,scale:1.5}},{{opacity:1,scale:1,duration:{d(.24)},ease:"power4.out",overwrite:"auto"}},{at:.3f});')
            settle = d(.24)
        if st.get("dim_previous"):
            # linhas que já estavam na tela recuam para ~70% quando a palavra principal entra
            for k, l in enumerate(g["lines"]):
                if l["role"] == "above":
                    js.append(f'tl.to("#{gid}-l{k}",{{opacity:{st.get("dim_previous"):.2f},duration:.15,ease:"power1.out"}},{at:.3f});')
        if t1 - at > 0.9:
            js.append(f'tl.to("#{mid}",{{scale:1.035,duration:{max(0.2, t1 - at - settle - 0.15):.3f},ease:"none",overwrite:"auto"}},{at + settle:.3f});')
        sh_at = at + settle + 0.05
        sh_dur = min(0.9, max(0.45, exit_t - sh_at - 0.05))
        if exit_t - sh_at > 0.4:
            js.append(f'tl.fromTo("#{gid}-sh",{{backgroundPosition:"100% 0%",opacity:1}},{{backgroundPosition:"0% 0%",duration:{sh_dur:.3f},ease:"power2.inOut"}},{sh_at:.3f});')
        if not cut_exit:
            js.append(f'tl.to("#{mid}",{{opacity:0,scale:.97,filter:"blur(6px)",duration:.16,ease:"power1.in",overwrite:"auto"}},{exit_t:.3f});')
        report.append({"group": gid, "kind": "lockup", "main": main["text"], "entry": v, "nest": q, "main_px": main_px, "t0": t0, "t1": t1})

    total = max([g["t1"] for g in groups] + [1.0]) + 0.3

    def fam(name):
        generic = "serif" if name in ("Playfair Display", "EB Garamond") else "sans-serif"
        return f"'{name}',{generic}"

    sh_tuple = st.get("shine", ("#ffffff", "rgba(255,255,255,.9)"))
    acc_extra_css = st.get("accent_extra_css", "")

    css = f"""
html,body{{margin:0;padding:0;background:{bg};}}
#root{{position:relative;width:100%;height:100%;overflow:hidden;}}
.shadow-overlay{{position:absolute;bottom:0;left:0;width:100%;height:100%;background:linear-gradient(to top, rgba(0,0,0,0.65) 0%, rgba(0,0,0,0.22) 22%, transparent 40%);pointer-events:none;z-index:0;}}
.anchor{{position:absolute;left:0;right:0;height:0;display:flex;align-items:center;justify-content:center;z-index:1;}}
.lockup{{position:relative;flex:none;}}
.cell{{position:absolute;white-space:nowrap;{st.get("cell_css", "")}}}
.line{{display:block;will-change:transform,opacity;}}
.main{{position:relative;font-family:{fam(st["main_font"])};font-weight:{st["main_weight"]};font-style:{st.get("main_style", "normal")};letter-spacing:{st["main_track"]}em;line-height:inherit;font-size:1em;}}
.main .txt{{display:inline-block;padding:0 .04em;white-space:nowrap;}}
.main .ch{{display:inline-block;}}
.main .txt .ch{{{st["main_css"]}}}
.main .shine{{position:absolute;left:0;top:0;display:inline-block;padding:0 .04em;white-space:nowrap;pointer-events:none;
  color:transparent;background-image:linear-gradient(105deg,transparent 43%,{sh_tuple[0]}80 47.5%,{sh_tuple[0]} 50%,{sh_tuple[0]}80 52.5%,transparent 57%);
  background-size:250% 100%;background-repeat:no-repeat;background-position:100% 0%;
  -webkit-background-clip:text;background-clip:text;filter:drop-shadow(0 0 .07em {sh_tuple[1]});}}
.small{{font-family:{fam(st["small_font"])};font-weight:{st["small_weight"]};font-style:{st.get("small_style", "normal")};letter-spacing:{st["small_track"]}em;line-height:inherit;}}
.small .txt{{display:inline-block;{st["small_css"]}}}
.main.acc .txt .ch{{background:none;-webkit-background-clip:border-box;background-clip:border-box;color:{st["accent"]};{acc_extra_css}}}
.plain-row{{width:{int(W * st.get("plain_width", 0.86))}px;text-align:{st.get("plain_align", "center")};font-family:{fam(st["plain_font"])};font-weight:{st["plain_weight"]};font-style:{st.get("plain_style", "normal")};font-size:{px(st.get("plain_px", 78))}px;line-height:{st.get("plain_lh", 1.12)};letter-spacing:{st.get("plain_track", 0)}em;{st["plain_css"]}}}
.w{{display:inline-block;margin:0 .04em;will-change:transform,opacity;}}
.line.small.spread{{display:flex;justify-content:space-between;}}
.small .sp{{white-space:pre;}}
.line.small[style*="color"] .kw,.line.small [style*="color"]{{color:inherit!important;}}
.small .kw{{color:{st.get("support_kw_color", st["accent"])};text-shadow:none;}}
.stairs{{display:inline-flex;flex-direction:column;align-items:flex-start;flex:none;}}
.st-line{{display:block;white-space:nowrap;will-change:transform,opacity;font-family:{fam(st["small_font"])};font-weight:{st["small_weight"]};font-style:{st.get("small_style", "normal")};letter-spacing:{st["small_track"]}em;font-size:{px(st.get("stairs_px", 66))}px;line-height:{st.get("stairs_lh", 0.98)};{st["small_css"]}}}
.st-line.st-main{{font-family:{fam(st["main_font"])};font-weight:{st["main_weight"]};font-style:{st.get("main_style", "normal")};letter-spacing:{st["main_track"]}em;font-size:{px(st.get("stairs_main_px", 150))}px;line-height:{st.get("stairs_main_lh", 0.9)};{st["main_css"]}}}
.main .txt .ch{{transform-origin:50% 85%;}}
{".grp{mix-blend-mode:difference;}" if st.get("blend") == "difference" else ""}
.w.acc{{color:{st["accent"]};{acc_extra_css}}}
{_inherit_color_css(st)}
{".w.acc,.small .kw{text-shadow:none!important;}" if st.get("accent_no_glow") else ""}
"""

    vid_tag = ""
    if video_src:
        vrel = video_src.replace("\\", "/")
        vid_tag = f'\n<video id="bg-video" class="clip" src="{vrel}" playsinline data-start="0.000" data-duration="{total:.3f}" data-track-index="0" data-has-audio="true" style="position:absolute;inset:0;width:{W}px;height:{H}px;object-fit:cover;z-index:0;"></video>'

    doc = f"""<!doctype html>
<html lang="pt-BR" data-resolution="portrait">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={W}, height={H}" />
<title>Legendas Dinâmicas — {esc(st.get("label", style_name))}</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>{css}</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-width="{W}" data-height="{H}" data-duration="{total:.3f}">{vid_tag}
<div class="shadow-overlay"></div>
{chr(10).join(body)}
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
// alvo de reserva: se uma edição no Studio apagou o id da palavra, anima a linha/bloco (uma vez só)
function P(s, f) {{ if (document.querySelector(s)) return s; P.u = P.u || {{}}; if (!f || P.u[f]) return []; P.u[f] = 1; return f; }}
{chr(10).join(js)}
window.__timelines["main"] = tl;
</script>
</body>
</html>
"""
    return doc, report, loose


def render_embeddable(
    groups,
    prefix="v1",
    style_name="serif_clean",
    W=1080,
    H=1920,
    y_lockup=0.74,
    y_plain=0.75,
    min_hold=0.42,
    accent_override=None,
    track_index=3,
    z_index=95,
    extra_styles_dir=None,
):
    """
    Gera `(caps_css, caps_dom, caps_js, report)` prontos para embutir em uma composição
    HyperFrames multi-track (converte divs internas de cada grupo em `<span>` para zero warnings no lint).
    """
    doc, report, _ = build(
        groups,
        style_name=style_name,
        W=W,
        H=H,
        y_lockup=y_lockup,
        y_plain=y_plain,
        bg="transparent",
        min_hold=min_hold,
        accent_override=accent_override,
        extra_styles_dir=extra_styles_dir,
    )
    styles_m = re.search(r"<style>(.*?)</style>", doc, re.DOTALL)
    caps_css = styles_m.group(1) if styles_m else ""
    caps_css += f"""
      .grp {{ position: absolute; inset: 0; width: {W}px; height: {H}px; pointer-events: none; }}
      .grp .anchor {{ position: absolute; left: 0; right: 0; width: {W}px; height: 0; display: flex !important; align-items: center !important; justify-content: center !important; }}
      .grp .plain-row {{ display: block; width: {int(W * 0.86)}px; margin: 0 auto; text-align: center; }}
      .grp .lockup {{ display: block; position: relative; flex: none; margin: 0 auto; }}
      .grp .line {{ display: block; }}
    """

    body_m = re.search(r'<div class="shadow-overlay"></div>(.*?)</div>\s*<script>', doc, re.DOTALL)
    body_raw = body_m.group(1) if body_m else ""
    body_raw = re.sub(r'\bid="g(\d+)', f'id="{prefix}-g\\1', body_raw)

    caps_lines = []
    for raw_line in body_raw.strip().splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        m_outer = re.match(r'^(<div id="[^"]+" class="clip grp"[^>]*>)(.*)(</div>)$', raw_line)
        if m_outer:
            open_tag = m_outer.group(1).replace(
                'class="clip grp"',
                f'class="clip grp" data-track-index="{track_index}" style="z-index: {z_index};"',
            )
            inner = m_outer.group(2)
            inner = re.sub(r"<div\b", "<span", inner)
            inner = re.sub(r"</div>", "</span>", inner)
            caps_lines.append(f"      {open_tag}{inner}</div>")
        else:
            caps_lines.append(f"      {raw_line}")

    js_m = re.search(r'const tl = gsap\.timeline\(\{ paused: true \}\);(.*?)window\.__timelines', doc, re.DOTALL)
    caps_js = js_m.group(1) if js_m else ""
    caps_js = re.sub(r'#g(\d+)', f'#{prefix}-g\\1', caps_js)

    return caps_css, "\n".join(caps_lines), caps_js, report

