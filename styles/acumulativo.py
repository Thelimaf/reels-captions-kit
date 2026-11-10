"""
Padrão: Bloco Acumulativo — ref. Giullya Becker.
A frase vai se montando na tela palavra por palavra (cada uma aparece seca no instante em que é
falada); a palavra principal entra maior, em Oswald 700 amarelo neon. O bloco inteiro some de
uma vez quando a próxima frase começa. Apoio em Oswald 300 caixa alta, alinhado à esquerda.
"""

STYLE = {
    "id": "acumulativo",
    "label": "Acumulativo (Oswald 300/700 caixa alta, destaque neon)",
    "layout": "accumulate",
    "main_font": "Oswald", "main_weight": 700, "main_style": "normal", "main_track": 0.0,
    "main_case": "upper", "main_lh": 0.9, "main_css": "color:#ffffff;", "max_px": 250,
    "small_font": "Oswald", "small_weight": 300, "small_style": "normal", "small_track": 0.0,
    "small_case": "upper", "small_css": "color:#ffffff;", "small_scale": 0.4,
    "plain_font": "Oswald", "plain_weight": 300, "plain_style": "normal", "plain_case": "upper",
    "plain_css": "color:#ffffff;", "plain_px": 76, "plain_lh": 1.0, "plain_track": 0.01,
    "plain_width": 0.8, "plain_align": "left", "plain_entry": "cut",
    "accent": "#E9FF3B",
    "accent_extra_css": "font-weight:700;font-size:1.55em;line-height:.95;text-shadow:0 0 18px rgba(233,255,59,.45);",
    "shine": ("rgba(255,255,255,0)", "rgba(255,255,255,0)"),
    "tilt": (0, 0), "clear": 0.04, "variants": ("rise",), "exit": "cut",
}
