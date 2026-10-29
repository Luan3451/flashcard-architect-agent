#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "genanki>=0.13.0",
#     "pymupdf>=1.23.0",
#     "python-docx>=1.1.0",
#     "pillow>=10.0.0",
#     "pydantic>=2.7.0",
#     "json-repair>=0.25.0",
#     "watchdog>=4.0.0",
#     "rapidocr-onnxruntime>=1.2.0",
# ]
# ///
# -*- coding: utf-8 -*-
"""
anki_generator.py — v3.1.0 (Antigravity Native Edition)
Pipeline completo com Wizard Interativo, Bypass condicional de mídias e Prompts adaptativos.
Zero dependência de APIs externas (sem Google AI Studio / sem GEMINI_API_KEY).
Utiliza exclusivamente o ecossistema Antigravity (Antigravity CLI / IDE / APP)
com o modelo Gemini 3.8 Flash (High reasoning effort).
"""

import argparse
import glob
import hashlib
import importlib.util
from io import BytesIO
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

# Força UTF-8 no Windows para evitar UnicodeEncodeError ('charmap')
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# 1. AUTO-BOOTSTRAPPER E AUTO-PROVISIONAMENTO
# ---------------------------------------------------------------------------
REQUIRED_PACKAGES = {
    "genanki": "genanki>=0.13.0",
    "fitz": "pymupdf>=1.23.0",
    "docx": "python-docx>=1.1.0",
    "PIL": "Pillow>=10.0.0",
    "pydantic": "pydantic>=2.7.0",
    "json_repair": "json-repair>=0.25.0",
}

def bootstrap_environment() -> None:
    """Garante que todas as dependências e o binário 'agy' estejam prontos sem intervenção humana."""
    missing = [
        pkg for mod, pkg in REQUIRED_PACKAGES.items()
        if importlib.util.find_spec(mod) is None
    ]
    if missing:
        print(f"[Auto-Setup] Instalando dependências ausentes: {', '.join(missing)}...")
        uv_bin = shutil.which("uv")
        cmd = (
            [uv_bin, "pip", "install", "--system", "--quiet", *missing]
            if uv_bin
            else [sys.executable, "-m", "pip", "install", "--quiet", *missing]
        )
        try:
            subprocess.check_call(cmd)
            print("[Auto-Setup] Dependências instaladas com sucesso.")
        except Exception as e:
            print(f"[Auto-Setup] Aviso ao instalar dependências: {e}")

    # Auto-descoberta do binário 'agy' caso não esteja no PATH do sistema
    if not shutil.which("agy"):
        common_paths = [
            Path.home() / ".antigravity" / "bin",
            Path.home() / ".local" / "bin",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity" / "bin",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity",
        ]
        for p in common_paths:
            if (p / "agy").exists() or (p / "agy.exe").exists():
                os.environ["PATH"] = f"{p}{os.pathsep}{os.environ.get('PATH', '')}"
                break

bootstrap_environment()

# Imports das bibliotecas garantidas pelo bootstrap
try:
    import genanki
except ImportError:
    genanki = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import json_repair
except ImportError:
    json_repair = None

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

try:
    from rapidocr_onnxruntime import RapidOCR
    RAPID_OCR_AVAILABLE = True
except ImportError:
    RAPID_OCR_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("flashcard-architect")

# Constantes do sistema
VERSION = "3.1.0"
MEDIA_DIR = "anki_media"
MAX_RETRIES = 3
RETRY_DELAY_SECS = 4
DEFAULT_MODEL = "gemini-3.8-flash-high"
DEFAULT_EFFORT = "high"

MODEL_BASIC_ID = 1607392319
MODEL_CLOZE_ID = 1607392320

# ---------------------------------------------------------------------------
# 2. GERADOR DETERMINÍSTICO DE DECK ID
# ---------------------------------------------------------------------------
def get_deck_id(deck_name: str) -> int:
    """Gera um inteiro positivo de 31 bits único e determinístico a partir do nome do deck."""
    digest = hashlib.sha256(deck_name.strip().lower().encode("utf-8")).hexdigest()
    return int(digest[:8], 16) & 0x7FFFFFFF

# ---------------------------------------------------------------------------
# 3. MATRIZ DE PROMPTS ADAPTATIVOS (Curadoria vs. Fidelidade Estrita vs. Exame)
# ---------------------------------------------------------------------------
MODE_INSTRUCTIONS = {
    "curated": (
        "MODO CURADORIA & ALTA RECORRÊNCIA (80/20):\n"
        "- Filtre textos introdutórios irrelevantes, históricos prolixos ou exemplos redundantes.\n"
        "- Priorize os conceitos mais cobrados em provas e certificações, definições-chave, "
        "arquiteturas, comandos e diferenciações críticas.\n"
        "- Reescreva o conteúdo em perguntas atômicas, diretas e autossuficientes."
    ),
    "strict": (
        "MODO FIDELIDADE ESTRITA À FONTE (PROVAS / SIMULADOS / NORMAS):\n"
        "- NÃO omita tópicos e NÃO altere o sentido ou a terminologia exata do texto-fonte.\n"
        "- Se o texto de entrada contiver questões de prova ou simulado, preserve fielmente o cenário, "
        "o comando da questão e os termos técnicos originais na FRENTE do cartão.\n"
        "- No VERSO, apresente o gabarito exato seguido da justificativa técnica detalhada de cada item."
    ),
    "exam": (
        "MODO AUDITORIA DE ERROS E PEGADINHAS DE PROVA:\n"
        "- Analise cada questão ou tópico identificando as pegadinhas clássicas e alternativas incorretas.\n"
        "- Crie cartões que confrontem o erro comum (ex: 'No contexto X, por que a afirmativa Y é falsa ou incorreta?').\n"
        "- Explique no verso a causa exata do erro e qual seria a configuração/conceito correto."
    ),
}

DENSITY_INSTRUCTIONS = {
    "essential": "DENSIDADE ESSENCIAL: Gere apenas os cartões indispensáveis (1 a 2 cartões por seção/página).",
    "high": "DENSIDADE EXAUSTIVA: Extraia o máximo de cartões atômicos possíveis cobrindo cada detalhe, tabela, exceção e observação técnica (3 a 6 cartões por seção/página).",
}

def build_master_prompt(mode: str, density: str, use_media: bool, card_style: str) -> str:
    media_rule = (
        "4. GESTÃO DE IMAGENS ATIVA:\n"
        "   - Sempre que o texto indicar '[Imagem extraída: nome_arquivo.ext]', associe-a ao cartão correspondente usando:\n"
        "     <br><img src=\"nome_arquivo.ext\">\n"
        "   - Coloque na FRENTE se for diagrama de enunciado/topologia, ou no VERSO se for resolução explicativa."
        if use_media
        else "4. MODO SOMENTE TEXTO:\n"
             "   - Ignore referências a figuras externas e NÃO inclua tags <img>."
    )

    cloze_rule = (
        "- Para listas curtas, portas, comandos ou parâmetros exatos, você pode destacar lacunas no formato Cloze ({{c1::termo}}) na pergunta."
        if card_style == "hybrid"
        else "- Formule todas as notas estritamente no formato Pergunta Direta (frente) e Resposta + Justificativa (verso)."
    )

    return f"""Você é o Flashcard Architect — especialista em aprendizagem ativa e algoritmo FSRS do Anki.

{MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["curated"])}
{DENSITY_INSTRUCTIONS.get(density, DENSITY_INSTRUCTIONS["high"])}
{cloze_rule}

REGRAS OBRIGATÓRIAS DE FORMATAÇÃO:
1. FRENTE (pergunta): Enunciado claro, objetivo e autossuficiente (sem pronomes soltos). Cada cartão deve testar rigorosamente UMA ÚNICA associação mental.
2. VERSO (resposta): Gabarito direto dentro de <span class="ans"><b>Resposta direta</b></span> seguido de <br><br><i>Justificativa:</i> com explicação técnica concisa e sólida.
3. ESTILOS HTML PERMITIDOS (NÃO USE style="" INLINE): <b>termo</b>, <i>conceito</i>, <code>comando/porta</code>, <ul><li>item</li></ul>, <br>.
{media_rule}
5. METADADOS OBRIGATÓRIOS:
   - "id_conceito": crie um identificador estável em snake_case (ex: "redes_bgp_keepalive_objetivo").
   - "tags": gere de 1 a 3 tags curtas em snake_case identificando o tópico (ex: ["redes", "bgp"]).
   - "suggested_deck": sugira uma taxonomia hierárquica no formato "Categoria::Subcategoria::Assunto".

6. SAÍDA EXCLUSIVA: Retorne APENAS um array JSON puro (sem blocos ```json, sem introduções ou saudações):
[
  {{
    "id_conceito": "redes_bgp_keepalive_objetivo",
    "pergunta": "No protocolo <b>BGP</b>, qual é o objetivo da mensagem <i>Keepalive</i> e seu intervalo padrão de envio?",
    "resposta": "<span class=\\"ans\\"><b>Manter a sessão ativa entre peers (60 segundos).</b></span><br><br><i>Justificativa:</i> Confirma a alcançabilidade da sessão TCP na porta <code>179</code> antes que o <i>Hold Timer</i> expire.",
    "tags": ["redes", "bgp"],
    "suggested_deck": "Tecnologia::Redes::Roteamento_Avancado"
  }}
]
"""

# ---------------------------------------------------------------------------
# 4. FOLHA DE ESTILOS CSS DARK MODE NATIVA
# ---------------------------------------------------------------------------
ANKI_CSS = """
.card {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    font-size: 19px;
    text-align: left;
    color: #e6edf3;
    background-color: #1e1e1e;
    padding: 24px;
    line-height: 1.65;
    max-width: 780px;
    margin: 0 auto;
}
.card-front {
    font-size: 20px;
    font-weight: 500;
    color: #ffffff;
}
.card-back {
    margin-top: 14px;
    font-size: 18px;
    color: #d1d5db;
}
hr#answer {
    border: none;
    border-top: 1px solid #3d444d;
    margin: 18px 0;
}
b, strong { color: #58a6ff; font-weight: 600; }
i, em { color: #f0883e; }

/* Correção de especificidade: verde neon para o gabarito principal mesmo se contiver <b> dentro */
.ans, .ans b, .ans strong {
    color: #4af626 !important;
    font-weight: 700;
}

.cloze {
    font-weight: 700;
    color: #4af626 !important;
}

.justificativa {
    margin-top: 12px;
    padding: 10px 14px;
    background-color: #161b22;
    border-left: 3px solid #58a6ff;
    border-radius: 4px;
    font-size: 0.92em;
    color: #c9d1d9;
}

code {
    background-color: #0d1117;
    padding: 2px 7px;
    border-radius: 5px;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    color: #4af626;
    font-size: 0.92em;
    border: 1px solid #30363d;
}
pre {
    background-color: #0d1117;
    padding: 12px 16px;
    border-radius: 8px;
    overflow-x: auto;
    border: 1px solid #30363d;
}
ul, ol {
    padding-left: 24px;
    margin: 10px 0;
}
li {
    margin-bottom: 6px;
}
img {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    margin-top: 12px;
    margin-bottom: 12px;
    border: 1px solid #30363d;
    display: block;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 14px 0;
}
th, td {
    border: 1px solid #30363d;
    padding: 8px 12px;
    text-align: left;
}
th {
    background-color: #161b22;
    color: #4af626;
    font-weight: 600;
}
""".strip()

# ---------------------------------------------------------------------------
# 5. PIPELINE DE EXTRAÇÃO CONDICIONAL (LAZY MEDIA EXTRACTION)
# ---------------------------------------------------------------------------
def ensure_media_dir() -> Path:
    p = Path(MEDIA_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p

def save_normalized_image(img_bytes: bytes, min_dim: int = 60) -> str | None:
    """Filtra ruídos, converte para WebP e nomeia por hash SHA-256 (anti-colisão global)."""
    if len(img_bytes) < 2048:
        return None

    try:
        if PIL_AVAILABLE:
            with Image.open(BytesIO(img_bytes)) as im:
                w, h = im.size
                if w < min_dim or h < min_dim:
                    return None
                if (w / max(h, 1)) > 12 or (h / max(w, 1)) > 12:
                    return None

                out_buffer = BytesIO()
                im.convert("RGB").save(out_buffer, format="WEBP", quality=85)
                webp_bytes = out_buffer.getvalue()
        else:
            webp_bytes = img_bytes

        img_hash = hashlib.sha256(webp_bytes).hexdigest()[:12]
        filename = f"ag_{img_hash}.webp"
        filepath = os.path.join(MEDIA_DIR, filename)

        ensure_media_dir()
        if not os.path.exists(filepath):
            with open(filepath, "wb") as f:
                f.write(webp_bytes)

        return filename
    except Exception as e:
        log.debug(f"Aviso ao normalizar imagem: {e}")
        return None

def extract_pdf_content(pdf_path: str, use_media: bool) -> tuple[list[str], list[str]]:
    """Extrai conteúdo de PDF. Se use_media=False, pula totalmente o PyMuPDF de imagens (modo turbo)."""
    if fitz is None:
        log.error("[ERRO] PyMuPDF não está instalado. Execute: pip install PyMuPDF")
        sys.exit(1)

    doc = fitz.open(pdf_path)
    pages_content = []
    media_files = []
    seen_hashes = set()

    for page_idx, page in enumerate(doc):
        text = page.get_text("text").strip()
        extracted_tags = []

        # OCR transparente em páginas escaneadas se tiver muito pouco texto
        if len(text) < 40 and RAPID_OCR_AVAILABLE:
            try:
                pix = page.get_pixmap(dpi=200)
                ocr_engine = RapidOCR()
                result, _ = ocr_engine(pix.tobytes("png"))
                if result:
                    text = "\n".join([line[1] for line in result])
                    log.info(f"      [OCR Offline] Extraídos {len(text)} caracteres na pág. {page_idx + 1}")
            except Exception:
                pass

        # SÓ executa varredura de imagem e diagramas vetoriais se use_media for True
        if use_media:
            # 1. Bitmaps XRef
            for img_info in page.get_images(full=True):
                try:
                    xref = img_info[0]
                    base_img = doc.extract_image(xref)
                    img_bytes = base_img["image"]
                    fname = save_normalized_image(img_bytes)
                    if fname:
                        fpath = os.path.join(MEDIA_DIR, fname)
                        if fpath not in media_files:
                            media_files.append(fpath)
                        if fname not in seen_hashes:
                            seen_hashes.add(fname)
                            extracted_tags.append(f"[Imagem extraída: {fname}]")
                except Exception:
                    pass

            # 2. Agrupamentos Vetoriais (cluster_drawings)
            try:
                for rect in page.cluster_drawings():
                    if rect.width >= 100 and rect.height >= 80:
                        pix = page.get_pixmap(clip=rect, dpi=200)
                        vname = save_normalized_image(pix.tobytes("png"))
                        if vname:
                            vpath = os.path.join(MEDIA_DIR, vname)
                            if vpath not in media_files:
                                media_files.append(vpath)
                            if vname not in seen_hashes:
                                seen_hashes.add(vname)
                                extracted_tags.append(f"[Imagem extraída: {vname}]")
            except Exception:
                pass

        page_block = f"--- PÁGINA {page_idx + 1} ---\n{text}"
        if extracted_tags:
            page_block += "\n" + "\n".join(extracted_tags)
        pages_content.append(page_block)

    mode_label = f"{len(media_files)} imagem(ns) coletada(s)" if use_media else "Modo Turbo (Sem Imagens)"
    log.info(f"      → PDF: {len(doc)} página(s) | {mode_label}.")
    return pages_content, media_files

def extract_docx_content(docx_path: str, use_media: bool) -> tuple[list[str], list[str]]:
    """Extrai texto e imagens de DOCX. Se use_media=False, pula leitura de mídias binárias."""
    if not DOCX_AVAILABLE:
        log.error("[ERRO] python-docx não instalado. Execute: pip install python-docx")
        sys.exit(1)

    doc = DocxDocument(docx_path)
    media_files = []
    paragraphs_text = []

    for para in doc.paragraphs:
        p_text = para.text.strip()
        if use_media:
            try:
                blips = para._element.xpath('.//a:blip/@r:embed')
                for r_id in blips:
                    rel = doc.part.rels.get(r_id)
                    if rel and "image" in rel.reltype:
                        img_bytes = rel.target_part.blob
                        fname = save_normalized_image(img_bytes)
                        if fname:
                            fpath = os.path.join(MEDIA_DIR, fname)
                            if fpath not in media_files:
                                media_files.append(fpath)
                            p_text += f"\n[Imagem extraída: {fname}]\n"
            except Exception:
                pass

        if p_text:
            paragraphs_text.append(p_text)

    full_text = "\n\n".join(paragraphs_text)
    mode_label = f"{len(media_files)} imagem(ns)" if use_media else "Modo Turbo (Sem Imagens)"
    log.info(f"      → DOCX: {len(paragraphs_text)} parágrafo(s) | {mode_label}.")
    return [full_text], media_files

def extract_markdown_content(md_path: str, use_media: bool, attach_dir: str | None = None) -> tuple[list[str], list[str]]:
    """Extrai conteúdo de Markdown. Se use_media=False, preserva o texto sem copiar arquivos."""
    md_dir = os.path.dirname(os.path.abspath(md_path))
    content = ""
    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            with open(md_path, "r", encoding=enc) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    media_files = []
    if use_media:
        search_dirs = [md_dir]
        if attach_dir and os.path.exists(attach_dir):
            search_dirs.append(attach_dir)
        for sub in ["attachments", "anexos", "media", "images", "img", "assets"]:
            cand = os.path.join(md_dir, sub)
            if os.path.exists(cand):
                search_dirs.append(cand)

        md_pattern = re.compile(r'!\[(.*?)\]\((.*?)\)')
        html_pattern = re.compile(r'<img[^>]+src=["\'](.*?)["\']', re.IGNORECASE)

        found_refs = []
        for m in md_pattern.finditer(content):
            found_refs.append(m.group(2).strip())
        for m in html_pattern.finditer(content):
            found_refs.append(m.group(1).strip())

        for img_ref in set(found_refs):
            if img_ref.startswith("http://") or img_ref.startswith("https://"):
                continue

            resolved = None
            for s_dir in search_dirs:
                cand = os.path.normpath(os.path.join(s_dir, img_ref))
                if os.path.exists(cand) and os.path.isfile(cand):
                    resolved = cand
                    break

            if resolved:
                try:
                    with open(resolved, "rb") as f:
                        b = f.read()
                    norm = save_normalized_image(b, min_dim=20)
                    if norm:
                        p = os.path.join(MEDIA_DIR, norm)
                        if p not in media_files:
                            media_files.append(p)
                        content = content.replace(img_ref, norm)
                except Exception:
                    pass

    mode_label = f"{len(media_files)} imagem(ns)" if use_media else "Modo Turbo (Sem Imagens)"
    log.info(f"      → Markdown: {len(content)} caracteres | {mode_label}.")
    return [content], media_files

def extract_content(path: str, use_media: bool, attach_dir: str | None = None) -> tuple[list[str], list[str]]:
    """Roteador inteligente com controle condicional de extração de mídias."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return extract_pdf_content(path, use_media)
    elif ext in [".md", ".markdown"]:
        return extract_markdown_content(path, use_media, attach_dir)
    elif ext == ".docx":
        return extract_docx_content(path, use_media)
    else:
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                with open(path, "r", encoding=enc) as f:
                    content = f.read()
                return [content], []
            except UnicodeDecodeError:
                continue
        return [""], []

# ---------------------------------------------------------------------------
# 6. QUESTIONÁRIO INTERATIVO DE TERMINAL (WIZARD PRÉ-VOO)
# ---------------------------------------------------------------------------
def run_interactive_wizard(args: argparse.Namespace) -> argparse.Namespace:
    """Executa perguntas breves de triagem caso o usuário rode o script sem definir flags explícitas."""
    if args.non_interactive or args.no_ai:
        args.mode = args.mode or "curated"
        args.use_media = True if args.media is True else (False if args.no_media else False)
        args.density = args.density or "high"
        args.style = args.style or "qa"
        return args

    # Se já passou todas as flags principais na linha de comando, não pergunta
    if args.mode and (args.media or args.no_media) and args.density and args.style:
        args.use_media = True if args.media else False
        return args

    print("\n" + "=" * 68)
    print("🧠 FLASHCARD ARCHITECT — CONFIGURAÇÃO RÁPIDA DO BARALHO (WIZARD)")
    print("=" * 68)
    print("👉 Dica: Você pode responder todas as perguntas de uma vez separadas por vírgula")
    print("   (ex: '1, 2, 1, 2' para Curadoria + Sem Imagens + P/R + Exaustivo) ou teclar Enter para padrão.\n")

    quick_input = input("⚡ Configuração Rápida em linha única [Enter para responder passo a passo]: ").strip()
    if quick_input and "," in quick_input:
        parts = [p.strip() for p in quick_input.split(",")]
        mode_choice = parts[0] if len(parts) > 0 else "1"
        media_choice = parts[1] if len(parts) > 1 else "2"
        style_choice = parts[2] if len(parts) > 2 else "1"
        density_choice = parts[3] if len(parts) > 3 else "2"

        args.mode = {"1": "curated", "2": "strict", "3": "exam"}.get(mode_choice, "curated")
        args.use_media = (media_choice == "1")
        args.style = "hybrid" if style_choice == "2" else "qa"
        args.density = "essential" if density_choice == "1" else "high"
    else:
        # Pergunta 1: Modo de Fidelidade
        if not args.mode:
            print("\n[1/4] Como deseja tratar o conteúdo do arquivo fonte?")
            print("  [1] Curadoria & Recorrência (80/20: Seleciona o mais importante / reescreve enxuto)")
            print("  [2] Fidelidade Estrita (Provas/Simulados/Normas: NÃO altera nada do texto fonte)")
            print("  [3] Dissecação de Pegadinhas (Foco em erros de alternativas de provas)")
            choice_mode = input("👉 Escolha [1/2/3] (Padrão: 1): ").strip()
            args.mode = {"1": "curated", "2": "strict", "3": "exam"}.get(choice_mode, "curated")

        # Pergunta 2: Imagens / Anexos
        if not args.media and not args.no_media:
            print("\n[2/4] O arquivo (.pdf, .md, .docx) possui imagens/diagramas que devem ir para o Anki?")
            print("  [1] Sim — Rodar extratores de imagem e embutir mídias no baralho")
            print("  [2] Não — Somente Texto (Desativa motor de imagens para máxima velocidade)")
            choice_media = input("👉 Escolha [1/2] (Padrão: 2 - Somente Texto): ").strip()
            args.use_media = (choice_media == "1")
        else:
            args.use_media = True if args.media else False

        # Pergunta 3: Estilo de Card
        if not args.style:
            print("\n[3/4] Qual formato de flashcard prefere?")
            print("  [1] Pergunta & Resposta Clássica + Justificativa Técnica")
            print("  [2] Híbrido (Pergunta/Resposta + Lacunas Cloze para comandos e listas)")
            choice_style = input("👉 Escolha [1/2] (Padrão: 1): ").strip()
            args.style = "hybrid" if choice_style == "2" else "qa"

        # Pergunta 4: Densidade
        if not args.density:
            print("\n[4/4] Qual nível de profundidade/quantidade de cartões deseja?")
            print("  [1] Essencial (Enxuto, apenas conceitos principais)")
            print("  [2] Exaustivo (Cobertura completa de todos os detalhes e questões)")
            choice_density = input("👉 Escolha [1/2] (Padrão: 2): ").strip()
            args.density = "essential" if choice_density == "1" else "high"

    print("\n" + "-" * 68)
    print(
        f"✅ Configuração Aplicada: Modo={args.mode.upper()} | "
        f"Imagens={'ATIVADO' if args.use_media else 'DESATIVADO (Turbo)'} | "
        f"Estilo={args.style.upper()} | Densidade={args.density.upper()}"
    )
    print("-" * 68 + "\n")
    return args

# ---------------------------------------------------------------------------
# 7. CHUNKING COM JANELA DESLIZANTE (OVERLAP)
# ---------------------------------------------------------------------------
def chunk_with_overlap(pages: list[str], max_chars_per_chunk: int = 8000, overlap_ratio: float = 0.15) -> list[str]:
    chunks = []
    current_chunk = []
    current_len = 0

    for page in pages:
        page_len = len(page)
        if current_len + page_len > max_chars_per_chunk and current_chunk:
            chunks.append("\n".join(current_chunk))
            overlap_target = int(max_chars_per_chunk * overlap_ratio)
            overlap_accum = 0
            overlap_blocks = []
            for blk in reversed(current_chunk):
                overlap_accum += len(blk)
                overlap_blocks.insert(0, blk)
                if overlap_accum >= overlap_target:
                    break
            current_chunk = overlap_blocks + [page]
            current_len = sum(len(b) for b in current_chunk)
        else:
            current_chunk.append(page)
            current_len += page_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks

# ---------------------------------------------------------------------------
# 8. PARSER E VALIDAÇÃO DE RESPOSTAS JSON
# ---------------------------------------------------------------------------
def parse_and_validate_cards(raw_response: str) -> tuple[list[dict], str]:
    if not raw_response or not raw_response.strip():
        return [], ""

    text = raw_response.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text).strip()

    if json_repair:
        try:
            parsed = json_repair.repair_json(text, return_objects=True)
        except Exception:
            try:
                parsed = json.loads(text)
            except Exception:
                return [], ""
    else:
        try:
            parsed = json.loads(text)
        except Exception:
            return [], ""

    cards_data = []
    suggested_deck = ""

    if isinstance(parsed, dict):
        suggested_deck = parsed.get("suggested_deck", "")
        for key in ["cards", "flashcards", "items"]:
            if key in parsed and isinstance(parsed[key], list):
                cards_data = parsed[key]
                break
    elif isinstance(parsed, list):
        cards_data = parsed

    valid_cards = []
    for item in cards_data:
        if not isinstance(item, dict):
            continue

        p = item.get("pergunta", "").strip()
        r = item.get("resposta", "").strip()
        if not p or not r:
            continue

        cid = item.get("id_conceito", "").strip()
        tags = item.get("tags", [])
        if not isinstance(tags, list):
            tags = [str(tags)]
        tags = [str(t).strip().lower().replace(" ", "_") for t in tags if t]

        if not suggested_deck and item.get("suggested_deck"):
            suggested_deck = item.get("suggested_deck").strip()

        valid_cards.append({
            "id_conceito": cid,
            "pergunta": p,
            "resposta": r,
            "tags": tags,
            "suggested_deck": item.get("suggested_deck", "")
        })

    return valid_cards, suggested_deck

def reconcile_card_images(cards: list[dict], available_media: list[str]) -> None:
    if not available_media:
        return
    basenames = [os.path.basename(m) for m in available_media]
    for card in cards:
        for field in ["pergunta", "resposta"]:
            text = card[field]
            for m in re.finditer(r'<img[^>]+src=["\'](.*?)["\']', text, re.IGNORECASE):
                img_src = m.group(1).strip()
                src_base = os.path.basename(img_src)
                if src_base not in basenames:
                    for b in basenames:
                        if b in src_base or src_base in b:
                            card[field] = card[field].replace(img_src, b)
                            break

# ---------------------------------------------------------------------------
# 9. GERAÇÃO NATIVA COM ANTIGRAVITY CLI (AGY)
# ---------------------------------------------------------------------------
def call_antigravity_cli(prompt_text: str, model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT) -> str | None:
    cmd = [
        "agy",
        "--model", model,
        "--effort", effort,
        "--dangerously-skip-permissions",
        "-p", prompt_text
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        stdout, stderr = proc.communicate(timeout=180)
        if proc.returncode != 0:
            log.warning(f"  ⚠ Antigravity CLI retornou código {proc.returncode}: {stderr.strip()}")
            return None
        return stdout.strip()
    except subprocess.TimeoutExpired:
        log.warning("  ⚠ Tempo limite de resposta excedido no Antigravity CLI (180s).")
        proc.kill()
        return None
    except FileNotFoundError:
        log.error("[ERRO] Binário 'agy' não encontrado no PATH.")
        return None
    except Exception as e:
        log.warning(f"  ⚠ Erro inesperado ao invocar Antigravity CLI: {e}")
        return None

def generate_flashcards_antigravity(
    chunks: list[str],
    master_prompt: str,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT
) -> tuple[list[dict], str]:
    all_cards = []
    overall_suggested_deck = ""
    total_chunks = len(chunks)

    log.info(f"\n  Iniciando processamento nativo via Antigravity ({model} - esforço: {effort})...")

    for idx, chunk in enumerate(chunks):
        log.info(f"  → Lote {idx + 1}/{total_chunks} (~{len(chunk):,} caracteres)...")
        prompt = f"{master_prompt}\n\nMATERIAL DE ESTUDO:\n{chunk}"

        success = False
        for attempt in range(1, MAX_RETRIES + 1):
            raw_out = call_antigravity_cli(prompt, model=model, effort=effort)
            if not raw_out:
                time.sleep(RETRY_DELAY_SECS)
                continue

            cards, deck_sug = parse_and_validate_cards(raw_out)
            if cards:
                all_cards.extend(cards)
                if deck_sug and not overall_suggested_deck:
                    overall_suggested_deck = deck_sug
                log.info(f"     ✓ {len(cards)} flashcard(s) gerado(s) com sucesso.")
                success = True
                break
            else:
                log.warning(f"     ⚠ Resposta do lote {idx + 1} sem cards válidos (tentativa {attempt}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY_SECS)

        if not success:
            log.error(f"     ✗ Falha no lote {idx + 1} após {MAX_RETRIES} tentativas.")

    return all_cards, overall_suggested_deck

# ---------------------------------------------------------------------------
# 10. MONTAGEM DO PACOTE ANKI (.apkg)
# ---------------------------------------------------------------------------
def build_anki_deck(flashcards: list[dict], media_files: list[str], deck_name: str, output_path: str) -> None:
    if genanki is None:
        log.error("[ERRO] genanki não instalado. Execute: pip install genanki")
        sys.exit(1)

    deck_id = get_deck_id(deck_name)

    basic_model = genanki.Model(
        MODEL_BASIC_ID,
        "Flashcard Architect Native Basic",
        fields=[{"name": "Pergunta"}, {"name": "Resposta"}],
        templates=[{
            "name": "Cartão Básico",
            "qfmt": '<div class="card-front">{{Pergunta}}</div>',
            "afmt": '{{FrontSide}}<hr id="answer"><div class="card-back">{{Resposta}}</div>',
        }],
        css=ANKI_CSS
    )

    cloze_model = genanki.Model(
        MODEL_CLOZE_ID,
        "Flashcard Architect Native Cloze",
        fields=[{"name": "Text"}, {"name": "Extra"}],
        templates=[{
            "name": "Cartão Cloze",
            "qfmt": '<div class="card-front">{{cloze:Text}}</div>',
            "afmt": '<div class="card-front">{{cloze:Text}}</div><hr id="answer"><div class="card-back">{{Extra}}</div>',
        }],
        css=ANKI_CSS,
        model_type=genanki.Model.CLOZE
    )

    deck = genanki.Deck(deck_id, deck_name)
    reconcile_card_images(flashcards, media_files)

    added_basic = 0
    added_cloze = 0

    for card in flashcards:
        p = card["pergunta"]
        r = card["resposta"]
        cid = card.get("id_conceito")
        tags = card.get("tags", ["antigravity-native"])

        guid_seed = f"{deck_name}_{cid}" if cid else f"{deck_name}_{p}"
        note_guid = genanki.guid_for(guid_seed)

        if "{{c" in p:
            note = genanki.Note(
                model=cloze_model,
                fields=[p, r],
                tags=tags,
                guid=note_guid
            )
            added_cloze += 1
        else:
            note = genanki.Note(
                model=basic_model,
                fields=[p, r],
                tags=tags,
                guid=note_guid
            )
            added_basic += 1

        deck.add_note(note)

    package = genanki.Package(deck)
    valid_media = [m for m in media_files if os.path.exists(m)]
    package.media_files = valid_media
    package.write_to_file(output_path)

    log.info(f"      → {added_basic + added_cloze} card(s) empacotado(s) ({added_basic} básicos, {added_cloze} cloze).")
    if valid_media:
        log.info(f"      → {len(valid_media)} imagem(ns) e diagrama(s) WebP embutido(s).")

# ---------------------------------------------------------------------------
# 11. PIPELINE PRINCIPAL E CLI
# ---------------------------------------------------------------------------
def run_pipeline(
    input_file: str,
    deck: str | None,
    output: str | None,
    mode: str,
    density: str,
    style: str,
    use_media: bool,
    attachments: str | None,
    model: str,
    effort: str,
    chunk_size: int,
    no_ai: bool
) -> None:
    base_name = os.path.splitext(os.path.basename(input_file))[0]

    # 1. Extração
    print(f"\n[1/3] Processando material: {input_file} (Imagens={'Ativado' if use_media else 'Desativado/Turbo'})")
    pages, media = extract_content(input_file, use_media=use_media, attach_dir=attachments)
    total_chars = sum(len(p) for p in pages)
    print(f"      → {len(pages)} bloco(s) | {len(media)} imagem(ns) | ~{total_chars:,} caracteres")

    # 2. Geração de Flashcards
    cards = []
    suggested_deck = ""
    is_json = input_file.lower().endswith(".json") or no_ai

    if is_json:
        print(f"\n[2/3] Carregando flashcards pré-estruturados (modo direto)...")
        raw_text = "\n".join(pages)
        cards, suggested_deck = parse_and_validate_cards(raw_text)
    else:
        print(f"\n[2/3] Gerando flashcards com Antigravity CLI ({model} / {effort} / modo: {mode})...")
        master_prompt = build_master_prompt(mode=mode, density=density, use_media=use_media, card_style=style)
        chunks = chunk_with_overlap(pages, max_chars_per_chunk=8000, overlap_ratio=0.15)
        cards, suggested_deck = generate_flashcards_antigravity(chunks, master_prompt, model=model, effort=effort)

    if not cards:
        log.error("\n[ERRO] Nenhum flashcard foi gerado ou validado.")
        return

    # Taxonomia automática: define o nome do deck inteligente
    final_deck_name = deck
    if not final_deck_name or final_deck_name == "Meu Baralho Antigravity":
        if suggested_deck:
            final_deck_name = suggested_deck
        else:
            clean_title = re.sub(r"[_\-\.]+", " ", base_name).title()
            final_deck_name = f"Estudos::{clean_title}"

    if not output:
        slug = re.sub(r"[^\w\s-]", "", final_deck_name.replace("::", "_")).strip().replace(" ", "_")
        output = f"{slug}.apkg"

    # 3. Empacotamento
    print(f"\n[3/3] Montando pacote Anki: '{final_deck_name}' -> {output}")
    build_anki_deck(cards, media, final_deck_name, output)

    print(f"\n{'='*56}")
    print(f"  ✅ Baralho Anki gerado com sucesso!")
    print(f"  📦 Arquivo .apkg : {output}")
    print(f"  🃏 Total de cards: {len(cards)}")
    print(f"  🖼️  Mídias WebP  : {len(media)}")
    print(f"  📂 Baralho Anki  : {final_deck_name}")
    print(f"  🎯 Modo de Estudo: {mode.upper()} | Estilo: {style.upper()}")
    print(f"{'='*56}\n")

    # Prévia de 2 cartões para validação
    print("👀 Prévia de Cartões Gerados:")
    for i, c in enumerate(cards[:2], 1):
        clean_p = re.sub(r"<[^>]+>", "", c["pergunta"])
        clean_r = re.sub(r"<[^>]+>", "", c["resposta"])
        print(f"  [{i}] Frente: {clean_p[:100]}...")
        print(f"      Verso : {clean_r[:120]}...\n")

def main():
    parser = argparse.ArgumentParser(
        prog="anki_generator",
        description="Flashcard Architect — Pipeline com Wizard Interativo, Bypass de Mídia e Prompts Adaptativos.",
        epilog="Exemplo: python anki_generator.py --input simulado.pdf --mode strict --no-media"
    )
    parser.add_argument("--input", "-i", default=None, help="Caminho do arquivo fonte (.pdf, .md, .docx, .txt, .json)")
    parser.add_argument("--deck", "-d", default="Meu Baralho Antigravity", help="Nome do baralho no Anki (suporta ::)")
    parser.add_argument("--output", "-o", default=None, help="Caminho do arquivo .apkg de saída")
    parser.add_argument("--mode", "-M", choices=["curated", "strict", "exam"], default=None, help="Modo de fidelidade: curated (80/20), strict (literal) ou exam (erros)")
    parser.add_argument("--media", action="store_true", default=None, help="Força ativação da extração de imagens")
    parser.add_argument("--no-media", action="store_true", default=False, help="Força desativação da extração de imagens (Modo Turbo)")
    parser.add_argument("--density", "-D", choices=["essential", "high"], default=None, help="Densidade dos cartões: essential ou high")
    parser.add_argument("--style", choices=["qa", "hybrid"], default=None, help="Estilo dos cartões: qa ou hybrid (com Cloze)")
    parser.add_argument("--attachments", "-a", default=None, help="Pasta de anexos extras de imagem")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Modelo do Antigravity CLI (padrão: {DEFAULT_MODEL})")
    parser.add_argument("--effort", "-e", default=DEFAULT_EFFORT, choices=["low", "medium", "high", "xhigh", "max"], help=f"Nível de esforço (padrão: {DEFAULT_EFFORT})")
    parser.add_argument("--chunk-size", "-c", type=int, default=10, help="Páginas/seções por lote (padrão: 10)")
    parser.add_argument("--non-interactive", "-y", action="store_true", help="Pula o Wizard interativo usando padrões/flags")
    parser.add_argument("--no-ai", "--offline", action="store_true", help="Empacota diretamente um arquivo .json sem chamar IA")
    parser.add_argument("--version", "-v", action="version", version=f"Flashcard Architect v{VERSION}")

    args = parser.parse_args()

    # Auto-descoberta de arquivo se --input for omitido
    target_file = args.input
    if not target_file:
        candidates = []
        for ext in ["*.pdf", "*.md", "*.docx", "*.txt", "*.json"]:
            for f in glob.glob(ext):
                if not f.lower().startswith("requirements") and not f.lower().startswith("readme") and not f.lower().startswith("guia_mestre"):
                    candidates.append(f)
        if candidates:
            target_file = candidates[0]
            log.info(f"[Auto-Descoberta] Arquivo selecionado: {target_file}")
        else:
            log.error("[ERRO] Nenhum arquivo especificado e nenhum documento encontrado na pasta atual.")
            sys.exit(1)

    # Executa Wizard Interativo caso necessário
    args = run_interactive_wizard(args)

    run_pipeline(
        input_file=target_file,
        deck=args.deck,
        output=args.output,
        mode=args.mode,
        density=args.density,
        style=args.style,
        use_media=args.use_media,
        attachments=args.attachments,
        model=args.model,
        effort=args.effort,
        chunk_size=args.chunk_size,
        no_ai=args.no_ai
    )

if __name__ == "__main__":
    main()
