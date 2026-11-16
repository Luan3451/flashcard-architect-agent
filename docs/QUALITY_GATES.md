# Controle determinístico de qualidade — 4.2.1

A exportação agora distingue falhas estruturais de alertas que exigem revisão. São verificações locais, sem chamadas adicionais de IA. Não garantem correção factual nem equivalência entre modelos.

## O que impede a exportação

- Registro que não é um objeto, campo obrigatório ausente ou de tipo inválido.
- Pergunta/resposta que fica vazia após a sanitização, incluindo markup vazio, espaços invisíveis e mídia não autorizada. Uma imagem ou áudio registrado pode ser o único conteúdo do campo.
- IDs de conceito repetidos no pacote.
- Cloze simples sem fechamento, resposta oculta vazia ou índice zero.

Um item inválido não é mais descartado silenciosamente para produzir um lote parcial. O lote falha, registra o índice/campo problemático (e o lote, quando a origem é geração por IA) em `.quality.json` e preserva eventual APKG anterior. Na geração por IA, a política de tentativas existente pode solicitar outra saída; se falhar, não compila o lote. Não se deve interpretar a existência de um arquivo antigo como sucesso da execução nova.

## Alertas de Cloze

Detecta resposta repetida no lado da pergunta, incluindo valores curtos como `22` e siglas como `IP`. Considera pistas e respostas de outros índices, mas oculta conjuntamente repetições do mesmo índice. A resposta no verso/Extra não conta como vazamento na frente.

- `{{c1::22}} ... 22` → alerta de possível vazamento.
- `{{c1::DNS}} ... {{c2::DNS}}` → alerta, porque o outro índice fica visível.
- `{{c1::DNS}} ... {{c1::DNS}}` → permitido.
- `{{c2::22}}` sem `c1` → permitido; não se exige numeração contínua.

Clozes aninhados e separadores ambíguos, como um literal IPv6 com `::`, recebem alerta de revisão manual em vez de um veredito baseado numa interpretação parcial de regex. O sistema não renumera nem reescreve Clozes. Isso é uma auditoria textual conservadora, não um parser completo de todas as extensões do Anki. Não detecta pistas conceituais, imagens semanticamente equivalentes ou respostas inferíveis por lógica/gramática.

## Números e unidades no Exam Coach

Confronta os números mencionados em `concept`/`mechanism` com `source`. Uma evidência literal correta não pode mascarar um número novo no restante da explicação.

Exemplos: `2222` ausente na fonte ou `50 s` quando a fonte informa `50 ms` acrescentam motivo de revisão, sem alterar gabarito, fonte ou IDs. `ms`/`msec` são reconhecidos como a mesma unidade; `Mbps` e `MBps` permanecem distintos. Essa checagem não acrescenta chamadas e também é reaplicada a checkpoints.

Limites: comparação lexical de números isolados e um conjunto explícito de unidades. Não valida endereços IP, prefixos CIDR, VLANs escritos junto de siglas, expressões simbólicas, números por extenso ou associação entre parâmetro e valor. Não converte automaticamente `50 ms` em `0.05 s`, nem presume convenção de separador decimal/milhar. Um cálculo correto ou conversão equivalente pode gerar alerta: revisar a derivação ou fornecer a fonte adequada. A presença de um número na fonte não prova que ele foi aplicado ao parâmetro correto.

## Usar os relatórios

```bash
python scripts/anki_generator.py --input cards.json --no-ai \
  --output baralho.apkg --non-interactive
# Bloquear também os alertas:
python scripts/anki_generator.py --input cards.json --no-ai \
  --output baralho.apkg --strict-quality --non-interactive
# Salvar candidatos para corrigir, mesmo com alertas:
python scripts/anki_generator.py --input cards.json --no-ai \
  --output baralho.apkg --strict-quality --review-only --non-interactive
```

O arquivo `baralho.quality.json` contém status `passed`, `review_required` ou `rejected`, contagens, índices dos itens e códigos dos problemas. `package_created` indica se esta execução concluiu a gravação do pacote; em revisão e rejeição ele é falso. `--no-report` suprime a auditoria geral, mas não este diagnóstico de qualidade. Campos, estrutura de modelos e fórmulas de GUID existentes permanecem iguais.

No modo padrão, alertas adicionam a tag `revisar` e permitem o pacote. `--strict-quality` bloqueia o pacote diante de alertas ou de uma tag `revisar` já presente (inclusive do Exam Coach). A barreira é aplicada antes da narração TTS para não gastar processamento com uma exportação já reprovada. `--review-only` permite salvar candidatos com alertas; erros estruturais continuam bloqueados.

Esses relatórios podem conter trechos de respostas e números privados. `*.quality.json` está ignorado pelo Git. Não confundir esses arquivos pessoais com o resultado público do replay, que usa somente fixtures sintéticas já publicadas.

## Identidade e compatibilidade

O agente continua calculando GUID por nome de deck + `id_conceito`; corrigir uma resposta com o mesmo ID não cria uma identidade nova. Nenhuma alteração nos IDs de modelo ou no histórico foi introduzida. Para importações repetidas, forneça IDs persistentes: o fallback de quem omite `id_conceito` ainda depende do texto da pergunta. Esta versão não migra IDs antigos nem modifica coleções abertas no Anki.

Não adotamos a função do relatório que calcula identidade QA a partir da resposta, pois corrigir a resposta mudaria o GUID. Também não escapamos globalmente todo HTML: preservamos o sanitizador e seus elementos permitidos, com testes para comparações `<`/`>` e conteúdo recolhido.

## Validação

- Suíte local: **111 testes passaram**, incluindo 46 casos adicionais de qualidade.
- Pacotes reais gerados e inspecionados em SQLite: bloqueio de campos vazios antes de substituir um APKG, aceitação de `c2`, tag `revisar` em vazamento e manutenção do GUID após correção da resposta.
- Reaplicação dos verificadores às **22 saídas reais de modelo já registradas**, sem nova inferência: zero erros estruturais, quatro registros com alertas. Duas explicações antigas de OSPF mencionam a faixa 1–255 que não estava na fonte curta; o fato pode ser verdadeiro, mas precisa de sustentação no material. Dois registros já indicavam gabarito contraditório e mantiveram a exigência de revisão.

Reproduzir o replay:

```bash
python benchmarks/replay_quality.py --output replay_local.json
```

Os resultados estão em [quality-replay.json](../benchmarks/results/quality-replay.json). Isso valida o pós-processamento das saídas existentes, não representa 22 novas chamadas nem um ganho semântico medido. Não foram alterados prompts, modelos padrão, regras de backup ou autorização da manutenção de decks.
