"""
cli.py — Interface de Linha de Comando do Kit de Legendas Dinâmicas (HyperFrames)

Exemplos de uso:
  1. Listar todos os estilos disponíveis na pasta `styles/`:
       python cli.py --list-styles

  2. Gerar um demo rápido de qualquer estilo:
       python cli.py --demo --style serif_clean

  3. Gerar legendas a partir de um arquivo de palavras (words.json com timestamps):
       python cli.py --words examples/demo_words_pt.json --style barlow_drive --out saida_barlow

  4. Gerar legendas trocando apenas a cor de destaque (sem precisar criar arquivo de estilo):
       python cli.py --words examples/demo_words_pt.json --style serif_clean --accent "#00ff88"

  5. Transcrever um áudio/vídeo (.wav/.mp3/.mp4) e já gerar as legendas de uma vez:
       python cli.py --media meu_video.mp4 --lang pt --style sans_solid --video meu_video.mp4

  6. Gerar um PROJETO HyperFrames editável (abre no Studio, ajusta e exporta de lá):
       python cli.py --media meu_video.mp4 --style serif_clean --project projetos/meu_video --sfx click
       npx hyperframes preview projetos/meu_video

  7. Depois de editar textos/tempos em projetos/meu_video/groups.json, regenerar sem renderizar:
       python cli.py --rebuild projetos/meu_video
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from caption_kit import (
    build,
    build_project,
    rebuild_project,
    build_groups_from_words,
    groups_from_simple,
    load_styles,
    transcribe_media,
)

DEMO_GROUPS_PT = [
    {"kind": "lockup", "above": "O verdadeiro", "main": "segredo", "below": "dos vídeos virais", "dur": 1.6, "accent": True},
    {"kind": "plain", "text": "não é sorte nem equipamento caro", "dur": 1.5},
    {"kind": "lockup", "above": "é prender a", "main": "atenção", "below": "nos 3 primeiros segundos", "dur": 1.7, "accent": True},
    {"kind": "lockup", "above": "quando o", "main": "design", "below": "acompanha o ritmo", "dur": 1.6, "accent": False},
    {"kind": "lockup", "above": "a sua", "main": "retenção", "below": "dobra na hora", "dur": 1.7, "accent": True},
]


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--list-styles", action="store_true", help="Lista todos os estilos instalados na pasta styles/")
    ap.add_argument("--demo", action="store_true", help="Gera uma composição de demonstração do estilo escolhido")
    ap.add_argument("--words", help="Caminho para JSON com palavras e timestamps ({'words': [{'word','start','end'}]})")
    ap.add_argument("--groups", help="Caminho para JSON de grupos explícitos (lockup/plain)")
    ap.add_argument("--media", help="Caminho para áudio/vídeo (.wav/.mp3/.mp4) para transcrever e gerar legendas")
    ap.add_argument("--lang", default="pt", help="Idioma da transcrição quando usar --media (pt, en, es)")
    ap.add_argument("--style", default="serif_clean", help="ID do estilo (nome do arquivo em styles/ sem extensão)")
    ap.add_argument("--accent", default=None, help="Sobrescreve a cor de destaque (ex: '#ff3355' ou '#b855ff')")
    ap.add_argument("--out", default=None, help="Pasta de saída (padrão: output/<style>)")
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--y", type=float, default=0.74, help="Posição vertical (0..1) do lockup (padrão 0.74 = faixa segura Reels)")
    ap.add_argument("--y-plain", type=float, default=0.75, help="Posição vertical (0..1) da legenda simples")
    ap.add_argument("--bg", default="transparent", help="Cor de fundo ('transparent' ou ex: '#0a0f18')")
    ap.add_argument("--min-hold", type=float, default=0.42, help="Tempo mínimo (s) de permanência na tela")
    ap.add_argument("--video", default="", help="Vídeo de fundo opcional para incluir na composição HTML")
    ap.add_argument("--project", default=None, help="Gera uma pasta de projeto HyperFrames editável (vídeo + legendas + SFX)")
    ap.add_argument("--sfx", default="click", choices=["click", "typing", "mouse", "whoosh", "none"], help="SFX: click (tique na palavra principal), typing (digitação na linha de apoio + tique), mouse, whoosh ou none")
    ap.add_argument("--sfx-volume", type=float, default=None, help="Multiplica o volume padrão dos SFX (1 = padrão, 0.5 = metade)")
    ap.add_argument("--lead", type=float, default=0.0, help="Adianta legendas e SFX em segundos (ex.: 0.3 = aparecem antes da fala)")
    ap.add_argument("--keywords", default=None, help="Arquivo .txt (uma por linha) ou lista separada por vírgula de palavras que devem virar destaque")
    ap.add_argument("--rhythm", default="key", choices=["key", "all"], help="key: lockup só nos momentos-chave (padrão); all: todo bloco vira lockup")
    ap.add_argument("--lockup-ratio", type=float, default=0.4, help="Máximo de blocos em lockup com --rhythm key (0..1)")
    ap.add_argument("--no-auto-y", action="store_true", help="Desliga a posição automática por contraste (com --project e vídeo)")
    ap.add_argument("--lead-plain", type=float, default=None, help="Lead só da legenda comum (padrão = --lead). Referências: 0–0.15")
    ap.add_argument("--sfx-min-gap", type=float, default=0.0, help="Intervalo mínimo (s) entre SFX; ex.: 4 = no máximo 1 som a cada 4 s")
    ap.add_argument("--retime", default=None, help="Com --rebuild: JSON de transcrição (ElevenLabs/Whisper) para atualizar início e fim de cada palavra do projeto")
    ap.add_argument("--rebuild", default=None, help="Regenera um projeto a partir do groups.json dele")
    args = ap.parse_args()

    kw = []
    if args.keywords:
        if os.path.isfile(args.keywords):
            kw = [l.strip() for l in open(args.keywords, encoding="utf-8") if l.strip()]
        else:
            kw = [k.strip() for k in args.keywords.split(",") if k.strip()]

    if args.rebuild:
        if args.retime:
            from caption_kit.align import load_transcript_words, retime_groups
            from caption_kit.grouper import regroup
            gpath = os.path.join(args.rebuild, "groups.json")
            gdata = json.load(open(gpath, encoding="utf-8"))
            gs, ok, tot = retime_groups(gdata["groups"], load_transcript_words(args.retime))
            json.dump({"groups": regroup(gs)}, open(gpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"[OK] tempos atualizados: {ok}/{tot} palavras alinhadas com {args.retime}")
        print(f"[OK] {rebuild_project(args.rebuild)} regenerado a partir de groups.json")
        return 0

    styles = load_styles()

    if args.list_styles:
        print(f"\n=== Estilos Disponíveis ({len(styles)}) em styles/ ===")
        for sid, st in sorted(styles.items()):
            acc = st.get("accent", "")
            lbl = st.get("label", sid)
            mf = st.get("main_font", "")
            sf = st.get("small_font", "")
            print(f"  • {sid:<16} | {lbl:<48} | Principal: {mf} | Apoio: {sf} | Cor: {acc}")
        print("\nPara criar um novo estilo: copie `styles/_TEMPLATE_NOVO_ESTILO.py` para `styles/meu_estilo.py`!\n")
        return 0

    if args.media:
        out_dir = args.out or os.path.join(os.getcwd(), "output", args.style)
        os.makedirs(out_dir, exist_ok=True)
        words_json = os.path.join(out_dir, "words_transcribed.json")
        print(f"[1/2] Transcrevendo mídia '{args.media}' (idioma={args.lang})...")
        payload = transcribe_media(args.media, out_json_path=words_json, language=args.lang)
        groups = build_groups_from_words(payload["words"], custom_power_keywords=kw, rhythm=args.rhythm, lockup_ratio=args.lockup_ratio)
    elif args.words:
        data = json.load(open(args.words, encoding="utf-8"))
        words_list = data["words"] if isinstance(data, dict) and "words" in data else data
        groups = build_groups_from_words(words_list, custom_power_keywords=kw, rhythm=args.rhythm, lockup_ratio=args.lockup_ratio)
        out_dir = args.out or os.path.join(os.getcwd(), "output", args.style)
    elif args.groups:
        data = json.load(open(args.groups, encoding="utf-8"))
        items = data["groups"] if isinstance(data, dict) and "groups" in data else data
        groups = groups_from_simple(items)
        out_dir = args.out or os.path.join(os.getcwd(), "output", args.style)
    elif args.demo:
        groups = groups_from_simple(DEMO_GROUPS_PT)
        out_dir = args.out or os.path.join(os.getcwd(), "output", f"demo_{args.style}")
        if args.bg == "transparent" and not args.video:
            args.bg = "#0c121e"
    else:
        ap.error("Informe --list-styles, --demo, --words <arq.json>, --groups <arq.json> ou --media <audio_ou_video>.")
        return 1

    if args.project:
        video = args.video or (args.media if args.media and args.media.lower().endswith((".mp4", ".mov", ".webm")) else None)
        idx = build_project(
            groups, args.project, style_name=args.style, video=video,
            sfx=None if args.sfx == "none" else args.sfx, sfx_volume=args.sfx_volume,
            W=args.width, H=args.height, y_lockup=args.y, y_plain=args.y_plain,
            bg="#0c121e" if args.bg == "transparent" else args.bg, min_hold=args.min_hold,
            accent_override=args.accent, lead=args.lead,
            auto_y=False if args.no_auto_y else None, keywords=kw,
            lead_plain=args.lead_plain, sfx_min_gap=args.sfx_min_gap,
        )
        print(f"[OK] Projeto editável: {idx}")
        print(f"     Abra no Studio:  npx hyperframes preview \"{args.project}\"")
        return 0

    os.makedirs(out_dir, exist_ok=True)
    doc, report, loose = build(
        groups,
        style_name=args.style,
        W=args.width,
        H=args.height,
        y_lockup=args.y,
        y_plain=args.y_plain,
        bg=args.bg,
        min_hold=args.min_hold,
        video_src=args.video,
        accent_override=args.accent,
    )
    html_path = os.path.join(out_dir, "index.html")
    rep_path = os.path.join(out_dir, "captions_report.json")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(doc)
    with open(rep_path, "w", encoding="utf-8") as f:
        json.dump({"style": args.style, "accent": args.accent, "groups": report, "loose": loose}, f, indent=2, ensure_ascii=False)

    n_lock = sum(1 for r in report if r["kind"] == "lockup")
    print(f"[OK] {html_path} | estilo={args.style} | {len(report)} grupos ({n_lock} lockups, {len(report) - n_lock} simples)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
