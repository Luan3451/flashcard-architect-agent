# Avaliação de geração real: Exam Coach 4.2

Ensaio em 15/11/2026 (America/Sao_Paulo). Foram feitas **22 chamadas reais** a um modelo aberto: 12 na comparação inicial, 7 no perfil ajustado e 3 na repetição de casos reservados com outra seed. Os testes de código são uma evidência separada.

## Ambiente e método

- Qwen3 4B, quantização Q4_K_M, pesos [oficiais](https://huggingface.co/Qwen/Qwen3-4B-GGUF), revisão `bc640142c66e1fdd12af0bd68f40445458f3869b`.
- SHA-256 do GGUF conferido com os metadados do distribuidor: `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`.
- llama.cpp b12359, commit b1b770d90, Linux CPU, dois threads, quota de duas CPUs e 8 GiB de RAM; contexto de 4096 tokens, temperatura 0.2, até 700 tokens de saída e thinking desativado.
- Seed 42; repetição dos três casos reservados com seed 7. Sem credenciais de APIs comerciais, sem GPU. Isso não é um teste de GPT, Antigravity ou Qwen3 8B.
- Quatro questões sintéticas de desenvolvimento: SSH, OSPF DR/BDR, longest-prefix matching e trunk. Mesmas questões, respostas e fontes em todas as estratégias. Três casos reservados foram avaliados após o ajuste: ARP para outro subnet, ordem de ACL e gabarito contraditório. Não são perguntas de conversa privada nem de simulado comercial.
- Conferência semântica feita pelo assistente desenvolvedor, com referência às fontes técnicas do [README do benchmark](../benchmarks/README.md). Não houve avaliador humano independente, revisão cega, teste de retenção ou medição de criatividade. As observações abaixo não são uma nota de um juiz LLM automático.

## Comparação inicial

| Estratégia | Uma saída por questão | Alternativas preservadas | Explicação de mecanismo | Explicação em português | Tempo acumulado, 4 questões |
| --- | --- | --- | --- | --- | --- |
| Prompt padrão `strict/keep/high` | 4/4 | 0/4 | 0/4 | Ausente | 59,2 s |
| Primeiro perfil guiado | 4/4 | 4/4, pelo renderer | 4/4, com falha causal em SSH | 2/4 | 103,9 s |
| Guiado + revisão pelo mesmo modelo | 4/4 | 4/4 | Repetiu as mesmas explicações | 2/4 | 219,5 s |

O padrão respondeu corretamente aos quatro gabaritos, mas produziu só respostas curtas e omitiu as alternativas. Em uma questão também traduziu/reescreveu o enunciado. Isso não é falha de conhecimento sobre a resposta, mas fica distante do produto desejado para revisão de simulados.

O perfil guiado acrescentou conceitos, mecanismos e citações. Contudo, no caso SSH afirmou que o número da porta era essencial à segurança; a criptografia não é causada pelo número da porta. Também escreveu duas explicações em inglês. A revisão devolveu objetos JSON **idênticos em conteúdo nos quatro casos**, sem corrigir esses problemas, a aproximadamente 2,1 vezes o tempo do guiado simples.

## Ajuste e validação

O perfil final (`exam-coach-2`) passou a distinguir convenção de causa, explicitar conflito entre fonte e gabarito e repetir a exigência de português no fim do prompt. Não houve ajuste de pesos. O prompt foi congelado antes da leitura das saídas dos casos reservados.

Nos quatro casos de desenvolvimento, o perfil final preservou pergunta/alternativas e forneceu explicação em português com citação literal em **4/4**. O tempo foi de 120,0 s no total, cerca de duas vezes o padrão, com uma chamada por questão. A falsa causalidade forte de SSH não apareceu na nova resposta. Em roteamento, explicou corretamente por que /24 vence /16 e por que AD não substitui longest-prefix matching.

Nos três casos reservados, com seeds 42 e 7:

- ARP: identificou o gateway como próximo salto e manteve a distinção entre destino MAC local e destino IP remoto. Na seed 7, usou “pacote enviado para o MAC” onde “quadro” seria mais preciso.
- ACL: explicou a primeira correspondência e por que o deny posterior não é avaliado.
- Gabarito SSH deliberadamente errado: sinalizou contradição e exigiu revisão em **2/2 execuções**, sem alterar silenciosamente o gabarito recebido. O renderer final usa “Gabarito fornecido — REVISAR”, em vez de apresentar a resposta duvidosa como correta.

Todas as seis respostas desses casos vieram em português e com evidência literal encontrada. Há problemas de naturalidade e terminologia: “porto” em vez de “porta”, “hospedeira” e a formulação “incompatível com a eleição” em vez de “inelegível”. Portanto, há proximidade estrutural com o padrão de explicação desejado e ganho observável neste pequeno conjunto, mas **não foi demonstrada equivalência geral com modelos comerciais de maior capacidade**.

## Decisão de produto

1. Disponibilizar o perfil guiado como **opção 4**, usando uma questão estruturada e sua fonte por chamada; o modo geral de cartões permanece disponível.
2. Preservar texto e alternativas pelo código, limitar destaques e montar a seção recolhida sem delegar essa fidelidade à IA.
3. Manter uma chamada por questão como padrão. Revisão extra é opt-in: não entregou ganho nos quatro casos iniciais.
4. Retomar resultados por checkpoint para evitar custo de geração repetida. Invalidação por perfil/prompt/fonte/modelo/configuração é testada, mas a economia monetária depende do provedor; não foi medida com APIs pagas.
5. Exportar primeiro candidatos revisáveis e auditoria. Citação literal é um sinal, não verificação semântica. Solicitar revisão em lacunas e conflitos.

## Reproduzir e auditar

As saídas brutas e tempos estão em [benchmarks/results](../benchmarks/results). O arquivo da primeira rodada preserva o prompt inicial em `benchmarks/prompts/exam-coach-1.txt`. Os artefatos mantêm as respostas brutas sem edição. O renderer foi reforçado depois para limitar os destaques e corrigir a rotulagem de respostas em revisão; os textos do modelo não foram reescritos para parecer melhores.

```bash
# Configure seu provedor primeiro. Para repetir com seu Ollama:
python benchmarks/run_network_eval.py --provider ollama --model qwen3:8b \
  --profile initial --output inicial.json
python benchmarks/run_network_eval.py --provider ollama --model qwen3:8b \
  --strategy guided-only --output final.json
python benchmarks/run_network_eval.py --provider ollama --model qwen3:8b \
  --cases benchmarks/heldout_cases.json --strategy guided-only --seed 7 --output reservados.json
```

Para repetir o ensaio com os mesmos pesos GGUF, inicie llama-server local em `127.0.0.1:8767` com a configuração acima e substitua os argumentos de provedor por `--llama-url http://127.0.0.1:8767 --model Qwen3-4B-Q4_K_M`. O modelo não é instalado automaticamente. No Ollama, a seed do runner não é enviada pelo adaptador de produção; a seed/temperatura explícitas desta medição aplicam-se ao modo llama.cpp. Registre as opções do seu servidor ao comparar.

Limites: conjunto pequeno, conteúdo didático fornecido, fontes curtas, dois valores de seed apenas em três casos, revisão não independente e latências sensíveis a cache/ordem. Não mede extração de PDF, figuras, provas extensas, pronúncia, retenção ou capacidade geral de raciocínio. Para escolher definitivamente um modelo, ampliar o corpus e fazer revisão cega com especialistas; este ensaio sustenta a arquitetura e o perfil opcional, não um ranking universal.
