---
name: flashcard-architect
description: Analisa documentos de estudo (PDF, DOCX, TXT, Markdown) e gera flashcards de alta retenção para o Anki (.apkg), com imagens embutidas, formatação HTML/CSS dark mode e saída JSON estruturada. 100% nativo no Antigravity CLI/IDE/APP com Gemini 3.8 Flash (High), sem requerer APIs externas.
---

# Flashcard Architect — Skill

## Overview

O **Flashcard Architect** transforma materiais de estudo (PDFs de simulados, anotações em Markdown com anexos, documentos DOCX e resumos) em baralhos completos `.apkg` para o Anki.

Diferenciais da versão 3.0:
- **100% Nativo no Antigravity**: Não requer chaves de API externas (como Google AI Studio ou `GEMINI_API_KEY`).
- **Modelo Prioritário**: Opera nativamente com **Gemini 3.8 Flash (High reasoning effort)**.
- **Coleta Inteligente de Anexos**: Extrai imagens de PDFs e localiza referências `![alt](img)` em Markdown e diretórios de anexos automaticamente.
- **Empacotamento Automático**: Gera o `.apkg` pronto para importação com mídias embutidas e estilização Dark Mode profissional para o algoritmo FSRS.

## When to Use

- Você tem um PDF, DOCX, TXT ou Markdown e quer convertê-lo em flashcards Anki
- Você quer revisar questões que errou em simulados ou provas anteriores
- Você tem anotações em Markdown com diagramas e capturas de tela e deseja embuti-los no Anki
- Você quer gerar flashcards atômicos (uma ideia por card) com Active Recall e justificativas claras
- Você quer executar toda a esteira dentro do Antigravity APP, Antigravity IDE ou Antigravity CLI

## Process

### Passo 1 — Instalar dependências locais do Python

Para extração de documentos e geração do pacote `.apkg`:

```bash
pip install PyMuPDF genanki python-docx
```

*(Nenhuma biblioteca externa de API como google-generativeai é necessária).*

### Passo 2 — Execução

#### Modo 1: Via Antigravity CLI (`agy`) com Script Automatizado

O script utiliza nativamente o `agy` em segundo plano com o Gemini 3.8 Flash High:

```bash
# Markdown com imagens e pasta de anexos:
python scripts/anki_generator.py --input "resumo.md" --attachments "./anexos" --deck "Meu Baralho" --output baralho.apkg

# PDF de simulado:
python scripts/anki_generator.py --input "simulado.pdf" --deck "Simulado Redes" --output simulado.apkg

# Documento DOCX:
python scripts/anki_generator.py --input "anotacoes.docx" --deck "Bio Celular"
```

**Parâmetros do CLI:**

| Parâmetro | Obrigatório | Padrão | Descrição |
|-----------|-------------|--------|-----------|
| `--input`, `-i` | ✅ Sim | - | Caminho do arquivo (PDF, DOCX, MD, TXT, JSON) |
| `--deck`, `-d` | ❌ Não | "Meu Baralho Antigravity" | Nome do deck no Anki |
| `--output`, `-o` | ❌ Não | "flashcards.apkg" | Caminho do arquivo `.apkg` de saída |
| `--attachments`, `-a` | ❌ Não | None | Pasta com imagens e anexos extras |
| `--model`, `-m` | ❌ Não | `gemini-3.8-flash-high` | Modelo do Antigravity |
| `--effort`, `-e` | ❌ Não | `high` | Nível de raciocínio (low, medium, high, max) |
| `--chunk-size`, `-c` | ❌ Não | 10 | Páginas/seções por lote |
| `--no-ai` | ❌ Não | False | Modo offline direto para JSON pré-estruturado |

#### Modo 2: Diretamente no Antigravity APP ou Antigravity IDE

1. Abra o painel de chat no Antigravity.
2. Ative o agente ou mencione `@flashcard-architect`.
3. Anexe ou indique o caminho do seu PDF ou Markdown de estudo.
4. O Antigravity processará o conteúdo, estruturará os cards e gerará o arquivo `.apkg` no workspace.

### Passo 3 — Importar no Anki

```
No Anki: Arquivo → Importar → selecione o arquivo .apkg gerado
```

## Formatos e Suporte a Imagens

| Formato | Extensão | Tratamento de Imagens | Detalhes |
|---------|----------|-----------------------|----------|
| PDF | `.pdf` | ✅ Automático (PyMuPDF) | Extrai figuras, esquemas e gráficos por página |
| Markdown | `.md`, `.markdown` | ✅ Automático + Anexos | Detecta `![alt](img)` e `<img src="img">`, coletando na pasta do MD ou `--attachments` |
| Word | `.docx` | ✅ Automático | Extrai imagens embutidas no documento |
| Texto | `.txt` | ✅ Via `--attachments` | Associa imagens da pasta de anexos |
| JSON | `.json` | ✅ Embutidas | Empacotamento direto offline sem requerer IA |

## Prompts Recomendados no Antigravity

### 📄 Simulado PDF com Imagens
```
Analise o PDF simulado_concurso.pdf com foco nas questões erradas.
Mapeie os diagramas e esquemas para a frente dos cards e inclua a justificativa técnica no verso.
Gere o baralho com layout Dark Mode para o Anki.
```

### 📝 Markdown com Diagramas e Anexos
```
Transforme meu arquivo resumo_redes.md em flashcards atômicos.
Colete as imagens referenciadas na pasta ./anexos e vincule-as aos respectivos cards.
Use o modelo Gemini 3.8 Flash High para estruturar as perguntas em active recall.
```

## Verification

- [ ] Arquivo `.apkg` gerado com sucesso
- [ ] Mídias e imagens embutidas no arquivo ZIP interno do `.apkg`
- [ ] CSS Dark Mode aplicado (`#1e1e1e`, texto claro, código em verde `#4af626`)
- [ ] Cada card segue o princípio atômico (uma ideia central por card)
- [ ] Ausência total de dependência de `GEMINI_API_KEY` ou Google AI Studio
