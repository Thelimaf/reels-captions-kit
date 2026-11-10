"""
caption_kit — Biblioteca Modular de Legendas Dinâmicas "Lockup" para HyperFrames
"""
from .grouper import build_groups_from_words
from .project import build_project, rebuild_project
from .renderer import build, groups_from_simple, load_styles, render_embeddable
from .transcribe import transcribe_media

__all__ = [
    "build_groups_from_words",
    "groups_from_simple",
    "load_styles",
    "build",
    "build_project",
    "rebuild_project",
    "render_embeddable",
    "transcribe_media",
]

