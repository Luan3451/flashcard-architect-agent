---
name: flashcard-architect
description: Fluxo portátil de produção de flashcards Anki (.apkg) com agentes ChatGPT, Claude e Antigravity; geração offline de JSON; PDFs com recortes geométricos e tema selecionável.
---

# Flashcard Architect — Portable Skill v4

Para geração local, execute `python scripts/anki_generator.py`. Não instale dependências automaticamente. Consulte `README.md`.

O fluxo possui **sete eixos** distintos: fidelidade, imagens, filtro de acertos, idioma, densidade, **tema visual** e **provedor**. Pergunte somente o que o usuário ainda não tiver especificado.

| Tema | Quando usar |
| --- | --- |
| `studio` | Estudo técnico geral; escuro e estruturado |
| `atlas` | Redes, anatomia, esquemas e diagramas grandes |
| `paper` | Leitura de textos, legislação e estudo diurno |
| `contrast` | Maior separação visual e legibilidade |

| Provedor | Flag | Pré-requisito |
| --- | --- | --- |
| Antigravity | `--provider agy` | `agy` autenticado e com sandbox |
| OpenAI | `--provider openai` | Variável `OPENAI_API_KEY` |
| Anthropic | `--provider anthropic` | Variável `ANTHROPIC_API_KEY` |
| Claude Code | `--provider claude-cli` | CLI autenticado, sem ferramentas habilitadas |
| ChatGPT/Claude web | `--extract-only` e `--no-ai --source-media material.pdf` | JSON de cartões salvo localmente |

Para imagens, o pipeline extrai bitmaps por ocorrência, grupos vetoriais renderizados em alta definição e coordenadas `bbox`. Associação incerta NÃO autoriza inventar correspondência; reporte `media_unused` e use `--strict-media` quando cobertura total for obrigatória.

O formato de cartões é array JSON: `[{"id_conceito":"...", "pergunta":"...", "resposta":"...", "tags":["..."]}]`. As imagens são referenciadas por `<img src="fa_[hash].webp">` e só são anexadas se estiverem na lista de mídias extraídas.

Após exportar, mostrar nome do arquivo, tema, número de cartões e mídias utilizadas; indicar que a fidelidade semântica de imagens deve ser validada visualmente no Anki.
