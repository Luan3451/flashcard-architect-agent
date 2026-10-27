---
name: flashcard-architect
description: Analisa documentos de estudo (PDF, DOCX, TXT, Markdown) e gera flashcards de alta retenção para o Anki (.apkg), com imagens embutidas, formatação HTML/CSS e saída JSON estruturada.
---

# Flashcard Architect — Skill

## Overview

Transforma qualquer material de estudo em flashcards organizados para o Anki, otimizados para o algoritmo FSRS de repetição espaçada. Gerencia extração de imagens, formatação HTML/CSS dark mode e entrega um `.apkg` pronto para importar.

## When to Use

- Você tem um PDF, DOCX, TXT ou Markdown e quer convertê-lo em flashcards Anki
- Você quer revisar questões que errou em simulados
- Você precisa organizar anotações brutas em cards atômicos (uma ideia por card)
- Você quer que as imagens do documento apareçam embutidas nos flashcards
- Você precisa gerar um `.apkg` com formatação visual profissional

## Process

### Passo 1 — Instalar dependências

```bash
pip install PyMuPDF genanki google-generativeai python-docx
```

### Passo 2 — Configurar

Configure a variável de ambiente com sua chave Gemini:

**Windows:**
```cmd
set GEMINI_API_KEY=sua-api-key-aqui
```

**Linux/macOS:**
```bash
export GEMINI_API_KEY="sua-api-key-aqui"
```

> Obtenha sua API key em: https://aistudio.google.com/app/apikey

### Passo 3 — Executar o script

```bash
python scripts/anki_generator.py --input "C:\Caminho\Para\Seu\Arquivo.pdf" --deck "Nome do Deck" --output flashcards.apkg
```

**Parâmetros CLI:**

| Parâmetro | Obrigatório | Descrição |
|-----------|-------------|-----------|
| `--input` | ✅ | Caminho do arquivo (PDF, DOCX, TXT, MD) |
| `--deck` | ❌ | Nome do deck no Anki (padrão: "Flashcards") |
| `--output` | ❌ | Nome do arquivo de saída (padrão: "flashcards.apkg") |
| `--chunk-size` | ❌ | Páginas por lote no Gemini (padrão: 15) |

O script irá:
1. Detectar o formato e extrair texto + imagens do documento
2. Dividir em lotes e enviar para o Gemini com o system prompt especialista
3. Validar o JSON de cada lote e consolidar os cards
4. Montar o pacote `.apkg` com imagens embutidas e CSS dark mode

### Passo 4 — Importar no Anki

```
Anki → Arquivo → Importar → selecione o .apkg gerado
```

## Prompts Recomendados Após Instalação

Após ativar o agente com `agy agent use flashcard-architect`, use estes prompts:

### 📄 Simulado (PDF) — foco em erros
```
Analise o conteúdo extraído do arquivo simulado_redes.pdf.
Imagens extraídas pelo script: img_p1_0.png, img_p3_1.png, img_p12_0.png.
Foco: SOMENTE as questões que errei (marcadas como ERRADO no texto).
Para cada erro: enunciado completo na frente + resposta correta com justificativa no verso.

[TEXTO EXTRAÍDO]
```

### 📝 Anotações (DOCX/TXT)
```
Transforme estas anotações do documento biologia_celular.docx em flashcards atômicos.
Priorize: definições, processos e exemplos práticos.
Imagem referenciada: mitocondria.png (respiração celular).

[TEXTO EXTRAÍDO]
```

### 🎯 Revisão focada
```
Questões que errei no simulado de Segurança da Informação:
Para cada uma: card com enunciado completo + alternativa correta + justificativa do erro.
Se houver topologia/imagem referenciada, inclua com <img src="...">.

[LISTA DE QUESTÕES ERRADAS]
```

## Formatos Suportados

| Formato | Extensão | Imagens | Observações |
|---------|----------|---------|-------------|
| PDF | `.pdf` | ✅ Extraídas automaticamente | Melhor opção para simulados com figuras |
| Word | `.docx` | ⚠️ Somente texto | Imagens do DOCX não são extraídas nesta versão |
| Texto | `.txt` | ❌ | Ideal para anotações e transcrições |
| Markdown | `.md`, `.markdown` | ❌ | Suporta formatação markdown no input |

## Verification

- [ ] O `.apkg` foi criado sem erros no terminal
- [ ] `agy plugin validate flashcard-architect` retorna ✔
- [ ] Os cards aparecem com imagens no Anki após importar
- [ ] Formatação HTML (negrito, listas, código) renderiza corretamente
- [ ] CSS dark mode aplicado (fundo escuro, texto claro, código verde)
- [ ] Cada card testa uma única ideia (princípio atômico)

## Common Rationalizations (Anti-padrões)

- ❌ "Vou colocar tudo em um só card" → Quebre em cards atômicos
- ❌ "A imagem não é importante" → Se referenciada, DEVE estar no card
- ❌ "Vou pular a justificativa" → Justificativa diferencia memorização de entendimento
- ❌ "Posso formatar em texto simples" → HTML/CSS é obrigatório para legibilidade

## Red Flags

- JSON retornado com blocos markdown (```` ```json ````) → script limpa automaticamente
- Imagens quebradas no Anki → verifique se `anki_media/` foi incluída no `.apkg`
- Cards sem resposta → o texto pode estar mal extraído; verifique o PDF original
- Erro "JSONDecodeError" → o Gemini retornou texto fora do formato; tente reduzir `--chunk-size`
