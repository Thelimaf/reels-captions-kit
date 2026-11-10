"""
caption_kit/align.py — Reaproveita os blocos de um projeto com tempos de uma transcrição nova

Alinha, por texto, as palavras do groups.json (que podem ter sido editadas à mão) com as palavras de
uma transcrição (ex.: ElevenLabs scribe, mais precisa no fim de cada palavra que o Whisper) e grava
`t0`/`t1` em cada palavra. Palavras sem par recebem tempos interpolados dos vizinhos.
"""
import difflib
import json
import re
import unicodedata


def _norm(t):
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^\w]", "", t)


def load_transcript_words(path):
    """Aceita JSON da ElevenLabs ({"words":[{"text","start","end","type"}]}) ou do Whisper/kit
    ({"words":[{"word","start","end"}]}) ou lista [[texto, início, fim], ...]."""
    d = json.load(open(path, encoding="utf-8"))
    items = d.get("words", d) if isinstance(d, dict) else d
    out = []
    for w in items:
        if isinstance(w, (list, tuple)):
            out.append((str(w[0]), float(w[1]), float(w[2])))
        elif w.get("type", "word") == "word":
            out.append((w.get("text", w.get("word", "")).strip(), float(w["start"]), float(w["end"])))
    return [w for w in out if _norm(w[0])]


def retime_groups(groups, transcript_words):
    """Atualiza `t0`/`t1` das palavras e o `t0` de cada bloco. Retorna (groups, n_alinhadas, n_total)."""
    flat = [(gi, wi) for gi, g in enumerate(groups) for wi, _ in enumerate(g.get("words") or [])]
    a = [_norm(groups[gi]["words"][wi]["text"]) for gi, wi in flat]
    b = [_norm(w[0]) for w in transcript_words]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    times = [None] * len(flat)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                times[i1 + k] = transcript_words[j1 + k][1:]
    # interpola o que ficou sem par
    for k in range(len(times)):
        if times[k] is None:
            prev = next((times[j] for j in range(k - 1, -1, -1) if times[j]), None)
            nxt = next((times[j] for j in range(k + 1, len(times)) if times[j]), None)
            if prev and nxt:
                times[k] = (prev[1], max(prev[1] + 0.05, nxt[0]))
            elif prev:
                times[k] = (prev[1], prev[1] + 0.3)
            elif nxt:
                times[k] = (max(0.0, nxt[0] - 0.3), nxt[0])
    n_ok = sum(1 for op in sm.get_opcodes() if op[0] == "equal" for _ in range(op[2] - op[1]))
    for (gi, wi), t in zip(flat, times):
        if t:
            groups[gi]["words"][wi]["t0"] = round(t[0], 3)
            groups[gi]["words"][wi]["t1"] = round(t[1], 3)
    for g in groups:
        if g.get("words"):
            g["t0"] = g["words"][0]["t0"]
            for ln in g.get("lines", []):
                ln.pop("t0", None)
    return groups, n_ok, len(flat)
