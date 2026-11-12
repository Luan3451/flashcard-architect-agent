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
| Ollama local | `--provider ollama --model qwen3:8b` | Ollama iniciado em 127.0.0.1:11434 e modelo baixado |
| Claude Code | `--provider claude-cli` | CLI autenticado, sem ferramentas habilitadas |
| ChatGPT/Claude web | `--extract-only` e `--no-ai --source-media material.pdf` | JSON de cartões salvo localmente |

Para imagens, o pipeline extrai bitmaps por ocorrência, grupos vetoriais renderizados em alta definição e coordenadas `bbox`. Associação incerta NÃO autoriza inventar correspondência; reporte `media_unused` e use `--strict-media` quando cobertura total for obrigatória.

O formato de cartões é array JSON: `[{"id_conceito":"...", "pergunta":"...", "resposta":"...", "tags":["..."]}]`. As imagens são referenciadas por `<img src="fa_[hash].webp">` e só são anexadas se estiverem na lista de mídias extraídas.

Após exportar, mostrar nome do arquivo, tema, número de cartões e mídias utilizadas; indicar que a fidelidade semântica de imagens deve ser validada visualmente no Anki.

Recomendação de nuvem: Gemini 3.8 Flash no Antigravity com `--effort high`, confirmando o ID na conta (`gemini-3.8-flash-high` é o alias atual, não verificado). Recomendação local para RTX 4060 8 GB: Qwen3 8B via Ollama com `--chunk-chars 3000 --timeout 1200`. Não confunda CLI local com inferência local; `--effort` não se aplica ao Ollama. Consulte alternativas e limites de memória no README.

## Áudio e manutenção — experimentais

A interface `python scripts/interface.py` oferece 1 geração, 2 manutenção e 3 transcrição. Leia `docs/EXPERIMENTAL.md` antes de operar uma coleção real.

Para pedidos como “tirar tudo sobre tema X”, converta a solicitação em termos explícitos e apresente a prévia de `deck_maintenance.py preview`. A correspondência é lexical; não prometa classificação semântica completa. O comando `apply` exige token da prévia e backup APKG com agendamento validado. Não contorne bloqueios de notas/modelos compartilhados. Nunca modifique SQLite diretamente, apague mídia compartilhada ou sincronize automaticamente. Uma falha parcial exige inspeção do journal; não repetir operações destrutivas cegamente.

ASR: `audio_experimental.py` com pesos faster-whisper locais exporta transcrição revisável com timestamps. TTS: gerador com `--experimental-audio --tts-voice voz.onnx --tts-side resposta`. Voz e configuração precisam estar instaladas; dependências opcionais. Revisão textual precede narração. Sempre informar que reprodução em dispositivos e classificação por tema ainda precisam de revisão humana.
