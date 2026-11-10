"""
Padrão: Máquina de Escrever com Pop — ref. Iasmin Moraes.
Lockup de 2–3 camadas: apoio em Montserrat 600 caixa alta pequena e palavra principal em Playfair
Display itálica creme (#FCE9BF) com brilho quente, que aparece letra a letra (1 a cada ~0,035 s,
cada letra "pula" de 20% a 100% em 0,12 s). Quando a palavra principal entra, a linha de cima
recua para 70% de opacidade, guiando o olho para o destaque.
"""

STYLE = {
    "id": "maquina_pop",
    "label": "Máquina Pop (Montserrat 600 + Playfair itálica creme, letra a letra)",
    "main_font": "Playfair Display", "main_weight": 500, "main_style": "italic", "main_track": -0.01,
    "main_case": "none", "main_lh": 0.88,
    "main_css": "color:#FCE9BF;text-shadow:0 0 22px rgba(252,214,140,.45);", "max_px": 270,
    "small_font": "Montserrat", "small_weight": 600, "small_style": "normal", "small_track": 0.04,
    "small_case": "upper", "small_css": "color:#ffffff;", "small_scale": 0.3,
    "plain_font": "Montserrat", "plain_weight": 600, "plain_style": "normal", "plain_case": "upper",
    "plain_css": "color:#ffffff;", "plain_px": 54, "plain_entry": "cut", "plain_max_words": 3,
    "accent": "#FCE9BF", "accent_extra_css": "text-shadow:0 0 22px rgba(252,214,140,.45);",
    "shine": ("rgba(255,255,255,0)", "rgba(255,255,255,0)"),
    "tilt": (0, 0), "clear": 0.05, "variants": ("typepop",), "dim_previous": 0.7, "exit": "cut",
}
