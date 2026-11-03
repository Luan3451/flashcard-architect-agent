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
#     "rapidocr-onnxruntime>=1.2.0",
# ]
# ///
# -*- coding: utf-8 -*-
"""
anki_generator.py — v3.2.0 (Agensi.io Commercial & Multi-Agent Edition)
Automated Anki Flashcard Engine with Y0 Spatial Diagram Anchoring,
Practice Exam Audit Filtering, Universal Multi-Agent Support, and Native FSRS Optimization.
Compatible with Claude Code, Cursor, Copilot, Windsurf, and Google Antigravity.
"""

import argparse
from datetime import datetime
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
import warnings

# Suppress PyMuPDF migration warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Force UTF-8 encoding on Windows to prevent charmap encoding errors
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# 1. OPTIONAL DEPENDENCY BOOTSTRAPPER & IMPORTS
# ---------------------------------------------------------------------------
REQUIRED_PACKAGES = {
    "genanki": "genanki>=0.13.0",
    "fitz": "pymupdf>=1.23.0",
    "docx": "python-docx>=1.1.0",
    "PIL": "Pillow>=10.0.0",
    "pydantic": "pydantic>=2.7.0",
    "json_repair": "json-repair>=0.25.0",
}

def check_or_install_dependencies(auto_install: bool = False) -> None:
    """Verifies dependencies. If auto_install is True, installs missing packages without --system."""
    missing = [
        pkg for mod, pkg in REQUIRED_PACKAGES.items()
        if importlib.util.find_spec(mod) is None
    ]
    if missing:
        if auto_install:
            print(f"[Auto-Install] Installing missing dependencies: {', '.join(missing)}...")
            uv_bin = shutil.which("uv")
            cmd = (
                [uv_bin, "pip", "install", "--quiet", *missing]
                if uv_bin
                else [sys.executable, "-m", "pip", "install", "--quiet", *missing]
            )
            try:
                subprocess.check_call(cmd)
                print("[Auto-Install] Dependencies successfully installed.")
            except Exception as e:
                print(f"[Auto-Install] Warning during package installation: {e}")
        else:
            print(f"\n[ERROR] Missing required dependencies: {', '.join(missing)}")
            print("Please install them using pip:")
            print(f"  pip install {' '.join(missing)}")
            print("Or run this script with '--auto-install' to install them automatically.\n")
            sys.exit(1)

    # Auto-discover 'agy' binary in PATH if available
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

# Lazy-loaded module references
try:
    import genanki
except ImportError:
    genanki = None

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
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

# System Constants
VERSION = "3.2.0"
MEDIA_DIR = "anki_media"
MAX_RETRIES = 3
RETRY_DELAY_SECS = 4
DEFAULT_MODEL = "gemini-3.8-flash-high"
DEFAULT_EFFORT = "high"

MODEL_BASIC_ID = 1607392319
MODEL_CLOZE_ID = 1607392320

# ---------------------------------------------------------------------------
# 2. DETERMINISTIC DECK ID GENERATOR
# ---------------------------------------------------------------------------
def get_deck_id(deck_name: str) -> int:
    """Generates a positive 31-bit integer deterministic Deck ID from the deck name."""
    digest = hashlib.sha256(deck_name.strip().lower().encode("utf-8")).hexdigest()
    return int(digest[:8], 16) & 0x7FFFFFFF

# ---------------------------------------------------------------------------
# 3. PROMPT MATRIX & LOCALIZATION STRATEGIES
# ---------------------------------------------------------------------------
MODE_INSTRUCTIONS = {
    "curated": (
        "CURATION & HIGH-YIELD MODE (80/20):\n"
        "- Filter out irrelevant introductory text, lengthy background details, or redundant examples.\n"
        "- Prioritize high-yield exam concepts, key definitions, core architectures, essential commands, and critical distinctions.\n"
        "- Synthesize into atomic, direct, and self-contained questions."
    ),
    "strict": (
        "STRICT SOURCE FIDELITY MODE (EXAMS / STANDARDS / CERTIFICATIONS):\n"
        "- Do NOT omit topics and do NOT alter the technical meaning or exact phrasing of the source text.\n"
        "- When processing practice exam questions or scenarios, preserve the question prompt, case scenario, and technical terms verbatim on the FRONT of the card.\n"
        "- On the BACK, provide the exact correct answer followed by a rigorous technical rationale."
    ),
    "exam": (
        "ERROR AUDIT & EXAM TRAPS MODE:\n"
        "- Analyze each question or topic by identifying common pitfalls, distractor options, and misconception traps.\n"
        "- Create diagnostic cards that directly address why incorrect options are false (e.g., 'In context X, why is statement Y invalid?').\n"
        "- Explain the exact root cause of the error on the back and state the correct configuration or standard."
    ),
}

DENSITY_INSTRUCTIONS = {
    "essential": "ESSENTIAL DENSITY: Generate only critical core flashcards (1 to 2 cards per section/page).",
    "high": "EXHAUSTIVE DENSITY: Extract maximum atomic flashcards covering every nuance, command, table, exception, and technical note (3 to 6 cards per section/page).",
}

LANG_INSTRUCTIONS = {
    "en": (
        "LANGUAGE RULE (ENGLISH):\n"
        "- Generate all flashcards (front prompt, back answer, and technical rationale) entirely in professional technical English."
    ),
    "keep": (
        "BILINGUAL / SOURCE-PRESERVATION RULE (KEEP):\n"
        "- Preserve 100% of the original question prompts, answer choices, CLI outputs, code snippets, and exam commands in the original exam language (e.g., English for Cisco, AWS, CompTIA).\n"
        "- The FRONT must maintain the authenticity of the test item.\n"
        "- The BACK should provide the direct answer and a comprehensive technical explanation in Portuguese, accurately correlating the technical terms."
    ),
    "pt": (
        "LANGUAGE RULE (PORTUGUESE):\n"
        "- Translate questions, prompts, and concepts into formal Portuguese, keeping well-established technical terms and commands in their standard form."
    ),
}

FILTER_INSTRUCTIONS = {
    "all": (
        "QUESTION FILTER (ALL):\n"
        "- Process all questions and topics from the material.\n"
        "- If a question contains status markings (wrong/incorrect or correct/passed), apply the corresponding tag: 'status::wrong' for errors or 'status::correct' for correct questions."
    ),
    "wrong": (
        "ERROR-FOCUSED FILTER (INCORRECT ONLY):\n"
        "- Prioritize questions identified as incorrect/failed (status::wrong) from the practice exam.\n"
        "- Create high-yield reinforcement flashcards with in-depth technical rationales explaining why the chosen option was wrong and solidifying the correct concept.\n"
        "- Mandatory tag: 'status::wrong' on each generated card."
    ),
    "correct": (
        "MASTERY FILTER (CORRECT ONLY):\n"
        "- Process questions identified as passed/correct to consolidate and reinforce mastered topics.\n"
        "- Mandatory tag: 'status::correct' on each generated card."
    ),
}

def build_master_prompt(
    mode: str,
    density: str,
    use_media: bool,
    card_style: str,
    lang: str = "en",
    filter_mode: str = "all"
) -> str:
    media_rule = (
        "4. IMAGE & DIAGRAM MANAGEMENT (SPATIAL Y0 ANCHORING ACTIVE):\n"
        "   - Whenever the source text marks '[Image: ag_xxxx.webp]' or '[Imagem extraída: ag_xxxx.webp]', "
        "it is geometrically anchored directly below the question prompt or concept it illustrates.\n"
        "   - Embed it into the corresponding card using:\n"
        "     <br><img src=\"ag_xxxx.webp\">\n"
        "   - Place on the FRONT if it is a topology, network diagram, UI screenshot, or question prompt visual; "
        "place on the BACK if it is an explanatory resolution diagram."
        if use_media
        else "4. TEXT-ONLY TURBO MODE:\n"
             "   - Ignore external visual references and do NOT include <img> tags."
    )

    cloze_rule = (
        "- For exact commands, port numbers, parameters, or short lists, format cloze deletions ({{c1::term}}) in the question prompt."
        if card_style == "hybrid"
        else "- Formulate all notes strictly as Direct Question (front) and Answer + Rationale (back)."
    )

    lang_rule = LANG_INSTRUCTIONS.get(lang, LANG_INSTRUCTIONS["en"])
    filter_rule = FILTER_INSTRUCTIONS.get(filter_mode, FILTER_INSTRUCTIONS["all"])

    return f"""You are the Flashcard Architect — an expert cognitive learning engineer and Anki FSRS optimization specialist.

{MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS['curated'])}
{DENSITY_INSTRUCTIONS.get(density, DENSITY_INSTRUCTIONS['high'])}
{lang_rule}
{filter_rule}
{cloze_rule}

MANDATORY CARD GENERATION RULES:
1. FRONT (Question): Clear, objective, self-contained prompt (no dangling pronouns like 'this diagram' without context). Each card must test exactly ONE mental association.
   - When the text includes a header like '[Page X | Question Y (Global #Z)]', preserve it as an autonomous context anchor.
2. BACK (Answer): Direct answer prominently styled inside <span class="ans"><b>Direct Answer</b></span> followed by <br><br><i>Rationale:</i> with a concise, rigorous, cause-and-effect technical explanation.
3. PERMITTED HTML TAGS (DO NOT USE INLINE style=""): <b>term</b>, <i>concept</i>, <code>command/port</code>, <ul><li>item</li></ul>, <br>.
{media_rule}
5. MANDATORY METADATA:
   - "concept_id": stable snake_case identifier (e.g., "ccna_ospf_dr_bdr_priority_p12_q1").
   - "tags": array of snake_case tags (e.g., ["networking", "ospf", "status::wrong"]).
   - "suggested_deck": hierarchical taxonomy in "Category::Subcategory::Topic" format.

6. EXCLUSIVE OUTPUT: Return ONLY a raw JSON array (no ```json code fences, no introductory or concluding chatter):
[
  {{
    "concept_id": "ccna_ospf_dr_bdr_priority_p12_q1",
    "question": "[Page 12 | Question 1 (Global #1)] Which OSPF router priority value prevents a router from participating in the DR/BDR election?<br><img src=\\"ag_3a8f12c9b4e1.webp\\">",
    "answer": "<span class=\\"ans\\"><b>Priority value of 0.</b></span><br><br><i>Rationale:</i> In OSPF, a router configured with an interface priority of <code>0</code> (via <code>ip ospf priority 0</code>) becomes permanently a <i>DROTHER</i> and is ineligible to become a <i>DR</i> or <i>BDR</i>.",
    "tags": ["networking", "ospf", "status::wrong"],
    "suggested_deck": "Certifications::Cisco::CCNA_200_301"
  }}
]
"""

# ---------------------------------------------------------------------------
# 4. NATIVE DARK MODE CSS STYLESHEET
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

/* Maximum specificity for neon green key answer even with nested bold tags */
.ans, .ans b, .ans strong {
    color: #4af626 !important;
    font-weight: 700;
}

.cloze {
    font-weight: 700;
    color: #4af626 !important;
}

.justificativa, .rationale {
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
# 5. EXTRACTION PIPELINE WITH Y0 GEOMETRIC ANCHORING & STATUS DETECTION
# ---------------------------------------------------------------------------
def ensure_media_dir() -> Path:
    p = Path(MEDIA_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p

def save_normalized_image(img_bytes: bytes, min_dim: int = 50) -> str | None:
    """Filters noise/logos, converts to WebP, and names using content SHA-256 hash."""
    if len(img_bytes) < 1800:
        return None

    try:
        if PIL_AVAILABLE:
            with Image.open(BytesIO(img_bytes)) as im:
                w, h = im.size
                if w < min_dim or h < min_dim:
                    return None
                # Filter out linear decorative banners or spacers
                if (w / max(h, 1)) > 14 or (h / max(w, 1)) > 14:
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
        log.debug(f"Notice during image normalization: {e}")
        return None

def detect_question_status(text: str) -> str:
    """Detects whether a question or block is marked as incorrect/wrong or correct/passed."""
    lower = text.lower()
    wrong_patterns = [
        r"\b(?:incorrect|wrong|failed|errou|incorreta|invalida)\b",
        r"your\s+answer.*(?:incorrect|wrong)",
        r"status\s*:\s*(?:incorrect|failed)",
        r"resposta\s+(?:incorreta|errada)",
        r"[❌✗✖]",
    ]
    for pat in wrong_patterns:
        if re.search(pat, lower):
            return "wrong"

    correct_patterns = [
        r"\b(?:correct|passed|acertou|correta)\b",
        r"your\s+answer.*(?:correct|right)",
        r"status\s*:\s*(?:correct|passed)",
        r"resposta\s+correta",
        r"[✅✔✓]",
    ]
    for pat in correct_patterns:
        if re.search(pat, lower):
            return "correct"

    return "unspecified"

def extract_pdf_content(
    pdf_path: str,
    use_media: bool,
    filter_mode: str = "all"
) -> tuple[list[str], list[str], dict]:
    """
    Extracts PDF content using Spatial Geometric Anchoring by Y-coordinate (y0).
    Aligns diagrams and topologies directly between prompt and options,
    injects sequential global indexing [Page X | Question Y (Global #Z)],
    and tracks comprehensive audit statistics.
    """
    if fitz is None:
        log.error("[ERROR] PyMuPDF is not installed. Run: pip install pymupdf")
        sys.exit(1)

    doc = fitz.open(pdf_path)
    pages_content = []
    media_files = []
    seen_hashes = set()

    stats = {
        "total_pages": len(doc),
        "total_questions_detected": 0,
        "wrong_questions": 0,
        "correct_questions": 0,
        "unspecified_questions": 0,
        "diagrams_mapped": 0,
    }

    global_question_counter = 0
    question_regex = re.compile(
        r"(?:^|\n)\s*(?:Question|Questão|Q\.|Q)\s*(\d+)[\s:\.]|(?:^|\n)\s*(\d{1,3})[\.\)]\s+",
        re.IGNORECASE
    )

    for page_idx, page in enumerate(doc):
        page_num = page_idx + 1
        page_elements = []  # List of dicts: {"y0": float, "type": "text"|"image", "content": str}

        # 1. Collect native text blocks with bounding boxes
        text_blocks = page.get_text("blocks")
        for b in text_blocks:
            # b: (x0, y0, x1, y1, text, block_no, block_type)
            if b[6] == 0:  # Type 0 = Text
                b_text = b[4].strip()
                if b_text:
                    page_elements.append({
                        "y0": b[1],
                        "type": "text",
                        "content": b_text
                    })

        # Transparent offline OCR for scanned pages if text is sparse
        raw_page_text = " ".join([elem["content"] for elem in page_elements if elem["type"] == "text"])
        if len(raw_page_text) < 40 and RAPID_OCR_AVAILABLE:
            try:
                pix = page.get_pixmap(dpi=200)
                ocr_engine = RapidOCR()
                result, _ = ocr_engine(pix.tobytes("png"))
                if result:
                    ocr_text = "\n".join([line[1] for line in result])
                    page_elements.append({
                        "y0": 0.0,
                        "type": "text",
                        "content": f"[OCR Text]\n{ocr_text}"
                    })
                    log.info(f"      [Offline OCR] Extracted {len(ocr_text)} characters on page {page_num}")
            except Exception:
                pass

        # 2. Collect images with physical Y-coordinates on the page
        if use_media:
            # Bitmaps via XRef
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

                        rects = page.get_image_rects(xref)
                        img_y0 = rects[0].y0 if rects else 0.0

                        if fname not in seen_hashes:
                            seen_hashes.add(fname)
                            stats["diagrams_mapped"] += 1
                            page_elements.append({
                                "y0": img_y0,
                                "type": "image",
                                "content": f"[Image: {fname}]"
                            })
                except Exception:
                    pass

            # Vector drawings & clustered topologies via cluster_drawings
            try:
                for rect in page.cluster_drawings():
                    if rect.width >= 90 and rect.height >= 70:
                        pix = page.get_pixmap(clip=rect, dpi=200)
                        vname = save_normalized_image(pix.tobytes("png"))
                        if vname:
                            vpath = os.path.join(MEDIA_DIR, vname)
                            if vpath not in media_files:
                                media_files.append(vpath)
                            if vname not in seen_hashes:
                                seen_hashes.add(vname)
                                stats["diagrams_mapped"] += 1
                                page_elements.append({
                                    "y0": rect.y0,
                                    "type": "image",
                                    "content": f"[Image: {vname}]"
                                })
            except Exception:
                pass

        # 3. Rigorous Spatial Sorting by Y0 Coordinate (Top-to-Bottom)
        page_elements.sort(key=lambda elem: (round(elem["y0"], 1), elem["type"] == "text"))

        # 4. Format page block with global indexing and status detection
        page_lines = []
        for elem in page_elements:
            content = elem["content"]
            if elem["type"] == "text":
                # Detect new question and inject canonical prefix [Page X | Question Y (Global #Z)]
                m_q = question_regex.search(content)
                if m_q:
                    global_question_counter += 1
                    stats["total_questions_detected"] += 1
                    q_num = m_q.group(1) or m_q.group(2) or str(global_question_counter)
                    header = f"\n### [Page {page_num} | Question {q_num} (Global #{global_question_counter})]"
                    content = question_regex.sub(f"{header}\n", content, count=1)

                # Identify practice exam status
                st = detect_question_status(content)
                if st == "wrong":
                    stats["wrong_questions"] += 1
                    content = f"[STATUS: INCORRECT / WRONG]\n{content}"
                elif st == "correct":
                    stats["correct_questions"] += 1
                    content = f"[STATUS: CORRECT]\n{content}"
                else:
                    if m_q:
                        stats["unspecified_questions"] += 1

            page_lines.append(content)

        formatted_page = f"--- PAGE {page_num} ---\n" + "\n\n".join(page_lines)
        pages_content.append(formatted_page)

    mode_label = f"{len(media_files)} anchored diagram(s)" if use_media else "Turbo Mode (Text-Only)"
    log.info(f"      → PDF: {len(doc)} page(s) | {stats['total_questions_detected']} question(s) detected | {mode_label}.")
    return pages_content, media_files, stats

def extract_docx_content(docx_path: str, use_media: bool) -> tuple[list[str], list[str], dict]:
    """Extracts text and embedded images from DOCX documents."""
    if not DOCX_AVAILABLE:
        log.error("[ERROR] python-docx is not installed. Run: pip install python-docx")
        sys.exit(1)

    doc = DocxDocument(docx_path)
    media_files = []
    paragraphs_text = []
    stats = {
        "total_pages": 1,
        "total_questions_detected": 0,
        "wrong_questions": 0,
        "correct_questions": 0,
        "unspecified_questions": 0,
        "diagrams_mapped": 0,
    }

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
                                stats["diagrams_mapped"] += 1
                            p_text += f"\n[Image: {fname}]\n"
            except Exception:
                pass

        if p_text:
            st = detect_question_status(p_text)
            if st == "wrong":
                stats["wrong_questions"] += 1
            elif st == "correct":
                stats["correct_questions"] += 1
            paragraphs_text.append(p_text)

    full_text = "\n\n".join(paragraphs_text)
    mode_label = f"{len(media_files)} image(s)" if use_media else "Turbo Mode"
    log.info(f"      → DOCX: {len(paragraphs_text)} paragraph(s) | {mode_label}.")
    return [full_text], media_files, stats

def extract_markdown_content(
    md_path: str,
    use_media: bool,
    attach_dir: str | None = None
) -> tuple[list[str], list[str], dict]:
    """Extracts Markdown content resolving local visual attachments."""
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
    stats = {
        "total_pages": 1,
        "total_questions_detected": 0,
        "wrong_questions": 0,
        "correct_questions": 0,
        "unspecified_questions": 0,
        "diagrams_mapped": 0,
    }

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
                            stats["diagrams_mapped"] += 1
                        content = content.replace(img_ref, norm)
                except Exception:
                    pass

    mode_label = f"{len(media_files)} image(s)" if use_media else "Turbo Mode"
    log.info(f"      → Markdown: {len(content):,} character(s) | {mode_label}.")
    return [content], media_files, stats

def extract_content(
    path: str,
    use_media: bool,
    attach_dir: str | None = None,
    filter_mode: str = "all"
) -> tuple[list[str], list[str], dict]:
    """Universal intelligent content router with lazy media extraction and statistics tracking."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return extract_pdf_content(path, use_media, filter_mode=filter_mode)
    elif ext in [".md", ".markdown"]:
        return extract_markdown_content(path, use_media, attach_dir)
    elif ext == ".docx":
        return extract_docx_content(path, use_media)
    else:
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                with open(path, "r", encoding=enc) as f:
                    content = f.read()
                return [content], [], {
                    "total_pages": 1,
                    "total_questions_detected": 0,
                    "wrong_questions": 0,
                    "correct_questions": 0,
                    "unspecified_questions": 0,
                    "diagrams_mapped": 0
                }
            except UnicodeDecodeError:
                continue
        return [""], [], {
            "total_pages": 0,
            "total_questions_detected": 0,
            "wrong_questions": 0,
            "correct_questions": 0,
            "unspecified_questions": 0,
            "diagrams_mapped": 0
        }

# ---------------------------------------------------------------------------
# 6. INTERACTIVE 5-AXIS PRE-FLIGHT TRIAGE WIZARD
# ---------------------------------------------------------------------------
def run_interactive_wizard(args: argparse.Namespace) -> argparse.Namespace:
    """Executes a 5-axis pre-flight triage questionnaire when flags are omitted."""
    if args.non_interactive or args.no_ai:
        args.mode = args.mode or "curated"
        args.use_media = True if args.media is True else (False if args.no_media else True)
        args.filter = args.filter or "all"
        args.lang = args.lang or "en"
        args.density = args.density or "high"
        args.style = args.style or "qa"
        return args

    # If all primary flags are supplied via CLI, skip interactive prompt
    if args.mode and (args.media or args.no_media) and args.filter and args.lang and args.style:
        args.use_media = True if args.media else False
        return args

    print("\n" + "═" * 72)
    print("🧠 FLASHCARD ARCHITECT v3.2.0 — 5-AXIS PRE-FLIGHT TRIAGE WIZARD")
    print("═" * 72)
    print("💡 Tip: Press Enter to accept all recommended defaults,")
    print("   or enter comma-separated numbers in a single line (e.g., '1, 1, 1, 1, 1'):\n")

    quick_input = input("⚡ Quick 1-Line Configuration [Press Enter for step-by-step]: ").strip()
    if quick_input and ("," in quick_input or " " in quick_input):
        delimiter = "," if "," in quick_input else " "
        parts = [p.strip() for p in quick_input.split(delimiter) if p.strip()]
        mode_choice = parts[0] if len(parts) > 0 else "1"
        media_choice = parts[1] if len(parts) > 1 else "1"
        filter_choice = parts[2] if len(parts) > 2 else "1"
        lang_choice = parts[3] if len(parts) > 3 else "1"
        style_choice = parts[4] if len(parts) > 4 else "1"

        args.mode = {"1": "curated", "2": "strict", "3": "exam"}.get(mode_choice, "curated")
        args.use_media = (media_choice == "1")
        args.filter = {"1": "all", "2": "wrong", "3": "correct"}.get(filter_choice, "all")
        args.lang = {"1": "en", "2": "keep", "3": "pt"}.get(lang_choice, "en")
        args.style = "hybrid" if style_choice == "2" else "qa"
        args.density = "essential" if style_choice == "3" else "high"
    else:
        # Axis 1: Content Fidelity
        if not args.mode:
            print("\n[1/5] Content Treatment & Fidelity:")
            print("  [1] High-Yield Curation (80/20: Key concepts rewritten atomically) [Default]")
            print("  [2] Strict Source Fidelity (Exams/Standards: Verbatim prompts & technical terms)")
            print("  [3] Error Diagnostic & Pitfalls (Deep dive into why distractors are false)")
            choice_mode = input("👉 Choose [1/2/3] (Default: 1): ").strip()
            args.mode = {"1": "curated", "2": "strict", "3": "exam"}.get(choice_mode, "curated")

        # Axis 2: Media & Diagrams
        if not args.media and not args.no_media:
            print("\n[2/5] Media & Visual Diagrams (.pdf, .md, .docx):")
            print("  [1] Yes — Extract with Y0 Spatial Anchoring & embed WebP into Anki [Default]")
            print("  [2] No — Text-Only Turbo Mode (Maximum processing speed)")
            choice_media = input("👉 Choose [1/2] (Default: 1): ").strip()
            args.use_media = (choice_media != "2")
        else:
            args.use_media = True if args.media else False

        # Axis 3: Practice Exam Question Filter
        if not args.filter:
            print("\n[3/5] Practice Exam Question Filtering:")
            print("  [1] All Questions (Full document coverage with automated status tagging) [Default]")
            print("  [2] Incorrect / Failed Only (status::wrong — Surgical focus on learning gaps)")
            print("  [3] Correct Only (status::correct — Mastery reinforcement)")
            choice_filter = input("👉 Choose [1/2/3] (Default: 1): ").strip()
            args.filter = {"1": "all", "2": "wrong", "3": "correct"}.get(choice_filter, "all")

        # Axis 4: Language Mode
        if not args.lang:
            print("\n[4/5] Language Configuration:")
            print("  [1] English (Standard technical English for international exams) [Default]")
            print("  [2] Bilingual / Keep (Verbatim prompts/CLI in English, technical rationale in Portuguese)")
            print("  [3] Portuguese (Full Portuguese translation)")
            choice_lang = input("👉 Choose [1/2/3] (Default: 1): ").strip()
            args.lang = {"1": "en", "2": "keep", "3": "pt"}.get(choice_lang, "en")

        # Axis 5: Format & Density
        if not args.style:
            print("\n[5/5] Card Format & Generation Density:")
            print("  [1] Exhaustive Classic Q&A (3 to 6 cards/section) [Default]")
            print("  [2] Hybrid Mode (Q&A + Cloze Deletions for commands, ports, and tables)")
            print("  [3] Essential Density (1 to 2 cards/section, core concepts only)")
            choice_style = input("👉 Choose [1/2/3] (Default: 1): ").strip()
            if choice_style == "2":
                args.style = "hybrid"
                args.density = "high"
            elif choice_style == "3":
                args.style = "qa"
                args.density = "essential"
            else:
                args.style = "qa"
                args.density = "high"

    print("\n" + "─" * 72)
    print(
        f"✅ Active Config: Mode={args.mode.upper()} | "
        f"Media={'ENABLED (Y0)' if args.use_media else 'DISABLED (Turbo)'} | "
        f"Filter={args.filter.upper()} | Language={args.lang.upper()} | Style={args.style.upper()}"
    )
    print("─" * 72 + "\n")
    return args

# ---------------------------------------------------------------------------
# 7. CHUNKING WITH SLIDING OVERLAP
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
# 8. MULTI-LANGUAGE JSON RESPONSE PARSER & VALIDATOR
# ---------------------------------------------------------------------------
def parse_and_validate_cards(raw_response: str) -> tuple[list[dict], str]:
    """Parses and validates flashcard payloads accepting English and Portuguese keys."""
    if not raw_response or not raw_response.strip():
        return [], ""

    text = raw_response.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text).strip()

    parsed = None
    if json_repair:
        try:
            parsed = json_repair.repair_json(text, return_objects=True)
        except Exception:
            pass

    if parsed is None:
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

        q = (
            item.get("question") or
            item.get("front") or
            item.get("pergunta") or
            ""
        ).strip()
        a = (
            item.get("answer") or
            item.get("back") or
            item.get("resposta") or
            ""
        ).strip()
        if not q or not a:
            continue

        cid = (
            item.get("concept_id") or
            item.get("id") or
            item.get("id_conceito") or
            ""
        ).strip()
        tags = item.get("tags", [])
        if not isinstance(tags, list):
            tags = [str(tags)]
        tags = [str(t).strip().lower().replace(" ", "_") for t in tags if t]

        if not suggested_deck and item.get("suggested_deck"):
            suggested_deck = str(item.get("suggested_deck")).strip()

        valid_cards.append({
            "concept_id": cid,
            "question": q,
            "answer": a,
            "id_conceito": cid,
            "pergunta": q,
            "resposta": a,
            "tags": tags,
            "suggested_deck": item.get("suggested_deck", "")
        })

    return valid_cards, suggested_deck

def reconcile_card_images(cards: list[dict], available_media: list[str]) -> None:
    """Ensures <img> tags in cards reference existing WebP files in anki_media/."""
    if not available_media:
        return
    basenames = [os.path.basename(m) for m in available_media]
    for card in cards:
        for field in ["question", "answer", "pergunta", "resposta", "front", "back"]:
            if field in card and isinstance(card[field], str):
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
# 9. NATIVE INFERENCE ENGINE (ANTIGRAVITY CLI)
# ---------------------------------------------------------------------------
def call_antigravity_cli(prompt_text: str, model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT) -> str | None:
    cmd = [
        "agy",
        "--model", model,
        "--effort", effort,
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
        stdout, stderr = proc.communicate(timeout=240)
        if proc.returncode != 0:
            log.warning(f"  ⚠ Antigravity CLI exited with code {proc.returncode}: {stderr.strip()}")
            return None
        return stdout.strip()
    except subprocess.TimeoutExpired:
        log.warning("  ⚠ Response timeout exceeded in Antigravity CLI (240s).")
        proc.kill()
        return None
    except FileNotFoundError:
        log.error("[ERROR] 'agy' CLI binary not found in PATH.")
        return None
    except Exception as e:
        log.warning(f"  ⚠ Unexpected error invoking Antigravity CLI: {e}")
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

    log.info(f"\n  Starting native Antigravity inference ({model} - reasoning effort: {effort})...")

    for idx, chunk in enumerate(chunks):
        log.info(f"  → Batch {idx + 1}/{total_chunks} (~{len(chunk):,} characters)...")
        prompt = f"{master_prompt}\n\nSTUDY MATERIAL:\n{chunk}"

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
                log.info(f"     ✓ {len(cards)} flashcard(s) successfully generated.")
                success = True
                break
            else:
                log.warning(f"     ⚠ Batch {idx + 1} produced no valid cards (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY_SECS)

        if not success:
            log.error(f"     ✗ Batch {idx + 1} failed after {MAX_RETRIES} attempts.")

    return all_cards, overall_suggested_deck

# ---------------------------------------------------------------------------
# 10. ANKI PACKAGE BUILDER (.apkg) WITH BASIC + CLOZE DUAL ROUTING
# ---------------------------------------------------------------------------
def build_anki_deck(flashcards: list[dict], media_files: list[str], deck_name: str, output_path: str) -> tuple[int, int]:
    if genanki is None:
        log.error("[ERROR] genanki is not installed. Run with --auto-install or: pip install genanki")
        sys.exit(1)

    deck_id = get_deck_id(deck_name)

    basic_model = genanki.Model(
        MODEL_BASIC_ID,
        "Flashcard Architect Native Basic",
        fields=[{"name": "Question"}, {"name": "Answer"}],
        templates=[{
            "name": "Basic Card",
            "qfmt": '<div class="card-front">{{Question}}</div>',
            "afmt": '{{FrontSide}}<hr id="answer"><div class="card-back">{{Answer}}</div>',
        }],
        css=ANKI_CSS
    )

    cloze_model = genanki.Model(
        MODEL_CLOZE_ID,
        "Flashcard Architect Native Cloze",
        fields=[{"name": "Text"}, {"name": "Extra"}],
        templates=[{
            "name": "Cloze Card",
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
    cloze_regex = re.compile(r"\{\{c\d+::")

    for card in flashcards:
        q = card.get("question") or card.get("pergunta", "")
        a = card.get("answer") or card.get("resposta", "")
        cid = card.get("concept_id") or card.get("id_conceito")
        tags = card.get("tags", ["flashcard-architect"])

        guid_seed = f"{deck_name}_{cid}" if cid else f"{deck_name}_{q}"
        note_guid = genanki.guid_for(guid_seed)

        if cloze_regex.search(q):
            note = genanki.Note(
                model=cloze_model,
                fields=[q, a],
                tags=tags,
                guid=note_guid
            )
            added_cloze += 1
        else:
            note = genanki.Note(
                model=basic_model,
                fields=[q, a],
                tags=tags,
                guid=note_guid
            )
            added_basic += 1

        deck.add_note(note)

    package = genanki.Package(deck)
    valid_media = [m for m in media_files if os.path.exists(m)]
    package.media_files = valid_media
    package.write_to_file(output_path)

    log.info(f"      → Packaged {added_basic + added_cloze} card(s) ({added_basic} basic, {added_cloze} cloze).")
    if valid_media:
        log.info(f"      → Embedded {len(valid_media)} WebP image(s) and diagram(s).")

    return added_basic, added_cloze

# ---------------------------------------------------------------------------
# 11. AUDIT REPORT GENERATOR (<output>_Audit_Report.md)
# ---------------------------------------------------------------------------
def write_audit_report(
    report_path: str,
    input_file: str,
    output_apkg: str,
    deck_name: str,
    stats: dict,
    cards: list[dict],
    basic_count: int,
    cloze_count: int,
    media_count: int,
    mode: str,
    density: str,
    filter_mode: str,
    lang: str
) -> None:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    wrong_cards = sum(1 for c in cards if "status::wrong" in c.get("tags", []))
    correct_cards = sum(1 for c in cards if "status::correct" in c.get("tags", []))

    md = f"""# 📊 Flashcard Architect v{VERSION} — Extraction & Audit Report

> **Source Material:** `{os.path.basename(input_file)}`  
> **Execution Timestamp:** `{now_str}`  
> **Generated Package (.apkg):** `{os.path.basename(output_apkg)}`  
> **Target Anki Deck:** `{deck_name}`  
> **Inference Engine:** Native Antigravity CLI / Host Agent (`{DEFAULT_MODEL}`)

---

## 📈 1. Executive Summary & Global Metrics

| Metric | Value | Technical Details |
| :--- | :--- | :--- |
| **Pages / Sections Processed** | `{stats.get('total_pages', 0)}` | Vectorized text extraction via PyMuPDF |
| **Questions Detected in Document** | `{stats.get('total_questions_detected', 0)}` | Tracked via contextual regex & global sequence indexing |
| **Questions Identified as Incorrect (Wrong)** | `{stats.get('wrong_questions', 0)}` | Detected via failure patterns & negative status markings |
| **Questions Identified as Correct** | `{stats.get('correct_questions', 0)}` | Detected via passing patterns & positive answer keys |
| **Diagrams / Topologies Mapped (Y0)** | `{stats.get('diagrams_mapped', 0)}` | Geometrically aligned by vertical coordinate to the question |
| **Atomic Flashcards Created** | `{len(cards)}` | `{basic_count}` Basic Cards + `{cloze_count}` Cloze Deletion Cards |
| **Cards Tagged `status::wrong`** | `{wrong_cards}` | High-priority deficit review deck |
| **Cards Tagged `status::correct`** | `{correct_cards}` | Mastery consolidation cards |

---

## ⚙️ 2. Active Provisioning Configuration

- **Content Fidelity Mode:** `{mode.upper()}`
- **Question Filter:** `{filter_mode.upper()}`
- **Language Mode:** `{lang.upper()}`
- **Density Level:** `{density.upper()}`
- **Embedded WebP Media:** `{media_count}` normalized files in package

---

## 📋 3. Sample Generated Flashcards

"""
    for idx, c in enumerate(cards[:5], 1):
        q_text = c.get("question") or c.get("pergunta", "")
        clean_q = re.sub(r"<[^>]+>", " ", q_text).strip()
        cid = c.get("concept_id") or c.get("id_conceito") or f"card_{idx}"
        tags_str = ", ".join(f"`{t}`" for t in c.get("tags", []))
        sug_deck = c.get("suggested_deck") or deck_name
        md += f"### Card #{idx} — `{cid}`\n"
        md += f"- **Prompt (Front):** {clean_q}\n"
        md += f"- **Tags:** {tags_str}\n"
        md += f"- **Suggested Deck:** `{sug_deck}`\n\n"

    md += """---

## 💡 4. Next Steps in Anki with FSRS

1. Open Anki desktop or AnkiMobile and import the `.apkg` file.
2. In the deck options, verify that **FSRS (Free Spaced Repetition Scheduler)** is enabled.
3. Use the search filter `tag:status::wrong` in Anki Browse to create a **Filtered Deck** dedicated exclusively to overcoming your practice exam errors.
"""

    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md)
        log.info(f"      → Audit Report generated: {report_path}")
    except Exception as e:
        log.warning(f"  ⚠ Could not write audit report: {e}")

# ---------------------------------------------------------------------------
# 12. CORE PIPELINE & RUNNER
# ---------------------------------------------------------------------------
def run_pipeline(
    input_file: str,
    deck: str | None,
    output: str | None,
    mode: str,
    density: str,
    style: str,
    use_media: bool,
    filter_mode: str,
    lang: str,
    attachments: str | None,
    model: str,
    effort: str,
    chunk_size: int,
    no_ai: bool,
    generate_report: bool = True
) -> None:
    base_name = os.path.splitext(os.path.basename(input_file))[0]

    # 1. Extraction
    print(f"\n[1/3] Processing source material: {input_file} (Media={'Enabled (Y0)' if use_media else 'Disabled/Turbo'})")
    pages, media, stats = extract_content(input_file, use_media=use_media, attach_dir=attachments, filter_mode=filter_mode)
    total_chars = sum(len(p) for p in pages)
    print(f"      → {len(pages)} block(s) | {len(media)} diagram(s) | ~{total_chars:,} characters")

    # 2. Card Generation
    cards = []
    suggested_deck = ""
    is_json = input_file.lower().endswith(".json") or no_ai

    if is_json:
        print(f"\n[2/3] Loading pre-structured flashcards (direct packaging mode)...")
        raw_text = "\n".join(pages)
        cards, suggested_deck = parse_and_validate_cards(raw_text)
    else:
        print(f"\n[2/3] Generating flashcards via Antigravity CLI ({model} / {effort} / mode: {mode} / filter: {filter_mode})...")
        master_prompt = build_master_prompt(
            mode=mode,
            density=density,
            use_media=use_media,
            card_style=style,
            lang=lang,
            filter_mode=filter_mode
        )
        chunks = chunk_with_overlap(pages, max_chars_per_chunk=8000, overlap_ratio=0.15)
        cards, suggested_deck = generate_flashcards_antigravity(chunks, master_prompt, model=model, effort=effort)

    if not cards:
        log.error("\n[ERROR] No valid flashcards were generated or parsed.")
        return

    # Intelligent taxonomy naming
    final_deck_name = deck
    if not final_deck_name or final_deck_name in ["Study::Flashcard_Architect", "Meu Baralho Antigravity"]:
        if suggested_deck:
            final_deck_name = suggested_deck
        else:
            clean_title = re.sub(r"[_\-\.]+", " ", base_name).title()
            final_deck_name = f"Study::{clean_title}"

    if not output:
        slug = re.sub(r"[^\w\s-]", "", final_deck_name.replace("::", "_")).strip().replace(" ", "_")
        output = f"{slug}.apkg"

    # 3. Packaging
    print(f"\n[3/3] Building Anki package: '{final_deck_name}' -> {output}")
    basic_count, cloze_count = build_anki_deck(cards, media, final_deck_name, output)

    # 4. Audit Report
    report_file = os.path.splitext(output)[0] + "_Audit_Report.md"
    if generate_report:
        write_audit_report(
            report_path=report_file,
            input_file=input_file,
            output_apkg=output,
            deck_name=final_deck_name,
            stats=stats,
            cards=cards,
            basic_count=basic_count,
            cloze_count=cloze_count,
            media_count=len(media),
            mode=mode,
            density=density,
            filter_mode=filter_mode,
            lang=lang
        )

    print(f"\n{'═'*64}")
    print(f"  ✅ Anki Deck v{VERSION} Successfully Built!")
    print(f"  📦 Package (.apkg)  : {output}")
    print(f"  📊 Audit Report     : {report_file}")
    print(f"  🃏 Total Cards      : {len(cards)} ({basic_count} basic, {cloze_count} cloze)")
    print(f"  🖼️  WebP Diagrams   : {len(media)} anchored via Y0")
    print(f"  📂 Anki Deck Name   : {final_deck_name}")
    print(f"  🎯 Mode / Filter    : {mode.upper()} | {filter_mode.upper()} | Lang: {lang.upper()}")
    print(f"{'═'*64}\n")

    # Preview 2 sample cards for immediate validation
    print("👀 Flashcard Sample Preview:")
    for i, c in enumerate(cards[:2], 1):
        q_text = c.get("question") or c.get("pergunta", "")
        a_text = c.get("answer") or c.get("resposta", "")
        clean_q = re.sub(r"<[^>]+>", "", q_text).strip()
        clean_a = re.sub(r"<[^>]+>", "", a_text).strip()
        print(f"  [{i}] Front : {clean_q[:110]}...")
        print(f"      Back  : {clean_a[:130]}...\n")

def main():
    parser = argparse.ArgumentParser(
        prog="anki_generator",
        description=f"Flashcard Architect v{VERSION} — Automated Anki Deck Architect with Spatial Y0 Anchoring, Exam Auditing, and 5-Axis Triage.",
        epilog="Examples:\n  python anki_generator.py --input exam.pdf --extract-only\n  python anki_generator.py --input cards.json --no-ai --deck 'Study::Cisco'\n  python anki_generator.py --input exam.pdf --mode strict --filter wrong --lang en",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--input", "-i", default=None, help="Path to source document (.pdf, .md, .docx, .txt, .json)")
    parser.add_argument("--deck", "-d", default="Study::Flashcard_Architect", help="Target Anki deck name (hierarchical with ::)")
    parser.add_argument("--output", "-o", default=None, help="Output .apkg package path")
    parser.add_argument("--mode", "-M", choices=["curated", "strict", "exam"], default=None, help="Content fidelity mode: curated (80/20), strict (verbatim), exam (error audit)")
    parser.add_argument("--media", action="store_true", default=None, help="Force enable media extraction with Y0 geometric anchoring")
    parser.add_argument("--no-media", action="store_true", default=False, help="Force disable media extraction (Turbo Text-Only Mode)")
    parser.add_argument("--filter", "-F", choices=["all", "wrong", "correct"], default=None, help="Exam question filter: all (entire doc), wrong (incorrect only), correct (passed only)")
    parser.add_argument("--lang", "-L", choices=["en", "keep", "pt"], default=None, help="Language mode: en (English default), keep (bilingual source preservation), pt (Portuguese)")
    parser.add_argument("--density", "-D", choices=["essential", "high"], default=None, help="Card generation density: essential (1-2/page) or high (3-6/page)")
    parser.add_argument("--style", "-S", choices=["qa", "hybrid"], default=None, help="Card format: qa (classic Q&A) or hybrid (Q&A + Cloze deletions)")
    parser.add_argument("--attachments", "-a", default=None, help="Directory for extra visual attachments")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Antigravity CLI model (default: {DEFAULT_MODEL})")
    parser.add_argument("--effort", "-e", default=DEFAULT_EFFORT, choices=["low", "medium", "high", "xhigh", "max"], help=f"Reasoning effort level (default: {DEFAULT_EFFORT})")
    parser.add_argument("--chunk-size", "-c", type=int, default=10, help="Pages/sections per batch (default: 10)")
    parser.add_argument("--extract-only", action="store_true", help="Extract text and anchor WebP diagrams without calling AI, writing to --extracted-output")
    parser.add_argument("--extracted-output", default=None, help="Output file path for structured extracted text (default: <input>_extracted.txt)")
    parser.add_argument("--no-report", action="store_true", help="Skip generating the Markdown audit report")
    parser.add_argument("--auto-install", action="store_true", help="Automatically install any missing python dependencies via pip")
    parser.add_argument("--non-interactive", "-y", action="store_true", help="Skip interactive wizard using CLI flags/defaults")
    parser.add_argument("--no-ai", "--offline", action="store_true", help="Directly package a pre-structured .json file without AI inference")
    parser.add_argument("--version", "-v", action="version", version=f"Flashcard Architect v{VERSION}")

    args = parser.parse_args()

    # Verify or provision dependencies
    check_or_install_dependencies(auto_install=args.auto_install)

    # Auto-discover file if --input is omitted
    target_file = args.input
    if not target_file:
        candidates = []
        for ext in ["*.pdf", "*.md", "*.docx", "*.txt", "*.json"]:
            for f in glob.glob(ext):
                fl = f.lower()
                if not (
                    fl.startswith("requirements") or
                    fl.startswith("readme") or
                    fl.startswith("guia_mestre") or
                    fl.endswith("_audit_report.md") or
                    fl.endswith("_relatorio_auditoria.md") or
                    fl.endswith("_extracted.txt")
                ):
                    candidates.append(f)
        if candidates:
            target_file = candidates[0]
            log.info(f"[Auto-Discovery] Selected source file: {target_file}")
        else:
            log.error("[ERROR] No input file specified and no valid source document found in current directory.")
            sys.exit(1)

    # Handle --extract-only for Universal Multi-Agent Host Support
    if args.extract_only:
        extracted_output = args.extracted_output or f"{os.path.splitext(target_file)[0]}_extracted.txt"
        use_media = not args.no_media if args.no_media else True
        if args.media is not None:
            use_media = args.media

        print(f"\n[Extraction Mode] Processing material: {target_file} (Media={'Enabled (Y0)' if use_media else 'Disabled/Turbo'})")
        pages, media, stats = extract_content(target_file, use_media=use_media, attach_dir=args.attachments, filter_mode=args.filter or "all")
        total_chars = sum(len(p) for p in pages)

        combined_text = "\n\n".join(pages)
        with open(extracted_output, "w", encoding="utf-8") as f:
            f.write(combined_text)

        summary = {
            "status": "success",
            "input_file": target_file,
            "extracted_output": extracted_output,
            "total_pages": stats.get("total_pages", len(pages)),
            "total_characters": total_chars,
            "diagrams_mapped": len(media),
            "total_questions_detected": stats.get("total_questions_detected", 0),
            "wrong_questions": stats.get("wrong_questions", 0),
            "correct_questions": stats.get("correct_questions", 0),
        }

        print(f"      → Saved structured text to: {extracted_output}")
        print(f"      → Total Pages: {summary['total_pages']} | Total Chars: {total_chars:,} | Diagrams: {len(media)}")
        print(f"      → Questions Detected: {summary['total_questions_detected']} (Wrong: {summary['wrong_questions']}, Correct: {summary['correct_questions']})")
        print("\n" + json.dumps(summary, indent=2))
        sys.exit(0)

    # Run Interactive Wizard if needed
    args = run_interactive_wizard(args)

    run_pipeline(
        input_file=target_file,
        deck=args.deck,
        output=args.output,
        mode=args.mode,
        density=args.density,
        style=args.style,
        use_media=args.use_media,
        filter_mode=args.filter,
        lang=args.lang,
        attachments=args.attachments,
        model=args.model,
        effort=args.effort,
        chunk_size=args.chunk_size,
        no_ai=args.no_ai,
        generate_report=not args.no_report
    )

if __name__ == "__main__":
    main()
