---
name: subtitles-studio
description: Legendas dinâmicas estilo Lockup (palavra gigante + palavras de apoio encaixadas nos vãos das letras) para Reels/TikTok/Shorts no HyperFrames, com projeto editável no Studio, 8 estilos prontos (serif_clean, barlow_drive, sans_solid, jakarta_clean, escadinha, acumulativo, inverso, maquina_pop), SFX, edição manual preservada no --rebuild, b-rolls em tela cheia e render em máxima qualidade sem tremor nas letras. Use quando o usuário pedir para legendar um vídeo, criar ou ajustar um estilo de legenda, abrir ou editar o projeto no Studio, colocar b-rolls em um vídeo, regenerar com --rebuild ou renderizar o vídeo final.
---

# Subtitles Studio — Legendas dinâmicas Lockup + montagem de Reels

## 0. Instalação e caminhos

Esta pasta é independente: `caption_kit/` (motor), `styles/` (estilos), `fonts/`, `sfx/`, `examples/` e `cli.py`.

- **SK** = a pasta onde esta skill está instalada (`~/.claude/skills/subtitles-studio`; no Windows `%USERPROFILE%\.claude\skills\subtitles-studio`). Todos os comandos usam `python "$SK/cli.py"`; no shell, defina `SK` com o caminho real dessa pasta.
- **Projetos** ficam em qualquer pasta passada em `--project` (caminho absoluto). Use uma pasta de projetos do usuário (chamada `$PROJ` abaixo) e guarde cópias antes de regenerar (`$PROJ/_versoes/<nome>/`).
- **Repositório:** https://github.com/Thelimaf/reels-captions-kit (instalar com `git clone ... ~/.claude/skills/subtitles-studio`).
- **Dependências:** Python 3.9+ com `pip install -r "$SK/requirements.txt"`, `ffmpeg`/`ffprobe` e Node (`npx hyperframes`). Confira com `python "$SK/cli.py" --list-styles`.
- **Saídas de demonstração** (`--demo`, `--words` sem `--project`) vão para `./output/<estilo>`, na pasta onde o comando foi rodado.
- **Novos estilos e melhorias:** crie arquivos em `$SK/styles/` (seção 4) ou ajuste `$SK/caption_kit/`.

**Estilos incluídos (8):**

| Estilo | Visual |
|---|---|
| `serif_clean` (padrão) | Playfair Display itálico + Montserrat, off-white; elegante, saúde/bem-estar |
| `barlow_drive` | Barlow Condensed caixa alta + Barlow; dois trilhos (legenda comum pequena + lockup nos destaques) |
| `sans_solid` | Archivo 700 + Inter 500, branco; limpo e moderno |
| `jakarta_clean` | Plus Jakarta Sans 700/500, branco |
| `escadinha` | linhas em degraus, entram uma a uma |
| `acumulativo` | a frase se monta palavra a palavra; principal maior em cor de destaque (Oswald) |
| `inverso` | legenda invertida (`mix-blend-mode: difference`), 1–2 palavras, corte seco |
| `maquina_pop` | palavra principal letra a letra com pop; linha de cima recua |

## 1. Visão geral para a IA

O motor gera legendas **Lockup** (uma palavra principal gigante com palavras menores encaixadas geometricamente nos vãos reais dos glifos da fonte) para o **HyperFrames** (`1080x1920 @ 30fps`).

```text
subtitles-studio/
├── SKILL.md, README.md, requirements.txt, pyproject.toml
├── cli.py                    # interface de linha de comando
├── sfx/                      # tick_1..6, typing_a/b/c, mouse_1/2, whoosh_soft_a/b
├── fonts/                    # .woff2 locais (outras famílias do Google Fonts são baixadas sozinhas)
├── examples/                 # words/groups de demonstração
├── styles/                   # 1 arquivo .py = 1 estilo compartilhável (+ _TEMPLATE_NOVO_ESTILO.py)
└── caption_kit/
    ├── nesting.py            # geometria real de glifos + download de Google Fonts
    ├── grouper.py            # agrupador palavra a palavra (ritmo, destaque pelo sentido, anti-pisca)
    ├── renderer.py           # compilador HTML/CSS/GSAP e carregador de styles/
    ├── project.py            # projeto HyperFrames EDITÁVEL (vídeo + legendas + SFX + b-rolls + variáveis)
    ├── placement.py          # altura automática de cada legenda pelo contraste com o vídeo
    ├── align.py              # realinha tempos a partir de uma transcrição mais precisa (--retime)
    └── transcribe.py         # transcrição palavra a palavra (CrisperWhisper / faster-whisper / whisper)
```

## 2. Linha de comando (`cli.py`)

```bash
python "$SK/cli.py" --list-styles
python "$SK/cli.py" --demo --style serif_clean
python "$SK/cli.py" --words "$SK/examples/demo_words_pt.json" --style barlow_drive --out output/teste
python "$SK/cli.py" --words "$SK/examples/demo_words_pt.json" --style serif_clean --accent "#00ff88"
python "$SK/cli.py" --media meu_video.mp4 --lang pt --style sans_solid --video meu_video.mp4
```

## 2.1 Projeto editável no HyperFrames Studio (gera 1x, ajusta na mão, exporta)

```bash
# Vídeo → transcrição → projeto com legendas + cliques suaves nas palavras de destaque
python "$SK/cli.py" --media meu_video.mp4 --style serif_clean --project "$PROJ/meu_video" --sfx click

# A partir de grupos prontos (sem vídeo, fundo escuro)
python "$SK/cli.py" --groups "$SK/examples/demo_showcase.json" --style serif_clean --project "$PROJ/demo" --sfx click

# Abrir no Studio (timeline + painel Variables + botão Export)
cd "$PROJ/meu_video" && HF_DE_PARALLEL_ROUTER=false npx hyperframes preview
```

O que fica editável **sem passar pela IA**:
- **Timeline:** cada legenda é um clipe (trilha 3), cada SFX é um clipe `<audio>` (trilha 5/6) e cada b-roll é um clipe `<video>` (trilha 1): mover, aparar, ocultar, apagar, mudar volume.
- **Painel Variables:** cores (`cor_principal`, `cor_destaque`, `cor_apoio`, `cor_fundo`), `deslocar_y` (move TODAS as legendas juntas), `escala`, `sombra`, `degrade_inferior`, `opacidade_degrade`, `fonte_principal`/`fonte_apoio`, `peso_principal`/`peso_apoio` e `italico_principal`. Mudar uma variável mostra a prévia na hora; só **Set default** (ou gravar o valor em `data-composition-variables` do `index.html`) faz o `--rebuild` e o render manterem. Troca de fonte/peso: a prévia é aproximada; rode `--rebuild` para o motor baixar a fonte e recalcular o encaixe.
- **Export:** botão Export do Studio, ou `npx hyperframes render` (seção 2.2).

**Edição direta no Studio (editor padrão)**
- Cada linha da legenda é um texto próprio: clique nela e o painel **Text** mostra Conteúdo, Fonte, Tamanho, Peso, Espaçamento e Altura. Mudar uma linha não afeta as outras. Em linhas montadas palavra por palavra (revelação por palavra, layout espalhado), cada palavra é o texto selecionável.
- Mover: selecione a linha e use as setas (Shift+seta = 10 px) ou arraste. A animação de entrada fica no invólucro da linha (`gN-lK-c`), então a linha em si pode ser movida.
- O estilo de cada parte fica escrito no próprio elemento (inline): mesmo que o Studio reescreva um bloco, nada volta para a fonte padrão.
- `--rebuild` compara com o que o motor gerou (`.caption_baseline.json`) e mantém o que o usuário mudou no Studio: fonte, tamanho, peso, cor, posição, rotação e escala; também clipes ocultos, volumes e fades. Edições só são reaplicadas se o elemento tiver o mesmo texto de antes.
- Cor dada a uma **palavra** vale (não é sobrescrita pela cor da linha); cor da linha continua herdada pelas letras.

**Ritmo, destaque e posição (padrão nos projetos)**
- `--rhythm key` (padrão): lockup só nos momentos-chave (gancho, palavras fortes, números, retomadas após pausa), no máximo `--lockup-ratio 0.4` dos blocos e nunca dois seguidos; o resto vira legenda simples. `--rhythm all` faz tudo lockup.
- `--keywords arquivo.txt` (ou `"a,b,c"`): palavras do assunto/cliente que devem virar destaque. Muletas ("acho", "quase", "é", "aí"…) nunca viram principal.
- **Revisão pelo sentido (tarefa do agente):** depois de gerar, leia o `groups.json` e ajuste cada bloco pelo significado: `"kind": "lockup"|"plain"` e `"main_word": "<palavra do bloco>"`; depois `python "$SK/cli.py" --rebuild "$PROJ/<nome>"`. Destaque o soco da frase, não a primeira palavra longa.
- Posição automática (liga sozinha com vídeo; `--no-auto-y` desliga): cada legenda vai para a altura, dentro de 62–78% da tela, onde o fundo dá mais leitura, evitando áreas claras. Não adiciona sombra. Um `"y": 0.7` no grupo tem prioridade.
- Para mudar **texto ou tempo**, edite `"$PROJ/<nome>/groups.json"` e rode `--rebuild` (recalcula o encaixe em segundos; o Studio recarrega sozinho).

**Tempo preso à fala**
- Cada bloco termina 0,15 s depois da última palavra falada; se a próxima frase vem em menos de 0,35 s, emenda nela. `--lead 0.3` adianta só a ENTRADA (legendas e SFX), nunca a saída; `--lead-plain` adianta a legenda comum. As palavras guardam `t0`/`t1` no `groups.json`.
- Transcrição mais precisa (ex.: ElevenLabs scribe, fim de palavra ~0,1 s mais exato que o Whisper): `--rebuild "$PROJ/<nome>" --retime transcricao.json` alinha por texto sem perder as escolhas de destaque.
- Entradas rápidas por padrão (~0,3 s na principal); cada estilo ajusta com `"speed"` (1.3 mais rápido, 0.8 mais calmo).

**Dois trilhos e chaves de estilo**
- Legenda comum pequena em todas as falas + lockup só nos destaques (`--rhythm key`). Chaves: `"plain_px"`, `"plain_entry": "cut"`, `"plain_max_words": 3`, `"exit": "cut"`, `--sfx-min-gap 4` (no máximo 1 som a cada 4 s). Exemplo: `styles/barlow_drive.py`.
- Padrões além do lockup: `"layout": "plain"` + `"blend": "difference"` (inverso); `"layout": "stairs"` (escadinha); `"layout": "accumulate"` (acumulativo); `"variants": ("typepop",)` + `"dim_previous"` (maquina_pop); lockup espalhado com `"small_layout": "spread"`, `"small_entry": "blurin"`, `"support_kw_color"` (palavras de apoio-chave em outra cor). Qualquer estilo combina essas chaves.
- Fontes: o projeto copia os `.woff2` do estilo para `assets/fonts` e declara `@font-face`. Pesos intermediários (500/600) são baixados sob demanda. Trocar de estilo num projeto (`project.json` → `style`) descarta as fontes/cores escolhidas no painel do estilo antigo.

**SFX (`--sfx`)** — cada som é um clipe próprio na timeline:

| Preset | O que toca | Trilha |
| :--- | :--- | :--- |
| `click` (padrão) | tique suave quando a palavra principal entra | 5 |
| `typing` | digitação enquanto a linha de apoio entra + tique na principal | 6 + 5 |
| `mouse` | clique de mouse mais seco na principal | 5 |
| `whoosh` | sopro suave na principal | 5 |
| `none` | sem SFX | — |

`--sfx-volume 0.5` multiplica o volume padrão. No Studio, clique no clipe de som → **Volume**.

## 2.2 Fluxo completo de um vídeo: legendas + b-rolls em tela cheia + Studio + render

1. **Legendas:** `python "$SK/cli.py" --media video.mp4 --project "$PROJ/<nome>" --style serif_clean --sfx click`; abra no Studio e confira quadros.
2. **B-rolls (opcional):** busque, aprove e baixe os clipes com a skill **get-brolls** (https://github.com/engenheirodevideo/get-brolls). Critérios que funcionam: imagens realistas em tela cheia, só nas palavras de impacto, 3 a 5 por vídeo. **A aprovação de cada clipe é do usuário**, nunca da IA. Confira a licença real da fonte (Pexels: pessoa identificável não pode aparecer em "mau contexto").
3. **Montar no projeto:** crie `"$PROJ/<nome>/brolls.json"` e rode `--rebuild`:
   ```json
   {"clips": [{"id": "sopa", "src": "/caminho/clip.mp4", "start": 10.75, "duration": 1.6, "position": "50% 50%", "brilho": 0.72}]}
   ```
   - `start` = início da palavra de impacto (`groups.json` → campo `t0`); 1,4 a 2,8 s por clipe. `position` escolhe a parte de um clipe horizontal (ex.: `75% 50%`). `brilho` (padrão 0,72; 0,45 para fundo branco) escurece o clipe para a legenda branca ler. `media_start` pula o começo do arquivo.
   - O motor **re-codifica** cada clipe para `assets/broll/` (sem áudio, 30 fps, um quadro-chave por segundo, brilho gravado no arquivo); o original não é tocado.
   - Cada clipe vira `<video id="broll-<id>">` na trilha 1 (acima do vídeo, abaixo das legendas). No Studio dá para mover, aparar, ocultar ou **apagar**; o clipe apagado **não volta** no `--rebuild` (registro em `.broll_seen.json`; para recolocar, tire o id desse arquivo).
4. **Visual do cliente:** ajuste as variáveis (`deslocar_y`, `escala`, `sombra`, `degrade_inferior`, cores, fonte) e grave como `default`. Para copiar o visual de um vídeo já exportado pelo cliente, compare quadros do export com o render padrão.
5. **Render em máxima qualidade** (numa pasta separada):
   ```bash
   export TEMP=/pasta/com/espaco TMP=/pasta/com/espaco HF_DE_PARALLEL_ROUTER=false
   npx hyperframes render . --fps 30 --quality delivery --crf 14 -o "saida/video com legenda.mp4"
   ```
   Leva de 3 a 10 min. Depois confira com `ffprobe` (duração e 1080×1920), `volumedetect` (voz igual ao render anterior) e quadros em cada b-roll.
6. **Enviar:** arquivos acima de ~30 MB não vão por chat; gere uma cópia leve (`ffmpeg -i in.mp4 -c:v libx264 -crf 22 -maxrate 3800k -bufsize 7600k -c:a aac -b:a 128k out.mp4`).

**Armadilhas já resolvidas (e como não cair de novo):**
- **Letras tremendo no vídeo final** (cedilha, til, serifas finas): acima de ~700 quadros o HyperFrames renderiza com 3 processos de navegador intercalando quadros, e cada um suaviza as letras de um jeito. Renderize e abra o Studio **sempre** com `HF_DE_PARALLEL_ROUTER=false`; não use `HF_CAPTURE_PARALLEL_STREAM=true`.
- **Disco cheio no Windows:** o render guarda frames temporários; exporte `TEMP`/`TMP` para um disco com espaço.
- **Filtro CSS (`filter: brightness`) em vídeo tela cheia** faz o render estourar o tempo (`Runtime.evaluate timed out`) → escurecer no arquivo (é o que o `brilho` faz).
- **Corte do banco com um só quadro-chave** → `VIDEO_SOURCE_UNRENDERABLE` → o motor já re-codifica.
- **Studio apagava o estilo ao editar uma linha:** o estilo agora é inline em cada parte, só as linhas/palavras são clicáveis e a animação fica no invólucro.
- **Cor da palavra ignorada** por regra de herança → corrigido (cor própria da palavra vale).
- **Legendas fora de ordem ou sobrepostas:** cada bloco termina na fala e nunca invade o próximo.
- A mensagem 422 "media proxy" no `check` é inofensiva (o clipe já é compatível com o navegador).
- Confirme o conteúdo real de cada clipe de banco pelo `source_url` (o título do Pexels é só o número) e descarte o que diz outra mensagem.

## 3. Uso via Python (embutindo em uma composição HyperFrames)

```python
import sys
sys.path.insert(0, "/caminho/para/subtitles-studio")
from caption_kit import build_groups_from_words, render_embeddable

# words = [{"word": "Criar", "start": 0.15, "end": 0.42}, ...]
groups = build_groups_from_words(words, min_hold=0.38)
caps_css, caps_dom, caps_js, report = render_embeddable(
    groups, prefix="v1", style_name="serif_clean",
    accent_override=None, y_lockup=0.74, y_plain=0.75, track_index=3, z_index=95,
)
```

Injete `{caps_css}` na tag `<style>`, `{caps_dom}` dentro do `<div id="root">` e `{caps_js}` no `<script>`, logo após `const tl = gsap.timeline({ paused: true });`.

## 4. Como criar um novo estilo compartilhável (plugins em `styles/`)

- Todo `.py` (ou `.json`) em `styles/` cujo nome não comece com `_` é descoberto sozinho.
- Copie `styles/_TEMPLATE_NOVO_ESTILO.py` para `styles/<nome>.py` e edite o dicionário `STYLE`. Fontes novas do Google Fonts são baixadas automaticamente (`.woff2` em `fonts/<familia>/`).
- Para compartilhar o estilo, basta enviar o arquivo `styles/<nome>.py`.
- Valide: `python "$SK/cli.py" --list-styles` e `python "$SK/cli.py" --demo --style <nome>`.

Principais chaves de `STYLE`: `main_font/weight/style/track/case/lh/css`, `max_px`, `small_font/weight/css/scale` (0.25–0.50 da principal), `plain_*`, `accent`, `accent_extra_css`, `shine`, `tilt`, `clear`, `variants` (`slam`, `letters`, `rise`, `blur`, `typepop`, `blurin`). Use `"main_case": "none"` para preservar ascendentes/descendentes e permitir o encaixe (`"upper"` só com `"nest_mode": "overlap"`).

## 5. Regras de ouro de qualidade

1. **Tempo de leitura:** o agrupador garante no mínimo 0,38 s com a frase completa na tela antes de trocar de bloco; em fala rápida comprime o stagger de entrada para não cortar o final da frase.
2. **Ordem cronológica:** as linhas entram na ordem real da fala (`above` → `main` → `below`).
3. **Zona segura de Reels/TikTok (1080×1920):** padrão `y_lockup=0.74` (~1420 px), na faixa 1300–1560 px (abaixo do rosto e acima dos botões do Reels).
4. **Áudio no HyperFrames:** se o vídeo usar áudio cortado em vários segmentos, nunca use várias tags `<audio>` apontando para o mesmo arquivo com `data-media-start`; pré-corte um único `.wav` contínuo e use uma só tag `<audio data-start="0.000">`.
