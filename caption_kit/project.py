"""
caption_kit/project.py — Projeto HyperFrames EDITÁVEL (abre no Studio, ajusta e exporta)

Em vez de devolver só um index.html "fechado", monta uma pasta de projeto HyperFrames completa:

  <projeto>/
  ├── index.html        # Composição: vídeo (opcional) + legendas + SFX como clipes separados na timeline
  ├── groups.json       # Textos e tempos de cada legenda (edite aqui e rode --rebuild)
  ├── project.json      # Estilo, vídeo, SFX e posição usados (lido pelo --rebuild)
  ├── hyperframes.json / package.json
  └── assets/           # Vídeo e SFX copiados para o projeto

No Studio (`npx hyperframes preview <projeto>`) dá para:
  - mover, apagar ou mudar o volume de cada SFX (são clipes <audio> na timeline);
  - mudar cores, posição vertical, escala e ligar/desligar a sombra pelas VARIÁVEIS da composição;
  - exportar o MP4 direto pelo Studio (ou `npx hyperframes render <projeto>`).
Para mudar TEXTO ou TEMPO de uma legenda, edite `groups.json` e rode
`python cli.py --rebuild <projeto>` (o encaixe geométrico é recalculado em segundos, sem renderizar).
"""
import copy
import json
import os
import re
import shutil

from .grouper import regroup, retime_ends
from .placement import auto_place
from .renderer import KIT_ROOT, build, load_styles

SFX_DIR = os.path.join(KIT_ROOT, "sfx")
# Fontes oferecidas no painel Variables (Google Fonts; o motor baixa a fonte e refaz o encaixe no --rebuild)
MAIN_FONTS = ["Playfair Display", "Instrument Serif", "DM Serif Display", "Bodoni Moda", "Cormorant Garamond",
              "Libre Caslon Text", "Fraunces", "Inter", "Montserrat", "League Gothic", "Anton", "Bebas Neue"]
SMALL_FONTS = ["Montserrat", "Poppins", "Inter", "DM Sans", "Outfit", "Manrope", "Raleway", "Playfair Display"]
# variável do painel -> chave do estilo
FONT_VARS = {"fonte_principal": "main_font", "peso_principal": "main_weight",
             "fonte_apoio": "small_font", "peso_apoio": "small_weight"}

TICKS = ["tick_2.wav", "tick_3.wav", "tick_4.wav", "tick_5.wav", "tick_6.wav"]
TYPING = ["typing_a.wav", "typing_b.wav", "typing_c.wav"]
SFX_PRESETS = {
    # hit: som curto quando a palavra PRINCIPAL entra | typing: digitação enquanto a linha de APOIO entra
    # (arquivos alternados, duração do clipe, atraso após a entrada da linha, volume)
    "click": {"hit": (TICKS, 0.14, 0.05, 0.6)},
    "typing": {"hit": (TICKS, 0.14, 0.05, 0.6), "typing": (TYPING, None, 0.0, 0.35)},
    "mouse": {"hit": (["mouse_1.wav", "mouse_2.wav"], 0.13, 0.05, 0.45)},
    "whoosh": {"hit": (["whoosh_soft_a.mp3", "whoosh_soft_b.mp3"], 0.8, 0.0, 0.35)},
}


def _first_color(css, fallback):
    m = re.search(r"(?<![-\w])color:\s*(#[0-9a-fA-F]{3,8})", css or "")
    return m.group(1) if m else fallback


CONNECTIVES = {"e", "o", "a", "os", "as", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
               "que", "pra", "para", "com", "um", "uma", "se", "eu", "me", "te", "é", "ao", "à", "mas", "ou"}


def _move_tail_connectives(groups):
    """Palavra de ligação sozinha no fim de um bloco ("conhece e") passa para o início do bloco seguinte,
    que é onde ela faz sentido na leitura. Só mexe quando os blocos são vizinhos (pausa < 0,6 s)."""
    for a, b in zip(groups, groups[1:]):
        wa, wb = a.get("words"), b.get("words")
        if not wa or not wb or len(wa) < 2 or not all("t0" in w for w in wa + wb):
            continue
        while len(wa) >= 2 and wa[-1]["text"].lower() in CONNECTIVES and wb[0]["t0"] - wa[-1]["t0"] < 0.9:
            if a.get("kind") == "lockup" and (a.get("main_word") or "").lower() == wa[-1]["text"].lower():
                break
            w = wa.pop()
            # entra junto com a palavra seguinte; o bloco anterior não encolhe
            wb.insert(0, dict(w, t0=wb[0]["t0"]))
    return groups


def _shift(groups, lead, lead_plain=None):
    """Adianta os tempos (grupo, linhas e palavras) sem passar de 0.
    `lead` vale para os destaques (lockup); `lead_plain` para a legenda comum (padrão = `lead`).
    Referências: comum 0–0,15 s antes da fala; destaque 0,15–0,6 s antes."""
    if not lead and not lead_plain:
        return groups
    prev_t1 = None
    for g in groups:
        lg = lead if g.get("kind") == "lockup" or lead_plain is None else lead_plain
        if not lg:
            prev_t1 = g["t1"]
            continue
        g["t0"] = round(max(0.0, g["t0"] - lg), 3)
        # o lead adianta só a ENTRADA; a saída continua presa ao fim da fala (o vizinho corta se precisar)
        g["t1"] = round(max(g["t0"] + 0.3, g["t1"]), 3)
        for it in g.get("lines", []) + g.get("words", []):
            it["t0"] = round(max(g["t0"], it["t0"] - lg), 3)
    # leads diferentes podem sobrepor blocos vizinhos: o anterior termina quando o próximo começa
    for a, b in zip(groups, groups[1:]):
        if a["t1"] > b["t0"]:
            a["t1"] = round(max(a["t0"] + 0.2, b["t0"]), 3)
    return groups


EDIT_ATTRS = ("data-hidden", "data-volume", "data-fade-in", "data-fade-out")


def _text_by_id(html_txt):
    """Texto visível de cada elemento de legenda com id (gN, gN-box, gN-lK, gN-wK...), para conferir
    se uma edição antiga ainda pertence ao mesmo texto depois de uma regeneração."""
    out = {}
    for m in re.finditer(r'id="(g\d+(?:-[a-z]+\d*)*(?:-w\d+)?)"', html_txt):
        rest = html_txt[m.end():]
        rest = rest[rest.find(">") + 1:]          # pula o resto da própria tag
        # Linha de texto puro (gN-lK): o texto é tudo até a próxima tag, ignorando quebras/espaços
        # que o Studio insere ao regravar o arquivo
        leaf = rest[: rest.find("<")] if "<" in rest else rest
        if re.fullmatch(r"g\d+-l\d+", m.group(1)) and leaf.strip():
            out[m.group(1)] = " ".join(leaf.split())
            continue
        stop = len(rest)
        for marker in ('class="cell"', "\n", 'class="clip grp"'):
            k = rest.find(marker)
            if k != -1:
                stop = min(stop, k)
        out[m.group(1)] = " ".join(re.sub(r"<[^>]+>", "", rest[:stop]).split())
    return out


def _guard_by_text(edits, old_html, new_html):
    """Mantém só as edições cujo elemento tem o mesmo texto antes e depois (evita que uma edição caia em
    outro bloco quando a numeração muda). Clipes sem texto (vídeo, SFX, degradê) passam direto."""
    old_t, new_t = _text_by_id(old_html), _text_by_id(new_html)
    keep = {}
    for k, v in edits.items():
        if not k.startswith("g") or k not in old_t:
            keep[k] = v
        elif new_t.get(k) == old_t[k]:
            keep[k] = v
    return keep


def _studio_edits(index_path):
    """Lê do index.html atual os atributos que o usuário pode ter mudado no Studio, por id de clipe."""
    if not os.path.exists(index_path):
        return {}
    html_txt = open(index_path, encoding="utf-8").read()
    edits = {}
    for tag in re.findall(r"<(?:audio|video|div)\b[^>]*\bclass=\"clip[^>]*>", html_txt):
        m = re.search(r'(?<![\w-])id="([^"]+)"', tag)
        if not m:
            continue
        attrs = {}
        for a in EDIT_ATTRS:
            v = re.search(rf'\s{a}(?:="([^"]*)")?(?=[\s>])', tag)
            if v:
                attrs[a] = v.group(1) or ""
        edits[m.group(1)] = attrs
    return edits


TRANSFORM_PROPS = ("translate", "rotate", "scale")


def _studio_transforms(index_path):
    """Posição/rotação/escala arrastadas no Studio (propriedades CSS individuais no style), por id."""
    if not os.path.exists(index_path):
        return {}
    html_txt = open(index_path, encoding="utf-8").read()
    out = {}
    for tag in re.findall(r"<(?:span|div)\b[^>]*>", html_txt):
        m = re.search(r'(?<![\w-])id="([^"]+)"', tag)
        st = re.search(r'\sstyle="([^"]*)"', tag)
        if not m or not st:
            continue
        props = {k: v.strip() for k, v in re.findall(r"(?:^|;)\s*(translate|rotate|scale|color)\s*:\s*([^;]+)", st.group(1))}
        if props:
            out[m.group(1)] = props
    # cor que o Studio gravou num filho sem id dentro de uma linha (gN-lK) passa a ser a cor da linha
    for m in re.finditer(r'id="(g\d+-l\d+)"([^>]*)>((?:(?!class="cell").){0,1500})', html_txt, re.S):
        if m.group(1) in out and "color" in out[m.group(1)]:
            continue
        cols = re.findall(r'style="[^"]*?(?<![-\w])color:\s*([^;"]+)', m.group(3))
        if cols:
            out.setdefault(m.group(1), {})["color"] = cols[-1].strip()
    return out


def _apply_transforms(doc, transforms):
    def fix(m):
        tag = m.group(0)
        idm = re.search(r'(?<![\w-])id="([^"]+)"', tag)
        if not idm or idm.group(1) not in transforms:
            return tag
        # aspas duplas (ex.: font-family "Playfair Display") quebrariam o atributo style="..."
        extra = "".join(f"{k}:{str(v).replace(chr(34), chr(39))};" for k, v in transforms[idm.group(1)].items())
        if re.search(r'\sstyle="', tag):
            return re.sub(r'(\sstyle=")([^"]*)"', lambda s_: f'{s_.group(1)}{s_.group(2).rstrip(";")};{extra}"', tag, count=1)
        return tag[:-1] + f' style="{extra}">'
    return re.sub(r"<(?:span|div)\b[^>]*>", fix, doc)


# ---------------------------------------------------------------------------------------------
# Legendas "à prova de Studio": quando o Studio edita um elemento, ele reescreve os filhos e apaga
# class/id deles (só o atributo style sobrevive). Por isso cada parte da legenda leva o próprio
# estilo inline, e só as LINHAS (não o bloco inteiro) são selecionáveis no Studio.
# ---------------------------------------------------------------------------------------------
STYLE_PROPS_TRACKED = ("font-family", "font-weight", "font-style", "font-size", "line-height", "letter-spacing",
                       "color", "text-shadow", "translate", "rotate", "scale", "opacity", "text-transform")


def _fam(name, generic):
    return f"'{name}',{generic}"


def _nocolor(css):
    """Tira declarações de cor (color:) de um trecho de CSS, mantendo sombra, gradiente etc."""
    return re.sub(r"(?<![-\w])color\s*:[^;]+;?", "", css or "")


def _inline_rules(st, W, H):
    """Estilo inline por classe (equivale às regras do <style>, mas sobrevive à edição do Studio)."""
    main_font = _fam(st["main_font"], "serif" if "serif" in st["main_font"].lower() or st["main_font"] in ("Playfair Display", "EB Garamond", "Bodoni Moda", "Instrument Serif", "Fraunces", "Cormorant Garamond", "Libre Caslon Text", "DM Serif Display") else "sans-serif")
    small_font = _fam(st["small_font"], "sans-serif")
    plain_font = _fam(st.get("plain_font", st["small_font"]), "sans-serif")
    main_typo = (f"font-family:{main_font};font-weight:{st['main_weight']};font-style:{st.get('main_style', 'normal')};"
                 f"letter-spacing:{st['main_track']}em;")
    small_typo = (f"font-family:{small_font};font-weight:{st['small_weight']};font-style:{st.get('small_style', 'normal')};"
                  f"letter-spacing:{st['small_track']}em;")
    return {
        "anchor": f"position:absolute;left:0;right:0;width:{W}px;height:0;display:flex;align-items:center;justify-content:center;",
        "lockup": "position:relative;display:block;flex:none;",
        "cell": "position:absolute;white-space:nowrap;display:block;",
        # sem "color" inline: a cor vem das regras do estilo/variáveis, e a cor que o usuário der no Studio
        # (gravada no style da linha) passa por cima delas
        "main": main_typo + "white-space:nowrap;padding:0 .04em;" + _nocolor(st.get("main_css", "")),
        "main_acc": main_typo + "white-space:nowrap;padding:0 .04em;" + _nocolor(st.get("main_css", "")) + _nocolor(st.get("accent_extra_css", "")),
        # cor das linhas pequenas/palavras-chave fica nas regras do estilo (o motor usa a presença de
        # "color" no style da linha para saber se o usuário recoloriu a linha no Studio)
        "small": small_typo + "white-space:nowrap;" + re.sub(r"(?<![-\w])color:[^;]+;?", "", st.get("small_css", "")),
        "txt_main": "display:inline-block;padding:0 .04em;white-space:nowrap;",
        "txt_small": "display:inline-block;",
        "ch": "display:inline-block;",
        "w": "display:inline-block;margin:0 .04em;",
        "kw": "",
        "plain": (f"font-family:{plain_font};font-weight:{st.get('plain_weight', st['small_weight'])};"
                  f"font-style:{st.get('plain_style', 'normal')};letter-spacing:{st.get('plain_track', 0)}em;"
                  + st.get("plain_css", "")),
    }


def _add_style(tag, css):
    """Acrescenta `css` ANTES do style existente (o que já estava no elemento continua valendo)."""
    css = css.strip()
    if not css:
        return tag
    if re.search(r'\sstyle="', tag):
        return re.sub(r'(\sstyle=")([^"]*)"', lambda m: f'{m.group(1)}{css.rstrip(";")};{m.group(2)}"', tag, count=1)
    return tag[:-1] + f' style="{css}">'


def _flatten_leaves(doc):
    """Cada linha da legenda (e a legenda simples) vira TEXTO PURO: o Studio só mostra os controles de
    fonte/tamanho/cor para elementos de texto, e não tem filhos para reescrever. As animações por letra/palavra
    caem no alvo alternativo do motor (a linha inteira)."""
    out, pos = [], 0
    it = re.finditer(r"<(/?)(span|div)\b([^>]*)>", doc)
    for m in it:
        if m.group(1):
            continue
        if m.start() < pos:
            continue
        tag = m.group(0)
        cls = re.search(r'\sclass="([^"]*)"', tag)
        classes = cls.group(1).split() if cls else []
        is_word = bool(re.search(r'\sid="g\d+(?:-l\d+)?-w\d+"', tag))
        is_row = "plain-row" in classes or ("line" in classes and ("main" in classes or "small" in classes))
        if not (is_word or is_row):
            continue
        # acha o fechamento correspondente
        depth, end = 1, None
        for n in re.finditer(r"<(/?)(span|div)\b[^>]*>", doc[m.end():]):
            depth += -1 if n.group(1) else 1
            if depth == 0:
                end = m.end() + n.start()
                close_end = m.end() + n.end()
                break
        if end is None:
            continue
        inner = doc[m.end():end]
        # Linha montada palavra por palavra (revelação por palavra, "espalhado"): mantém as palavras;
        # cada PALAVRA vira texto puro selecionável (tratada quando o laço chegar nela)
        if is_row and re.search(r'\sid="g\d+(?:-l\d+)?-w\d+"', inner):
            continue
        # remove a camada de brilho (cópia do texto) e mantém só o texto visível
        inner = re.sub(r'<span id="g\d+-sh"[^>]*>.*?</span>(?:</span>)?', "", inner, flags=re.S)
        text = re.sub(r"<[^>]+>", "", inner)
        text = re.sub(r"\s+", " ", text.replace("&nbsp;", " ")).strip()
        if is_word and 'class="kw"' in inner and "kw" not in classes:
            tag = re.sub(r'\sclass="([^"]*)"', r' class="\1 kw"', tag, count=1) if cls else tag[:-1] + ' class="kw">'
        out.append(doc[pos:m.start()])
        out.append(tag)
        out.append(text)
        out.append(doc[end:close_end])
        pos = close_end
    out.append(doc[pos:])
    return "".join(out)


def _move_line_motion_to_cell(doc):
    """O Studio não grava arraste/posição de um elemento animado pelo GSAP. A animação de cada linha
    passa para o invólucro dela (a "cell", que ganha id gN-lK-c); a linha (texto) fica parada, livre
    para selecionar, arrastar e mudar fonte/tamanho."""
    doc = re.sub(r'<span class="cell"([^>]*)>(\s*)<span id="(g\d+-l\d+)"',
                 r'<span id="\3-c" class="cell"\1>\2<span id="\3"', doc)
    head, sep, script = doc.rpartition("<script>")
    script = re.sub(r'#(g\d+-l\d+)(?=["\s])', r"#\1-c", script)
    # Animações por palavra/letra cujos alvos viraram texto da linha: anima a linha uma vez só
    ids = set(re.findall(r'\sid="([^"]+)"', head))
    used, lines_out = set(), []
    for ln in script.split("\n"):
        m = re.search(r'P\("([^"]+)","([^"]+)"\)', ln)
        if m and m.group(1).split()[0].lstrip("#") not in ids:
            if m.group(2) in used:
                continue
            used.add(m.group(2))
            ln = ln.replace(m.group(0), '"' + m.group(2) + '"', 1)
        lines_out.append(ln)
    return head + sep + "\n".join(lines_out)


def _make_studio_safe(doc, st, W, H):
    rules = _inline_rules(st, W, H)
    out, pos = [], 0
    ctx = []  # pilha de "main"/"small" para saber o tipo de .txt
    for m in re.finditer(r"<(/?)(span|div)\b([^>]*)>", doc):
        out.append(doc[pos:m.start()])
        pos = m.end()
        tag = m.group(0)
        if m.group(1):          # fechamento
            if ctx:
                ctx.pop()
            out.append(tag)
            continue
        cls = re.search(r'\sclass="([^"]*)"', tag)
        classes = cls.group(1).split() if cls else []
        kind = ctx[-1] if ctx else None
        add = ""
        if "anchor" in classes:
            add = rules["anchor"]
        elif "lockup" in classes:
            add = rules["lockup"]
        elif "cell" in classes:
            add = rules["cell"]
        elif "line" in classes and "main" in classes:
            add, kind = (rules["main_acc"] if "acc" in classes else rules["main"]), "main"
        elif "line" in classes and "small" in classes:
            add, kind = rules["small"] + ("display:flex;justify-content:space-between;" if "spread" in classes else ""), "small"
        elif "txt" in classes:
            add = (rules["txt_main"] if kind == "main" else rules["txt_small"]) + (rules["kw"] if "kw" in classes else "")
        elif "ch" in classes:
            add = rules["ch"]
        elif "w" in classes:
            add = rules["w"] + (rules["kw"] if "acc" in classes else "")
        elif "kw" in classes:
            add = rules["kw"]
        elif "sp" in classes:
            add = "white-space:pre;"
        elif "plain-row" in classes:
            add, kind = rules["plain"], "plain"
        out.append(_add_style(tag, add) if add else tag)
        ctx.append(kind)
    out.append(doc[pos:])
    return "".join(out)


def _style_map(html_txt):
    """id -> {propriedade: valor} do style inline de cada span/div com id."""
    res = {}
    for tag in re.findall(r"<(?:span|div)\b[^>]*>", html_txt):
        m = re.search(r'(?<![\w-])id="([^"]+)"', tag)
        st_ = re.search(r'\sstyle="([^"]*)"', tag)
        if not m or not st_:
            continue
        props = {}
        import html as _h
        for k, v in re.findall(r"(?:^|;)\s*([a-z-]+)\s*:\s*([^;]+)", _h.unescape(st_.group(1))):
            if k in STYLE_PROPS_TRACKED:
                props[k] = v.strip()
        res[m.group(1)] = props
    return res


def _studio_style_edits(index_path, baseline_path):
    """O que o usuário mudou no Studio (fonte, tamanho, cor, posição...) = style atual − style gerado."""
    if not (os.path.exists(index_path) and os.path.exists(baseline_path)):
        return {}
    cur = _style_map(open(index_path, encoding="utf-8").read())
    base = json.load(open(baseline_path, encoding="utf-8"))
    edits = {}
    for eid, props in cur.items():
        b = base.get(eid, {})
        diff = {k: v for k, v in props.items() if b.get(k) != v}
        if diff:
            edits[eid] = diff
    return edits


def _apply_edits(doc, edits):
    """Reaplica os atributos editados no Studio nos clipes com o mesmo id."""
    def fix(m):
        tag = m.group(0)
        idm = re.search(r'(?<![\w-])id="([^"]+)"', tag)
        if not idm or idm.group(1) not in edits:
            return tag
        for a in EDIT_ATTRS:
            tag = re.sub(rf'\s{a}(?:="[^"]*")?(?=[\s>])', "", tag)
        extra = "".join(f' {a}="{v}"' if v != "" else f' {a}=""' for a, v in edits[idm.group(1)].items())
        return tag[:-1] + extra + ">"
    return re.sub(r"<(?:audio|video|div)\b[^>]*\bclass=\"clip[^>]*>", fix, doc)


def _studio_variables(index_path):
    """Valores atuais das variáveis (o Studio grava a escolha do painel como `default`)."""
    if not os.path.exists(index_path):
        return {}
    import html as _html
    h = open(index_path, encoding="utf-8").read()
    m = re.search(r"""data-composition-variables=("[^"]*"|'[^']*')""", h)
    if not m:
        return {}
    try:
        return {v["id"]: v.get("default") for v in json.loads(_html.unescape(m.group(1)[1:-1]))}
    except (ValueError, KeyError, TypeError):
        return {}


def _unicode_range(path):
    """Faixas unicode cobertas por um .woff2 (para o navegador escolher o arquivo certo por caractere)."""
    from fontTools.ttLib import TTFont
    cps = sorted((TTFont(path).getBestCmap() or {}).keys())
    ranges, start, prev = [], None, None
    for c in cps:
        if start is None:
            start = prev = c
        elif c == prev + 1:
            prev = c
        else:
            ranges.append((start, prev)); start = prev = c
    if start is not None:
        ranges.append((start, prev))
    return ",".join(f"U+{a:X}" if a == b else f"U+{a:X}-{b:X}" for a, b in ranges)


def _font_faces(st, out_dir):
    """Copia os .woff2 das fontes do estilo para assets/fonts e devolve as regras @font-face.
    O HyperFrames só resolve sozinho algumas famílias; sem isso o render cai numa fonte genérica."""
    import glob as _glob
    from . import nesting as cn
    used = {(st["main_font"], int(st["main_weight"]), st.get("main_style", "normal")),
            (st["small_font"], int(st["small_weight"]), st.get("small_style", "normal")),
            (st["plain_font"], int(st["plain_weight"]), st.get("plain_style", "normal"))}
    rules = []
    for fam, w, sty in sorted(used):
        try:
            cn.face(fam, w, sty, "Aa")  # garante download (inclusive do peso exato)
        except Exception:
            continue
        d = os.path.join(cn.LOCAL_FONT_ROOT, cn._slug(fam))
        files = sorted(_glob.glob(os.path.join(d, f"{w}-{sty}-*.woff2")))
        if not files:
            have = sorted({int(os.path.basename(f).split("-")[0]) for f in _glob.glob(os.path.join(d, f"*-{sty}-*.woff2"))},
                          key=lambda x: abs(x - w))
            files = sorted(_glob.glob(os.path.join(d, f"{have[0]}-{sty}-*.woff2"))) if have else []
        for f in files:
            rel = f"assets/fonts/{cn._slug(fam)}/{os.path.basename(f)}"
            os.makedirs(os.path.dirname(os.path.join(out_dir, rel)), exist_ok=True)
            _place(f, os.path.join(out_dir, rel))
            rules.append(f"@font-face{{font-family:'{fam}';font-style:{sty};font-weight:{w};font-display:block;"
                         f"src:url('{rel}') format('woff2');unicode-range:{_unicode_range(f)};}}")
    return "\n".join(rules)


def _place(src, dst):
    """Hardlink quando possível (vídeos grandes no mesmo disco), senão copia."""
    if os.path.exists(dst):
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _encode_broll(src, dst, brilho=1.0, newer_than=0.0):
    """Cópia do b-roll feita para renderizar: sem áudio, 30 fps constantes e um quadro-chave por segundo.
    Os cortes do banco têm um só quadro-chave e o render falha ao extrair quadros deles. O original (em
    brolls/clips) não é tocado: se `dst` for um link para ele, o link é desfeito antes de gravar."""
    if os.path.exists(dst) and os.path.getmtime(dst) >= max(os.path.getmtime(src), newer_than) and not os.path.islink(dst):
        try:
            if os.stat(dst).st_nlink == 1:
                return
        except OSError:
            pass
    if os.path.exists(dst):
        # o link para o original é somente-leitura (e compartilha o atributo com ele): solta, apaga e recoloca
        import stat
        src_ro = not os.access(src, os.W_OK)
        os.chmod(dst, stat.S_IWRITE)
        os.remove(dst)
        if src_ro and os.path.exists(src):
            os.chmod(src, stat.S_IREAD)
    import subprocess
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", src, "-an", "-vf", f"fps=30,lutyuv=y=val*{brilho}", "-c:v", "libx264", "-crf", "14",
         "-preset", "medium", "-g", "30", "-keyint_min", "30", "-sc_threshold", "0", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", dst],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou ao preparar o b-roll {src}: {r.stderr[:300]}")


def _broll_tags(out_dir):
    """B-rolls em tela cheia lidos de `brolls.json` (na pasta do projeto). Cada clipe vira um <video> na
    timeline, entre o vídeo de fundo e as legendas, e pode ser movido/aparado/ocultado no Studio (o --rebuild
    mantém o que foi mudado lá). Formato: {"clips": [{"id", "src", "start", "duration", "position"}]}."""
    path = os.path.join(out_dir, "brolls.json")
    if not os.path.exists(path):
        return []
    clips = json.load(open(path, encoding="utf-8")).get("clips", [])
    # Clipe que já foi gerado antes e não está mais no index.html foi apagado no Studio: continua apagado
    idx = os.path.join(out_dir, "index.html")
    present = set(re.findall(r'<video[^>]*\bid="broll-([^"]+)"', open(idx, encoding="utf-8").read())) if os.path.exists(idx) else set()
    seen_path = os.path.join(out_dir, ".broll_seen.json")
    seen = set(json.load(open(seen_path, encoding="utf-8"))) if os.path.exists(seen_path) else set()
    tags = []
    for c in clips:
        name = re.sub(r"[^a-z0-9-]+", "-", str(c["id"]).lower()).strip("-")
        if name in seen and name not in present:
            continue
        seen.add(name)
        rel = f"assets/broll/{name}.mp4"
        os.makedirs(os.path.join(out_dir, "assets", "broll"), exist_ok=True)
        # o escurecimento (brilho) vai gravado no próprio arquivo: filtro CSS em vídeo tela cheia trava o render
        _encode_broll(c["src"], os.path.join(out_dir, rel), c.get("brilho", 0.72), os.path.getmtime(path))
        pos = c.get("position", "50% 50%")
        media = f' data-media-start="{c["media_start"]:.3f}"' if c.get("media_start") else ""
        tags.append(
            f'<video id="broll-{name}" class="clip" src="{rel}" muted playsinline data-start="{c["start"]:.3f}" '
            f'data-duration="{c["duration"]:.3f}"{media} data-track-index="1" '
            'style="position:absolute;inset:0;width:{W}px;height:{H}px;object-fit:cover;'
            f'object-position:{pos};z-index:10;"></video>'
        )
    json.dump(sorted(seen), open(seen_path, "w", encoding="utf-8"))
    return tags


def build_project(
    groups,
    out_dir,
    style_name="serif_clean",
    video=None,
    sfx="click",
    sfx_volume=None,
    sfx_on="lockup",
    W=1080,
    H=1920,
    y_lockup=0.74,
    y_plain=0.75,
    bg="#0c121e",
    min_hold=0.42,
    accent_override=None,
    fps=30,
    lead=0.0,
    preserve_edits=True,
    lead_plain=None,
    sfx_min_gap=0.0,
    auto_y=None,
    keywords=None,
    style_overrides=None,
    tail=0.15,
):
    """
    Gera uma pasta de projeto HyperFrames editável. `sfx`: "click", "typing", "mouse", "whoosh" ou None.
    `sfx_on`: "lockup" (só blocos com palavra de destaque) ou "all".
    `lead`: adianta legendas e SFX em segundos em relação à fala (ex.: 0.3 = aparecem 0,3 s antes).
    `preserve_edits`: ao regenerar, mantém o que foi mudado no Studio em cada elemento que ainda existir
    (clipe oculto, volume/fades do SFX e posição/rotação/escala arrastadas na legenda).
    `auto_y`: escolhe a altura de cada legenda pelo contraste com o vídeo (padrão: liga quando há vídeo).
    Um `"y"` escrito à mão num grupo do groups.json tem prioridade.
    `keywords`: palavras do assunto/cliente que devem virar destaque (ex.: ["marca", "promoção"]).
    Retorna o caminho do index.html.
    """
    styles = load_styles()
    if style_name not in styles:
        raise ValueError(f"Estilo '{style_name}' não encontrado. Disponíveis: {', '.join(sorted(styles))}")
    index_path = os.path.join(out_dir, "index.html")
    # Valores escolhidos no painel Variables do Studio (fonte, peso, cores, posição...) viram o novo padrão
    prev_vars = _studio_variables(index_path) if preserve_edits else {}
    # Trocou de estilo: fontes/cores escolhidas no painel eram do estilo antigo; mantém só posição/fundo/degradê
    prev_cfg = os.path.join(out_dir, "project.json")
    if prev_vars and os.path.exists(prev_cfg):
        if json.load(open(prev_cfg, encoding="utf-8")).get("style") != style_name:
            keep = ("deslocar_y", "escala", "cor_fundo", "degrade_inferior", "opacidade_degrade")
            prev_vars = {k: v for k, v in prev_vars.items() if k in keep}
    style_overrides = dict(style_overrides or {})
    for var, key in FONT_VARS.items():
        if prev_vars.get(var) not in (None, ""):
            style_overrides[key] = prev_vars[var]
    if "italico_principal" in prev_vars:
        style_overrides["main_style"] = "italic" if prev_vars["italico_principal"] else "normal"
    # Nomes próprios/marcas das keywords (com maiúscula) não viram minúscula no estilo
    proper = [k for k in (keywords or []) if k[:1].isupper()]
    if proper:
        style_overrides["keep_case"] = sorted(set(style_overrides.get("keep_case", [])) | set(proper))
    if keywords:
        style_overrides["support_kw"] = sorted({k.lower() for k in keywords})
    st = dict(styles[style_name])
    st.update(style_overrides)
    # Reaplica edições de texto/palavra principal/tipo feitas no groups.json
    src_groups = regroup(copy.deepcopy(groups), keywords)  # tempos da fala, salvos no groups.json
    groups = _shift(retime_ends(regroup(_move_tail_connectives(copy.deepcopy(src_groups)), keywords),
                                tail=tail), lead, lead_plain)
    if auto_y is None:
        auto_y = bool(video)
    if auto_y and video:
        manual = {i: g["y"] for i, g in enumerate(src_groups) if "y" in g}
        auto_place(groups, video, _first_color(st.get("main_css"), "#ffffff"), y_lockup, y_plain,
                   mode="per_block" if auto_y == "per_block" else "uniform")
        for i, y in manual.items():
            groups[i]["y"] = y
    os.makedirs(os.path.join(out_dir, "assets", "sfx"), exist_ok=True)

    video_rel = ""
    if video:
        # Nome seguro para URL (espaços/parênteses quebram o carregamento no Studio)
        video_rel = "assets/" + re.sub(r"[^\w.-]+", "_", os.path.basename(video)).strip("_")
        _place(video, os.path.join(out_dir, video_rel))

    doc, report, loose = build(
        groups, style_name=style_name, W=W, H=H, y_lockup=y_lockup, y_plain=y_plain,
        bg="transparent" if video else bg, min_hold=min_hold, video_src=video_rel,
        accent_override=accent_override, style_overrides=style_overrides,
    )

    total = max((g["t1"] for g in groups), default=0.0)
    if video:
        import subprocess
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                           capture_output=True, text=True)
        try:
            total = max(total, float(r.stdout.strip()))
        except ValueError:
            pass
        doc = re.sub(r'(<video id="bg-video"[^>]*data-duration=")[\d.]+', rf"\g<1>{total:.3f}", doc)
    doc = re.sub(r'(<div id="root"[^>]*data-duration=")[\d.]+', rf"\g<1>{total:.3f}", doc)

    # --- Estrutura "plana" por grupo (divs internas viram spans) para o Studio mostrar 1 linha por legenda ---
    def _flatten(m):
        inner = re.sub(r"<div\b", "<span", m.group(2))
        inner = re.sub(r"</div>", "</span>", inner)
        return m.group(1) + inner + m.group(3)
    doc = re.sub(r'^(<div id="g\d+" class="clip grp"[^>]*>)(.*)(</div>)$', _flatten, doc, flags=re.MULTILINE)
    doc = re.sub(r'(<div id="g\d+" class="clip grp")', r'\1 data-track-index="3"', doc)
    # Itálicos e serifas passam um pouco da caixa medida: sobra intencional, não erro de layout
    doc = doc.replace('<span class="cell"', '<span class="cell" data-layout-allow-overflow')
    # Estilo sem brilho (shine totalmente transparente): remove a camada de luz e as animações dela
    if all(re.search(r"rgba\([^)]*,\s*0\)$", c.replace(" ", "")) for c in st.get("shine", ("#fff", "#fff"))):
        doc = re.sub(r'<span id="g\d+-sh" class="shine"[^>]*>.*?</span></span>', "", doc)
        doc = re.sub(r'^tl\.[a-zA-Z]+\("#g\d+-sh".*$\n?', "", doc, flags=re.MULTILINE)
    doc = doc.replace("</style>", f"""
.grp{{position:absolute;inset:0;width:{W}px;height:{H}px;pointer-events:none;z-index:95;}}
.grp .lockup,.grp .stairs,.grp .anchor,.grp .cell{{pointer-events:none;}}
.grp .line *,.grp .plain-row *,.grp .st-line *{{pointer-events:none;}}
/* Linha montada palavra por palavra: cada palavra é o texto selecionável (a linha não) */
.grp .line:has([id*="-w"]),.grp .plain-row:has([id*="-w"]){{pointer-events:none;}}
.grp [id*="-w"]{{pointer-events:auto!important;cursor:move;}}
/* palavra-chave que virou texto da própria palavra (classes txt + kw) mantém a cor de destaque */
.grp .line.small .txt.kw{{color:{st.get("support_kw_color", st["accent"])};}}
/* Só as LINHAS (e a legenda simples) são selecionáveis: o Studio edita uma linha sem apagar o resto */
.grp .line,.grp .plain-row,.grp .st-line{{pointer-events:auto;cursor:move;}}
.grp .anchor{{position:absolute;left:0;right:0;width:{W}px;height:0;display:flex;align-items:center;justify-content:center;}}
.grp .plain-row{{display:block;margin:0 auto;}}
.grp .lockup,.grp .cell{{display:block;}}
.grp .line{{display:block;}}
</style>""", 1)

    doc = _flatten_leaves(doc)
    doc = _move_line_motion_to_cell(doc)
    doc = _make_studio_safe(doc, st, W, H)
    # No projeto cada palavra é um texto próprio: a cor dada a uma PALAVRA no Studio tem que valer.
    # A regra do motor "tudo dentro de linha colorida herda a cor" passa a valer só para quem não tem cor própria.
    doc = doc.replace('.line.small[style*="color"] .kw,.line.small [style*="color"]{color:inherit!important;}',
                      '.line.small[style*="color"] .kw:not([style*="color"]){color:inherit!important;}')

    # --- SFX como clipes de áudio independentes na timeline ---
    sfx_tags = []
    if sfx:
        preset = SFX_PRESETS[sfx]
        for files, *_ in preset.values():
            for f in files:
                _place(os.path.join(SFX_DIR, f), os.path.join(out_dir, "assets", "sfx", f))
        # Volume: --sfx-volume multiplica o padrão de cada camada (1 = padrão)
        mult = 1.0 if sfx_volume is None else sfx_volume
        n = {"hit": 0, "typing": 0}
        last_sfx = -1e9
        for g in groups:
            if sfx_on == "lockup" and g["kind"] != "lockup":
                continue
            # densidade: referências usam ~1 SFX a cada 10–15 s; sfx_min_gap evita som em todo destaque
            if g["t0"] - last_sfx < sfx_min_gap:
                continue
            last_sfx = g["t0"]
            lines = g.get("lines") or [{"role": "main", "t0": g["t0"]}]
            main_t0 = next((l["t0"] for l in lines if l["role"] == "main"), g["t0"])
            above = next((l for l in lines if l["role"] == "above"), None)
            if "typing" in preset and above is not None:
                files, _, delay, vol = preset["typing"]
                t = above["t0"] + delay
                dur = min(1.2, max(0.25, main_t0 - t + 0.04))
                f = files[n["typing"] % len(files)]
                sfx_tags.append(
                    f'<audio id="sfx-typing-{n["typing"]}" class="clip" src="assets/sfx/{f}" data-start="{t:.3f}" '
                    f'data-duration="{dur:.3f}" data-track-index="6" data-volume="{round(vol * mult, 3)}" '
                    f'data-fade-out="0.06"></audio>'
                )
                n["typing"] += 1
            files, dur, delay, vol = preset["hit"]
            f = files[n["hit"] % len(files)]
            sfx_tags.append(
                f'<audio id="sfx-hit-{n["hit"]}" class="clip" src="assets/sfx/{f}" data-start="{main_t0 + delay:.3f}" '
                f'data-duration="{dur:.3f}" data-track-index="5" data-volume="{round(vol * mult, 3)}"></audio>'
            )
            n["hit"] += 1
    broll_tags = [t.replace("{W}", str(W)).replace("{H}", str(H)) for t in _broll_tags(out_dir)]
    doc = doc.replace('<div class="shadow-overlay"></div>', "\n".join(broll_tags + sfx_tags + ['<div class="shadow-overlay"></div>']), 1)

    # --- Fundo sólido (preto com vídeo; aparece se o vídeo for ocultado no Studio) ---
    page_bg = "#000000" if video else bg
    doc = re.sub(r"html,body\{margin:0;padding:0;background:[^;]*;\}",
                 f"html,body,#root{{margin:0;padding:0;background:{page_bg};}}", doc, count=1)

    doc = doc.replace('<div class="shadow-overlay"></div>', '<div id="degrade" class="shadow-overlay"></div>', 1)
    doc = doc.replace("<style>", "<style>\n" + _font_faces(st, out_dir) + "\n", 1)

    # --- Variáveis editáveis no Studio / no render (--variables) ---
    main_c = _first_color(st.get("main_css"), "#ffffff")
    small_c = _first_color(st.get("small_css"), "#ffffff")
    acc_c = accent_override or st.get("accent", main_c)
    variables = [
        {"id": "cor_principal", "type": "color", "label": "Cor da palavra principal", "default": main_c},
        {"id": "cor_destaque", "type": "color", "label": "Cor da palavra destacada", "default": acc_c},
        {"id": "cor_apoio", "type": "color", "label": "Cor das palavras de apoio", "default": small_c},
        {"id": "cor_fundo", "type": "color", "label": "Cor do fundo (aparece sem vídeo)", "default": page_bg},
        {"id": "deslocar_y", "type": "number", "label": "Mover TODAS as legendas (px, negativo sobe)", "default": 0, "min": -900, "max": 300, "step": 10},
        {"id": "escala", "type": "number", "label": "Escala de todas as legendas (1 = original)", "default": 1, "min": 0.5, "max": 1.5, "step": 0.05},
        {"id": "sombra", "type": "boolean", "label": "Sombra no texto", "default": True},
        {"id": "degrade_inferior", "type": "boolean", "label": "Degradê escuro na base do vídeo", "default": bool(video)},
        {"id": "opacidade_degrade", "type": "number", "label": "Opacidade do degradê (0 a 1)", "default": 1, "min": 0, "max": 1, "step": 0.05},
        {"id": "fonte_principal", "type": "enum", "label": "Fonte da palavra principal (rode --rebuild p/ reencaixar)",
         "options": [{"value": f, "label": f} for f in sorted(set(MAIN_FONTS + [st["main_font"]]))], "default": st["main_font"]},
        {"id": "peso_principal", "type": "number", "label": "Peso da principal (300 fina a 900 grossa)", "default": int(st["main_weight"]), "min": 100, "max": 900, "step": 100},
        {"id": "italico_principal", "type": "boolean", "label": "Principal em itálico", "default": st.get("main_style") == "italic"},
        {"id": "fonte_apoio", "type": "enum", "label": "Fonte das palavras de apoio",
         "options": [{"value": f, "label": f} for f in sorted(set(SMALL_FONTS + [st["small_font"]]))], "default": st["small_font"]},
        {"id": "peso_apoio", "type": "number", "label": "Peso das palavras de apoio (300 a 900)", "default": int(st["small_weight"]), "min": 100, "max": 900, "step": 100},
    ]
    # Mantém o que foi escolhido no painel (cores, posição, degradê...) como valor padrão da nova versão
    for v in variables:
        old = prev_vars.get(v["id"])
        if old is None:
            continue
        # número inteiro e decimal são compatíveis (ex.: escala 1 -> 0,9); bool só com bool
        both_num = all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (old, v["default"]))
        if both_num or type(old) is type(v["default"]):
            v["default"] = old
    var_attr = json.dumps(variables, ensure_ascii=False).replace("'", "&#39;")
    doc = doc.replace('<html lang="pt-BR"', f"<html lang=\"pt-BR\" data-composition-variables='{var_attr}'", 1)
    var_js = """
(function(){
  var V = (window.__hyperframes && window.__hyperframes.getVariables) ? window.__hyperframes.getVariables() : {};
  var css = "";
  if (V.cor_fundo) css += "html,body,#root{background:" + V.cor_fundo + "!important}";
  if (V.cor_principal) css += "#root .line.main{color:" + V.cor_principal + "}";
  // Estilos sem cor de destaque (destaque == principal): mudar a principal muda as duas
  var acc = V.cor_destaque;
  if (SAME_ACC && (!acc || String(acc).toLowerCase() === DEF_ACC)) acc = V.cor_principal;
  if (acc) css += "#root .line.main.acc,#root .w.acc{color:" + acc + "}";
  if (V.cor_apoio) css += "#root .line.small,#root .plain-row .w:not(.acc),#root .st-line:not(.st-main){color:" + V.cor_apoio + "}";
  var dy = Number(V.deslocar_y || 0), sc = Number(V.escala || 1);
  if (dy || sc !== 1) css += ".anchor{transform:translateY(" + dy + "px) scale(" + sc + ");transform-origin:50% 0}";
  if (V.sombra === false) css += ".main .txt .ch,.small .txt,.plain-row{text-shadow:none!important}";
  if (V.degrade_inferior === false) css += ".shadow-overlay{display:none}";
  if (V.opacidade_degrade !== undefined && Number(V.opacidade_degrade) !== 1) css += ".shadow-overlay{opacity:" + Math.max(0, Math.min(1, Number(V.opacidade_degrade))) + "}";
  // Prévia da troca de fonte/peso (o encaixe exato entre as linhas é recalculado no --rebuild)
  if (V.fonte_principal) css += ".main{font-family:'" + V.fonte_principal + "',serif!important}";
  if (V.peso_principal) css += ".main{font-weight:" + Number(V.peso_principal) + "!important}";
  if (V.italico_principal !== undefined) css += ".main{font-style:" + (V.italico_principal ? "italic" : "normal") + "!important}";
  if (V.fonte_apoio) css += ".small,.plain-row{font-family:'" + V.fonte_apoio + "',sans-serif!important}";
  if (V.peso_apoio) css += ".small,.plain-row{font-weight:" + Number(V.peso_apoio) + "!important}";
  var el = document.createElement("style"); el.id = "caption-vars"; el.textContent = css; document.head.appendChild(el);
})();
"""
    var_js = var_js.replace("SAME_ACC", "true" if acc_c.lower() == main_c.lower() else "false", 1)
    var_js = var_js.replace("DEF_ACC", json.dumps(acc_c.lower()), 1)
    doc = doc.replace("<script>\nwindow.__timelines", "<script>" + var_js + "window.__timelines", 1)

    gen_doc = doc
    if preserve_edits:
        edits = _studio_edits(index_path)
        # Categoria de SFX silenciada inteira no Studio (ex.: toda a digitação) -> novos clipes dela também
        for prefix in ("sfx-typing-", "sfx-hit-"):
            ids = [k for k in edits if k.startswith(prefix)]
            if ids and all("data-hidden" in edits[k] for k in ids):
                for k in re.findall(rf'id="({prefix}\d+)"', doc):
                    edits.setdefault(k, {})["data-hidden"] = ""
        old_html = open(index_path, encoding="utf-8").read() if os.path.exists(index_path) else ""
        doc = _apply_edits(doc, _guard_by_text(edits, old_html, doc))
        # ignora o que o próprio motor gerou na versão anterior (só fica o que o usuário mudou)
        _bpath = os.path.join(out_dir, ".caption_baseline.json")
        _base = json.load(open(_bpath, encoding="utf-8")) if os.path.exists(_bpath) else {}
        _tr = {}
        _own = _style_map(old_html)  # só vale o que está no style do PRÓPRIO elemento (não de um filho)
        for _id, _props in _studio_transforms(index_path).items():
            _keep = {k: v for k, v in _props.items()
                     if _base.get(_id, {}).get(k) != v and k in _own.get(_id, {})}
            if _keep:
                _tr[_id] = _keep
        doc = _apply_transforms(doc, _guard_by_text(_tr, old_html, doc))
        # Fonte, tamanho, cor, sombra... mudados numa linha no Studio (comparando com o que foi gerado)
        style_edits = _studio_style_edits(index_path, os.path.join(out_dir, ".caption_baseline.json"))
        doc = _apply_transforms(doc, _guard_by_text(style_edits, old_html, doc))
    with open(os.path.join(out_dir, ".caption_baseline.json"), "w", encoding="utf-8") as f:
        json.dump(_style_map(gen_doc), f, ensure_ascii=False)
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(doc)
    with open(os.path.join(out_dir, "groups.json"), "w", encoding="utf-8") as f:
        json.dump({"groups": src_groups}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "project.json"), "w", encoding="utf-8") as f:
        json.dump({"style": style_name, "video": video, "sfx": sfx, "sfx_volume": sfx_volume, "sfx_on": sfx_on,
                   "W": W, "H": H, "y_lockup": y_lockup, "y_plain": y_plain, "bg": bg, "min_hold": min_hold,
                   "accent": accent_override, "fps": fps, "lead": lead, "lead_plain": lead_plain, "tail": tail, "sfx_min_gap": sfx_min_gap, "auto_y": auto_y, "keywords": keywords or [], "style_overrides": style_overrides, "report": report, "loose": loose},
                  f, ensure_ascii=False, indent=1)
    if not os.path.exists(os.path.join(out_dir, "hyperframes.json")):
        with open(os.path.join(out_dir, "hyperframes.json"), "w", encoding="utf-8") as f:
            json.dump({"$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
                       "paths": {"assets": "assets"}, "media": {"autoProxy": True}}, f, indent=2)
    if not os.path.exists(os.path.join(out_dir, "package.json")):
        hf = "npx --yes hyperframes@0.8.179"
        with open(os.path.join(out_dir, "package.json"), "w", encoding="utf-8") as f:
            json.dump({"name": os.path.basename(os.path.abspath(out_dir)).lower().replace(" ", "-"), "private": True,
                       "scripts": {"dev": f"{hf} preview", "check": f"{hf} check",
                                   "render": f"{hf} render --fps {fps}"}}, f, indent=2)
    return os.path.join(out_dir, "index.html")


def rebuild_project(out_dir):
    """Regenera o index.html a partir de groups.json + project.json (após editar textos/tempos)."""
    cfg = json.load(open(os.path.join(out_dir, "project.json"), encoding="utf-8"))
    groups = json.load(open(os.path.join(out_dir, "groups.json"), encoding="utf-8"))["groups"]
    return build_project(
        groups, out_dir, style_name=cfg["style"], video=cfg.get("video"), sfx=cfg.get("sfx"),
        sfx_volume=cfg.get("sfx_volume"), sfx_on=cfg.get("sfx_on", "lockup"), W=cfg["W"], H=cfg["H"],
        y_lockup=cfg["y_lockup"], y_plain=cfg["y_plain"], bg=cfg["bg"], min_hold=cfg["min_hold"],
        accent_override=cfg.get("accent"), fps=cfg.get("fps", 30), lead=cfg.get("lead", 0.0), lead_plain=cfg.get("lead_plain"), tail=cfg.get("tail", 0.15),
        sfx_min_gap=cfg.get("sfx_min_gap", 0.0),
        auto_y=cfg.get("auto_y"), keywords=cfg.get("keywords"),
    )
