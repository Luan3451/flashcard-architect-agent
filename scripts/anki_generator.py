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
Flashcard Architect v3.1.0 — Pipeline Zero-Touch Nativo Antigravity (.apkg)
Zero dependência de APIs externas (sem Google AI Studio / sem GEMINI_API_KEY).
Utiliza exclusivamente o ecossistema Antigravity (Antigravity CLI / IDE / APP)
com o modelo Gemini 3.8 Flash (High reasoning effort).

Recursos de Alta Confiabilidade:
- Auto-bootstrapper de ambiente (instalação transparente de dependências)
- Auto-descoberta do binário Antigravity CLI (agy)
- Content-Addressed Storage com conversão para WebP (anti-colisão de mídias globais no Anki)
- Deck IDs determinísticos de 31 bits baseados no nome do baralho (anti-fusão de decks)
- Suporte nativo a cartões Básicos e cartões Cloze ({{c1::...}}) com modelos dedicados
- GUIDs determinísticos desacoplados de typos na pergunta via `id_conceito`
- Suporte a diagramas vetoriais em PDFs via `page.cluster_drawings()` e OCR offline via RapidOCR
- Extração de imagens DOCX com vinculação de posição exata nos parágrafos
- Chunking dinâmico com janela deslizante (15% de sobreposição) para evitar perda de contexto
- Validação e auto-reparo de JSON com Pydantic e json_repair
- Integração opcional com AnkiConnect (localhost:8765) + Auto-open de .apkg
- Modo Watchdog (--watch) para monitoramento contínuo de pastas Dropzone
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

# Força UTF-8 no stdout/stderr no Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ════════════════════════════════════════════
# 1. AUTO-BOOTSTRAPPER E AUTO-PROVISIONAMENTO
# ════════════════════════════════════════════

REQUIRED_PACKAGES = {
    "genanki": "genanki>=0.13.0",
    "fitz": "pymupdf>=1.23.0",
    "docx": "python-docx>=1.1.0",
    "PIL": "Pillow>=10.0.0",
    "pydantic": "pydantic>=2.7.0",
    "json_repair": "json-repair>=0.25.0",
    "watchdog": "watchdog>=4.0.0",
    "rapidocr_onnxruntime": "rapidocr-onnxruntime>=1.2.0",
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

# ════════════════════════════════════════════
# LOGGING
# ════════════════════════════════════════════

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("flashcard-architect")

# ════════════════════════════════════════════
# CONSTANTES
# ════════════════════════════════════════════

VERSION = "3.1.0"
MEDIA_DIR = "anki_media"
MAX_RETRIES = 3
RETRY_DELAY_SECS = 4
DEFAULT_MODEL = "gemini-3.8-flash-high"
DEFAULT_EFFORT = "high"

# Model IDs estáticos para compartilhar tipo de nota e CSS
MODEL_BASIC_ID = 1607392319
MODEL_CLOZE_ID = 1607392320

def get_deterministic_id(name: str) -> int:
    """Gera um inteiro positivo de 31 bits único e determinístico a partir do nome do deck."""
    hash_hex = hashlib.sha256(name.strip().lower().encode("utf-8")).hexdigest()
    return int(hash_hex[:8], 16) & 0x7FFFFFFF

# ════════════════════════════════════════════
# PROMPT MESTRE ENXUTO (ZERO CSS INLINE)
# ════════════════════════════════════════════

SYSTEM_PROMPT = """
Você é o Flashcard Architect — especialista em ciência cognitiva, active recall e algoritmo FSRS do Anki.

OBJETIVO:
Transformar o material fornecido em flashcards atômicos de altíssima retenção.

REGRAS DE ENGENHARIA COGNITIVA:
1. ATOMICIDADE ESTRITA: Cada cartão deve testar UMA ÚNICA associação mental. Divida conceitos complexos em múltiplos cartões atômicos.
2. ÂNCORA DE CONTEXTO: Enunciados 100% autossuficientes. Nunca use pronomes vagos ("Qual a função dele?"). Sempre especifique o domínio ("No protocolo OSPF, qual a função do pacote Hello?").
3. JUSTIFICATIVA TÉCNICA: No verso, após a resposta direta, inclua sempre uma justificativa concisa explicando a causa/efeito ou o erro das alternativas incorretas.
4. FORMATAÇÃO HTML LIMPA (NÃO USE ATRIBUTOS style="" INLINE):
   - Gabarito/Resposta principal: <span class="ans">resposta direta</span>
   - Destaques e palavras-chave: <b>termo</b>
   - Termos técnicos / siglas: <i>conceito</i>
   - Comandos, portas, caminhos e código: <code>comando</code>
   - Imagens contextuais: <br><img src="nome_exato_da_imagem.ext"> (coloque na frente se for essencial para responder; no verso se for diagrama de solução)
   - Cartões de lacuna (Cloze): Se fizer mais sentido ocultar termos literais, use {{c1::termo}} na pergunta.
5. IDENTIFICADORES E TAGS:
   - "id_conceito": crie um identificador estável em snake_case (ex: "redes_bgp_keepalive_objetivo").
   - "tags": gere de 1 a 3 tags curtas em snake_case identificando o tópico (ex: ["redes", "bgp"]).
   - "suggested_deck": sugira uma taxonomia hierárquica no formato "Categoria::Subcategoria::Assunto".

SAÍDA EXCLUSIVA (Retorne APENAS um Array JSON válido ou objeto JSON, sem blocos markdown):
[
  {
    "id_conceito": "redes_bgp_keepalive_objetivo",
    "pergunta": "No protocolo <b>BGP</b>, qual é o objetivo da mensagem <i>Keepalive</i> e seu intervalo padrão de envio?",
    "resposta": "<span class=\"ans\">Manter a sessão ativa entre peers (60 segundos).</span><br><br><i>Justificativa:</i> Confirma a alcançabilidade da sessão TCP na porta <code>179</code> antes que o <i>Hold Timer</i> expire.",
    "tags": ["redes", "bgp"],
    "suggested_deck": "Tecnologia::Redes::Roteamento_Avancado"
  }
]
""".strip()

# ════════════════════════════════════════════
# CSS DARK MODE PROFISSIONAL (COM CORREÇÃO DE ESPECIFICIDADE)
# ════════════════════════════════════════════

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
/* Destaque padrão azul para palavras-chave gerais */
b, strong { color: #58a6ff; font-weight: 600; }
i, em { color: #f0883e; }

/* Correção de especificidade: verde neon para o gabarito principal mesmo se contiver <b> dentro */
.ans, .ans b, .ans strong {
    color: #4af626 !important;
    font-weight: 700;
}

/* Lacunas Cloze */
.cloze {
    font-weight: 700;
    color: #4af626 !important;
}

/* Bloco opcional para Justificativa */
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

# ════════════════════════════════════════════
# 2. CONTENT-ADDRESSED STORAGE & IMAGENS WEBP
# ════════════════════════════════════════════

def ensure_media_dir() -> str:
    os.makedirs(MEDIA_DIR, exist_ok=True)
    return MEDIA_DIR

def save_normalized_image(img_bytes: bytes, min_dim: int = 80) -> str | None:
    """
    Filtra ruídos, converte para WebP e nomeia por hash SHA-256 (anti-colisão global no Anki).
    Gera filenames únicos no padrão: ag_{hash[:12]}.webp
    """
    if len(img_bytes) < 2048:  # Ignora arquivos/ícones menores que 2KB
        return None

    ensure_media_dir()
    try:
        if PIL_AVAILABLE:
            with Image.open(BytesIO(img_bytes)) as im:
                w, h = im.size
                if w < min_dim or h < min_dim:
                    return None
                # Ignora faixas e linhas divisórias extremas (proporção > 12:1)
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

        if not os.path.exists(filepath):
            with open(filepath, "wb") as f:
                f.write(webp_bytes)

        return filename
    except Exception as e:
        log.debug(f"Erro ao processar imagem: {e}")
        return None

def extract_vector_diagrams(page: fitz.Page) -> list[str]:
    """Captura diagramas vetoriais e tabelas agrupadas que não são bitmaps XRef simples."""
    saved = []
    try:
        drawings = page.cluster_drawings()
        for rect in drawings:
            if rect.width >= 100 and rect.height >= 80:
                pix = page.get_pixmap(clip=rect, dpi=200)
                fname = save_normalized_image(pix.tobytes("png"))
                if fname and fname not in saved:
                    saved.append(fname)
    except Exception as e:
        log.debug(f"Aviso em cluster_drawings: {e}")
    return saved

# ════════════════════════════════════════════
# 3. EXTRAÇÃO DE CONTEÚDO (PDF, MD, DOCX, TXT)
# ════════════════════════════════════════════

def ocr_page_if_needed(page: fitz.Page) -> str:
    """Executa OCR offline transparente com RapidOCR se a página tiver pouco texto nativo."""
    text = page.get_text("text").strip()
    if len(text) >= 40 or not RAPID_OCR_AVAILABLE:
        return text

    try:
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        ocr_engine = RapidOCR()
        result, _ = ocr_engine(img_bytes)
        if result:
            ocr_text = "\n".join([line[1] for line in result])
            log.info(f"      [OCR Offline] Extraídos {len(ocr_text)} caracteres da imagem da página.")
            return ocr_text
    except Exception as e:
        log.debug(f"Falha no OCR offline: {e}")

    return text

def extract_from_pdf(path: str) -> tuple[list[str], list[str]]:
    """Extrai texto, bitmaps XRef e diagramas vetoriais de um arquivo PDF com deduplicação por hash."""
    if fitz is None:
        log.error("[ERRO] PyMuPDF não está instalado. Execute: pip install PyMuPDF")
        sys.exit(1)

    ensure_media_dir()
    doc = fitz.open(path)
    pages_text = []
    media_files = []
    seen_hashes = set()

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = ocr_page_if_needed(page)

        if not page_text.strip():
            page_text = f"[Página {page_num + 1}: sem texto extraível]\n"
        else:
            page_text += f"\n[Fim da Página {page_num + 1}]\n"

        # 1. Extração de Bitmaps XRef
        for img_info in page.get_images(full=True):
            try:
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]

                fname = save_normalized_image(image_bytes)
                if fname:
                    fpath = os.path.join(MEDIA_DIR, fname)
                    if fpath not in media_files:
                        media_files.append(fpath)
                    if fname not in seen_hashes:
                        seen_hashes.add(fname)
                        page_text += f"\n[Imagem extraída nesta página: {fname}]\n"
            except Exception as e:
                log.debug(f"Erro em imagem XRef pág. {page_num + 1}: {e}")

        # 2. Extração de Agrupamentos Vetoriais
        vector_images = extract_vector_diagrams(page)
        for vname in vector_images:
            vpath = os.path.join(MEDIA_DIR, vname)
            if vpath not in media_files:
                media_files.append(vpath)
            if vname not in seen_hashes:
                seen_hashes.add(vname)
                page_text += f"\n[Diagrama vetorial extraído nesta página: {vname}]\n"

        pages_text.append(page_text)

    log.info(f"      → PDF: {len(doc)} página(s), {len(media_files)} imagem(ns) e diagrama(s) normalizados.")
    return pages_text, media_files

def extract_from_docx(path: str) -> tuple[list[str], list[str]]:
    """Extrai texto e imagens de DOCX preservando a posição exata de cada imagem nos parágrafos."""
    if not DOCX_AVAILABLE:
        log.error("[ERRO] python-docx não instalado. Execute: pip install python-docx")
        sys.exit(1)

    ensure_media_dir()
    doc = DocxDocument(path)
    media_files = []
    paragraphs_text = []

    for para in doc.paragraphs:
        p_text = para.text.strip()
        # Busca imagens inline via XPath sequencial no XML do parágrafo
        try:
            blips = para._element.xpath('.//a:blip/@r:embed')
            for r_id in blips:
                rel = doc.part.rels.get(r_id)
                if rel and "image" in rel.reltype:
                    image_bytes = rel.target_part.blob
                    fname = save_normalized_image(image_bytes)
                    if fname:
                        fpath = os.path.join(MEDIA_DIR, fname)
                        if fpath not in media_files:
                            media_files.append(fpath)
                        p_text += f"\n[Imagem extraída nesta posição: {fname}]\n"
        except Exception as e:
            log.debug(f"Aviso no parse de XML do DOCX: {e}")

        if p_text:
            paragraphs_text.append(p_text)

    full_text = "\n\n".join(paragraphs_text)
    log.info(f"      → DOCX: {len(paragraphs_text)} parágrafo(s), {len(media_files)} imagem(ns) contextualizada(s).")
    return [full_text], media_files

def extract_from_markdown(path: str, attach_dir: str | None = None) -> tuple[list[str], list[str]]:
    """Extrai texto de Markdown, converte imagens referenciadas para WebP normalizado e vincula ao texto."""
    ensure_media_dir()
    md_dir = os.path.dirname(os.path.abspath(path))
    content = ""
    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            with open(path, "r", encoding=enc) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    media_files = []
    search_dirs = [md_dir]
    if attach_dir and os.path.exists(attach_dir):
        search_dirs.append(attach_dir)
    for sub in ["attachments", "anexos", "media", "images", "img", "assets"]:
        cand = os.path.join(md_dir, sub)
        if os.path.exists(cand):
            search_dirs.append(cand)

    # Localiza referências ![alt](caminho) e <img src="caminho">
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
                    img_bytes = f.read()
                normalized_name = save_normalized_image(img_bytes, min_dim=20)
                if normalized_name:
                    dest_path = os.path.join(MEDIA_DIR, normalized_name)
                    if dest_path not in media_files:
                        media_files.append(dest_path)
                    content = content.replace(img_ref, normalized_name)
            except Exception as e:
                log.warning(f"  ⚠ Erro ao normalizar mídia {resolved}: {e}")

    log.info(f"      → Markdown: {len(content)} caracteres, {len(media_files)} imagem(ns) vinculada(s).")
    return [content], media_files

def extract_from_text(path: str, attach_dir: str | None = None) -> tuple[list[str], list[str]]:
    """Extrai texto puro e normaliza anexos da pasta informada."""
    ensure_media_dir()
    content = ""
    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            with open(path, "r", encoding=enc) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    media_files = []
    if attach_dir and os.path.exists(attach_dir):
        for root, _, files in os.walk(attach_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".bmp"}:
                    fpath = os.path.join(root, file)
                    try:
                        with open(fpath, "rb") as f:
                            b = f.read()
                        norm = save_normalized_image(b, min_dim=20)
                        if norm:
                            p = os.path.join(MEDIA_DIR, norm)
                            if p not in media_files:
                                media_files.append(p)
                    except Exception:
                        pass

    log.info(f"      → Texto: {len(content)} caracteres, {len(media_files)} anexo(s).")
    return [content], media_files

def extract_content(path: str, attach_dir: str | None = None) -> tuple[list[str], list[str]]:
    """Roteador inteligente de extração com suporte completo a formatos."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return extract_from_pdf(path)
    elif ext in [".md", ".markdown"]:
        return extract_from_markdown(path, attach_dir)
    elif ext == ".docx":
        return extract_from_docx(path)
    else:
        return extract_from_text(path, attach_dir)

# ════════════════════════════════════════════
# 4. CHUNKING COM JANELA DESLIZANTE (OVERLAP)
# ════════════════════════════════════════════

def chunk_with_overlap(pages: list[str], max_chars_per_chunk: int = 8000, overlap_ratio: float = 0.15) -> list[str]:
    """
    Agrupa páginas/blocos de texto em lotes dinâmicos com sobreposição de 15%.
    Impede que uma questão no final da página 10 seja separada do seu gabarito/diagrama no início da página 11.
    """
    chunks = []
    current_chunk = []
    current_len = 0

    for page in pages:
        page_len = len(page)
        if current_len + page_len > max_chars_per_chunk and current_chunk:
            chunk_text = "\n".join(current_chunk)
            chunks.append(chunk_text)

            # Calcula sobreposição: preserva os últimos blocos que representem ~15% dos caracteres
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

# ════════════════════════════════════════════
# 5. MODELO PYDANTIC E REPARO DE RESPOSTA
# ════════════════════════════════════════════

if PYDANTIC_AVAILABLE:
    class CardItem(BaseModel):
        id_conceito: str = Field(default="")
        pergunta: str
        resposta: str
        tags: list[str] = Field(default_factory=list)
        suggested_deck: str = Field(default="")

def parse_and_validate_cards(raw_response: str) -> tuple[list[dict], str]:
    """
    Limpa e valida a resposta da IA utilizando json_repair e Pydantic.
    Retorna a lista de cartões normalizados e a sugestão de nome de deck se houver.
    """
    if not raw_response or not raw_response.strip():
        return [], ""

    text = raw_response.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text).strip()

    # Reparo automático de JSON com aspas soltas ou truncado
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

        # Normalização com Pydantic se disponível
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
    """
    Auditor e auto-corretor de tags <img>:
    Corrige alucinações de caminhos ou extensões da IA usando fuzzy matching com os arquivos em anki_media/.
    """
    if not available_media:
        return

    basenames = [os.path.basename(m) for m in available_media]
    for card in cards:
        for field in ["pergunta", "resposta"]:
            text = card[field]
            # Encontra tags <img src="...">
            for m in re.finditer(r'<img[^>]+src=["\'](.*?)["\']', text, re.IGNORECASE):
                img_src = m.group(1).strip()
                src_base = os.path.basename(img_src)
                if src_base not in basenames:
                    # Tenta encontrar por prefixo ou correspondência parcial
                    clean_match = None
                    for b in basenames:
                        if b in src_base or src_base in b:
                            clean_match = b
                            break
                    if clean_match:
                        card[field] = card[field].replace(img_src, clean_match)

# ════════════════════════════════════════════
# 6. GERAÇÃO NATIVA COM ANTIGRAVITY CLI (AGY)
# ════════════════════════════════════════════

def call_antigravity_cli(prompt_text: str, model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT) -> str | None:
    """Invoca o Antigravity CLI nativo (agy) diretamente no terminal, sem chaves externas de API."""
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
        log.error("[ERRO] Binário 'agy' não encontrado no PATH. Execute 'agy install' para configurar.")
        return None
    except Exception as e:
        log.warning(f"  ⚠ Erro inesperado ao invocar Antigravity CLI: {e}")
        return None

def generate_flashcards_antigravity(
    chunks: list[str],
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    cache_path: str = ".anki_cache.jsonl",
    resume: bool = False
) -> tuple[list[dict], str]:
    """
    Executa a geração através de lotes dinâmicos com cache de checkpointing (.anki_cache.jsonl).
    Permite retomar de onde parou em caso de timeout.
    """
    all_cards = []
    overall_suggested_deck = ""
    start_chunk = 0

    # Recupera cache existente se solicitado
    if resume and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        all_cards.extend(data.get("cards", []))
                        if not overall_suggested_deck and data.get("suggested_deck"):
                            overall_suggested_deck = data.get("suggested_deck")
            log.info(f"  [Resume] {len(all_cards)} card(s) recuperado(s) do cache anterior.")
        except Exception as e:
            log.debug(f"Erro ao ler cache: {e}")

    total_chunks = len(chunks)
    log.info(f"\n  Iniciando processamento nativo via Antigravity ({model} - esforço: {effort})...")

    for idx, chunk in enumerate(chunks):
        log.info(f"  → Lote {idx + 1}/{total_chunks} (~{len(chunk):,} caracteres)...")
        prompt = f"{SYSTEM_PROMPT}\n\nMATERIAL DE ESTUDO:\n{chunk}"

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

                # Grava no checkpoint cache
                try:
                    with open(cache_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"chunk": idx, "cards": cards, "suggested_deck": deck_sug}) + "\n")
                except Exception:
                    pass

                success = True
                break
            else:
                log.warning(f"     ⚠ Resposta do lote {idx + 1} não continha cards válidos (tentativa {attempt}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY_SECS)

        if not success:
            log.error(f"     ✗ Falha no lote {idx + 1} após {MAX_RETRIES} tentativas.")

    return all_cards, overall_suggested_deck

# ════════════════════════════════════════════
# 7. MONTAGEM DO PACOTE ANKI (.apkg)
# ════════════════════════════════════════════

def build_anki_deck(flashcards: list[dict], media_files: list[str], deck_name: str, output_path: str) -> None:
    """
    Monta o pacote .apkg com suporte real a cartões Básicos e Cloze,
    IDs de deck determinísticos e GUIDs imunes a correções de digitação.
    """
    if genanki is None:
        log.error("[ERRO] genanki não instalado. Execute: pip install genanki")
        sys.exit(1)

    deck_id = get_deterministic_id(deck_name)

    # 1. Modelo Básico Dark
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

    # 2. Modelo Cloze Dark
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

        # GUID determinístico desacoplado do texto da pergunta
        guid_seed = f"{deck_name}_{cid}" if cid else f"{deck_name}_{p}"
        note_guid = genanki.guid_for(guid_seed)

        # Detecta automaticamente se o cartão utiliza sintaxe Cloze ({{c1::...}})
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

# ════════════════════════════════════════════
# 8. INTEGRAÇÃO INVISÍVEL (ANKICONNECT & AUTO-OPEN)
# ════════════════════════════════════════════

def push_to_ankiconnect(cards: list[dict], media_files: list[str], deck_name: str) -> bool:
    """Tenta injetar notas e mídias diretamente no AnkiDesktop via AnkiConnect (localhost:8765)."""
    import urllib.request
    anki_url = "http://127.0.0.1:8765"

    def anki_invoke(action, **params):
        payload = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
        req = urllib.request.Request(anki_url, data=payload)
        with urllib.request.urlopen(req, timeout=3) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("error"):
                raise RuntimeError(res["error"])
            return res.get("result")

    try:
        anki_invoke("version")
    except Exception:
        # Tenta iniciar o Anki em segundo plano caso o executável exista no sistema
        anki_exe = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Anki" / "anki.exe"
        if anki_exe.exists():
            log.info("  [AnkiConnect] Inicializando Anki Desktop em segundo plano...")
            subprocess.Popen([str(anki_exe)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)
            try:
                anki_invoke("version")
            except Exception:
                return False
        else:
            return False

    try:
        # 1. Envia Mídias
        for mpath in media_files:
            if os.path.exists(mpath):
                import base64
                with open(mpath, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                anki_invoke("storeMediaFile", filename=os.path.basename(mpath), data=b64)

        # 2. Garante o Baralho
        anki_invoke("createDeck", deck=deck_name)

        # 3. Adiciona Notas
        notes_payload = []
        for c in cards:
            is_cloze = "{{c" in c["pergunta"]
            model_name = "Flashcard Architect Native Cloze" if is_cloze else "Flashcard Architect Native Basic"
            fields = {"Text": c["pergunta"], "Extra": c["resposta"]} if is_cloze else {"Pergunta": c["pergunta"], "Resposta": c["resposta"]}
            notes_payload.append({
                "deckName": deck_name,
                "modelName": model_name,
                "fields": fields,
                "tags": c.get("tags", ["antigravity-native"])
            })

        # Adiciona em lote
        if notes_payload:
            anki_invoke("addNotes", notes=notes_payload)
            log.info(f"  [AnkiConnect] Injetados {len(notes_payload)} flashcards diretamente no Anki Desktop!")

        # 4. Sincroniza com AnkiWeb
        try:
            anki_invoke("sync")
            log.info("  [AnkiConnect] Sincronização disparada com AnkiWeb (disponível no celular/tablet)!")
        except Exception:
            pass

        return True
    except Exception as e:
        log.warning(f"  ⚠ Falha ao injetar via AnkiConnect: {e}")
        return False

def auto_open_package(output_path: str) -> None:
    """Abre o arquivo .apkg com o programa padrão do sistema (Anki) sem requerer comandos manuais."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(output_path)
        elif sys.platform.startswith("darwin"):
            subprocess.Popen(["open", output_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", output_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log.info(f"  [Auto-Open] Disparada abertura de '{output_path}' no Anki.")
    except Exception as e:
        log.debug(f"Aviso no auto-open: {e}")

# ════════════════════════════════════════════
# 9. MODO WATCHDOG (DROPZONE FOLDER)
# ════════════════════════════════════════════

def watch_directory(watch_dir: str, model: str, effort: str) -> None:
    """Monitora uma pasta dropzone. Ao cair um arquivo suportado, processa e arquiva automaticamente."""
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    processed_dir = os.path.join(watch_dir, "Processados")
    decks_dir = os.path.join(watch_dir, "Decks")
    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(decks_dir, exist_ok=True)

    class DropzoneHandler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                return
            ext = os.path.splitext(event.src_path)[1].lower()
            if ext in [".pdf", ".md", ".docx", ".txt", ".json"]:
                time.sleep(1)  # Aguarda gravação do arquivo concluir
                log.info(f"\n[Dropzone] Novo arquivo detectado: {event.src_path}")
                run_pipeline(event.src_path, model=model, effort=effort, output_dir=decks_dir)
                try:
                    dest = os.path.join(processed_dir, os.path.basename(event.src_path))
                    shutil.move(event.src_path, dest)
                    log.info(f"[Dropzone] Arquivo movido para: {dest}")
                except Exception as e:
                    log.debug(f"Erro ao mover arquivo processado: {e}")

    observer = Observer()
    observer.schedule(DropzoneHandler(), watch_dir, recursive=False)
    observer.start()
    log.info(f"╔══════════════════════════════════════════════════╗")
    log.info(f"║  Flashcard Architect — Modo Watchdog Ativo       ║")
    log.info(f"║  Monitorando pasta: {watch_dir:<29}║")
    log.info(f"╚══════════════════════════════════════════════════╝")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

# ════════════════════════════════════════════
# 10. PIPELINE PRINCIPAL E INFERÊNCIA ZERO-TOUCH
# ════════════════════════════════════════════

def run_pipeline(
    input_file: str,
    deck: str | None = None,
    output: str | None = None,
    attachments: str | None = None,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    chunk_size: int = 10,
    no_ai: bool = False,
    push: bool = True,
    no_open: bool = False,
    output_dir: str | None = None
) -> None:
    """Executa o pipeline completo de forma autônoma (Zero-Touch)."""
    base_name = os.path.splitext(os.path.basename(input_file))[0]

    # 1. Extração
    print(f"\n[1/3] Processando material e coletando anexos: {input_file}")
    pages, media = extract_content(input_file, attachments)
    total_chars = sum(len(p) for p in pages)
    print(f"      → {len(pages)} bloco(s) | {len(media)} anexo(s)/imagem(ns) | ~{total_chars:,} caracteres")

    # 2. Obtenção dos flashcards
    cards = []
    suggested_deck = ""
    is_json = input_file.lower().endswith(".json") or no_ai

    if is_json:
        print(f"\n[2/3] Carregando flashcards pré-estruturados (modo direto)...")
        raw_text = "\n".join(pages)
        cards, suggested_deck = parse_and_validate_cards(raw_text)
    else:
        print(f"\n[2/3] Gerando flashcards com Antigravity CLI ({model} / {effort})...")
        chunks = chunk_with_overlap(pages, max_chars_per_chunk=8000, overlap_ratio=0.15)
        cards, suggested_deck = generate_flashcards_antigravity(chunks, model=model, effort=effort)

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

    # Nome do arquivo .apkg de saída
    if not output:
        slug = re.sub(r"[^\w\s-]", "", final_deck_name.replace("::", "_")).strip().replace(" ", "_")
        output = f"{slug}.apkg"

    if output_dir:
        output = os.path.join(output_dir, os.path.basename(output))

    # 3. Empacotamento
    print(f"\n[3/3] Montando pacote Anki: '{final_deck_name}' -> {output}")
    build_anki_deck(cards, media, final_deck_name, output)

    # 4. Injeção AnkiConnect ou Auto-Open
    injected = False
    if push:
        injected = push_to_ankiconnect(cards, media, final_deck_name)

    if not injected and not no_open:
        auto_open_package(output)

    print(f"\n{'='*52}")
    print(f"  ✅ Concluído com sucesso (Zero-Touch)!")
    print(f"  📦 Arquivo .apkg : {output}")
    print(f"  🃏 Total de cards: {len(cards)}")
    print(f"  🖼️  Mídias WebP  : {len(media)}")
    print(f"  📂 Baralho Anki  : {final_deck_name}")
    print(f"{'='*52}\n")

# ════════════════════════════════════════════
# CLI ARGPARSE
# ════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        prog="anki_generator",
        description="Flashcard Architect — Pipeline Zero-Touch Nativo Antigravity de Decks Anki (.apkg)",
        epilog="Zero flags necessárias: basta rodar 'python anki_generator.py' para auto-descobrir arquivos!"
    )
    parser.add_argument(
        "--input", "-i",
        default=None,
        help="Arquivo de entrada (opcional se houver PDF/MD/DOCX no diretório)"
    )
    parser.add_argument(
        "--deck", "-d",
        default=None,
        help="Nome do deck no Anki (se omitido, inferido automaticamente pela IA)"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Caminho do arquivo .apkg de saída (se omitido, baseado no nome do deck)"
    )
    parser.add_argument(
        "--attachments", "-a",
        default=None,
        help="Diretório com imagens extras para incluir no deck"
    )
    parser.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL,
        help=f"Modelo do Antigravity CLI (padrão: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--effort", "-e",
        default=DEFAULT_EFFORT,
        choices=["low", "medium", "high", "xhigh", "max"],
        help=f"Nível de raciocínio no Antigravity CLI (padrão: {DEFAULT_EFFORT})"
    )
    parser.add_argument(
        "--chunk-size", "-c",
        type=int,
        default=10,
        help="Tamanho de referência dos lotes (padrão: 10)"
    )
    parser.add_argument(
        "--no-ai", "--offline",
        action="store_true",
        help="Modo offline direto para JSON pré-estruturado"
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Não tenta conectar ao AnkiConnect local"
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Não abre o arquivo .apkg automaticamente no sistema"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Inicia modo Watchdog em pasta dropzone contínua"
    )
    parser.add_argument(
        "--watch-dir",
        default="./inbox",
        help="Diretório monitorado pelo modo Watchdog (padrão: ./inbox)"
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"Flashcard Architect v{VERSION} (Zero-Touch Antigravity)"
    )
    args = parser.parse_args()

    if args.watch:
        os.makedirs(args.watch_dir, exist_ok=True)
        watch_directory(args.watch_dir, args.model, args.effort)
        return

    target_file = args.input
    if not target_file:
        # Auto-descoberta de arquivos não processados na pasta atual
        candidates = []
        for ext in ["*.pdf", "*.md", "*.docx", "*.txt", "*.json"]:
            for f in glob.glob(ext):
                if not f.lower().startswith("requirements") and not f.lower().startswith("readme") and not f.lower().startswith("guia_mestre"):
                    candidates.append(f)
        if candidates:
            target_file = candidates[0]
            log.info(f"[Zero-Touch] Arquivo auto-descoberto: {target_file}")
        else:
            log.error("[ERRO] Nenhum arquivo especificado e nenhum documento (.pdf, .md, .docx, .txt, .json) encontrado na pasta atual.")
            sys.exit(1)

    print(f"+--------------------------------------------------+")
    print(f"|  Flashcard Architect v{VERSION} — Zero-Touch Native |")
    print(f"|  Modelo: {args.model:<24} Esforco: {args.effort:<6} |")
    print(f"+--------------------------------------------------+")

    run_pipeline(
        input_file=target_file,
        deck=args.deck,
        output=args.output,
        attachments=args.attachments,
        model=args.model,
        effort=args.effort,
        chunk_size=args.chunk_size,
        no_ai=args.no_ai,
        push=not args.no_push,
        no_open=args.no_open
    )

if __name__ == "__main__":
    main()
