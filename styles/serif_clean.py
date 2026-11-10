"""
Estilo: Serif Clean (Montserrat em cima + Playfair Display Italic gigante)
Lettering editorial e monocromático: linha de apoio sem serifa em minúsculas e a palavra
principal em serifa itálica, sem cor de destaque e sem brilho. A hierarquia vem só do
contraste entre as duas fontes. Funciona melhor com 2 linhas (apoio em cima + principal).
"""

STYLE = {
    "id": "serif_clean",
    "label": "Serif Clean (Montserrat + Playfair Display Italic 400, off-white)",
    # Palavra principal: serifa itálica, gigante, off-white
    "main_font": "Playfair Display",
    "main_weight": 400,
    "main_style": "italic",
    "main_track": -0.02,
    "main_case": "none",
    "main_lh": 0.86,
    "main_css": "color:#fffbf3;text-shadow:0 6px 26px rgba(0,0,0,.35);",
    "max_px": 300,
    # Apoio: sem serifa geométrica, minúscula
    "small_font": "Montserrat",
    "small_weight": 600,
    "small_style": "normal",
    "small_track": -0.03,
    "small_case": "lower",
    "small_css": "color:#fffbf3;text-shadow:0 4px 16px rgba(0,0,0,.35);",
    "small_scale": 0.40,
    # Legenda corrida
    "plain_font": "Montserrat",
    "plain_weight": 600,
    "plain_style": "normal",
    "plain_case": "lower",
    "plain_css": "color:#fffbf3;text-shadow:0 4px 16px rgba(0,0,0,.4);",
    # Sem cor de destaque e sem feixe de luz visível
    "accent": "#fffbf3",
    "accent_extra_css": "text-shadow:0 6px 26px rgba(0,0,0,.35);",
    "shine": ("rgba(255,255,255,0)", "rgba(255,255,255,0)"),
    # Reto e com entradas suaves
    "tilt": (0, 0),
    "clear": 0.045,
    "variants": ("rise", "blur"),
}
