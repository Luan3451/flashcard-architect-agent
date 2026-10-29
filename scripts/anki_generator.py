#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flashcard Architect v3.0.0 — Gerador Nativo Antigravity de Decks Anki (.apkg)
Zero dependência de APIs externas (sem Google AI Studio / sem GEMINI_API_KEY).
Utiliza exclusivamente o ecossistema Antigravity (Antigravity CLI / IDE / APP)
com o modelo Gemini 3.8 Flash (High reasoning effort).

Recursos:
- Processa PDF, DOCX, Markdown (.md), TXT e JSON pré-estruturado
- Coleta anexos e extrai imagens automaticamente de PDFs, DOCXs e referências em Markdown
- Empacota tudo em .apkg com mídias embutidas e CSS dark mode para Anki (algoritmo FSRS)
"""

import argparse
import glob
import json
import logging
import os
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
# DEPENDÊNCIAS OPCIONAIS / OBRIGATÓRIAS
# ════════════════════════════════════════════

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import genanki
except ImportError:
    genanki = None

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# ════════════════════════════════════════════
# LOGGING
# ════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)
log = logging.getLogger("flashcard-architect")

# ════════════════════════════════════════════
# CONSTANTES
# ════════════════════════════════════════════

VERSION = "3.0.0"
MEDIA_DIR = "anki_media"
MAX_RETRIES = 3
RETRY_DELAY_SECS = 4
DEFAULT_MODEL = "gemini-3.8-flash-high"
DEFAULT_EFFORT = "high"

# IDs fixos do genanki (consistentes entre execuções para atualizar notas sem duplicar)
MODEL_ID = 1607392319
DECK_ID  = 2059400110

SYSTEM_PROMPT = """
Você é o Flashcard Architect — um especialista em aprendizagem ativa, design instrucional e criação de flashcards de alta retenção para o Anki (algoritmo FSRS).

OBJETIVO: Processar o material de estudo e retornar flashcards estruturados, atômicos e explicativos.

REGRAS OBRIGATÓRIAS:
1. FRENTE (Pergunta):
   - Enunciado claro, objetivo e contextualizado.
   - Princípio atômico: UMA ÚNICA ideia/conceito por card.
   - Active Recall: a pergunta deve exigir esforço ativo de recuperação da memória.
   - Se o texto referenciar uma imagem (ex: [Imagem: X] ou <img src="X">), OBRIGATORIAMENTE inclua:
     <br><br><img src="X" style="max-width:100%; border-radius:8px; border:1px solid #444;">
2. VERSO (Resposta):
   - Resposta correta de forma direta e concisa.
   - "Justificativa" detalhada que explique o porquê do acerto e promova o entendimento real.
   - Se houver alternativas incorretas no material de origem, explique sucintamente por que estão erradas.
   - Quando útil, inclua mnemônicos ou diagramas em texto.
3. FORMATAÇÃO VISUAL (Dark Mode Anki nativo):
   - Palavras-chave essenciais: <b>termo</b>
   - Conceitos e termos técnicos: <i>conceito</i>
   - Definições e destaques: <span style="color:#4af626;"><b>definição</b></span>
   - Código, comandos ou portas de rede: <code style="background-color:#121212; padding:2px 6px; border-radius:4px; font-family:monospace; color:#4af626;">comando</code>
   - Listas: <ul><li>item 1</li><li>item 2</li></ul>
   - Espaçamento: <br>
4. GESTÃO DE IMAGENS:
   - Se uma imagem ou figura é necessária para resolver a questão, coloque-a na FRENTE.
   - Se for um diagrama de solução explicativa, inclua-a no VERSO.
   - Use o nome exato do arquivo de imagem (ex: imagem_1.png).
5. SAÍDA EXCLUSIVA:
   - Retorne ESTRITAMENTE um array JSON válido: [{"pergunta": "...", "resposta": "..."}]
   - Sem blocos markdown (não use ```json), sem texto adicional antes ou depois.
""".strip()

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
# UTILITÁRIOS E DIRETÓRIO DE MÍDIA
# ════════════════════════════════════════════

def ensure_media_dir():
    os.makedirs(MEDIA_DIR, exist_ok=True)
    return MEDIA_DIR

def sanitize_filename(name):
    """Sanitiza o nome do arquivo para compatibilidade com o Anki."""
    clean = re.sub(r'[^\w\.-]', '_', os.path.basename(name))
    return clean

# ════════════════════════════════════════════
# EXTRAÇÃO DE CONTEÚDO E IMAGENS (PDF, MD, DOCX, TXT)
# ════════════════════════════════════════════

def copy_to_media(source_path):
    """Copia uma imagem para o diretório anki_media e retorna o caminho final."""
    ensure_media_dir()
    if not os.path.exists(source_path):
        return None
    dest_name = sanitize_filename(source_path)
    dest_path = os.path.join(MEDIA_DIR, dest_name)
    try:
        shutil.copy2(source_path, dest_path)
        return dest_path
    except Exception as e:
        log.warning(f"  ⚠ Erro ao copiar mídia {source_path}: {e}")
        return None

def collect_attachments(attach_dir):
    """Varre um diretório de anexos em busca de arquivos de imagem."""
    collected = []
    if not attach_dir or not os.path.exists(attach_dir):
        return collected

    extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}
    for root, _, files in os.walk(attach_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in extensions:
                full_path = os.path.join(root, f)
                copied = copy_to_media(full_path)
                if copied and copied not in collected:
                    collected.append(copied)
    return collected

def extract_from_pdf(path):
    """Extrai texto e imagens embutidas de um arquivo PDF com PyMuPDF."""
    if fitz is None:
        log.error("[ERRO] PyMuPDF não está instalado. Execute: pip install PyMuPDF")
        sys.exit(1)

    ensure_media_dir()
    doc = fitz.open(path)
    pages_text = []
    media_files = []
    img_count = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text("text")

        if not page_text.strip():
            page_text = f"[Página {page_num + 1}: sem texto extraível]\n"
        else:
            page_text += f"\n[Fim da Página {page_num + 1}]\n"

        for img_index, img in enumerate(page.get_images(full=True)):
            try:
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                # Ignora apenas se for minúsculo (ícone de 1-10px ou menor que 100 bytes)
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)
                if (width > 0 and width < 12 and height > 0 and height < 12) or len(image_bytes) < 100:
                    continue

                image_name = f"pdf_p{page_num + 1}_{img_index}.{image_ext}"
                image_path = os.path.join(MEDIA_DIR, image_name)

                with open(image_path, "wb") as f:
                    f.write(image_bytes)

                if image_path not in media_files:
                    media_files.append(image_path)
                img_count += 1
                page_text += f"\n[Imagem extraída nesta página: {image_name}]\n"
            except Exception as e:
                log.warning(f"  ⚠ Erro ao extrair imagem do PDF pág. {page_num + 1}: {e}")

        pages_text.append(page_text)

    log.info(f"      → PDF: {len(doc)} página(s), {img_count} imagem(ns) coletada(s)")
    return pages_text, media_files

def extract_from_markdown(path, attach_dir=None):
    """
    Extrai texto e imagens referenciadas em um arquivo Markdown (.md).
    Detecta ![alt](caminho) e <img src="caminho">, copia para anki_media
    e adapta o texto para o Anki.
    """
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
    # Possíveis locais de busca de anexos
    search_dirs = [md_dir]
    if attach_dir and os.path.exists(attach_dir):
        search_dirs.append(attach_dir)
    for sub in ["attachments", "media", "images", "img", "assets"]:
        cand = os.path.join(md_dir, sub)
        if os.path.exists(cand):
            search_dirs.append(cand)

    # 1. Regex para ![alt](path)
    md_img_pattern = re.compile(r'!\[(.*?)\]\((.*?)\)')
    # 2. Regex para <img src="path">
    html_img_pattern = re.compile(r'<img[^>]+src=["\'](.*?)["\']', re.IGNORECASE)

    found_paths = []
    for match in md_img_pattern.finditer(content):
        found_paths.append(match.group(2).strip())
    for match in html_img_pattern.finditer(content):
        found_paths.append(match.group(1).strip())

    for img_ref in found_paths:
        # Ignora URLs remotas http:// ou https://
        if img_ref.startswith("http://") or img_ref.startswith("https://"):
            continue

        resolved = None
        for s_dir in search_dirs:
            candidate = os.path.normpath(os.path.join(s_dir, img_ref))
            if os.path.exists(candidate):
                resolved = candidate
                break

        if resolved and os.path.isfile(resolved):
            copied = copy_to_media(resolved)
            if copied and copied not in media_files:
                media_files.append(copied)
                base_name = os.path.basename(copied)
                # Normaliza referência no markdown
                content = content.replace(img_ref, base_name)
        else:
            log.warning(f"  ⚠ Imagem referenciada no Markdown não encontrada localmente: {img_ref}")

    # Coleta anexos adicionais da pasta se houver
    if attach_dir:
        extra = collect_attachments(attach_dir)
        for m in extra:
            if m not in media_files:
                media_files.append(m)

    log.info(f"      → Markdown: {len(content)} caracteres, {len(media_files)} imagem(ns) vinculada(s)")
    return [content], media_files

def extract_from_docx(path):
    """Extrai texto e imagens embutidas de um arquivo DOCX."""
    if not DOCX_AVAILABLE:
        log.error("[ERRO] python-docx não instalado. Execute: pip install python-docx")
        sys.exit(1)

    ensure_media_dir()
    doc = DocxDocument(path)
    media_files = []
    paragraphs = []
    img_count = 0

    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            try:
                image_data = rel.target_part.blob
                ext = rel.target_part.content_type.split("/")[-1]
                if ext == "jpeg":
                    ext = "jpg"
                image_name = f"docx_img_{img_count}.{ext}"
                image_path = os.path.join(MEDIA_DIR, image_name)

                with open(image_path, "wb") as f:
                    f.write(image_data)
                if image_path not in media_files:
                    media_files.append(image_path)
                img_count += 1
            except Exception as e:
                log.warning(f"  ⚠ Erro ao extrair imagem do DOCX: {e}")

    for para in doc.paragraphs:
        if para.text.strip():
            paragraphs.append(para.text)

    full_text = "\n".join(paragraphs)
    if img_count > 0:
        full_text += f"\n\n[{img_count} imagem(ns) extraída(s) do DOCX: "
        full_text += ", ".join([os.path.basename(f) for f in media_files])
        full_text += "]\n"

    log.info(f"      → DOCX: {len(paragraphs)} parágrafo(s), {img_count} imagem(ns)")
    return [full_text], media_files

def extract_from_text(path, attach_dir=None):
    """Extrai texto simples e vincula anexos se informados."""
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
    if attach_dir:
        media_files = collect_attachments(attach_dir)

    log.info(f"      → Texto: {len(content)} caracteres, {len(media_files)} anexo(s)")
    return [content], media_files

def extract_content(path, attach_dir=None):
    """Roteador inteligente de extração baseado no tipo de arquivo."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        pages, media = extract_from_pdf(path)
        if attach_dir:
            extra = collect_attachments(attach_dir)
            for m in extra:
                if m not in media:
                    media.append(m)
        return pages, media
    elif ext in [".md", ".markdown"]:
        return extract_from_markdown(path, attach_dir)
    elif ext == ".docx":
        pages, media = extract_from_docx(path)
        if attach_dir:
            extra = collect_attachments(attach_dir)
            for m in extra:
                if m not in media:
                    media.append(m)
        return pages, media
    elif ext == ".json":
        return extract_from_text(path, attach_dir)
    else:
        return extract_from_text(path, attach_dir)

# ════════════════════════════════════════════
# GERAÇÃO NATIVA COM ANTIGRAVITY CLI (AGY)
# ════════════════════════════════════════════

def clean_json_response(text):
    """Remove marcações markdown e resgata o array JSON puro."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return match.group(0)
    return text

def validate_flashcards(cards):
    """Valida e normaliza a estrutura dos flashcards."""
    valid = []
    for i, card in enumerate(cards):
        if not isinstance(card, dict):
            continue
        pergunta = card.get("pergunta", "").strip()
        resposta = card.get("resposta", "").strip()
        if not pergunta or not resposta:
            continue
        valid.append({"pergunta": pergunta, "resposta": resposta})
    return valid

def call_antigravity_cli(prompt_text, model=DEFAULT_MODEL, effort=DEFAULT_EFFORT):
    """
    Executa a geração através do Antigravity CLI (agy) nativo.
    Totalmente integrado ao ambiente, sem requerer GEMINI_API_KEY do AI Studio.
    """
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
        log.error("[ERRO] Comando 'agy' não encontrado no PATH. Instale ou configure o Antigravity CLI.")
        return None
    except Exception as e:
        log.warning(f"  ⚠ Erro inesperado ao executar agy: {e}")
        return None

def chunk_content(pages, chunk_size):
    """Divide a lista de blocos de texto em lotes controlados."""
    for i in range(0, len(pages), chunk_size):
        yield pages[i:i + chunk_size]

def generate_flashcards_antigravity(pages_text, model=DEFAULT_MODEL, effort=DEFAULT_EFFORT, chunk_size=10):
    """
    Gera flashcards utilizando o motor nativo Antigravity (Gemini 3.8 Flash High).
    """
    all_cards = []
    chunks = list(chunk_content(pages_text, chunk_size))
    total_chunks = len(chunks)

    log.info(f"\n  Iniciando processamento nativo via Antigravity ({model} - esforço: {effort})...")

    for idx, chunk in enumerate(chunks):
        log.info(f"  → Lote {idx + 1}/{total_chunks} ({len(chunk)} página(s)/seção(ões))...")
        batch_text = "\n".join(chunk)
        full_prompt = f"{SYSTEM_PROMPT}\n\nMATERIAL DE ESTUDO PARA CONVERTER EM FLASHCARDS:\n{batch_text}"

        success = False
        for attempt in range(1, MAX_RETRIES + 1):
            raw_response = call_antigravity_cli(full_prompt, model=model, effort=effort)
            if not raw_response:
                time.sleep(RETRY_DELAY_SECS)
                continue

            try:
                json_str = clean_json_response(raw_response)
                parsed = json.loads(json_str)
                if isinstance(parsed, list):
                    valid = validate_flashcards(parsed)
                    all_cards.extend(valid)
                    log.info(f"     ✓ {len(valid)} flashcard(s) gerado(s) com sucesso")
                    success = True
                    break
                else:
                    log.warning(f"     ⚠ Resposta do lote {idx+1} não é uma lista JSON (tentativa {attempt})")
            except json.JSONDecodeError as e:
                log.warning(f"     ⚠ Erro ao decodificar JSON (tentativa {attempt}/{MAX_RETRIES}): {e}")
                time.sleep(RETRY_DELAY_SECS)

        if not success:
            log.error(f"     ✗ Falha no lote {idx + 1} após {MAX_RETRIES} tentativas.")

    return all_cards

# ════════════════════════════════════════════
# MONTAGEM DO PACOTE ANKI (.apkg)
# ════════════════════════════════════════════

def build_anki_deck(flashcards, media_files, deck_name, output_path):
    """Monta o pacote .apkg com mídias embutidas e CSS dark mode."""
    if genanki is None:
        log.error("[ERRO] Pacote genanki não instalado. Execute: pip install genanki")
        sys.exit(1)

    anki_model = genanki.Model(
        MODEL_ID,
        "Flashcard Architect Native Dark",
        fields=[{"name": "Pergunta"}, {"name": "Resposta"}],
        templates=[{
            "name": "Card 1",
            "qfmt": '<div class="card-front">{{Pergunta}}</div>',
            "afmt": '{{FrontSide}}<hr id="answer"><div class="card-back">{{Resposta}}</div>',
        }],
        css=ANKI_CSS
    )

    deck = genanki.Deck(DECK_ID, deck_name)
    added = 0

    for card in flashcards:
        # Gera GUID único e determinístico baseado na pergunta para evitar duplicatas em reimportações
        note = genanki.Note(
            model=anki_model,
            fields=[card["pergunta"], card["resposta"]],
            guid=genanki.guid_for(card["pergunta"])
        )
        deck.add_note(note)
        added += 1

    package = genanki.Package(deck)

    # Filtrar mídias existentes
    valid_media = []
    if media_files:
        for m in media_files:
            if os.path.exists(m) and m not in valid_media:
                valid_media.append(m)

    package.media_files = valid_media
    package.write_to_file(output_path)

    log.info(f"      → {added} card(s) empacotado(s)")
    if valid_media:
        log.info(f"      → {len(valid_media)} imagem(ns) e anexo(s) embutido(s)")

# ════════════════════════════════════════════
# PARSER DE LINHA DE COMANDO
# ════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        prog="anki_generator",
        description="Flashcard Architect — Gerador Nativo Antigravity de Decks Anki (.apkg)",
        epilog="Exemplo: python anki_generator.py --input simulado.pdf --deck \"Certificação TI\" --output cert.apkg"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Caminho do arquivo de entrada (PDF, DOCX, Markdown, TXT ou JSON pré-formatado)"
    )
    parser.add_argument(
        "--deck", "-d",
        default="Meu Baralho Antigravity",
        help="Nome do deck no Anki (padrão: 'Meu Baralho Antigravity')"
    )
    parser.add_argument(
        "--output", "-o",
        default="flashcards.apkg",
        help="Caminho do arquivo .apkg gerado (padrão: flashcards.apkg)"
    )
    parser.add_argument(
        "--attachments", "-a",
        default=None,
        help="Diretório com imagens e anexos extras para incluir no deck"
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
        help="Páginas ou seções por lote no processamento (padrão: 10)"
    )
    parser.add_argument(
        "--no-ai", "--offline",
        action="store_true",
        help="Modo offline: se o arquivo de entrada já for um JSON com [{'pergunta': '...', 'resposta': '...'}]"
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"Flashcard Architect v{VERSION} (Antigravity Native)"
    )
    return parser.parse_args()

# ════════════════════════════════════════════
# PONTO DE ENTRADA PRINCIPAL
# ════════════════════════════════════════════

def main():
    args = parse_args()

    if not os.path.exists(args.input):
        log.error(f"[ERRO] Arquivo de entrada não encontrado: {args.input}")
        sys.exit(1)

    print(f"+--------------------------------------------------+")
    print(f"|   Flashcard Architect v{VERSION} - Antigravity Native  |")
    print(f"|   Modelo: {args.model:<24} Esforco: {args.effort:<6} |")
    print(f"+--------------------------------------------------+")

    # 1. Extração de conteúdo e anexos
    print(f"\n[1/3] Processando material e coletando anexos: {args.input}")
    pages, media = extract_content(args.input, args.attachments)
    total_chars = sum(len(p) for p in pages)
    print(f"      → {len(pages)} bloco(s) | {len(media)} anexo(s)/imagem(ns) | ~{total_chars:,} caracteres")

    # 2. Obtenção dos flashcards (offline ou via Antigravity)
    cards = []
    is_json_input = args.input.lower().endswith(".json") or args.no_ai

    if is_json_input:
        print(f"\n[2/3] Carregando flashcards pré-estruturados (modo direto)...")
        try:
            raw_text = "\n".join(pages)
            cleaned = clean_json_response(raw_text)
            parsed = json.loads(cleaned)
            cards = validate_flashcards(parsed)
            print(f"      → {len(cards)} card(s) validado(s) diretamente do arquivo")
        except Exception as e:
            log.error(f"[ERRO] Falha ao processar JSON direto: {e}")
            sys.exit(1)
    else:
        print(f"\n[2/3] Gerando flashcards com Antigravity CLI ({args.model} / {args.effort})...")
        cards = generate_flashcards_antigravity(
            pages,
            model=args.model,
            effort=args.effort,
            chunk_size=args.chunk_size
        )

    if not cards:
        log.error("\n[ERRO] Nenhum flashcard foi gerado ou validado.")
        sys.exit(1)

    # 3. Empacotamento Anki .apkg
    print(f"\n[3/3] Montando pacote Anki: '{args.deck}' -> {args.output}")
    build_anki_deck(cards, media, args.deck, args.output)

    print(f"\n{'='*50}")
    print(f"  ✅ Baralho Anki gerado com sucesso!")
    print(f"  📦 Arquivo .apkg: {args.output}")
    print(f"  🃏 Total de cards: {len(cards)}")
    print(f"  🖼️  Imagens/anexos: {len(media)}")
    print(f"  🎨 Estilo: Dark Mode nativo com Active Recall")
    print(f"{'='*50}")
    print(f"\n  Para importar no Anki:")
    print(f"  Arquivo → Importar → Selecione '{args.output}'\n")

if __name__ == "__main__":
    main()
