"""
Padrão: Escadinha — ref. Fernando Luz.
As palavras do bloco descem em degraus (cada linha deslocada ~6,5% da largura para a direita),
entrando uma a uma no tempo da fala e saindo todas juntas em corte seco.
Contraste por peso na mesma família: apoio Inter 300 pequeno, palavra principal Inter 900 2,3x
com tracking negativo e entrelinha justa.
"""

STYLE = {
    "id": "escadinha",
    "label": "Escadinha (Inter 300 + Inter 900, degraus)",
    "layout": "stairs",
    "main_font": "Inter", "main_weight": 900, "main_style": "normal", "main_track": -0.05,
    "main_case": "none", "main_lh": 0.9, "main_css": "color:#ffffff;", "max_px": 250,
    "small_font": "Inter", "small_weight": 300, "small_style": "normal", "small_track": -0.02,
    "small_case": "lower", "small_css": "color:#ffffff;", "small_scale": 0.4,
    "plain_font": "Inter", "plain_weight": 500, "plain_style": "normal", "plain_case": "none",
    "plain_css": "color:#ffffff;",
    "stairs_px": 64, "stairs_main_px": 150, "stairs_offset": 70, "stairs_words_per_line": 2,
    "stairs_lh": 1.0, "stairs_main_lh": 0.88,
    "accent": "#ffffff", "accent_extra_css": "",
    "shine": ("rgba(255,255,255,0)", "rgba(255,255,255,0)"),
    "tilt": (0, 0), "clear": 0.04, "variants": ("rise",), "exit": "cut",
}
