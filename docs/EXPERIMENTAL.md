# Áudio e manutenção de decks — EXPERIMENTAIS

Estas funções são opt-in. O modo de manutenção opera na coleção aberta no **Anki Desktop**, na mesma máquina, via [AnkiConnect](https://git.sr.ht/~foosoft/anki-connect). Não abra a coleção SQLite diretamente. Não há suporte a manutenção diretamente no AnkiWeb/AnkiDroid.

## Interface: opção 2

```bash
python scripts/interface.py
```

1. Criar cartões com o gerador existente.
2. Manter decks: estilizar, destacar termos, remover por tema ou por áudio inválido.
3. Transcrever aula localmente (experimental).

Instale o AnkiConnect seguindo o projeto oficial, mantenha o Anki aberto e o serviço restrito a `127.0.0.1:8765`. Se usar chave, configure `ANKICONNECT_API_KEY` no ambiente. O cliente usa API legada v6, mantida pelo projeto, sem proxy nem endpoint remoto configurável.

## Fluxo de manutenção

Selecione um deck e uma ação. Subdecks estão incluídos. A interface salva uma prévia em `maintenance_plans/`, mostrando candidatos, campos/CSS propostos e itens bloqueados. **Nada muda até digitar o token exato exibido.** Depois, exporta backups APKG com `includeSched=True` para uma nova subpasta local em `backups/` (ou pasta escolhida). Valida presença, estrutura ZIP, CRC e SHA-256 antes de qualquer escrita.

A pasta contém:

- Um `.apkg` por deck raiz selecionado, com mídia exportada pelo Anki e agendamento solicitado.
- `before.json`: perfil, cartões, campos, modelos e plano original.
- `manifest.json`: nomes dos decks, arquivos e hashes de integridade.
- `journal.json`: operações concluídas e operação pendente em caso de falha.

Feche o revisor e os editores do Anki; não sincronize nem altere a coleção durante a manutenção. O programa compara o perfil, os dados e os arquivos de áudio antes de aplicar, e novamente após o backup. A API não fornece uma transação única para todo o lote: interferências durante as escritas ainda podem causar resultado parcial. Em timeout, a operação pode ter sido executada; **não há repetição automática**.

Backups e prévias contêm material privado. As pastas padrão são ignoradas pelo Git. Se escolher outra pasta, mantenha-a fora do repositório.

### Remover por tema

Exemplo para “tirar tudo sobre OSPF ou BGP”:

```bash
python scripts/deck_maintenance.py preview --deck "Redes" --action remove-topic \
  --term OSPF --term BGP --plan maintenance_plans/redes.json
python scripts/deck_maintenance.py apply --plan maintenance_plans/redes.json \
  --confirm TOKEN_DA_PREVIA --backup-dir backups
```

A busca é por termos/frases explícitos nos campos e tags, sem diferença de caixa/acentos e com limite de palavra. Termos são combinados por OU. Não interpreta semanticamente “tudo que remeta ao assunto” e não envia notas para IA. Acrescente sinônimos e confira a prévia. AnkiConnect exclui **notas e todos os cartões associados**; notas com cartões fora dos decks escolhidos são bloqueadas.

### Remover referências a áudio inválido

```bash
python scripts/deck_maintenance.py preview --deck "Idiomas" \
  --action remove-broken-audio --plan maintenance_plans/audio.json
```

Verifica referências `[sound:...]` e `<audio>/<source>`. Quando Anki remove tags de áudio do HTML renderizado, consulta campos da nota; essa origem fica registrada na prévia. Nota com múltiplos cartões e associação de áudio ambígua é bloqueada. A presença em um campo não garante que o template o reproduza: confira os candidatos.

Detecta arquivo ausente, vazio, sem stream de áudio ou indecodificável localmente. FFmpeg e ffprobe devem estar instalados no PATH; sem eles, formatos existentes ficam como **unknown** e não são removidos. Timeout, arquivo maior que 100 MB e referência remota/insegura também ficam inconclusivos. Não baixa URLs e não apaga arquivos de mídia, que podem ser compartilhados.

Falhar no FFmpeg não prova incompatibilidade em todos os clientes Anki; sucesso não garante reprodução no celular. Áudio silencioso, pronúncia incorreta e voz ruim não são considerados corrupção. Áudio dinâmico por TTS do Anki não é validado por este scanner.

### Estilizar e destacar

`--action style --theme paper` adiciona CSS ao modelo, preservando templates e campos. Se o modelo também é usado fora dos decks escolhidos, a operação é bloqueada; selecione todos os decks envolvidos ou duplique o tipo de nota manualmente no Anki primeiro. Não há troca automática de modelo, para preservar identidade e histórico.

`--action highlight --term DNS --term OSPF` destaca termos explícitos em campos. Preserva atributos, entidades, código, marcações de Cloze e áudio; não decide automaticamente quais conceitos são importantes. O destaque é literal, sem diferença de caixa (inclua variantes com/sem acento quando necessário). Templates muito personalizados precisam de revisão visual. Não é um editor HTML completo.

## Recuperação

1. Pare a manutenção e preserve a pasta de backup. Confira `journal.json`; `failed_or_uncertain` exige verificar o estado real antes de repetir.
2. Abra um **perfil temporário** no Anki e importe o APKG de backup. Habilite a opção de importar/agregar o agendamento (scheduling) e configurações de deck na importação. Verifique cartões, mídia e agendamento antes de mexer no perfil original; sem essa opção, o Anki pode reiniciar os intervalos.
3. Para notas excluídas, importe o backup no perfil original após revisar as opções de atualização/importação do Anki. Para campos/CSS, os valores antigos estão em `before.json`; o pacote também inclui os tipos de nota exportados.
4. Reimportação de APKG não é rollback atômico: notas já existentes, alterações posteriores, IDs e opções de importação podem interferir. Para recuperação integral do perfil, use também o backup nativo de coleção do Anki.

O projeto não faz rollback automático nem sincronização automática. CRC e SHA-256 provam integridade do arquivo exportado, não a correção de todas as opções de importação em cada versão do Anki.

## Transcrever uma aula (ASR experimental)

```bash
python -m pip install -r requirements-audio-asr.txt
python scripts/audio_experimental.py --input aula.wav \
  --model-dir modelos/faster-whisper-small --language pt --output-dir transcripts/aula01
```

Instale previamente pesos compatíveis com CTranslate2/faster-whisper. O adaptador exige pasta local e `local_files_only=True`, sem download automático. CPU/int8 é padrão; `--device cuda` usa int8_float16 e exige runtime CUDA compatível. Referência RTX 4060 8 GB: comece com small e execute ASR e LLM em etapas separadas; não há benchmark de VRAM garantido.

A saída é `transcript.txt` com timestamps e `transcript.json` com segmentos, idioma e SHA-256 do áudio original. Revise nomes técnicos, números e gabaritos, depois gere candidatos:

```bash
python scripts/anki_generator.py --input transcripts/aula01/transcript.txt \
  --provider ollama --model qwen3:8b --review-only --non-interactive
```

Timestamps ficam no contexto; o LLM ainda pode omiti-los nos cartões. Isso não equivale a verificação factual de citações. Transcrição não inclui gravação de microfone, diarização nem tutor de voz nesta versão.

## Narrar cartões (TTS experimental)

```bash
python -m pip install -r requirements-audio-tts.txt
python scripts/anki_generator.py --input revisados.json --no-ai \
  --experimental-audio --tts-voice vozes/pt_BR-faber-medium.onnx \
  --tts-side resposta --output narrado.apkg --non-interactive
```

É necessário o `.onnx` e o `.onnx.json` da voz baixados localmente. Consulte licença da voz e do Piper antes de redistribuir modelos. O exemplo é uma voz, não uma garantia de disponibilidade futura. Não exige serviço externo de inferência.

Gera WAV, valida estrutura e inclui mídia no APKG. Reutiliza áudio por hash de texto + modelo/configuração. Pode narrar pergunta ou resposta; resposta é padrão para evitar revelar gabaritos. Texto de Cloze na face escolhida é rejeitado para revisão manual. Limites: 5000 caracteres por cartão e 500 mil por lote. `--review-only`/`--extract-only` não são combináveis com narração; faça a revisão primeiro.

## Fontes e limites de validação

- [API legada do AnkiConnect](https://git.sr.ht/~foosoft/anki-connect/blob/master/API_LEGACY.md): exportPackage, notesInfo, deleteNotes, modelStyling.
- [API Python do Piper](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md).
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper): transcrição local com CTranslate2.

Os testes automatizados de manutenção usam uma coleção simulada e validam ordem de backup, escopo, comparação de estado, falhas e registros. O teste de decodificação usa FFmpeg real quando disponível. Isso não substitui testes com Anki Desktop/AnkiDroid e modelos reais; consulte o registro de validação da versão.

Resultados observados nesta entrega: [registro de validação 4.1](VALIDACAO_4_1.md).
