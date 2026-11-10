"""
Padrão: Legenda Invertida (mix-blend-mode: difference) — ref. Bianca Vilaplana.
Branco puro em modo de mesclagem "diferença": a letra mostra o negativo do vídeo por trás
(escura sobre fundo claro, clara sobre fundo escuro, colorida sobre pele/roupa).
Sans geométrica larga 800 em caixa alta, 1–2 palavras por tela, sem animação (corte seco):
a própria inversão é o efeito. Funciona melhor sobre fundos de tom médio; sobre preto vira só branco.
"""

STYLE = {
    "id": "inverso",
    "label": "Inverso (blend difference, Montserrat 800 caixa alta)",
    "layout": "plain",
    "blend": "difference",
    "main_font": "Montserrat", "main_weight": 800, "main_style": "normal", "main_track": 0.0,
    "main_case": "upper", "main_lh": 0.9, "main_css": "color:#ffffff;", "max_px": 250,
    "small_font": "Montserrat", "small_weight": 800, "small_style": "normal", "small_track": 0.0,
    "small_case": "upper", "small_css": "color:#ffffff;", "small_scale": 0.4,
    "plain_font": "Montserrat", "plain_weight": 800, "plain_style": "normal", "plain_case": "upper",
    "plain_css": "color:#ffffff;", "plain_px": 118, "plain_lh": 0.98, "plain_track": 0.02,
    "plain_entry": "cut", "plain_max_words": 2,
    "accent": "#ffffff", "accent_extra_css": "",
    "shine": ("rgba(255,255,255,0)", "rgba(255,255,255,0)"),
    "tilt": (0, 0), "clear": 0.04, "variants": ("rise",), "exit": "cut",
}
