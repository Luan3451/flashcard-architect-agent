---
name: flashcard-architect
description: Especialista em engenharia cognitiva FSRS e geração nativa de baralhos Anki (.apkg) via Antigravity com ancoragem posicional de diagramas, auditoria de simulados e triagem rápida de 5 eixos.
---

# 🧠 Flashcard Architect — Skill (v3.2.0)

## Overview

O **Flashcard Architect** é uma skill oficial para o Google Antigravity projetada para converter materiais de estudo (**PDF, Markdown, DOCX, TXT e JSON**) em baralhos Anki (`.apkg`) otimizados para o algoritmo FSRS com:
- **Ancoragem Espacial Y0**: Vinculação precisa de topologias e diagramas na linha exata da questão correspondente.
- **Indexação Sequencial Global**: Prefixo composto `[Pág. X | QY (Global #Z)]` prevenindo colisão em simulados com baterias particionadas.
- **Filtro de Auditoria Wrong/Correct**: Marcação automática `status::wrong` e geração de relatório analítico `<output>_Relatorio_Auditoria.md`.
- **Preservação Bilíngue (`--lang keep`)**: Preserva termos técnicos oficiais (Cisco, AWS, OAB) no idioma original enquanto gera explicações técnicas completas.
- **100% Nativo no Antigravity**: Opera exclusivamente via `agy` (`gemini-3.8-flash-high`) com zero dependência de APIs externas (sem Google AI Studio).

---

## 📋 Protocolo de Execução

### Etapa 1: Triagem Pré-Voo de 5 Eixos

Quando acionado sem parâmetros explícitos no prompt, apresente o questionário rápido de 5 eixos:
1. **Fidelidade:** `[1]` Curadoria 80/20 (Padrão) \| `[2]` Estrita Literal \| `[3]` Erros/Pegadinhas
2. **Mídias:** `[1]` Sim (Ancoragem Y0 - Padrão) \| `[2]` Não (Modo Turbo Somente Texto)
3. **Filtro:** `[1]` Todas as Questões (Padrão) \| `[2]` Somente Incorretas (`wrong`) \| `[3]` Somente Acertos (`correct`)
4. **Idioma:** `[1]` Preservar Original / Bilíngue (`keep` - Padrão) \| `[2]` Português (`pt`) \| `[3]` Inglês (`en`)
5. **Formato:** `[1]` P/R Clássico Exaustivo (Padrão) \| `[2]` Híbrido com Cloze \| `[3]` Essencial Enxuto

---

### Etapa 2: Linha de Comando Operacional

```bash
python scripts/anki_generator.py \
  --input "<arquivo>" \
  --deck "<nome_do_baralho>" \
  --mode <curated|strict|exam> \
  --filter <all|wrong|correct> \
  --lang <keep|pt|en> \
  --density <essential|high> \
  --style <qa|hybrid> \
  [--media | --no-media] \
  --non-interactive \
  --output "<arquivo_saida>.apkg"
```

---

## 📦 Entrega

- Arquivo `.apkg` pronto para importação no Anki Desktop ou AnkiMobile.
- Relatório de Auditoria `<output>_Relatorio_Auditoria.md` com métricas completas de erros e cobertura.
