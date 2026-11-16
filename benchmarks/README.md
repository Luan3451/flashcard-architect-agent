# Ensaios de geração real

Os casos são perguntas sintéticas originais para esta avaliação, não questões copiadas de simulados ou de conversas pessoais. As fontes dentro do JSON são resumos didáticos originais dos conceitos, fornecidos igualmente às estratégias.

Referências técnicas para conferir os gabaritos:

- SSH: [RFC 4253, seção 4](https://www.rfc-editor.org/rfc/rfc4253.html#section-4).
- OSPF: [RFC 2328, seção 9.4](https://www.rfc-editor.org/rfc/rfc2328.html#section-9.4).
- Longest match: [RFC 1812, seção 5.2.4.3](https://www.rfc-editor.org/rfc/rfc1812.html#section-5.2.4.3).
- Trunk: [Cisco — Configuring VLAN Trunks](https://www.cisco.com/c/en/us/td/docs/switches/lan/c9000/lyr2-fwd/vlan/vlan-configuration-guide/configure-vlan-trunks.html).

O runner executa geração real usando os adaptadores do projeto ou um llama-server local. Ele grava saídas sem atribuir nota semântica automaticamente. Testes unitários simulados estão em tests/ e têm outra finalidade.

A estratégia guided_review reutiliza o candidato de guided. Seu tempo e custo incluem a primeira geração mais a revisão; não são uma segunda amostra independente. Semanas de retenção e ganho real de aprendizagem não são medidos aqui.

Não adicione suas questões pessoais nesta pasta pública. Use um diretório privado ignorado pelo Git para corpora, saídas e evidências particulares.

As observações, limites e configuração do ensaio publicado estão em [avaliação 4.2](../docs/AVALIACAO_EXAM_COACH.md).

Replay dos validadores da versão 4.2.1: `python benchmarks/replay_quality.py --output replay_local.json`. Reutiliza 22 respostas arquivadas, sem novas chamadas. Os critérios e os alertas estão documentados em [controle de qualidade](../docs/QUALITY_GATES.md).
