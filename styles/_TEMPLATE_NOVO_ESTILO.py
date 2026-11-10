"""
TEMPLATE DE ESTILO DE LEGENDA — Copie este arquivo para `styles/meu_estilo.py`!
=================================================================================
Como funciona:
  - Qualquer arquivo `.py` dentro da pasta `styles/` (que NÃO comece com `_`) é
    carregado automaticamente pela biblioteca!
  - Para compartilhar seu estilo com outra pessoa, basta enviar o seu arquivo
    `meu_estilo.py` e pedir para ela soltar dentro da pasta `styles/` dela!
  - Se você escolher uma fonte do Google Fonts que ainda não está na pasta `fonts/`,
    o motor baixa o `.woff2` automaticamente na primeira execução!
"""

STYLE = {
    # Identificador único (opcional: se omitido, usa o nome do arquivo .py)
    "id": "meu_estilo_exemplo",
    "label": "Meu Estilo Personalizado (Exemplo)",

    # 1. PALAVRA PRINCIPAL (GIGANTE NO CENTRO DO LOCKUP)
    "main_font": "Inter",          # Qualquer fonte do Google Fonts (ex: "Inter", "Montserrat", "Bebas Neue")
    "main_weight": 900,            # Peso da fonte (400, 700, 800, 900)
    "main_style": "normal",        # "normal" ou "italic"
    "main_track": -0.06,           # Letter-spacing em 'em' (negativo deixa mais compacto)
    "main_case": "none",           # "none" (preserva maiúsculas/minúsculas p/ encaixe), "upper" ou "lower"
    "main_lh": 0.80,               # Line-height (0.80 a 0.95)
    "main_css": "color:#ffffff;text-shadow:0 10px 34px rgba(0,0,0,.55);",
    "max_px": 280,                 # Tamanho máximo da palavra principal em tela 1080p

    # 2. PALAVRAS DE APOIO (ACIMA E ABAIXO, ENCAIXADAS NOS VÃOS DA PRINCIPAL)
    "small_font": "Inter",         # Pode ser a mesma família ou uma contrastante (ex: "Playfair Display")
    "small_weight": 800,
    "small_style": "normal",       # "normal" ou "italic"
    "small_track": -0.035,
    "small_case": "none",
    "small_css": "color:#ffffff;text-shadow:0 5px 20px rgba(0,0,0,.55);",
    "small_scale": 0.46,           # Proporção em relação à principal (0.25 a 0.50)

    # 3. LEGENDA SIMPLES (FRASES CORRIDAS PALAVRA POR PALAVRA)
    "plain_font": "Inter",
    "plain_weight": 800,
    "plain_style": "normal",
    "plain_case": "none",
    "plain_css": "color:#ffffff;text-shadow:0 5px 20px rgba(0,0,0,.6);",

    # 4. COR DE DESTAQUE (PALAVRAS DE PODER / ACCENT) E EFEITO DE BRILHO (SHINE)
    "accent": "#3de0c8",           # Cor principal das palavras destacadas
    "accent_extra_css": "",        # CSS extra opcional nas palavras destacadas (ex: text-shadow neon)
    "shine": ("#ffffff", "rgba(255,255,255,.9)"),  # (cor do feixe de luz, cor do glow)

    # 5. GEOMETRIA E ANIMAÇÃO DE ENTRADA
    "tilt": (0, 0),                # Rotação (graus) de (acima, abaixo), ex: (-3, 2.5)
    "clear": 0.03,                 # Folga mínima entre as letras pequenas e a principal (fração de main_px)
    "variants": ("slam", "letters", "rise"),  # Rodízio de entradas: "slam", "letters", "rise", "blur"
    "speed": 1.0,                  # Velocidade das entradas (1.3 = mais rápido, 0.8 = mais calmo)
}

