# Evolução aberta do Flashcard Architect

Pesquisa: 12/11/2026. Seleção técnica de candidatos, não ranking absoluto de mercado. Não houve benchmark comparativo em GPU. Nenhum código desses projetos foi copiado nesta mudança.

## Referências e decisões

| Projeto / fonte primária | Aplicação proposta | Licença / cuidados |
| --- | --- | --- |
| [Anki](https://docs.ankiweb.net/manual/deck-options) e [FSRS](https://github.com/open-spaced-repetition/fsrs4anki) | Usar agendamento nativo do Anki, manter identidade de notas nas atualizações e separar geração de revisão | fsrs4anki MIT; a licença varia entre implementações. Não reimplementar o agendador neste gerador |
| [Docling](https://github.com/docling-project/docling) | Adaptador opcional para documentos com tabelas e layout complexo, preservando estrutura | Código MIT; pesos possuem licenças próprias |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Transcrição local de aulas com timestamps; texto revisável antes da geração | Código MIT; verificar pesos e dependências ao distribuir |
| [Piper](https://github.com/OHF-Voice/piper1-gpl) | Narração local de perguntas e respostas, especialmente PT-BR | Linha atual GPL; verificar licença de cada voz. Integração/distribuição exige análise própria |

A prioridade inferida dessas referências é confiabilidade da fonte e controle do estudante. Aumentar a quantidade de cartões sem medir fidelidade pode piorar a aprendizagem.

## Entregue nesta etapa

- `--review-only`: gera um arquivo `.cards.json` editável, sem criar `.apkg`. O JSON pode ser reimportado com `--no-ai`.
- Bloqueio de IDs de conceitos repetidos na exportação, para evitar notas com a mesma identidade.
- Na etapa inicial deste roadmap, áudio e voz eram propostas. A versão 4.1 acrescenta ASR/TTS e manutenção experimentais: veja [guia e limites](EXPERIMENTAL.md). Docling e tutor de voz continuam propostos.

## Arquitetura de destino (proposta)

Entrada → documento estruturado → trechos com evidências → cartões candidatos → revisão → pacote Anki.

O futuro documento estruturado deve conter `document_sha256`, `segment_id`, texto e localização. Localização pode ser página/bbox em PDF ou início/fim em milissegundos em áudio. Cada cartão deve referenciar um ou mais segmentos; citação fornecida pela IA precisa ser comparada à fonte, não aceita automaticamente.

Separar adaptadores de extração, provedores de IA, validação, mídia e exportação. Usar contratos versionados e migrações; manter IDs e modelos Anki estáveis para preservar histórico. Guardar transcrições e áudio apenas em diretório local ignorado pelo Git. Dependências pesadas serão extras opcionais.

## Ordem sugerida e critérios de aceitação

1. **Qualidade e evidências:** corpus público/licenciado com texto, PDF em duas colunas, tabelas, questões e português. Medir precisão de gabaritos, cobertura, duplicatas, cartões sem fonte e associação correta de imagens. Exigir revisão humana independente; pontuação dada pelo próprio LLM não é prova.
2. **Documento estruturado:** experimentar Docling contra PyMuPDF no mesmo corpus. Aceitar somente se melhorar ordem de leitura/tabelas com consumo de memória e tempo documentados. Fallback explícito, nunca silencioso.
3. **Revisor visual:** editar, excluir e aprovar candidatos lado a lado com fonte; mostrar imagens e alertas. Prévia sem executar HTML/JavaScript do documento. Exportar somente itens aprovados e testar round-trip preservando IDs.
4. **Aulas para cartões:** adaptador faster-whisper com detecção de fala, segmentos e timestamps; revisão da transcrição e do gabarito antes da exportação. Não assumir que silêncio ou fala incompreensível contém conteúdo. Medir WER/CER, termos técnicos e alinhamento usando gravações autorizadas de referência.
5. **Cartões falados:** adaptador TTS opcional, cache por hash de texto/voz/configuração, arquivos locais e referências `[sound:...]` validadas. Escolher vozes pela licença e inteligibilidade em PT-BR; testar reprodução no Anki Desktop e mobile. Limitar duração e tamanho por baralho.
6. **Tutor de voz:** pergunta falada → resposta oral → transcrição editável → avaliação com evidência → feedback. Estudante confirma a classificação antes de afetar o histórico. Latência, ruído e sotaque entram no benchmark; não vender pontuação de transcrição como avaliação de conhecimento.
7. **Integração contínua com Anki:** sincronização opcional com revisão de diff e backup, sem sobrescrever histórico. Preferir FSRS nativo; medir retenção em estudo longitudinal antes de alegar ganho de aprendizagem.

## Referência de hardware e entrega

RTX 4060 8 GB: executar LLM, OCR e ASR de forma sequencial, descarregando pesos entre fases. Testar CPU fallback, consumo máximo de VRAM, tempo por página/minuto e cancelamento com retomada. Não prometer execução simultânea de todos os modelos na GPU.

Cada fase deve ter fixtures pequenas licenciadas, testes offline de contratos, avaliação real separada e uma matriz de compatibilidade. Publicar resultados, versões dos modelos, quantização e limites. “Livre para usar”, “código aberto” e “pesos abertos” não são sinônimos; conferir cada componente antes de empacotar.
