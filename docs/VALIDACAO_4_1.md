# Registro de validação — 4.1 experimental

Data: 12/11/2026. Ambiente Linux, Python 3.12; testes sem dados pessoais.

## Testes reais adicionais à suíte

- Piper 1.8.0 com pesos `pt_BR-faber-medium`: sintetizou a resposta “O sistema DNS traduz nomes de domínio em endereços de rede.”. O gerador produziu APKG com WAV incorporado; FFmpeg decodificou o arquivo com sucesso.
- faster-whisper 1.2.1, CTranslate2 4.9.0, tiny multilíngue local, CPU int8: transcreveu o WAV com timestamp 0–3,5 s. A saída confundiu **DNS com DNA** e perdeu palavras. Isso confirma o fluxo técnico, mas também a necessidade de revisão humana; não é benchmark de qualidade. Para uso real, testar small/medium e idioma explícito.
- PyAV 19.0.2 quebrou a transcrição (`metadata_errors` removido). Corrigido com dependência `av>=11,<19`; teste real passou com 18.1.0.
- Anki backend 26.9.4: coleção temporária com nota, mídia e cartão revisado; exportação APKG com scheduling, exclusão e importação em outra coleção. Campos, mídia, intervalo de 12 dias e 7 revisões foram recuperados. A importação precisa habilitar `with_scheduling`; sem isso, o intervalo foi reiniciado. O teste fica em `tests/test_anki_backup_integration.py` e em job separado do CI.

## Suíte automatizada

Testa geração existente, TTS com voz simulada/cache e pacote, ASR com modelo simulado/timestamps, FFmpeg com arquivo válido e corrompido, nomes de mídia inseguros, isolamento de decks, notas compartilhadas, CSS compartilhado, realce sem destruir Cloze/áudio, plano adulterado/desatualizado, falha de backup, alterações durante backup e falha parcial com journal. Testes do Anki real são opcionais localmente (`requirements-test-anki.txt`) e obrigatórios no job recovery.

## Ainda não validado

Anki Desktop com o add-on ativo, AnkiDroid/AnkiMobile, RTX 4060, desempenho de lotes longos, renderização visual dos temas em modelos personalizados, restauração sobre perfil original modificado e qualidade de ASR/TTS em corpus de aulas. Não há garantia de compatibilidade de áudio em todos os dispositivos. A suíte de manutenção simula o transporte do AnkiConnect; o backend real testa o formato de backup separadamente.

Não há rollback distribuído, exclusão semântica por LLM, gravação de microfone nem tutor de voz. Essas funções permanecem futuras.
