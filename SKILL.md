---
name: flashcard-architect
description: Analisa documentos de estudo (PDF, DOCX, TXT, Markdown) e gera flashcards de alta retenção para o Anki (.apkg), com imagens embutidas, formatação HTML/CSS e saída JSON estruturada.
---

# Flashcard Architect — Skill

## Overview

Esta skill transforma qualquer material de estudo em flashcards perfeitamente organizados para o Anki, usando o algoritmo FSRS de repetição espaçada. Ela gerencia extração de imagens, formatação HTML/CSS rica e entrega um arquivo `.apkg` pronto para importar.

## When to Use

- Você tem um PDF, DOCX, TXT ou arquivo Markdown de estudo e quer convertê-lo em flashcards
- Você quer revisar questões que errou em simulados
- Você precisa organizar anotações brutas em cards atômicos (uma ideia por card)
- Você quer que as imagens do documento apareçam nos flashcards gerados

## Process

### Passo 1 — Preparar o ambiente

Instale as dependências Python:

```bash
pip install PyMuPDF genanki google-generativeai python-docx
```

### Passo 2 — Configurar o script

Edite o arquivo `anki_generator.py` com:
- `GEMINI_API_KEY`: sua chave da API Gemini
- `INPUT_PATH`: caminho para o seu arquivo (PDF, DOCX, TXT ou MD)
- `DECK_NAME`: nome do deck no Anki
- `OUTPUT_APKG`: nome do arquivo de saída

### Passo 3 — Executar

```bash
python anki_generator.py
```

O script irá:
1. Extrair texto e imagens do documento
2. Enviar para o Gemini (com o system prompt do especialista em flashcards)
3. Receber o JSON estruturado de volta
4. Montar o pacote `.apkg` com imagens embutidas

### Passo 4 — Importar no Anki

Abra o Anki → Arquivo → Importar → selecione o `.apkg` gerado.

## Verification

- [ ] O arquivo `.apkg` foi criado sem erros
- [ ] Os cards aparecem com as imagens corretamente no Anki
- [ ] A formatação HTML (negrito, listas, blocos de código) está renderizando
- [ ] Cards atômicos: cada card tem uma única ideia principal
- [ ] O CSS dark mode está aplicado

## Common Rationalizations (Anti-padrões)

- ❌ "Vou colocar tudo em um só card gigante" → Quebre em cards atômicos
- ❌ "A imagem não é importante" → Se o conteúdo referencia uma imagem, ela DEVE estar no card
- ❌ "Vou pular a justificativa" → A justificativa é o que diferencia memorização de entendimento

## Red Flags

- JSON retornado com blocos de markdown (```json) → o script limpa automaticamente, mas investigue se persistir
- Imagens quebradas no Anki → verifique se a pasta `anki_media/` foi incluída no `.apkg`
- Cards sem resposta → o texto do documento pode estar mal formatado; pré-processe manualmente

## Agent System Prompt

O system prompt completo do agente está em `prompt_agente.txt`. Cole-o na seção **System Instructions** do Google AI Studio, Gemini Advanced (Gems) ou no arquivo de configuração do seu Antigravity CLI.
