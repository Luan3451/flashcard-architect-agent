# 🧠 Flashcard Architect (`v3.2.0` — Multi-Agent Commercial Edition)

[![Version](https://img.shields.io/badge/version-3.2.0-blue.svg)](https://github.com/Luan3451/flashcard-architect-agent-Agents.io-)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: >=3.10](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Anki FSRS: Compatible](https://img.shields.io/badge/Anki-FSRS%20Optimized-success.svg)](https://apps.ankiweb.net/)
[![Platform: Claude Code | Cursor | Copilot | Antigravity](https://img.shields.io/badge/agents-Universal%20Support-orange.svg)](https://agensi.io)

> **Enterprise-grade automated Anki deck architect (`.apkg`) with Y0 geometric diagram anchoring, practice exam error auditing, dual Basic + Cloze model routing, and native FSRS optimization for PDF, DOCX, Markdown, and TXT.**

---

## 📌 Executive Summary

**Flashcard Architect v3.2.0** transforms complex study materials and certification practice exams (Cisco CCNA/CCNP, AWS, CompTIA, Bar exams, Medical boards) into high-retention Anki decks (`.apkg`) ready for immediate import into Anki Desktop, AnkiMobile, and AnkiDroid.

Designed for international commercial distribution on **Agensi.io**, Flashcard Architect works across all modern AI coding harnesses (**Claude Code, Cursor, GitHub Copilot, Windsurf**) and operates natively in **Google Antigravity** without requiring third-party API keys.

---

## 🔬 Core Architectural Innovations

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   FLASHCARD ARCHITECT PIPELINE (v3.2.0)                │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
      ┌────────────────────────────┴─────────────────────────────┐
      ▼                                                          ▼
[PDF / DOCX / MD / TXT]                                   [Workflow A / B]
      │                                                          │
      ├─► Y0 Spatial Anchoring (bbox.y0 Top-to-Bottom Sorting)   │
      ├─► Content-Addressed WebP Storage (SHA-256 Deduplication) │
      ├─► Canonical Question Indexing: [Page X | Question Y]     │
      ├─► Exam Outcome Detection: status::wrong / status::correct│
      │                                                          ▼
      ▼                                                 [LLM Cognitive Engine]
[anki_media/*.webp]                                      (Atomicity & Rationale)
      │                                                          │
      └────────────────────────────┬─────────────────────────────┘
                                   ▼
             [Dual Model GenAnki: Basic + Cloze Deletions]
                                   │
      ┌────────────────────────────┴─────────────────────────────┐
      ▼                                                          ▼
[Compiled .apkg Deck with Native Dark Mode]          [<output>_Audit_Report.md]
```

### 1. Spatial Geometric Diagram Anchoring (Y0 Coordinate)
Legacy extractors dump all page images into a flat footer list, causing the LLM to hallucinate which question a network topology belongs to on multi-question pages. Flashcard Architect reads the vertical coordinate (`bbox.y0`) of every text block and bitmap/vector drawing via PyMuPDF, ordering elements sequentially from top to bottom. Images appear in the extracted stream directly below the question prompt they illustrate.

### 2. Global Sequential Indexing (`[Page X | Question Y (Global #Z)]`)
Multi-part certification exams frequently reset question numbers (e.g., Section 1: Q1–Q20; Section 2: Q1–Q25). Flashcard Architect injects a unique canonical prefix, preventing context collisions in LLM sliding windows and ensuring deterministic note GUIDs.

### 3. Practice Exam Outcome Auditing & Auto-Tagging
The engine automatically detects pass/fail patterns and status markings, applying `status::wrong` or `status::correct` tags to generated cards. Use `--filter wrong` to isolate learning deficits into a surgical remediation deck.

### 4. Automated Markdown Audit Report (`<output>_Audit_Report.md`)
Every run compiles an executive audit report detailing question detection, error percentages, diagram counts, and step-by-step instructions for creating Anki Filtered Decks.

### 5. Content-Addressed WebP Media Storage
Visual assets are normalized, filtered to eliminate decorative banners, converted to WebP (quality 85), and stored using content hash identifiers (`ag_{hash[:12]}.webp`), eliminating media collisions inside Anki's unified `collection.media` folder.

---

## ⚡ 5-Axis Pre-Flight Triage Wizard

When executed without explicit CLI flags, Flashcard Architect presents an interactive 5-axis questionnaire. Users can press **Enter** to accept recommended defaults or reply in a single line (e.g., `1, 1, 2, 1, 1`):

| Axis | Option 1 (Default) | Option 2 | Option 3 |
| :--- | :--- | :--- | :--- |
| **1. Content Fidelity** | **Curated 80/20 (`curated`)**<br>High-yield atomic synthesis | **Strict Literal (`strict`)**<br>Verbatim prompts & options | **Exam Traps (`exam`)**<br>Diagnostic distractor analysis |
| **2. Media Extraction** | **Enabled (`--media`)**<br>Y0 spatial WebP extraction | **Turbo Mode (`--no-media`)**<br>Text-only (70% faster) | — |
| **3. Question Filter** | **All Questions (`all`)**<br>Full coverage with tagging | **Errors Only (`wrong`)**<br>Surgical deficit remediation | **Correct Only (`correct`)**<br>Mastery reinforcement |
| **4. Language Mode** | **English (`en`)**<br>Standard technical English | **Bilingual Keep (`keep`)**<br>English prompt / PT rationale | **Portuguese (`pt`)**<br>Full Portuguese translation |
| **5. Card Format & Density** | **Exhaustive Q&A (`qa`)**<br>3 to 6 cards per section | **Hybrid Mode (`hybrid`)**<br>Q&A + Cloze (`{{c1::...}}`) | **Essential (`essential`)**<br>1 to 2 core cards |

---

## 🚀 Dual Execution Workflows

### Workflow A: Universal Host-Agent Mode (Claude Code, Cursor, Copilot, Windsurf)

AI coding assistants can leverage Flashcard Architect's decoupled pipeline without needing direct shell access to external inference binaries:

```bash
# Step 1: Extract text and anchor visual diagrams
python scripts/anki_generator.py \
  --input "practice_exam.pdf" \
  --extract-only \
  --extracted-output "extracted_text.txt"
```

1. The agent inspects `extracted_text.txt` containing anchored diagrams (`[Image: ag_xxxx.webp]`) and question status tags (`[STATUS: INCORRECT / WRONG]`).
2. The agent's LLM generates a clean JSON array adhering to `prompt_agente.txt` and writes it to `cards_payload.json`.
3. The agent compiles the `.apkg` with all embedded media:

```bash
# Step 2: Compile package and generate audit report
python scripts/anki_generator.py \
  --input "cards_payload.json" \
  --no-ai \
  --deck "Certifications::Cisco::CCNA_200_301" \
  --output "CCNA_Study.apkg"
```

### Workflow B: Standalone Antigravity CLI Mode

Environments with the Antigravity CLI (`agy`) can execute end-to-end autonomous generation with Gemini 3.8 Flash:

```bash
python scripts/anki_generator.py \
  --input "practice_exam.pdf" \
  --deck "Certifications::AWS::Solutions_Architect" \
  --mode strict \
  --filter wrong \
  --lang en \
  --media \
  --non-interactive
```

---

## 🛠️ CLI Reference Table (`--help`)

| Flag | Values | Default | Description |
| :--- | :--- | :--- | :--- |
| `-i, --input` | File path | Auto-detect | Source document (`.pdf`, `.md`, `.docx`, `.txt`, `.json`) |
| `-d, --deck` | String | `Study::Flashcard_Architect` | Target Anki deck name (supports `::` hierarchy) |
| `-o, --output` | File path | `<deck>.apkg` | Output path for compiled `.apkg` package |
| `-M, --mode` | `curated`, `strict`, `exam` | `curated` | Content treatment: 80/20, Verbatim, or Error Audit |
| `--media` | Flag | Enabled | Force enable Y0 geometric image extraction |
| `--no-media` | Flag | Disabled | Force disable image extraction (Turbo Mode) |
| `-F, --filter` | `all`, `wrong`, `correct` | `all` | Filter questions: entire doc, failed only, or passed only |
| `-L, --lang` | `en`, `keep`, `pt` | `en` | Language: English, Bilingual Keep, or Portuguese |
| `-D, --density` | `essential`, `high` | `high` | Card density: 1-2 vs. 3-6 cards per section |
| `-S, --style` | `qa`, `hybrid` | `qa` | Card template: classic Q&A or Hybrid with Cloze |
| `--extract-only` | Flag | Disabled | Perform Step 1 extraction and exit (Host-Agent mode) |
| `--extracted-output` | File path | `<input>_extracted.txt` | Target path for extracted structured text |
| `--auto-install` | Flag | Disabled | Automatically install missing Python packages via pip |
| `--no-report` | Flag | Disabled | Skip Markdown audit report generation |
| `-y, --non-interactive` | Flag | Disabled | Skip interactive wizard using flags/defaults |
| `--no-ai, --offline` | Flag | Disabled | Package pre-structured JSON directly without AI |
| `-v, --version` | Flag | N/A | Print version number and exit |

---

## 📂 Repository Layout

```text
flashcard-architect-agent/
├── .gitignore                        # Git exclusion rules allowing distribution zips
├── LICENSE                           # MIT License
├── README.md                         # Commercial international documentation
├── SKILL.md                          # Agensi.io root skill specification
├── plugin.json                       # Antigravity/Gemini plugin manifest v3.2.0
├── prompt_agente.txt                 # Master prompt engineering matrix (English)
├── agents/
│   └── flashcard-architect.md        # Antigravity Agent definition with 5-axis wizard
├── skills/
│   └── flashcard-architect/
│       └── SKILL.md                  # Backward-compatible mirrored skill
└── scripts/
    └── anki_generator.py             # Multi-agent Python core (Y0, WebP, GenAnki, Audit)
```

---

## 📦 Packaging for Agensi.io Marketplace

To generate a clean submission package for the Agensi.io marketplace:

```bash
zip -r flashcard-architect-agensi.zip . -x "*.git*" -x "anki_media/*" -x "*.apkg" -x "*__pycache__*" -x "*.venv*"
```

---

## 📄 License

Distributed under the **MIT License**. Created and maintained by **Luan3451**.
