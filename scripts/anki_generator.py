#!/usr/bin/env python3
"""
Flashcard Architect v2.0.0 — Gerador de Decks Anki
Transforma documentos de estudo em flashcards .apkg com imagens embutidas.

Formatos suportados: PDF, DOCX, TXT, Markdown
Dependências: pip install PyMuPDF genanki google-generativeai python-docx

Uso:
    python anki_generator.py --input material.pdf --deck "Meu Deck" --output flashcards.apkg
    python anki_generator.py --input anotacoes.docx
    python anki_generator.py --input resumo.md --chunk-size 10
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import hashlib

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import genanki
except ImportError:
    genanki = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

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

VERSION = "2.0.0"
MEDIA_DIR = "anki_media"
MAX_RETRIES = 3
RETRY_DELAY_SECS = 5

# IDs fixos do genanki (consistentes entre execuções)
MODEL_ID = 1607392319
DECK_ID  = 2059400110

SYSTEM_PROMPT = """
Você é o Flashcard Architect — um especialista em aprendizagem ativa, design instrucional e criação de flashcards de alta retenção para o Anki (algoritmo FSRS).

OBJETIVO: processar materiais de estudo e retornar flashcards estruturados.

REGRAS OBRIGATÓRIAS:
1. FRENTE: Enunciado claro, uma única ideia por card (princípio atômico).
   Se houver referência a imagem, inclua: <img src="nome.ext" style="max-width:100%; border-radius:8px; margin-top:10px;">
2. VERSO: Resposta direta + Justificativa concisa. Promova entendimento.
   Se houver alternativas erradas, explique brevemente por que estão incorretas.
3. FORMATAÇÃO (obrigatório, dark mode Anki):
   - Palavras-chave: <b>termo</b> ou <i>conceito</i>
   - Listas: <ul><li>item</li></ul>
   - Código: <code style="background-color:#1e1e1e; padding:2px 6px; border-radius:4px; font-family:monospace; color:#4af626;">comando</code>
   - Espaçamento: <br>
4. IMAGENS: Se o texto mencionar [Imagem extraída nesta página: X], OBRIGATORIAMENTE inclua <img src="X"> no card.
5. SAÍDA: EXCLUSIVAMENTE um array JSON válido, sem markdown, sem texto adicional.

FORMATO: [{"pergunta": "...", "resposta": "..."}]
""".strip()

ANKI_CSS = """
.card {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 18px;
    text-align: left;
    color: #e0e0e0;
    background-color: #1e1e1e;
    padding: 20px;
    line-height: 1.6;
}
.card-front {
    font-size: 19px;
    font-weight: 400;
}
.card-back {
    margin-top: 10px;
    font-size: 17px;
}
hr#answer {
    border: none;
    border-top: 1px solid #444;
    margin: 15px 0;
}
b { color: #ffffff; }
i { color: #a0c8ff; }
code {
    background-color: #121212;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'Consolas', 'Courier New', monospace;
    color: #4af626;
    font-size: 0.95em;
}
pre {
    background-color: #121212;
    padding: 10px;
    border-radius: 6px;
    overflow-x: auto;
}
ul { padding-left: 20px; }
li { margin-bottom: 4px; }
img {
    max-width: 100%;
    border-radius: 8px;
    margin-top: 10px;
    border: 1px solid #444;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 10px 0;
}
th, td {
    border: 1px solid #444;
    padding: 6px 10px;
    text-align: left;
}
th {
    background-color: #2a2a2a;
    color: #4af626;
}
""".strip()

# ════════════════════════════════════════════
# VALIDAÇÃO DE DEPENDÊNCIAS
# ════════════════════════════════════════════

def check_dependencies():
    """Verifica se todas as dependências necessárias estão instaladas."""
    missing = []
    if fitz is None:
        missing.append("PyMuPDF")
    if genanki is None:
        missing.append("genanki")
    if genai is None:
        missing.append("google-generativeai")
    if missing:
        log.error(f"[ERRO] Dependências ausentes: {', '.join(missing)}")
        log.error(f"       Execute: pip install {' '.join(missing)}")
        sys.exit(1)

# ════════════════════════════════════════════
# EXTRAÇÃO DE CONTEÚDO
# ════════════════════════════════════════════

def ensure_media_dir():
    os.makedirs(MEDIA_DIR, exist_ok=True)

def extract_from_pdf(path):
    """Extrai texto e imagens de um PDF, página a página."""
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

                # Ignora imagens muito pequenas (ícones, artefatos)
                if len(image_bytes) < 1024:
                    continue

                image_name = f"img_p{page_num + 1}_{img_index}.{image_ext}"
                image_path = os.path.join(MEDIA_DIR, image_name)

                with open(image_path, "wb") as f:
                    f.write(image_bytes)
                media_files.append(image_path)
                img_count += 1
                page_text += f"\n[Imagem extraída nesta página: {image_name}]\n"
            except Exception as e:
                log.warning(f"  ⚠ Erro ao extrair imagem na pág. {page_num + 1}: {e}")

        pages_text.append(page_text)

    log.info(f"      → PDF: {len(doc)} página(s), {img_count} imagem(ns) extraída(s)")
    return pages_text, media_files

def extract_from_docx(path):
    """Extrai texto e imagens inline de um arquivo DOCX."""
    if not DOCX_AVAILABLE:
        log.error("[ERRO] python-docx não instalado. Execute: pip install python-docx")
        sys.exit(1)

    ensure_media_dir()
    doc = DocxDocument(path)
    media_files = []
    paragraphs = []

    # Extrair imagens embutidas do DOCX
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

def extract_from_text(path):
    """Extrai texto de arquivos TXT ou Markdown."""
    encodings = ["utf-8", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                content = f.read()
            log.info(f"      → Texto: {len(content)} caracteres (encoding: {enc})")
            return [content], []
        except UnicodeDecodeError:
            continue
    log.error(f"[ERRO] Não foi possível decodificar o arquivo: {path}")
    sys.exit(1)

def extract_content(path):
    """Roteador de extração baseado na extensão do arquivo."""
    ext = os.path.splitext(path)[1].lower()
    extractors = {
        ".pdf":      extract_from_pdf,
        ".docx":     extract_from_docx,
        ".txt":      extract_from_text,
        ".md":       extract_from_text,
        ".markdown": extract_from_text,
    }
    extractor = extractors.get(ext)
    if extractor:
        return extractor(path)
    log.warning(f"  ⚠ Extensão '{ext}' não reconhecida. Tentando como texto...")
    return extract_from_text(path)

# ════════════════════════════════════════════
# GERAÇÃO DE FLASHCARDS COM GEMINI
# ════════════════════════════════════════════

def chunk_pages(pages, size):
    """Divide a lista de páginas em lotes."""
    for i in range(0, len(pages), size):
        yield pages[i:i + size]

def clean_json_response(text):
    """Remove formatação markdown ou texto extra que a IA pode retornar."""
    text = text.strip()
    # Remove blocos markdown
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    # Tenta encontrar o array JSON no texto
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return match.group(0)
    return text

def validate_flashcards(cards):
    """Valida e filtra flashcards inválidos."""
    valid = []
    for i, card in enumerate(cards):
        if not isinstance(card, dict):
            log.warning(f"     ⚠ Card {i+1} ignorado: não é um objeto JSON")
            continue
        pergunta = card.get("pergunta", "").strip()
        resposta = card.get("resposta", "").strip()
        if not pergunta:
            log.warning(f"     ⚠ Card {i+1} ignorado: pergunta vazia")
            continue
        if not resposta:
            log.warning(f"     ⚠ Card {i+1} ignorado: resposta vazia")
            continue
        valid.append({"pergunta": pergunta, "resposta": resposta})
    return valid

def generate_flashcards(pages_text, api_key, chunk_size):
    """Envia o texto em lotes para o Gemini e retorna flashcards validados."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT
    )

    all_cards = []
    chunks = list(chunk_pages(pages_text, chunk_size))
    total_chunks = len(chunks)

    for i, chunk in enumerate(chunks):
        log.info(f"  → Lote {i + 1}/{total_chunks} ({len(chunk)} bloco(s))...")

        batch_text = "\n".join(chunk)
        success = False

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = model.generate_content(batch_text)

                if not response.text:
                    log.warning(f"     ⚠ Resposta vazia no lote {i+1}, tentativa {attempt}/{MAX_RETRIES}")
                    time.sleep(RETRY_DELAY_SECS)
                    continue

                json_str = clean_json_response(response.text)
                cards = json.loads(json_str)

                if not isinstance(cards, list):
                    log.warning(f"     ⚠ Resposta não é uma lista JSON, tentativa {attempt}/{MAX_RETRIES}")
                    time.sleep(RETRY_DELAY_SECS)
                    continue

                valid_cards = validate_flashcards(cards)
                all_cards.extend(valid_cards)
                log.info(f"     ✓ {len(valid_cards)} card(s) válido(s)")
                success = True
                break

            except json.JSONDecodeError as e:
                log.warning(f"     ⚠ Erro JSON (tentativa {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    log.info(f"       Aguardando {RETRY_DELAY_SECS}s antes de tentar novamente...")
                    time.sleep(RETRY_DELAY_SECS)
            except Exception as e:
                log.warning(f"     ⚠ Erro (tentativa {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_SECS)

        if not success:
            log.error(f"     ✗ Lote {i+1} falhou após {MAX_RETRIES} tentativas.")

    return all_cards

# ════════════════════════════════════════════
# MONTAGEM DO DECK ANKI (.apkg)
# ════════════════════════════════════════════

def build_anki_deck(flashcards, media_files, deck_name, output_path):
    """Monta o pacote .apkg com os cards e mídias embutidas."""
    anki_model = genanki.Model(
        MODEL_ID,
        "Flashcard Architect Model",
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
        note = genanki.Note(
            model=anki_model,
            fields=[card["pergunta"], card["resposta"]],
            guid=genanki.guid_for(card["pergunta"])
        )
        deck.add_note(note)
        added += 1

    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(output_path)

    log.info(f"      → {added} card(s) empacotado(s)")
    if media_files:
        log.info(f"      → {len(media_files)} imagem(ns) embutida(s)")

# ════════════════════════════════════════════
# CLI (argparse)
# ════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        prog="anki_generator",
        description="Flashcard Architect — Gera decks Anki (.apkg) a partir de documentos de estudo.",
        epilog="Exemplo: python anki_generator.py --input simulado.pdf --deck \"Revisão\" --output revisao.apkg"
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Caminho do arquivo de entrada (PDF, DOCX, TXT, MD)"
    )
    parser.add_argument(
        "--deck", "-d",
        default="Flashcards",
        help="Nome do deck no Anki (padrão: Flashcards)"
    )
    parser.add_argument(
        "--output", "-o",
        default="flashcards.apkg",
        help="Caminho do arquivo .apkg de saída (padrão: flashcards.apkg)"
    )
    parser.add_argument(
        "--chunk-size", "-c",
        type=int,
        default=15,
        help="Número de páginas por lote enviado ao Gemini (padrão: 15)"
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"Flashcard Architect v{VERSION}"
    )
    return parser.parse_args()

# ════════════════════════════════════════════
# PONTO DE ENTRADA
# ════════════════════════════════════════════

def main():
    args = parse_args()
    check_dependencies()

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        log.error("[ERRO] GEMINI_API_KEY não configurada.")
        log.error("       Windows:    set GEMINI_API_KEY=sua-chave-aqui")
        log.error("       Linux/Mac:  export GEMINI_API_KEY=\"sua-chave-aqui\"")
        log.error("       Obtenha em: https://aistudio.google.com/app/apikey")
        sys.exit(1)

    if not os.path.exists(args.input):
        log.error(f"[ERRO] Arquivo não encontrado: {args.input}")
        sys.exit(1)

    print(f"╔══════════════════════════════════════╗")
    print(f"║   Flashcard Architect — v{VERSION}     ║")
    print(f"╚══════════════════════════════════════╝")

    # 1. Extração
    print(f"\n[1/3] Extraindo conteúdo de: {args.input}")
    pages, media = extract_content(args.input)
    total_chars = sum(len(p) for p in pages)
    print(f"      → {len(pages)} bloco(s) | {len(media)} imagem(ns) | ~{total_chars:,} caracteres")

    if total_chars < 50:
        log.error("[ERRO] Conteúdo extraído muito curto. Verifique se o arquivo está correto.")
        sys.exit(1)

    # 2. Geração
    print(f"\n[2/3] Gerando flashcards com Gemini (lotes de {args.chunk_size} pág.)...")
    cards = generate_flashcards(pages, api_key, args.chunk_size)
    print(f"      → Total: {len(cards)} card(s) gerado(s)")

    if not cards:
        log.error("\n[ERRO] Nenhum card foi gerado. Verifique o conteúdo do documento.")
        log.error("       Dica: tente reduzir --chunk-size para 5 ou 10.")
        sys.exit(1)

    # 3. Empacotamento
    print(f"\n[3/3] Montando pacote Anki: {args.deck}")
    build_anki_deck(cards, media, args.deck, args.output)

    print(f"\n{'='*42}")
    print(f"  ✅ Concluído com sucesso!")
    print(f"  📦 Arquivo: {args.output}")
    print(f"  🃏 Cards:   {len(cards)}")
    print(f"  🖼️  Imagens: {len(media)}")
    print(f"{'='*42}")
    print(f"\n  Importe no Anki:")
    print(f"  Arquivo → Importar → {args.output}")

if __name__ == "__main__":
    main()
