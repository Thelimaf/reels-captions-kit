"""
caption_kit/grouper.py — Agrupador Inteligente Palavra-por-Palavra -> Lockup + Plain

Transforma uma lista de palavras com timestamps (`[{"word": "...", "start": 0.1, "end": 0.4}, ...]`)
em grupos prontos para o motor de legendas dinâmicas, aplicando todas as melhorias validadas:
  - Hold mínimo de 0.38s com a frase COMPLETA na tela antes de trocar de grupo;
  - Compressão automática da revelação quando o locutor fala rápido (nunca corta o fim da frase);
  - Fusão de blocos curtos (<= 2 palavras) com o vizinho para evitar pisca-pisca;
  - Extensão suave em pausas longas (> 0.6s);
  - Seleção semântica da palavra principal (palavras de impacto + substantivos/verbos fortes).
"""
import re

DEFAULT_STOPWORDS = {
    # Português
    "o", "os", "a", "as", "um", "uma", "uns", "umas", "do", "da", "dos", "das", "no", "na", "nos",
    "nas", "ao", "aos", "à", "às", "pelo", "pela", "pelos", "pelas", "de", "em", "por", "com", "sem",
    "sob", "sobre", "para", "pra", "pro", "que", "se", "mas", "ou", "e", "como", "quando", "onde",
    "quem", "qual", "quais", "meu", "minha", "meus", "minhas", "seu", "sua", "seus", "suas",
    "ele", "ela", "eles", "elas", "nós", "você", "vocês", "isso", "isto", "aquilo", "este",
    "esta", "esse", "essa", "já", "só", "não", "sim", "muito", "mais", "menos", "tão", "também",
    "foi", "ser", "ter", "está", "estão", "era", "são", "num", "numa", "até", "entre", "depois",
    # Inglês
    "the", "and", "to", "of", "in", "is", "it", "that", "for", "on", "with", "as", "be", "at",
    "by", "this", "have", "from", "or", "an", "but", "not", "you", "your", "we", "they", "my",
}

DEFAULT_POWER_KEYWORDS = {
    # Português (Criadores, Negócios, Edição, Marketing, Produtividade)
    "segredo", "atenção", "retenção", "viral", "virais", "dinheiro", "lucro", "vendas", "clientes",
    "resultado", "resultados", "agora", "hoje", "nunca", "sempre", "milhões", "mil", "reais",
    "grátis", "bônus", "botão", "vídeo", "vídeos", "edição", "legenda", "legendas", "design",
    "marca", "conteúdo", "estratégia", "crescimento", "engajamento", "algoritmo", "segundos",
    "minutos", "horas", "dias", "foco", "mente", "liberdade", "escala", "sistema", "método",
    "passo", "passos", "erro", "erros", "verdade", "poder", "impacto", "futuro", "sucesso",
    # Inglês
    "money", "secret", "change", "growth", "profit", "results", "never", "always", "free",
}

# Palavras de apoio que nunca devem virar a principal (muletas, auxiliares, dêiticos)
FILLERS = {
    "acho", "quase", "aqui", "ali", "então", "porque", "porquê", "aí", "tipo", "bem", "ainda", "assim",
    "vai", "vou", "vamos", "tem", "têm", "tinha", "estou", "estava", "fica", "ficar", "coisa", "gente",
    "olha", "sabe", "né", "tá", "ok", "eu", "me", "te", "lhe", "mesmo", "mesma", "dele", "dela", "toda",
    "todo", "todos", "todas", "cada", "outro", "outra", "exatamente", "justamente", "realmente",
    "simplesmente", "apenas", "também", "agora", "depois", "antes", "faz", "fazer", "fez", "pode", "posso",
    "quer", "quero", "aquele", "aquela", "isso", "disso", "nisso", "lá", "cá", "nosso", "nossa",
    "pouco", "nada", "algo", "alguma", "algum", "bom", "boa", "vez", "vezes", "dia", "frase", "famoso",
}


def clean_token(w: str) -> str:
    return re.sub(r'^[¿¡"“”‘’\'«»(\[]+|[.,;:!?"“”‘’\'»)\]]+$', "", w.strip())


def build_groups_from_words(
    words,
    min_hold=0.38,
    min_group_dur=0.90,
    lockup_every=1,
    custom_power_keywords=None,
    custom_stopwords=None,
    rhythm="key",
    lockup_ratio=0.4,
    tail=0.15,
    bridge=0.35,
    min_vis=0.45,
):
    """
    Converte lista de palavras `[{"word": str, "start": float, "end": float}, ...]`
    em grupos `lockup` e `plain` prontos para `renderer.build()`.

    `rhythm="key"` (padrão): lockup só nos momentos-chave (gancho, palavras fortes, números,
    retomadas depois de pausa), no máximo `lockup_ratio` dos blocos e nunca dois seguidos; o resto
    vira legenda simples. `rhythm="all"`: comportamento antigo (todo bloco vira lockup).
    Cada grupo guarda `words` (texto + tempo) e `main_word`, então dá para trocar a palavra
    principal ou o tipo (`kind`) direto no groups.json e regenerar com `regroup()`.
    """
    if not words:
        return []

    stopwords = DEFAULT_STOPWORDS | FILLERS | set(custom_stopwords or [])
    power_kw = DEFAULT_POWER_KEYWORDS | {w.lower() for w in (custom_power_keywords or [])}

    chunks = []
    cur = []
    for i, w in enumerate(words):
        raw_w = w.get("word", w.get("text", "")).strip()
        tok = clean_token(raw_w)
        if not tok:
            continue
        cur.append({
            "raw": raw_w,
            "clean": tok,
            "start": float(w["start"]),
            "end": float(w["end"]),
        })
        has_punct = any(raw_w.endswith(p) for p in (".", "?", "!", ",", ";", ":"))
        gap_next = (float(words[i + 1]["start"]) - float(w["end"])) if (i + 1 < len(words)) else 9.0
        char_len = sum(len(x["clean"]) for x in cur)
        if len(cur) >= 6 or (len(cur) >= 4 and (has_punct or gap_next >= 0.28 or char_len >= 24)) or gap_next >= 0.45:
            chunks.append(cur)
            cur = []
    if cur:
        if chunks and len(cur) <= 2:
            chunks[-1].extend(cur)
        else:
            chunks.append(cur)

    # Funde blocos curtos (<= 2 palavras ou < 0.75s) com o vizinho se o gap for pequeno
    merged = []
    for ch in chunks:
        if merged:
            prev = merged[-1]
            gap = ch[0]["start"] - prev[-1]["end"]
            prev_dur = prev[-1]["end"] - prev[0]["start"]
            if (len(ch) <= 2 or (ch[-1]["end"] - ch[0]["start"] < 0.65)) and len(prev) + len(ch) <= 7 and gap < 0.35:
                prev.extend(ch)
                continue
            if len(prev) <= 2 and prev_dur < 0.75 and len(prev) + len(ch) <= 7 and gap < 0.35:
                prev.extend(ch)
                continue
        merged.append(ch)
    chunks = merged

    timed = []
    for idx, ch in enumerate(chunks):
        t0 = round(ch[0]["start"], 3)
        raw_end = ch[-1]["end"]
        next_start = chunks[idx + 1][0]["start"] if (idx + 1 < len(chunks)) else (raw_end + 0.6)
        pause_after = next_start - raw_end
        pause_before = (t0 - chunks[idx - 1][-1]["end"]) if idx else 9.0

        # Fim do bloco = fim da fala: última palavra + `tail`. Se a próxima frase vem logo
        # (pausa < `bridge`), emenda até ela (sem tela vazia piscando); nunca passa do próximo início.
        t1 = round(_block_end(t0, raw_end, next_start, tail, bridge, min_vis), 3)

        # Só comprime as entradas se a última palavra ficaria menos de 0,2 s na tela
        latest_reveal = max(t0 + 0.08, t1 - 0.2)
        orig_last = ch[-1]["start"]
        if orig_last > latest_reveal and orig_last > t0:
            scale_t = (latest_reveal - t0) / (orig_last - t0)
            for w in ch:
                w["start"] = round(t0 + (w["start"] - t0) * scale_t, 3)

        scores = [word_score(w["clean"], stopwords, power_kw) for w in ch]
        best_i = max(range(len(ch)), key=lambda k: scores[k])
        timed.append({"ch": ch, "t0": t0, "t1": t1, "best_i": best_i, "best": scores[best_i],
                      "pause_before": pause_before})

    # --- Ritmo: quais blocos viram lockup ---
    n = len(timed)
    if rhythm == "all":
        chosen = {i for i in range(n) if i % max(1, lockup_every) == 0 and len(timed[i]["ch"]) >= 2}
    else:
        def key_score(i):
            sc = timed[i]["best"]
            if timed[i]["pause_before"] > 0.45:
                sc += 6      # retomada depois de pausa = momento de ênfase
            if i == 0:
                sc += 100    # gancho sempre em destaque
            return sc

        budget = max(1, round(n * lockup_ratio))
        chosen = set()
        for i in sorted(range(n), key=key_score, reverse=True):
            if len(chosen) >= budget:
                break
            if i != 0 and timed[i]["best"] < 8:
                continue     # sem palavra forte o bastante: fica como legenda simples
            if (i - 1) in chosen or (i + 1) in chosen:
                continue     # nunca dois lockups seguidos
            chosen.add(i)

    groups = []
    for idx, t in enumerate(timed):
        g = {"t0": t["t0"], "t1": t["t1"],
             "words": [{"text": w["clean"], "t0": round(w["start"], 3), "t1": round(w["end"], 3)} for w in t["ch"]],
             "main_word": t["ch"][t["best_i"]]["clean"],
             "kind": "lockup" if idx in chosen else "plain"}
        groups.append(_materialize(g, power_kw))
    return groups


def _block_end(t0, last_end, next_start, tail=0.15, bridge=0.35, min_vis=0.45):
    """Fim de um bloco: segue a fala. Emenda no próximo se a pausa for curta; senão termina
    `tail` s depois da última palavra (mínimo `min_vis` s na tela), sem invadir o próximo."""
    if next_start is not None and next_start - last_end < bridge:
        return max(t0 + 0.2, next_start - 0.02)
    end = max(last_end + tail, t0 + min_vis)
    if next_start is not None:
        end = min(end, next_start - 0.02)
    return max(end, t0 + 0.2)


def retime_ends(groups, tail=0.15, bridge=0.35, min_vis=0.45):
    """Recalcula o fim de cada bloco pelo fim real da fala (palavras com `t1`).
    Blocos sem `t1` nas palavras ficam como estão."""
    for i, g in enumerate(groups):
        ws = g.get("words") or []
        if not ws or "t1" not in ws[-1]:
            continue
        nxt = groups[i + 1]["t0"] if i + 1 < len(groups) else None
        g["t1"] = round(_block_end(g["t0"], float(ws[-1]["t1"]), nxt, tail, bridge, min_vis), 3)
    return groups


def word_score(tok, stopwords, power_kw):
    """Peso semântico aproximado de uma palavra para virar a principal do lockup."""
    low = tok.lower()
    score = len(tok)
    if low in power_kw:
        score += 25
    if low in stopwords:
        score -= 20
    if re.fullmatch(r"\d+([.,]\d+)?%?|\d+[kKmM]?", tok):
        score += 22  # números chamam atenção
    if re.search(r"(ção|ções|mento|mentos|dade|dades|ismo|eza|ância|ência|agem|ura)$", low):
        score += 6   # substantivos de conceito
    if re.search(r"(oso|osa|ivo|iva|ável|ível|ado|ada)$", low) and len(low) > 5:
        score += 3   # adjetivos
    if low.endswith("mente"):
        score -= 8   # advérbios raramente são o núcleo
    if len(tok) > 13:
        score -= 8
    return score


def _materialize(g, power_kw=frozenset()):
    """Monta `lines` (lockup) ou `words` com destaque (plain) a partir de `words` + `main_word` + `kind`."""
    ws = g["words"]
    if not ws:
        return g
    if g.get("kind") == "plain" or len(ws) < 2:
        g["kind"] = "plain"
        g.pop("lines", None)
        g["words"] = [dict({"text": w["text"], "t0": w["t0"], "accent": w["text"].lower() in power_kw},
                           **({"t1": w["t1"]} if "t1" in w else {})) for w in ws]
        return g
    target = (g.get("main_word") or "").lower()
    idxs = [k for k, w in enumerate(ws) if w["text"].lower() == target]
    mi = idxs[0] if idxs else max(range(len(ws)), key=lambda k: len(ws[k]["text"]))
    g["main_word"] = ws[mi]["text"]
    lines = []
    if mi > 0:
        lines.append({"role": "above", "text": " ".join(w["text"] for w in ws[:mi]), "t0": ws[0]["t0"], "accent": False})
    lines.append({"role": "main", "text": ws[mi]["text"], "t0": ws[mi]["t0"], "accent": True})
    if mi < len(ws) - 1:
        lines.append({"role": "below", "text": " ".join(w["text"] for w in ws[mi + 1:]), "t0": ws[mi + 1]["t0"], "accent": False})
    g["kind"] = "lockup"
    g["lines"] = lines
    return g


def regroup(groups, power_keywords=None):
    """
    Reaplica edições feitas à mão no groups.json: trocar `main_word`, trocar `kind`
    ("lockup"/"plain") ou corrigir o texto de uma palavra em `words`.
    Grupos antigos (sem `words` com tempo por palavra) são mantidos como estão.
    """
    pk = DEFAULT_POWER_KEYWORDS | {w.lower() for w in (power_keywords or [])}
    out = []
    for g in groups:
        ws = g.get("words")
        if ws and all("t0" in w for w in ws) and ("main_word" in g or g.get("kind") == "plain"):
            g = dict(g)
            g["words"] = [dict({"text": w["text"], "t0": w["t0"]}, **({"t1": w["t1"]} if "t1" in w else {})) for w in ws]
            out.append(_materialize(g, pk))
        else:
            out.append(g)
    return out
