# Flashcard Architect Agent v4 — Portátil, resiliente e com temas originais

**Atualização proposta** para [`Luan3451/flashcard-architect-agent`](https://github.com/Luan3451/flashcard-architect-agent). O motor é independente do serviço de IA e transforma PDF, Markdown, DOCX, TXT e JSON em `.apkg` Anki.

Esta distribuição substitui o motor `scripts/anki_generator.py` v3 e mantém a estrutura de agente e skill, agora com triagem de 7 eixos. **Não foi publicada automaticamente no GitHub:** a integração rejeitou a criação da branch (403). Para aplicar: copie os arquivos do ZIP sobre os arquivos de mesmo nome no seu clone e use uma nova branch; veja `APLICAR.md`.

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
| Claude Code CLI | `claude-cli` | `claude` autenticado | `haiku` |
| ChatGPT/Claude no navegador | **offline JSON** | Nenhuma chave na execução local | Modelo escolhido pelo usuário no chat |

O serviço ChatGPT e a OpenAI API são produtos com credenciais/cobrança separados; a assinatura ChatGPT não fornece automaticamente chave de API. Para rodar no ChatGPT da web sem API, extraia o PDF localmente com `--extract-only`, compartilhe o documento ou os blocos relevantes no chat, peça um array JSON com campos `id_conceito`, `pergunta`, `resposta`, `tags` e referências `<img src="fa_...webp">`, salve em `flashcards.json`, e execute `--input flashcards.json --no-ai --source-media original.pdf` para embutir as imagens no `.apkg`.

As chaves devem ser definidas como **variáveis de ambiente** na máquina, nunca colocadas no código, arquivos versionados ou linha de comando. Os provedores de API enviam os trechos do documento ao serviço escolhido; respeite a confidencialidade do material.

### Exemplos

```bash
# Antigravity CLI: usa modo sandbox, sem skip-permissions
python scripts/anki_generator.py --input material.pdf --provider agy --theme atlas --non-interactive

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
7. **Provedor de IA:** Antigravity, OpenAI, Anthropic ou Claude CLI.

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
| LLM | Antigravity único | Antigravity, OpenAI, Anthropic, Claude CLI e JSON offline |
| Tema | CSS fixo | Quatro temas originais, opção no wizard |
| Diagramas | Imagens baseadas em xref/Y0, WebP com perdas | Imagens por ocorrência, `bbox` 2D, WebP lossless, recortes vetoriais |
| Confiabilidade | Timeout fixo, falha de lote ignorada | Timeout configurável, checkpoint, aborta se incompleto |
| Segurança | `--dangerously-skip-permissions` | Sandbox onde suportado, ferramentas Claude bloqueadas, sanitizador HTML |
| Validação | Sem CI no repositório | Testes `pytest` e GitHub Actions |

## Licença e crédito

O projeto de origem indica MIT. A inspiração para o conceito de temas é atribuída ao `anki-prettify`; nenhum recurso visual ou CSS dele foi copiado.
