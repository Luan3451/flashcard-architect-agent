---
name: flashcard-architect
description: Especialista em engenharia cognitiva FSRS e geração nativa de baralhos Anki (.apkg) via Antigravity com triagem rápida e bypass condicional de mídias.
version: 3.1.0
model: gemini-3.8-flash-high
---

# 🧠 Flashcard Architect — Skill

## Overview

O **Flashcard Architect** é uma skill oficial para o Google Antigravity que transforma materiais de estudo (**PDF, Markdown, DOCX, TXT e JSON**) em baralhos Anki (`.apkg`) otimizados para o algoritmo FSRS com **Questionário de Triagem Pré-Voo** e **Lazy Media Extraction**.

- **100% Nativo no Antigravity**: Opera diretamente com Gemini 3.8 Flash (High Reasoning Effort) sem chaves externas de API.
- **Wizard Interativo**: 4 perguntas rápidas para configurar fidelidade (curadoria vs. literalidade), processamento de mídias, formato de cartões e densidade.
- **Bypass Condicional de Mídia**: Desativa ferramentas de imagem (`--no-media`) para extração turbo de textos puros.
- **Deck IDs Determinísticos**: Hash de 31 bits prevenindo fusão acidental de decks no SQLite do Anki.

## 📋 Fluxo de Execução

### Etapa 1: Triagem Pré-Voo (Menu Rápido de 4 Opções)

Quando acionado sem parâmetros explícitos, o assistente apresenta:

1. **Fidelidade ao Texto-Fonte:**
   - `[1]` Curadoria & Recorrência (80/20)
   - `[2]` Fidelidade Estrita (Provas / Simulados / Letra da Norma)
   - `[3]` Auditoria de Erros e Pegadinhas
2. **Imagens e Anexos:**
   - `[1]` Sim (Ativar extratores de mídia `--media`)
   - `[2]` Não (Modo Turbo Somente Texto `--no-media`)
3. **Estilo dos Cartões:**
   - `[1]` Pergunta & Resposta Clássica + Justificativa
   - `[2]` Híbrido (com Lacunas Cloze)
4. **Densidade:**
   - `[1]` Essencial (Enxuto)
   - `[2]` Exaustivo (Alto Rendimento)

*(Resposta rápida aceita em uma única linha, ex: `1, 2, 1, 2` ou `padrão`).*

### Etapa 2: Execução do Gerador

```bash
python scripts/anki_generator.py \
  --input "<arquivo>" \
  --deck "<nome_deck>" \
  --mode <curated|strict|exam> \
  --density <essential|high> \
  [--media | --no-media] \
  --non-interactive \
  --output "<arquivo>.apkg"
```

### Etapa 3: Entrega do Pacote

Exibe o caminho do `.apkg`, total de cartões criados e prévia visual de validação.
