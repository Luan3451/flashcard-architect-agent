"""
Flashcard Architect — Gerador de Decks Anki
Suporta: PDF, DOCX, TXT, Markdown
Dependências: pip install PyMuPDF genanki google-generativeai python-docx
"""

import fitz  # PyMuPDF
import genanki
import json
import os
import sys
import re
import google.generativeai as genai

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# ════════════════════════════════════════════
# CONFIGURAÇÕES — edite aqui antes de rodar
# ════════════════════════════════════════════
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "SUA_API_KEY_AQUI")
INPUT_PATH     = "meu_material.pdf"    # PDF, DOCX, TXT ou MD
DECK_NAME      = "Revisão — Flashcards"
OUTPUT_APKG    = "flashcards.apkg"
CHUNK_PAGES    = 15                    # Páginas por lote (PDFs grandes)
MEDIA_DIR      = "anki_media"

# ════════════════════════════════════════════
# SYSTEM PROMPT DO ESPECIALISTA EM FLASHCARDS
# ════════════════════════════════════════════
SYSTEM_PROMPT = """
Você é um Especialista em Aprendizagem, Organização de Conteúdo e Criação de Flashcards de Alta Retenção, com profundo conhecimento em técnicas de repetição espaçada (algoritmo FSRS do Anki), aprendizado ativo e design instrucional.

Seu único objetivo é processar materiais de estudo e transformá-los em flashcards perfeitamente estruturados.

REGRAS:
1. FRENTE (Pergunta): Enunciado claro, uma única ideia por card (princípio atômico).
   Se houver referência a imagem, inclua:
   <img src="nome.ext" style="max-width:100%; border-radius:8px; margin-top:10px;">

2. VERSO (Resposta): Resposta direta + Justificativa concisa. Promova entendimento, não memorização.
   Se houver alternativas erradas, explique brevemente por que estão incorretas.

3. FORMATAÇÃO (obrigatório, compatível com dark mode Anki):
   - Palavras-chave: <b>termo</b> ou <i>conceito</i>
   - Listas: <ul><li>item</li></ul>
   - Código/comandos: <code style="background-color:#1e1e1e; padding:2px 6px; border-radius:4px; font-family:monospace; color:#4af626;">comando</code>
   - Espaçamento: <br>

4. SAÍDA: EXCLUSIVAMENTE um array JSON válido, sem markdown, sem texto adicional.

FORMATO JSON:
[{"pergunta": "...", "resposta": "..."}]
"""

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

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text("text") + f"\n[Fim da Página {page_num + 1}]\n"

        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext   = base_image["ext"]
            image_name  = f"img_p{page_num + 1}_{img_index}.{image_ext}"
            image_path  = os.path.join(MEDIA_DIR, image_name)

            with open(image_path, "wb") as f:
                f.write(image_bytes)
            media_files.append(image_path)
            page_text += f"\n[Imagem extraída nesta página: {image_name}]\n"

        pages_text.append(page_text)

    return pages_text, media_files

def extract_from_docx(path):
    """Extrai texto de um arquivo DOCX."""
    if not DOCX_AVAILABLE:
        raise ImportError("python-docx não instalado. Execute: pip install python-docx")
    doc = DocxDocument(path)
    full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    return [full_text], []

def extract_from_text(path):
    """Extrai texto de arquivos TXT ou Markdown."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return [content], []

def extract_content(path):
    """Roteador de extração por extensão de arquivo."""
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
    print(f"[AVISO] Extensão '{ext}' não reconhecida. Tentando ler como texto...")
    return extract_from_text(path)

# ════════════════════════════════════════════
# GERAÇÃO DE FLASHCARDS COM GEMINI
# ════════════════════════════════════════════

def chunk_pages(pages, size):
    for i in range(0, len(pages), size):
        yield pages[i:i + size]

def clean_json_response(text):
    """Remove formatação markdown extra que a IA pode retornar."""
    text = re.sub(r"^```json\s*", "", text.strip())
    text = re.sub(r"^```\s*",     "", text.strip())
    text = re.sub(r"```$",         "", text.strip())
    return text.strip()

def generate_flashcards(pages_text):
    """Envia o texto em lotes para o Gemini e retorna os flashcards."""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT
    )

    all_cards = []
    chunks = list(chunk_pages(pages_text, CHUNK_PAGES))

    for i, chunk in enumerate(chunks):
        print(f"  → Lote {i + 1}/{len(chunks)} ({len(chunk)} página(s))...")
        try:
            response = model.generate_content("\n".join(chunk))
            json_str = clean_json_response(response.text)
            cards    = json.loads(json_str)
            all_cards.extend(cards)
            print(f"     ✓ {len(cards)} card(s) gerado(s).")
        except json.JSONDecodeError as e:
            print(f"     ✗ Erro JSON no lote {i + 1}: {e}")
            print(f"       Resposta bruta: {response.text[:300]}")
        except Exception as e:
            print(f"     ✗ Erro inesperado no lote {i + 1}: {e}")

    return all_cards

# ════════════════════════════════════════════
# MONTAGEM DO DECK ANKI (.apkg)
# ════════════════════════════════════════════

def build_anki_deck(flashcards, media_files):
    """Monta o pacote .apkg com os cards e mídias embutidas."""
    anki_model = genanki.Model(
        1607392319,
        "Flashcard Architect Model",
        fields=[{"name": "Pergunta"}, {"name": "Resposta"}],
        templates=[{
            "name": "Card 1",
            "qfmt": '<div class="card-front">{{Pergunta}}</div>',
            "afmt": '{{FrontSide}}<hr id="answer"><div class="card-back">{{Resposta}}</div>',
        }],
        css="""
        .card {
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 18px;
            text-align: left;
            color: #e0e0e0;
            background-color: #1e1e1e;
            padding: 20px;
            line-height: 1.6;
        }
        .card-front { font-size: 19px; }
        .card-back  { margin-top: 10px; font-size: 17px; }
        hr#answer   { border: none; border-top: 1px solid #444; margin: 15px 0; }
        b           { color: #ffffff; }
        i           { color: #a0c8ff; }
        code {
            background-color: #121212;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Consolas', 'Courier New', monospace;
            color: #4af626;
        }
        ul  { padding-left: 20px; }
        li  { margin-bottom: 4px; }
        img { max-width: 100%; border-radius: 8px; margin-top: 10px; border: 1px solid #444; }
        """
    )

    deck = genanki.Deck(2059400110, DECK_NAME)

    skipped = 0
    for card in flashcards:
        pergunta = card.get("pergunta", "").strip()
        resposta = card.get("resposta", "").strip()
        if pergunta and resposta:
            deck.add_note(genanki.Note(model=anki_model, fields=[pergunta, resposta]))
        else:
            skipped += 1

    if skipped:
        print(f"  ⚠ {skipped} card(s) ignorado(s) por estarem incompletos.")

    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(OUTPUT_APKG)

# ════════════════════════════════════════════
# PONTO DE ENTRADA
# ════════════════════════════════════════════

if __name__ == "__main__":
    if not os.path.exists(INPUT_PATH):
        print(f"[ERRO] Arquivo não encontrado: {INPUT_PATH}")
        print(f"       Verifique a variável INPUT_PATH no início do script.")
        sys.exit(1)

    if GEMINI_API_KEY in ("SUA_API_KEY_AQUI", ""):
        print("[ERRO] Configure GEMINI_API_KEY como variável de ambiente ou diretamente no script.")
        print("       Exemplo: set GEMINI_API_KEY=sua-chave-aqui  (Windows)")
        sys.exit(1)

    print(f"╔══════════════════════════════════════╗")
    print(f"║     Flashcard Architect — v1.1.0     ║")
    print(f"╚══════════════════════════════════════╝")
    print(f"\n[1/3] Extraindo conteúdo de: {INPUT_PATH}")
    pages, media = extract_content(INPUT_PATH)
    print(f"      → {len(pages)} bloco(s) | {len(media)} imagem(ns) extraída(s)")

    print(f"\n[2/3] Gerando flashcards com Gemini...")
    cards = generate_flashcards(pages)
    print(f"      → Total: {len(cards)} card(s) gerado(s)")

    if not cards:
        print("\n[AVISO] Nenhum card foi gerado. Verifique o conteúdo do documento.")
        sys.exit(1)

    print(f"\n[3/3] Montando pacote Anki...")
    build_anki_deck(cards, media)
    print(f"\n✅ Concluído!")
    print(f"   Arquivo: {OUTPUT_APKG}")
    print(f"   Importe no Anki: Arquivo → Importar → {OUTPUT_APKG}")
