---
name: flashcard-architect
description: Automated Anki flashcard architect (.apkg) with Y0 geometric diagram anchoring, practice exam error auditing, FSRS optimization, and 5-axis customization for PDF, DOCX, Markdown, and TXT.
---

# 🧠 Flashcard Architect — Universal Agent Skill (v3.2.0)

## Overview

The **Flashcard Architect** is an enterprise-grade agent skill engineered to transform complex study materials (**PDF, DOCX, Markdown, and TXT**) into high-retention Anki decks (`.apkg`) optimized for the **FSRS (Free Spaced Repetition Scheduler)** algorithm.

It solves the classic failure modes of automated flashcard creation through five foundational architectural innovations:

1. **Y0 Spatial Geometric Diagram Anchoring**: Using PyMuPDF block extraction, visual diagrams, topologies, and graphs are bound directly to the question prompt above them rather than dumped at the end of the page.
2. **Global Sequential Question Indexing**: Injects canonical identifiers `[Page X | Question Y (Global #Z)]`, preventing context collision and duplicate IDs across multi-section or partitioned exams.
3. **Practice Exam Error Auditing**: Automatically detects question outcomes (wrong vs. correct), labels cards with `status::wrong` / `status::correct`, and allows targeted extraction via `--filter wrong`.
4. **Automated Markdown Audit Report**: Produces `<output>_Audit_Report.md` summarizing question metrics, error rates, and step-by-step guidance for Filtered Decks in Anki.
5. **Universal Host-Agent Compatibility**: Runs natively inside **Claude Code, Cursor, GitHub Copilot, Windsurf**, and **Google Antigravity** via a decoupled extraction and packaging pipeline.

---

## ⚙️ 5-Axis Pre-Flight Triage Questionnaire

When invoked without explicit configuration flags, present a **single 5-axis triage prompt** (respond with comma-separated numbers, e.g., `1, 1, 1, 1, 1`, or press Enter for defaults):

1. **Content Treatment & Fidelity**:
   - `[1]` **High-Yield Curation (80/20) [Default]**: Filters out noise, redundant historical context, and synthesizes atomic, high-retention cards.
   - `[2]` **Strict Source Fidelity (Exams / Certifications / Standards)**: Preserves verbatim question scenarios, prompts, and technical terminology on the Front without alterations.
   - `[3]` **Error Diagnostic & Pitfalls**: Focuses on why distractor options are false and how to avoid cognitive traps.
2. **Media & Visual Diagrams**:
   - `[1]` **Yes — Extract with Y0 Spatial Anchoring [Default]**: Converts diagrams to WebP and embeds them into the `.apkg`.
   - `[2]` **No — Text-Only Turbo Mode**: Bypasses image extraction for 70% faster processing.
3. **Practice Exam Question Filtering**:
   - `[1]` **All Questions [Default]**: Full coverage with automatic status tagging.
   - `[2]` **Incorrect / Failed Only (`status::wrong`)**: Surgical remediation targeting identified deficits.
   - `[3]` **Correct Only (`status::correct`)**: Mastery reinforcement.
4. **Language Configuration**:
   - `[1]` **English [Default]**: Complete English flashcards and technical rationales.
   - `[2]` **Bilingual Keep (`keep`)**: Verbatim English question/CLI prompts on the Front; detailed technical explanations in Portuguese on the Back.
   - `[3]` **Portuguese (`pt`)**: Translates full questions and explanations into Portuguese.
5. **Card Format & Generation Density**:
   - `[1]` **Exhaustive Classic Q&A (3 to 6 cards/section) [Default]**
   - `[2]` **Hybrid Mode (Q&A + Cloze Deletions)**: Uses `{{c1::...}}` for commands, ports, and parameters.
   - `[3]` **Essential Density (1 to 2 cards/section)**

---

## 🔄 Two Execution Workflows

### Workflow A: Universal Host-Agent Mode (Recommended for Claude Code, Cursor, Copilot, Windsurf)

Host AI agents that cannot execute external binary CLIs directly should use the 3-step decoupled pipeline:

```bash
# Step 1: Extract text and anchor visual diagrams
python scripts/anki_generator.py \
  --input "<file_path>" \
  --extract-only \
  --extracted-output "extracted_content.txt"
```

1. Read `extracted_content.txt`. Notice anchored diagrams marked as `[Image: ag_xxxx.webp]`, question prefixes `[Page X | Question Y (Global #Z)]`, and status markers `[STATUS: INCORRECT / WRONG]`.
2. Formulate flashcards with your own LLM according to the **Cognitive Construction Rules** below and save as a JSON array to `cards_payload.json`.
3. Package into `.apkg` with all embedded WebP media and audit reporting:

```bash
# Step 3: Package into .apkg and generate audit report
python scripts/anki_generator.py \
  --input "cards_payload.json" \
  --no-ai \
  --deck "Certifications::Cisco::CCNA_200_301" \
  --output "CCNA_Study.apkg"
```

---

### Workflow B: Standalone Antigravity CLI Mode

When running in an environment with the Antigravity CLI (`agy`) installed:

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

## 📐 Mandatory Card Construction Rules

Every flashcard generated must comply strictly with these cognitive engineering standards:

1. **Strict Atomicity**: Each card tests exactly ONE mental association. No compound multi-part questions on a single card.
2. **Context Anchors**: Prompts must be self-contained. When available, preserve `[Page X | Question Y (Global #Z)]` as a context anchor.
3. **Answer Styling**: The direct answer must be wrapped in `<span class="ans"><b>Direct Answer</b></span>` followed by `<br><br><i>Rationale:</i>` detailing the causal technical explanation.
4. **Spatial Diagram Placement**:
   - Question topologies, graphs, or UI screens: place on the **FRONT** (`<br><img src="ag_xxxx.webp">`).
   - Explanatory solution diagrams: place on the **BACK**.
5. **Permitted HTML Tags Only** (No inline `style=""`): `<b>`, `<i>`, `<code>`, `<ul>`, `<li>`, `<br>`.
6. **Required Metadata Schema**:
   - `concept_id`: Stable identifier in `snake_case` (e.g., `ccna_ospf_dr_bdr_priority_p12_q1`).
   - `question`: Front prompt with clean HTML.
   - `answer`: Back answer with `<span class="ans"><b>...</b></span>` and rationale.
   - `tags`: Array of lower-case snake_case tags, including `status::wrong` or `status::correct`.
   - `suggested_deck`: Hierarchical taxonomy (e.g., `Category::Subcategory::Topic`).

```json
[
  {
    "concept_id": "ccna_ospf_dr_bdr_priority_p12_q1",
    "question": "[Page 12 | Question 1 (Global #1)] Which OSPF router priority value prevents a router from participating in the DR/BDR election?<br><img src=\"ag_3a8f12c9b4e1.webp\">",
    "answer": "<span class=\"ans\"><b>Priority value of 0.</b></span><br><br><i>Rationale:</i> In OSPF, a router configured with an interface priority of <code>0</code> (via <code>ip ospf priority 0</code>) becomes permanently a <i>DROTHER</i> and is ineligible to become a <i>DR</i> or <i>BDR</i>.",
    "tags": ["networking", "ospf", "status::wrong"],
    "suggested_deck": "Certifications::Cisco::CCNA_200_301"
  }
]
```
