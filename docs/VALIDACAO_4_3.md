# Validação da versão 4.3 experimental

Execução local em 23/11/2026: **141 testes passaram**, incluindo regressões das versões anteriores. Python 3.11, backend `anki==26.9.4`, coleções temporárias criadas pelos testes; nenhum perfil ou baralho pessoal foi aberto.

## Evidência verificável

- `tests/test_bridge_security.py`: servidor HTTP real em loopback; token, Origin, Host, cabeçalhos duplicados, JSON ambíguo, limites, expiração, replay, recusa de autoaprovação, orçamento acumulado, cancelamento, falhas e redirecionamentos no legado. Processo MCP stdio executado com `python -S`, sem SDK/site-packages.
- `tests/test_native_bridge_integration.py`: APIs reais do backend Anki, criação de coleção temporária, prévia sem escrita, destaque, exclusão, backup e restauração via importação; outro deck preservado; modelo compartilhado bloqueado; revogação antes de chamadas; estado `is:due` e agendamento preservados no planejamento. Pacote reproduzível e conteúdo distribuído comparado com fontes atuais.
- `tests/test_addon_host.py`: pacote próprio instalado em pasta temporária, HTTP e backend reais; recusa não escreve, confirmação aceita produz backup e alteração. Dispatcher, operações Qt e decisão da janela são simulados.
- `tests/test_study_planner.py`: correspondência literal, ambiguidades, idiomas declarados, referências, pesos, prioridade de revisões vencidas, temas sem cobertura, metadados inválidos e ausência de mutação da entrada.
- CI: matriz Python 3.11/3.13 para a suíte geral e job separado com backend Anki instalado para os testes de recuperação, integração nativa e contrato do host.

## Limites

Não foi realizado teste visual do Anki Desktop, Windows/macOS, múltiplas versões reais do Qt, cliente MCP comercial específico ou auditoria independente. O pacote permanece experimental. A ausência de falhas nesses testes não prova ausência de vulnerabilidades ou transação atômica de todo o lote.

As referências de pesquisa e seus limites estão em [STUDY_PLANNER.md](STUDY_PLANNER.md). Não houve estudo de retenção, teste de aprovação em prova ou nova avaliação comparativa de modelos de linguagem nesta versão: as mudanças são de integração, controles e planejamento determinístico. Dados e conversas pessoais não integram os exemplos nem a avaliação pública.
