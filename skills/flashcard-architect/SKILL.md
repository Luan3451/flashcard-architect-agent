---
name: flashcard-architect
description: Analisa documentos de estudo (PDF, DOCX, TXT, Markdown) e gera flashcards de alta retenção para o Anki (.apkg), com imagens WebP embutidas, protocolo Zero-Touch, formatação HTML/CSS dark mode e saída JSON estruturada. 100% nativo no Antigravity CLI/IDE/APP com Gemini 3.8 Flash (High), sem APIs externas.
---

# Flashcard Architect — Skill

## Overview

O **Flashcard Architect** é uma skill oficial para o Google Antigravity que transforma materiais de estudo em baralhos completos `.apkg` para o Anki com **automação Zero-Touch**.

- **100% Nativo no Antigravity**: Sem APIs externas como o Google AI Studio.
- **Protocolo Zero-Touch**: Execução autônoma imediata, inferência de decks hierárquicos e auto-recuperação de erros.
- **Content-Addressed Storage WebP**: Imagens nomeadas por hash SHA-256 e compactadas em WebP, eliminando colisões globais na pasta `collection.media` do Anki.
- **Suporte Dual (Básico e Cloze)**: Detecção automática de omissões `{{c1::...}}` com modelos dedicados.
- **Integração AnkiConnect**: Injeção direta no AnkiDesktop e sincronização instantânea com o celular.

## ⚡ Protocolo Zero-Touch

1. NUNCA peça confirmação intermediária ao usuário antes de extrair textos ou rodar o script.
2. Se o usuário não informar parâmetros opcionais (`--deck`, `--output`), infira automaticamente a taxonomia hierárquica.
3. Entregue diretamente o resultado concluído com o arquivo `.apkg` pronto.

## Como Executar

### Via Antigravity CLI (Zero Flags)

Basta executar o script no diretório contendo o arquivo de estudo:

```bash
# Auto-descobre o arquivo, processa com Gemini 3.8 Flash High e injeta no Anki
python scripts/anki_generator.py

# Ou especificando arquivo e pasta de anexos
python scripts/anki_generator.py --input "resumo.md" --attachments "./anexos"

# Modo Dropzone contínuo (Watchdog)
python scripts/anki_generator.py --watch --watch-dir "./inbox"
```

### No Antigravity IDE ou APP

1. Mencione `@flashcard-architect` no chat.
2. Forneça o arquivo (PDF, Markdown ou apostila).
3. O agente executa o pipeline de ponta a ponta sem perguntas intermediárias e entrega o baralho pronto.
