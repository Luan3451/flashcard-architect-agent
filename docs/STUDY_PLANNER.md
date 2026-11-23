# Organização de temas por objetivo — 4.3 experimental

O planejador é determinístico e usa apenas a biblioteca padrão. Ele agrupa notas por uma taxonomia declarada, explica os termos encontrados e propõe uma ordem de estudo. **Não move, exclui, traduz ou avalia cartões, nem altera FSRS ou datas de revisão.**

## Objetivo e idiomas

Use `mode` como `language`, `exam` ou `general`, com `front_language` e `explanation_language` explícitos. Para provas, `reference` é obrigatório: identifique blueprint/material e versão reais. O programa não consulta/atualiza essa referência na internet nem prova aderência a uma certificação.

Os idiomas são declarações, não resultado de um detector. Metadados explícitos incompatíveis excluem o item da sugestão; quando não existem, usa-se o par declarado pelo usuário. Assim não se presume que uma questão em inglês deva ser traduzida nem que idiomas diferentes sejam o mesmo objetivo de estudo.

Exemplo: [study-goal.json](../examples/study-goal.json). Troque a referência sintética por sua fonte real. Para idiomas, defina temas e termos segundo o objetivo — vocabulário, compreensão ou produção — sem esperar que correspondência lexical avalie proficiência ou qualidade da tradução.

```bash
python scripts/study_planner.py --cards examples/study-cards.json \
  --goal examples/study-goal.json --output minha.study-plan.json
```

Ou use a ferramenta MCP `study_plan` com `cards`, `goal` e `limit`. O serviço da ponte também suporta `study_plan` sobre o deck autorizado, preservando os resultados de `is:due` do Anki.

## Algoritmo

1. Remover markup de apresentação e texto de scripts/estilos; normalizar caixa/acentos.
2. Encontrar termos/frases literais nos limites de palavra, respeitando exclusões configuradas. `IP` não casa com `RIP`.
3. Atribuir um tema somente quando existir vencedor único por número de termos distintos encontrados. Empates e ausência de correspondência ficam em `unclassified` para revisão.
4. Informar `matched_terms`, cobertura por tema e `uncovered_topics`, sem confundir quantidade de notas com domínio do conteúdo.
5. Sugerir fila intercalada por alocação ponderada: escolher o tema com menor razão `(selecionados+1)/peso` entre os disponíveis. Itens já vencidos precedem os não vencidos. Isso não estima intervalos de memória.

Limites: 200 registros, 50 temas e 30 termos por tema. A fila sugere **notas**, não a ordem de todos os cartões irmãos. No serviço nativo, uma nota é marcada vencida se algum cartão do escopo estiver em `is:due`; a revisão efetiva continua sendo feita no Anki. No arquivo avulso, o campo `due` precisa ser booleano e fornecido pelo chamador.

Essa abordagem favorece explicabilidade e abstenção. Não é um classificador semântico treinado: sinônimos omitidos, termos que aparecem só em distratores, contexto negativo e sobreposição de temas podem exigir intervenção. Não usar suas classificações para exclusão automática. O identificador do tema é configurado pelo usuário, não uma chave que reconcilia automaticamente fatos contraditórios.

## Embasamento e limites da evidência

- [Dunlosky et al., 2013](https://journals.sagepub.com/doi/10.1177/1529100612453266): revisão que destaca prática de recuperação e prática distribuída; a utilidade de intercalação depende das condições. Sustenta separar a recuperação ativa de mero destaque visual.
- [Spaced Practice on Second Language Learning — meta-análise](https://doi.org/10.1111/lang.12479): resultados favoráveis ao espaçamento variam com tarefa, intervalo de retenção e feedback. Motiva preservar o agendamento e explicitar o objetivo linguístico.
- [Revisão sistemática sobre intercalação e aprendizagem de categorias](https://doi.org/10.1002/rev3.3266): a mistura de categorias pode ajudar discriminação/transferência em condições estudadas, mas não significa que misturar quaisquer temas seja superior.

A fórmula de alocação e as regras lexicais são **decisões de engenharia do projeto**, não algoritmos cuja eficácia pedagógica foi demonstrada nesses artigos. Os testes verificam classificação controlada, abstenção, ponderação, idiomas e preservação do agendamento, não retenção ou aprovação em prova. Para validar aprendizagem, será necessário um estudo longitudinal com usuários.
