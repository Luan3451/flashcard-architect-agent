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
GEMINI_API_KEY = "SUA_API_KEY_AQUI"
INPUT_PATH     = "meu_material.pdf"   # PDF, DOCX, TXT ou MD
DECK_NAME      = "Revisão — Flashcards"
OUTPUT_APKG    = "flashcards.apkg"
CHUNK_PAGES    = 15                   # Número de páginas por lote (para PDFs grandes)
MEDIA_DIR      = "anki_media"

# ════════════════════════════════════════════
# SYSTEM PROMPT DO AGENTE ESPECIALISTA
# ════════════════════════════════════════════
SYSTEM_PROMPT = """
Você é um Especialista em Aprendizagem, Organização de Conteúdo e Criação de Flashcards de Alta Retenção, com profundo conhecimento em técnicas de repetição espaçada (algoritmo FSRS do Anki), aprendizado ativo e design instrucional.

Seu único objetivo é processar materiais de estudo e transformá-los em flashcards perfeitamente estruturados.

REGRAS:
1. FRENTE (Pergunta): Enunciado claro, uma única ideia por card. Se houver referência a imagem, inclua: <img src="nome.ext" style="max-width:100%; border-radius:8px; margin-top:10px;">
2. VERSO (Resposta): Resposta direta + Justificativa concisa. Promova entendimento, não memorização.
3. FORMATAÇÃO: Use HTML/CSS compatível com dark mode Anki. Palavras-chave em <b>, código em <code style="background-color:#1e1e1e; padding:2px 6px; border-radius:4px; font-family:monospace; color:#4af626;">, listas com <ul><li>.
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
    """Extrai texto e imagens de um PDF."""
    ensure_media_dir()
    doc = fitz.open(path)
    pages_text = []
    media_files = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text("text") + f"\n[Fim da Página {page_num + 1}]\n"

        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            image_name = f"img_p{page_num + 1}_{img_index}.{image_ext}"
            image_path = os.path.join(MEDIA_DIR, image_name)

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
    full_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
    return [full_text], []

def extract_from_text(path):
    """Extrai texto de arquivos TXT ou Markdown."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return [content], []

def extract_content(path):
    """Roteador de extração baseado na extensão do arquivo."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return extract_from_pdf(path)
    elif ext in (".docx",):
        return extract_from_docx(path)
    elif ext in (".txt", ".md", ".markdown"):
        return extract_from_text(path)
    else:
        print(f"[AVISO] Extensão '{ext}' não reconhecida. Tentando ler como texto...")
        return extract_from_text(path)

# ════════════════════════════════════════════
# GERAÇÃO DE FLASHCARDS COM GEMINI
# ════════════════════════════════════════════

def chunk_pages(pages, size):
    """Divide a lista de páginas em lotes."""
    for i in range(0, len(pages), size):
        yield pages[i:i + size]

def clean_json_response(text):
    """Remove formatação markdown extra que a IA pode retornar."""
    text = re.sub(r"^```json\s*", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    return text.strip()

def generate_flashcards(pages_text):
    """Envia o texto para o Gemini e recebe os flashcards em JSON."""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT
    )

    all_cards = []
    chunks = list(chunk_pages(pages_text, CHUNK_PAGES))
    total = len(chunks)

    for i, chunk in enumerate(chunks):
        print(f"  → Processando lote {i + 1}/{total}...")
        batch_text = "\n".join(chunk)

        try:
            response = model.generate_content(batch_text)
            json_string = clean_json_response(response.text)
            cards = json.loads(json_string)
            all_cards.extend(cards)
            print(f"     ✓ {len(cards)} cards gerados neste lote.")
        except json.JSONDecodeError as e:
            print(f"     ✗ Erro ao decodificar JSON no lote {i + 1}: {e}")
            print(f"     Resposta bruta: {response.text[:300]}")
        except Exception as e:
            print(f"     ✗ Erro inesperado no lote {i + 1}: {e}")

    return all_cards

# ════════════════════════════════════════════
# MONTAGEM DO DECK ANKI
# ════════════════════════════════════════════

def build_anki_deck(flashcards, media_files):
    """Monta o pacote .apkg com os cards e as mídias."""
    model_id = 1607392319
    deck_id  = 2059400110

    anki_model = genanki.Model(
        model_id,
        "Flashcard Architect Model",
        fields=[{"name": "Pergunta"}, {"name": "Resposta"}],
        templates=[{
            "name": "Card 1",
            "qfmt": """
                <div class="card-front">{{Pergunta}}</div>
            """,
            "afmt": """
                {{FrontSide}}
                <hr id="answer">
                <div class="card-back">{{Resposta}}</div>
            """,
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
        }
        ul { padding-left: 20px; }
        li { margin-bottom: 4px; }
        img {
            max-width: 100%;
            border-radius: 8px;
            margin-top: 10px;
            border: 1px solid #444;
        }
        """
    )

    deck = genanki.Deck(deck_id, DECK_NAME)

    for card in flashcards:
        pergunta = card.get("pergunta", "").strip()
        resposta = card.get("resposta", "").strip()
        if pergunta and resposta:
            note = genanki.Note(model=anki_model, fields=[pergunta, resposta])
            deck.add_note(note)

    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(OUTPUT_APKG)

# ════════════════════════════════════════════
# PONTO DE ENTRADA
# ════════════════════════════════════════════

if __name__ == "__main__":
    if not os.path.exists(INPUT_PATH):
        print(f"[ERRO] Arquivo não encontrado: {INPUT_PATH}")
        sys.exit(1)

    if GEMINI_API_KEY == "SUA_API_KEY_AQUI":
        print("[ERRO] Configure sua GEMINI_API_KEY no arquivo antes de executar.")
        sys.exit(1)

    print(f"[1/3] Extraindo conteúdo de: {INPUT_PATH}")
    pages, media = extract_content(INPUT_PATH)
    print(f"      → {len(pages)} bloco(s) extraído(s), {len(media)} imagem(ns) encontrada(s).")

    print(f"\n[2/3] Gerando flashcards com Gemini...")
    cards = generate_flashcards(pages)
    print(f"      → Total de cards gerados: {len(cards)}")

    print(f"\n[3/3] Montando pacote Anki...")
    build_anki_deck(cards, media)
    print(f"\n✅ Concluído! Arquivo salvo em: {OUTPUT_APKG}")
    print(f"   Importe no Anki: Arquivo → Importar → {OUTPUT_APKG}")
