# Reels Captions Kit (Subtitles Studio)

Legendas dinâmicas estilo **Lockup** para Reels, TikTok e Shorts: uma palavra gigante no centro com as palavras de apoio encaixadas nos vãos reais das letras, animadas com GSAP e prontas para o **[HyperFrames](https://github.com/heygen-com/hyperframes)**.

O que esta versão traz:

- **8 estilos prontos** (`serif_clean`, `barlow_drive`, `sans_solid`, `jakarta_clean`, `escadinha`, `acumulativo`, `inverso`, `maquina_pop`) e um template para criar o seu.
- **Projeto editável no HyperFrames Studio:** gera uma vez, ajusta na mão (fonte, tamanho, cor, posição de cada linha ou palavra) e exporta. Regenerar com `--rebuild` **mantém** o que você mudou.
- **Destaque pelo sentido da fala** (não pelo tamanho da palavra), com palavras-chave do cliente e ritmo de lockup só nos momentos-chave.
- **Tempo preso à fala:** a legenda sai logo depois da última palavra, sem tela vazia nem sobreposição.
- **B-rolls em tela cheia** nas palavras de impacto, com re-codificação automática para o render não falhar.
- **Render sem tremor nas letras** e documentação das armadilhas do HyperFrames que resolvemos.
- Funciona como **skill do Claude Code** e como **CLI/biblioteca Python**.

## Instalação

Requisitos: Python 3.9+, [ffmpeg](https://ffmpeg.org/) e Node.js (o HyperFrames roda com `npx hyperframes`).

### Como skill do Claude Code (recomendado)

```bash
# macOS / Linux
git clone https://github.com/Thelimaf/reels-captions-kit ~/.claude/skills/subtitles-studio
pip install -r ~/.claude/skills/subtitles-studio/requirements.txt
```

```powershell
# Windows (PowerShell)
git clone https://github.com/Thelimaf/reels-captions-kit "$env:USERPROFILE\.claude\skills\subtitles-studio"
pip install -r "$env:USERPROFILE\.claude\skills\subtitles-studio\requirements.txt"
```

Abra uma conversa nova no Claude Code. A skill aparece como `/subtitles-studio` (e ativa sozinha quando você pede para legendar um vídeo). Para atualizar: `git pull` dentro da pasta.

### Só como CLI

```bash
git clone https://github.com/Thelimaf/reels-captions-kit
cd reels-captions-kit
pip install -r requirements.txt
python cli.py --list-styles
```

## Começo rápido

```bash
# Demo de um estilo
python cli.py --demo --style serif_clean

# Vídeo → transcrição → projeto editável (legendas + cliques suaves nas palavras de destaque)
python cli.py --media meu_video.mp4 --style serif_clean --project projetos/meu_video --sfx click

# Abrir no Studio (timeline, painel Variables, botão Export)
cd projetos/meu_video
HF_DE_PARALLEL_ROUTER=false npx hyperframes preview

# Depois de editar textos ou tempos em projetos/meu_video/groups.json
python cli.py --rebuild projetos/meu_video

# Render em máxima qualidade
HF_DE_PARALLEL_ROUTER=false npx hyperframes render . --fps 30 --quality delivery --crf 14 -o saida.mp4
```

> **Importante:** renderize e abra o Studio sempre com `HF_DE_PARALLEL_ROUTER=false`. Sem isso, vídeos de mais de ~700 quadros são renderizados por 3 processos que se alternam e as letras finas (cedilha, til, serifas) tremem.

## Estilos

| Estilo | Visual |
|---|---|
| `serif_clean` (padrão) | Playfair Display itálico + Montserrat, off-white |
| `barlow_drive` | Barlow Condensed caixa alta; legenda comum pequena + lockup nos destaques |
| `sans_solid` | Archivo 700 + Inter 500, branco |
| `jakarta_clean` | Plus Jakarta Sans 700/500, branco |
| `escadinha` | linhas em degraus, entram uma a uma |
| `acumulativo` | a frase se monta palavra a palavra, principal em cor de destaque |
| `inverso` | legenda invertida (blend `difference`), 1–2 palavras |
| `maquina_pop` | palavra principal letra a letra com pop |

Criar o seu: copie `styles/_TEMPLATE_NOVO_ESTILO.py` para `styles/meu_estilo.py`, edite o dicionário `STYLE` e rode `python cli.py --demo --style meu_estilo`. Fontes do Google Fonts são baixadas automaticamente. Um estilo é um único arquivo: dá para enviar para outra pessoa.

## Edição no Studio

- Clique numa linha: o painel **Text** muda fonte, tamanho, peso e cor só dela. Mover: setas (Shift = 10 px) ou arrastar.
- O painel **Variables** muda cores, fonte, posição vertical, escala, sombra e degradê de todas as legendas. Clique em **Set default** para gravar.
- `--rebuild` mantém fonte, tamanho, cor, posição, rotação e escala editados, clipes ocultos, volumes e b-rolls apagados.

## B-rolls em tela cheia

Crie `projetos/<nome>/brolls.json` e rode `--rebuild`:

```json
{"clips": [{"id": "sopa", "src": "/caminho/clip.mp4", "start": 10.75, "duration": 1.6, "position": "50% 50%", "brilho": 0.72}]}
```

Cada clipe entra numa trilha própria (acima do vídeo, abaixo das legendas). Para buscar e aprovar clipes de bancos de vídeo, use a skill [get-brolls](https://github.com/engenheirodevideo/get-brolls). Veja o `SKILL.md` (seção 2.2) para o fluxo completo.

## Documentação completa

Todo o detalhe (flags do CLI, projeto editável, SFX, regras de qualidade, como criar estilos, armadilhas do render) está no [`SKILL.md`](SKILL.md), escrito para ser lido tanto por pessoas quanto pelo Claude.

## Créditos e licença

Este projeto parte do [`NicolasCoder/subtitles_studio`](https://github.com/NicolasCoder/subtitles_studio) (motor Lockup e estilos originais). Os estilos novos, o projeto editável, a edição direta no Studio, a integração de b-rolls e as correções de render são adições posteriores. O repositório original não declara licença: antes de redistribuir publicamente, confirme com o autor e adicione um arquivo `LICENSE`.

Os efeitos sonoros de `sfx/` são sintetizados (script `sfx/_gerar_sons.py`) e podem ser trocados por sons seus mantendo o nome do arquivo. As fontes de `fonts/` são do Google Fonts (licença OFL).
