"""
Estilo: Barlow Drive (Barlow Condensed 700 MAIÚSCULA + Barlow 500)
Condensada em caixa alta, cara de automotivo/esporte, firme sem ser extra bold.
Caixa alta não tem ascendentes/descendentes, por isso usa nest_mode "overlap" (empilhado justo).
Dois trilhos (padrão das referências): legenda comum pequena (~2,9% da altura) que aparece seca,
palavra a palavra, e destaque em lockup só nos momentos-chave. Saída em corte seco.
"""

STYLE = {
    "id": "barlow_drive",
    "label": "Barlow Drive (Barlow Condensed 700 caixa alta + Barlow 500)",
    "main_font": "Barlow Condensed",
    "main_weight": 700,
    "main_style": "normal",
    "main_track": 0.0,
    "main_case": "upper",
    "nest_mode": "overlap",
    "main_lh": 0.9,
    "main_css": "color:#ffffff;",
    "max_px": 260,
    "small_font": "Barlow",
    "small_weight": 500,
    "small_style": "normal",
    "small_track": 0.0,
    "small_case": "none",
    "small_css": "color:#ffffff;",
    "small_scale": 0.34,
    "plain_font": "Barlow",
    "plain_weight": 600,
    "plain_px": 56,
    "plain_entry": "cut",
    "plain_max_words": 3,
    "plain_style": "normal",
    "plain_case": "none",
    "plain_css": "color:#ffffff;",
    "accent": "#ffffff",
    "accent_extra_css": "",
    "shine": ("rgba(255,255,255,0)", "rgba(255,255,255,0)"),
    "tilt": (0, 0),
    "clear": 0.05,
    "variants": ("rise", "blur"),
    "speed": 1.0,
    "exit": "cut",
}
