# Flashcard Architect Agent v4 — Portátil, resiliente e com temas originais

**Atualização proposta** para [`Luan3451/flashcard-architect-agent`](https://github.com/Luan3451/flashcard-architect-agent). O motor é independente do serviço de IA e transforma PDF, Markdown, DOCX, TXT e JSON em `.apkg` Anki.

Esta distribuição substitui o motor `scripts/anki_generator.py` v3 e mantém a estrutura de agente e skill, agora com triagem de 7 eixos. Para aplicação manual a partir de um ZIP, veja `APLICAR.md`.

## Instalação

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/anki_generator.py --help
```

Para OCR em PDFs digitalizados, instale adicionalmente `python -m pip install rapidocr-onnxruntime`. A instalação **nunca é feita automaticamente** pelo script. Não é necessário instalar SDKs de OpenAI ou Anthropic, pois o projeto usa `urllib` da biblioteca padrão.

## Provedores de IA

| Provedor | `--provider` | Autenticação | Modelo padrão |
| --- | --- | --- | --- |
| Antigravity CLI | `agy` | `agy` autenticado | `gemini-3.8-flash-high` (ajuste via `--model`, se não existir) |
| OpenAI API | `openai` | `OPENAI_API_KEY` | `gpt-5.4-mini` |
| Anthropic Claude API | `anthropic` | `ANTHROPIC_API_KEY` | `claude-haiku-5-5` |
| Ollama local | `ollama` | Ollama iniciado e modelo baixado | `qwen3:8b` (RTX 4060 8 GB) |
| Claude Code CLI | `claude-cli` | `claude` autenticado | `haiku` |
| ChatGPT/Claude no navegador | **offline JSON** | Nenhuma chave na execução local | Modelo escolhido pelo usuário no chat |

O serviço ChatGPT e a OpenAI API são produtos com credenciais/cobrança separados; a assinatura ChatGPT não fornece automaticamente chave de API. Para rodar no ChatGPT da web sem API, extraia o PDF localmente com `--extract-only`, compartilhe o documento ou os blocos relevantes no chat, peça um array JSON com campos `id_conceito`, `pergunta`, `resposta`, `tags` e referências `<img src="fa_...webp">`, salve em `flashcards.json`, e execute `--input flashcards.json --no-ai --source-media original.pdf` para embutir as imagens no `.apkg`.

As chaves devem ser definidas como **variáveis de ambiente** na máquina, nunca colocadas no código, arquivos versionados ou linha de comando. Os provedores de API enviam os trechos do documento ao serviço escolhido; respeite a confidencialidade do material.

### Recomendação de IA

**Nuvem / Antigravity:** o perfil sugerido é Gemini 3.8 Flash com esforço **`high`**. O projeto mantém o identificador `gemini-3.8-flash-high` já utilizado, mas ele **não foi confirmado nem testado no catálogo do Antigravity**. Use `--model` com o identificador exato disponível na sua conta; o nome comercial e o ID podem ser diferentes. `--effort high` já é o padrão. Instalar a CLI no computador não torna o Gemini um modelo local.

**Local / RTX 4060 de 8 GB:** comece com **Qwen3 8B via Ollama**, tag `qwen3:8b`, na quantização padrão do Ollama. É uma recomendação inicial para português e saída estruturada, não uma garantia de qualidade equivalente ao Gemini. O pipeline envia texto e marcadores das figuras; esses modelos não interpretam visualmente os diagramas neste fluxo.

| Modelo local | Quando escolher | Memória de referência (aproximada) |
| --- | --- | --- |
| **`qwen3:8b` — padrão local** | Equilíbrio inicial entre qualidade e velocidade | RTX 4060 **8 GB**, preferencialmente 16 GB de RAM ou mais |
| `gemma3:12b` | Alternativa para comparar fidelidade e português | 8 GB pode exigir uso parcial da RAM; prefira 12–16 GB de VRAM e 24–32 GB de RAM |
| `qwen3:14b` | Buscar melhor qualidade em material técnico | Prefira 12–16 GB de VRAM (ex.: **4060 Ti 16 GB**) e 32 GB de RAM |
| `qwen3:32b` | Equipamentos com mais memória; mais lento | Prefira 24 GB de VRAM e 48–64 GB de RAM, conforme contexto e quantização |

RTX 4060 e RTX 4060 Ti são placas diferentes. Quantização, contexto, outros aplicativos e uso de CPU/RAM alteram o consumo: as faixas acima não garantem execução inteira na GPU. Sem GPU, o Ollama pode usar CPU, com maior latência. Os modelos locais sugeridos não foram comparados por benchmark neste projeto.

Instale o [Ollama](https://ollama.com/download), inicie o aplicativo (ou `ollama serve`) e baixe apenas o modelo desejado:

```bash
ollama pull qwen3:8b
python scripts/anki_generator.py --input material.pdf --provider ollama \
  --model qwen3:8b --chunk-chars 3000 --timeout 1200 --theme atlas --non-interactive
```

O provedor local usa somente `http://127.0.0.1:11434/api/chat`, sem chave de API e sem fallback para nuvem. O download inicial do modelo requer internet; após o download, a inferência é local. O script não instala Ollama nem baixa modelos automaticamente.

O perfil local solicita JSON estruturado, temperatura 0.2, contexto de 8192 tokens e até 4096 tokens de saída. Para Qwen3, desativa `thinking` para reservar o orçamento aos cartões. **`--effort high` não se aplica ao Ollama**; não representa a mesma configuração de raciocínio do Antigravity. Mantenha lotes pequenos (3000 caracteres) na RTX 4060. Para uma segunda revisão, acrescente `--verify-pass` (mais lento); confira perguntas e gabaritos com a fonte antes de estudar.

Tags consultadas no [catálogo Qwen3](https://ollama.com/library/qwen3) e [Gemma 3](https://ollama.com/library/gemma3). Requer uma versão do Ollama com `/api/chat` e saída estruturada compatíveis.

### Exemplos

```bash
# Antigravity CLI: usa modo sandbox, sem skip-permissions
python scripts/anki_generator.py --input material.pdf --provider agy \
  --model gemini-3.8-flash-high --effort high --theme atlas --non-interactive

# OpenAI API: exige OPENAI_API_KEY no ambiente
python scripts/anki_generator.py --input material.pdf --provider openai --model gpt-5.4-mini \
  --theme studio --mode curated --non-interactive

# Claude API: exige ANTHROPIC_API_KEY no ambiente
python scripts/anki_generator.py --input material.pdf --provider anthropic \
  --theme paper --timeout 1200 --non-interactive

# Claude Code CLI: exige instalação/autenticação do aplicativo
python scripts/anki_generator.py --input material.pdf --provider claude-cli \
  --theme contrast --non-interactive

# ChatGPT ou Claude (sem API): 1) extraia um manifesto para usar no chat
python scripts/anki_generator.py --input original.pdf --extract-only --non-interactive
# 2) salve o JSON gerado pelo chat em flashcards.json e anexe imagens extraídas
python scripts/anki_generator.py --input flashcards.json --no-ai --source-media original.pdf \
  --theme atlas --non-interactive
```

> Nota: os comandos acima demonstram integração, mas **não foram testados com contas reais nem servidores de IA** neste ambiente. IDs de modelos podem variar conforme o plano e a data.

## Escolha de design na triagem inicial

O assistente pergunta, nesta ordem:

1. Modo de conteúdo: curadoria, literal ou análise de erros.
2. Imagens: ativadas ou desativadas.
3. Filtro: todas, erradas ou corretas.
4. Idioma: original + explicação em PT, PT ou EN.
5. Densidade: alta ou essencial.
6. **Tema visual:** Studio Pro, Atlas Diagrams, Paper Study ou High Contrast.
7. **Provedor de IA:** Antigravity, OpenAI, Anthropic, Claude CLI ou Ollama local.

Os temas são implementações **originais** inspiradas apenas na possibilidade de personalização do projeto [`pranavdeshai/anki-prettify`](https://github.com/pranavdeshai/anki-prettify), sem reproduzir código ou ativos. Eles incluem layouts responsivos, suporte a imagens grandes, tipografia legível, tema noturno e cartões Basic/Cloze. O Atlas enfatiza diagramas amplos; o Studio é o padrão; Paper facilita leitura diurna e impressão; Contrast enfatiza acessibilidade. Não dependem de JavaScript nem de fontes remotas.

## Qualidade, fidelidade e limitações

- **PDF:** usa PyMuPDF para coordenadas 2D (`bbox`), imagens incorporadas e renderização de grupos vetoriais; as imagens são salvas em WebP **lossless**. Uma mesma imagem usada duas vezes mantém duas referências de posição, mas uma só cópia armazenada.
- **PDF digitalizado:** executa OCR offline se `rapidocr-onnxruntime` estiver instalado; quando não estiver, avisa. OCR pode conter erros que exigem revisão.
- **Qualidade do `.apkg`:** limpa HTML retornado pelo modelo, bloqueia scripts/links de mídia externos, valida nomes de arquivos e só embute imagens referenciadas nos cartões. Adiciona uma imagem automaticamente apenas quando há exatamente uma imagem e um cartão no lote; associação ambígua **não é adivinhada**.
- **Inspeção de mídia:** `--strict-media` exige que todas as imagens detectadas sejam vinculadas; em documentos com logos decorativos, prefira executar sem a flag e revisar o relatório de auditoria.
- **Longa duração:** lotes menores (`--chunk-chars`), `--timeout` configurável, retry com espera crescente e checkpoints em `.flashcard_cache`. Uma falha crítica interrompe a exportação, sem criar baralho parcial silencioso; execute novamente para retomar. `--verify-pass` faz uma segunda consulta de IA para confrontar cartões com a fonte (mais lenta e possivelmente mais cara; não garante correção absoluta).
- **Auditoria:** o arquivo `BARALHO.audit.json` registra contagem de páginas, cartões Basic/Cloze, imagens extraídas/incorporadas e tema/provedor.
- **Privacidade:** `.flashcard_cache` contém trechos transformados em cartões; mantenha a pasta fora do controle de versão e trate-a como material de estudo pessoal.

**Limite técnico importante:** nem o PyMuPDF nem modelos de IA garantem uma correspondência perfeita, milimétrica e semântica para todo tipo de PDF (especialmente documentos digitalizados ou com sobreposição complexa). As coordenadas dos recortes são preservadas para auditoria, e a transformação em WebP é sem perdas de pixel. A associação à questão é verificada por referência, mas o usuário ainda deve revisar diagramas críticos antes de estudar.

## Validação

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

A suíte possui testes para sanitização de HTML, chunking sem sobreposição, temas e Cloze, imagens lossless, figuras repetidas no mesmo PDF, extração de gráficos vetoriais, exigência de credenciais e recuperação de checkpoints. O teste de estrutura de `.apkg` exige `genanki` instalado.

## Comparação com a versão original

| Área | v3 | Atualização v4 |
| --- | --- | --- |
| LLM | Antigravity único | Antigravity, OpenAI, Anthropic, Claude CLI, Ollama local e JSON offline |
| Tema | CSS fixo | Quatro temas originais, opção no wizard |
| Diagramas | Imagens baseadas em xref/Y0, WebP com perdas | Imagens por ocorrência, `bbox` 2D, WebP lossless, recortes vetoriais |
| Confiabilidade | Timeout fixo, falha de lote ignorada | Timeout configurável, checkpoint, aborta se incompleto |
| Segurança | `--dangerously-skip-permissions` | Sandbox onde suportado, ferramentas Claude bloqueadas, sanitizador HTML |
| Validação | Sem CI no repositório | Testes `pytest` e GitHub Actions |

## Licença e crédito

O projeto de origem indica MIT. A inspiração para o conceito de temas é atribuída ao `anki-prettify`; nenhum recurso visual ou CSS dele foi copiado.
