---
name: flashcard-architect
description: Analisa documentos de estudo (PDF, DOCX, TXT, Markdown) e gera flashcards de alta retenção para o Anki (.apkg), com imagens embutidas, formatação HTML/CSS e saída JSON estruturada.
---

# Flashcard Architect — Skill

## Overview

Esta skill transforma qualquer material de estudo em flashcards perfeitamente organizados para o Anki, usando o algoritmo FSRS de repetição espaçada. Gerencia extração de imagens, formatação HTML/CSS rica e entrega um arquivo `.apkg` pronto para importar.

## When to Use

- Você tem um PDF, DOCX, TXT ou Markdown e quer convertê-lo em flashcards
- Você quer revisar questões que errou em simulados
- Você precisa organizar anotações brutas em cards atômicos (uma ideia por card)
- Você quer que as imagens do documento apareçam embutidas nos flashcards

## Process

### Passo 1 — Instalar dependências

```bash
pip install PyMuPDF genanki google-generativeai python-docx
```

### Passo 2 — Configurar o script

Edite `scripts/anki_generator.py` com suas credenciais e caminhos:

```python
GEMINI_API_KEY = "sua-api-key-gemini"   # https://aistudio.google.com/app/apikey
INPUT_PATH     = "caminho/para/seu/arquivo.pdf"
DECK_NAME      = "Meu Deck de Revisão"
OUTPUT_APKG    = "flashcards.apkg"
```

### Passo 3 — Executar

```bash
python scripts/anki_generator.py
```

O script irá:
1. Extrair texto e imagens do documento
2. Enviar em lotes para o Gemini (system prompt do especialista em flashcards)
3. Receber o JSON estruturado de volta
4. Montar o pacote `.apkg` com imagens embutidas

### Passo 4 — Importar no Anki

```
Anki → Arquivo → Importar → selecione o flashcards.apkg gerado
```

## Prompt Recomendado Após Instalação

Após ativar o agente com `agy agent use flashcard-architect`, use este prompt como ponto de partida:

```
Analise o seguinte material extraído do arquivo [NOME_DO_ARQUIVO].
Havia imagens extraídas nomeadas como: [lista de imagens, ex: img_p1_0.png, img_p3_1.png].
Foco principal: as questões que errei (marcadas como ERRADO no texto).
Gere os flashcards respeitando todas as suas regras de formatação HTML/CSS dark mode.

[COLE AQUI O TEXTO EXTRAÍDO DO SEU DOCUMENTO]
```

> Substitua os campos entre colchetes pelas informações do seu material.

## Formatos Suportados

| Formato | Extensão | Imagens extraídas? |
|---------|----------|-------------------|
| PDF | `.pdf` | ✅ Sim (automático via PyMuPDF) |
| Word | `.docx` | ❌ Somente texto |
| Texto | `.txt` | ❌ Somente texto |
| Markdown | `.md` | ❌ Somente texto |

## Verification

- [ ] O arquivo `.apkg` foi criado sem erros
- [ ] Os cards aparecem com imagens corretamente no Anki
- [ ] Formatação HTML (negrito, listas, blocos de código) está renderizando
- [ ] Cards atômicos: cada card tem uma única ideia principal
- [ ] CSS dark mode aplicado (fundo escuro, código verde)

## Common Rationalizations (Anti-padrões)

- ❌ "Vou colocar tudo em um só card" → Quebre em cards atômicos
- ❌ "A imagem não é importante" → Se o conteúdo referencia imagem, ela DEVE estar no card
- ❌ "Vou pular a justificativa" → A justificativa é o que diferencia memorização de entendimento

## Red Flags

- JSON retornado com blocos markdown → o script limpa automaticamente, mas investigue se persistir
- Imagens quebradas no Anki → verifique se a pasta `anki_media/` foi incluída no `.apkg`
- Cards sem resposta → o texto pode estar mal formatado; pré-processe manualmente
