# Exam Coach: questões preservadas e explicação guiada

O perfil é uma alternativa opt-in para provas e simulados. Não substitui o modo de cartões atômicos a partir de texto livre: uma questão composta pode exigir um cartão inteiro, enquanto aprender conceitos isolados pede outra estratégia.

## Uso

Prepare uma lista JSON com `id`, `stem`, `options`, `answer` e `source`. O exemplo original e público é [network_cases.json](../benchmarks/network_cases.json). A fonte é um trecho que sustenta a resposta; não é apenas o gabarito. Não use o banco público de exemplos para guardar material pessoal.

```bash
python scripts/exam_coach.py --input minhas_questoes.json \
  --provider ollama --model qwen3:8b --output candidatos.cards.json
# Revise o JSON e seu .audit.json; depois:
python scripts/anki_generator.py --input candidatos.cards.json --no-ai \
  --output revisados.apkg --theme atlas --non-interactive
```

Também aceita os provedores configurados no gerador (`agy`, `openai`, `anthropic`, `claude-cli`) e `--effort high`. Disponibilidade dos modelos e autenticação são pré-requisitos. O perfil não depende do modelo usado no ensaio de CPU para funcionar.

Campos opcionais:

- `exhibit`: texto exato de CLI; o programa preserva linhas e caracteres, sem corrigir comandos.
- `blueprint`: classificação fornecida pelo usuário; não é inventada pela IA nem validada automaticamente contra a certificação atual.
- `highlights`: até oito termos curtos fornecidos explicitamente, realçados apenas na explicação. No máximo oito ocorrências são realçadas por cartão. Não força uma quantidade mínima artificial nem destaca o enunciado.

## Como funciona

A IA recebe uma questão e sua fonte. Retorna conceito, mecanismo didático de causa/efeito, uma citação literal e motivo de revisão, quando necessário. O código monta o cartão: enunciado e alternativas preservados, gabarito no topo e explicação recolhida em `<details>`. O gerador/sanitizador mantém somente classes de destaque conhecidas e remove scripts/atributos ativos.

Cada questão produz exatamente um candidato ou a geração falha explicitamente. IDs duplicados e entrada inválida são rejeitados antes da inferência. O programa marca `REVISAR` para gabarito ausente, resposta que não coincide com uma alternativa ou citação que não aparece literalmente na fonte. Um trecho literal não prova que toda a explicação decorre da fonte; revise contradições e extrapolações. O perfil não interpreta exhibits de imagem.

`--verify` adiciona uma segunda chamada para confrontar a explicação com a fonte. É autocorreção pelo mesmo modelo, não auditoria independente nem garantia de precisão. O padrão é uma chamada por questão. Não exponha/solicite cadeia de pensamento privada; o resultado esperado é uma justificativa didática verificável.

Checkpoints ficam em `.flashcard_cache/exam-coach` e incluem o perfil, prompt, fonte, modelo/provedor, esforço e opção de revisão na chave. `--no-resume` refaz a geração. O relatório de auditoria informa chamadas efetivamente realizadas, cache, tempo, hash da fonte e explicação. Não use o relatório para alegar qualidade sem revisar o conteúdo.

## Fundamentação

- [SuperMemo: formulação do conhecimento](https://super-memory.org/archive/articles/20rules.htm): minimizar a informação por pergunta e reduzir interferência. No perfil de simulado, preservar a unidade da questão é uma escolha específica do produto, não uma alegação de superioridade universal.
- [Self-Refine](https://arxiv.org/abs/2303.17651): revisão iterativa é candidata a melhoria, mas custo e benefício precisam ser medidos na tarefa real.
- [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/): recuperar informação em contextos longos pode falhar; motivação para fontes curtas por questão. Não demonstra desempenho deste perfil nem de todos os modelos atuais.

## Avaliação reproduzível

`benchmarks/run_network_eval.py` compara a geração direta existente, o perfil guiado e o guiado com revisão, com os mesmos casos. O resultado guarda respostas reais, tempo e número de chamadas. O modo `--llama-url` serve somente para ensaios de CPU em servidor loopback; o perfil de produção usa os provedores do gerador. Não é necessário expor uma porta pública.

```bash
python benchmarks/run_network_eval.py --provider ollama --model qwen3:8b \
  --output meus_resultados.json
```

Use fontes e questões novas para um conjunto separado antes de tomar decisões de produção. Separe métricas de formato (contagem, preservação, HTML) de qualidade semântica (precisão, causalidade, clareza, cobertura) e de aprendizagem (retenção, que exige estudo longitudinal). Um pequeno ensaio não permite declarar equivalência com GPT nem liderança de mercado.

Resultados de geração real, falhas observadas e decisão de arquitetura: [avaliação 4.2](AVALIACAO_EXAM_COACH.md).
