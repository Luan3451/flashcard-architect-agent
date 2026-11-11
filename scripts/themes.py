"""Original, dependency-free, mobile-first Anki theme system.

Inspired by the *idea* of theme customization in anki-prettify, not its CSS.
No JavaScript, network fonts, or external assets are required.
"""
from __future__ import annotations

import hashlib

THEMES = {
    "studio": {"label": "Studio Pro", "bg": "#101827", "surface": "#172337", "fg": "#e7effa", "muted": "#a9bad1", "accent": "#71c4ff", "answer": "#90e0c1", "edge": "#34506c"},
    "atlas": {"label": "Atlas Diagrams", "bg": "#101b20", "surface": "#15282f", "fg": "#eef8f8", "muted": "#b9d0d0", "accent": "#70d6cf", "answer": "#a6eb9e", "edge": "#376068"},
    "paper": {"label": "Paper Study", "bg": "#f5f2eb", "surface": "#ffffff", "fg": "#253247", "muted": "#4e6077", "accent": "#1752a6", "answer": "#126746", "edge": "#d3dbe2"},
    "contrast": {"label": "High Contrast", "bg": "#090909", "surface": "#101010", "fg": "#ffffff", "muted": "#eeeeee", "accent": "#ffe568", "answer": "#a6ff7b", "edge": "#ffffff"},
}


def note_model_id(theme: str, card_kind: str) -> int:
    """Do not overwrite styling of cards imported using a different theme."""
    seed = f"flashcard-architect-v4:{theme}:{card_kind}".encode()
    return 1_000_000_000 + int(hashlib.sha256(seed).hexdigest()[:8], 16) % 900_000_000


def css_for_theme(theme: str) -> str:
    """Portable CSS: dark-mode override is handled by Anki's .night_mode class."""
    if theme not in THEMES:
        raise ValueError(f"Tema inválido: {theme}. Opções: {', '.join(THEMES)}")
    p = THEMES[theme]
    diagram = theme == "atlas"
    # Preserve each dark palette; only the light Paper theme switches in Anki night mode.
    night_override = (
        ".card.night_mode {--bg: #0e1624; --surface: #172336; --fg: #f0f6ff; "
        "--muted: #c5d3e5; --accent: #8fd1ff; --answer: #a5edcf; --edge: #455974;}"
        if theme == "paper" else ".card.night_mode {color-scheme: dark;}"
    )
    return f"""
/* Flashcard Architect: {p['label']} -- CSS próprio, offline */
.card {{
  --bg: {p['bg']}; --surface: {p['surface']}; --fg: {p['fg']};
  --muted: {p['muted']}; --accent: {p['accent']};
  --answer: {p['answer']}; --edge: {p['edge']};
  color: var(--fg); background: var(--bg);
  margin: 0; padding: clamp(12px, 3vw, 28px);
  font-family: system-ui, -apple-system, 'Segoe UI', Arial, sans-serif;
  font-size: clamp(16px, 1.8vw, 21px); line-height: 1.6;
  overflow-wrap: anywhere; text-align: left;
}}
.architect-card {{
  max-width: {'1100' if diagram else '820'}px; margin: 0 auto;
  border: 1px solid var(--edge); border-radius: 18px;
  padding: clamp(16px, 3.2vw, 32px); background: var(--surface);
}}
.architect-heading {{
  letter-spacing: .11em; font-size: .66em; text-transform: uppercase;
  color: var(--accent); font-weight: 700; margin-bottom: 1.2em;
}}
.architect-question {{font-weight: 540; font-size: 1.05em; line-height: 1.62;}}
.architect-answer {{font-size: 1em; line-height: 1.68;}}
.architect-divider {{border: 0; border-top: 1px solid var(--edge); margin: 1.4em 0;}}
.architect-footer {{border-top: 1px solid var(--edge); margin-top: 1.8em;
  padding-top: .7em; font-size: .65em; color: var(--muted); overflow-wrap: anywhere;}}
.ans, .ans b, .cloze {{color: var(--answer); font-weight: 750;}}
a {{color: var(--accent);}} b, strong {{color: var(--accent);}}
i, em {{color: var(--muted);}}
code, pre {{font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;}}
code {{color: var(--answer); background: var(--bg); padding: .08em .28em; border-radius: 4px;}}
pre {{white-space: pre-wrap; overflow-x: auto; border: 1px solid var(--edge);
  padding: .7em; border-radius: 9px; background: var(--bg);}}
img {{display: block; max-width: 100% !important; max-height: none !important;
  height: auto !important; width: auto !important; margin: 1em auto;
  border-radius: 9px; border: 1px solid var(--edge); object-fit: contain;
  background: #ffffff; image-rendering: auto;}}
/* Diagram detail matters: never darken or blur imported PDF images. */
.table-wrap {{overflow-x: auto;}}
table {{border-collapse: collapse; max-width: 100%; display: block; overflow-x: auto;}}
td, th {{border: 1px solid var(--edge); padding: .35em .6em;}}
ul, ol {{padding-left: 1.4em;}}
/* Honor Anki night mode without overriding selected dark themes. */
{night_override}
@media (max-width: 550px) {{
  .card {{padding: 8px; font-size: 17px;}}
  .architect-card {{border-radius: 11px; padding: 15px;}}
  .architect-footer {{font-size: .71em;}}
}}
@media (prefers-reduced-motion: reduce) {{* {{transition: none !important;}}}}
""".strip()


def templates():
    """Two genanki template dict pairs, avoiding JS so AnkiWeb also renders."""
    basic = [{
        "name": "Basic",
        "qfmt": '<main class="architect-card"><div class="architect-heading">Recordação ativa · {{Deck}}</div><section class="architect-question">{{Pergunta}}</section><footer class="architect-footer">{{Tags}}</footer></main>',
        "afmt": '<main class="architect-card"><div class="architect-heading">Resposta explicada · {{Deck}}</div><section class="architect-question">{{Pergunta}}</section><hr id="answer" class="architect-divider"><section class="architect-answer">{{Resposta}}</section><footer class="architect-footer">{{Tags}}</footer></main>',
    }]
    cloze = [{
        "name": "Cloze",
        "qfmt": '<main class="architect-card"><div class="architect-heading">Recuperação · {{Deck}}</div><section class="architect-question">{{cloze:Text}}</section><footer class="architect-footer">{{Tags}}</footer></main>',
        "afmt": '<main class="architect-card"><div class="architect-heading">Explicação · {{Deck}}</div><section class="architect-question">{{cloze:Text}}</section><hr id="answer" class="architect-divider"><section class="architect-answer">{{Extra}}</section><footer class="architect-footer">{{Tags}}</footer></main>',
    }]
    return basic, cloze
