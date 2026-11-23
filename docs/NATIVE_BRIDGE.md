# Ponte nativa e MCP próprios — 4.3 experimental

Esta versão oferece um add-on próprio para o **Anki Desktop** e um servidor MCP stdio escrito com a biblioteca padrão do Python. Não requer AnkiConnect, Node.js, SDK MCP ou instalação de pacotes para o transporte/planejador. O Anki Desktop e suas APIs/Qt são requisitos do add-on; as dependências existentes de geração, OCR e áudio continuam opcionais/independentes desse caminho.

O transporte HTTP local do add-on é uma API privada do projeto. **Não é** uma implementação de MCP Streamable HTTP. O MCP atende via stdio e anuncia a revisão **2025-11-25**, com `initialize`, `ping`, `tools/list` e `tools/call`. É um subconjunto deliberado, sem OAuth remoto, SSE, recursos ou escrita direta por ferramentas.

## Instalação

1. Baixe [flashcard_architect_bridge.ankiaddon](../addons/flashcard_architect_bridge.ankiaddon) do repositório. No GitHub, use o botão de download do arquivo.
2. No Anki Desktop, abra **Ferramentas → Complementos → Instalar a partir de arquivo** e selecione o pacote; reinicie o Anki.
3. Na lista de baralhos, abra **Ferramentas → Flashcard Architect — iniciar ponte segura** e selecione **um deck**. O escopo inclui seus subdecks.
4. O Anki mostrará o caminho de `user_files/session.json`. Esse arquivo contém um token: **não o compartilhe nem coloque no repositório**.
5. Use a opção **5** de `python scripts/interface.py`, ou o cliente abaixo. A opção 2 permanece como caminho legado AnkiConnect.

Para construir o pacote a partir do código, basta Python:

```bash
python scripts/build_native_addon.py --output minha_ponte.ankiaddon
```

O pacote contém somente módulos próprios e manifest. O build é reproduzível e não inclui credenciais, modelos ou dados de estudo. O add-on não inicia sozinho ao abrir um perfil.

## Usar a API pelo cliente

```bash
python scripts/bridge_client.py --session-file /CAMINHO/PRIVADO/session.json list-decks
python scripts/bridge_client.py --session-file /CAMINHO/PRIVADO/session.json preview \
  --action highlight --term OSPF
python scripts/bridge_client.py --session-file /CAMINHO/PRIVADO/session.json apply \
  --plan-id ID_RETORNADO_PELA_PREVIA
python scripts/bridge_client.py --session-file /CAMINHO/PRIVADO/session.json status \
  --plan-id ID_RETORNADO_PELA_PREVIA
```

`apply` abre no Anki uma janela de confirmação com plano completo em texto simples. Não edite/revise/sincronize durante a operação. Feche Browser e editores antes de aplicar. A API não aceita `approved`, SQL, código, caminhos de backup ou um corpo arbitrário de alterações. Confirmar pelo terminal não substitui a janela do Anki.

Ações: destacar termos, estilizar e remover notas por termos explícitos. O caminho nativo não oferece classificação semântica de exclusão nem remoção automática de áudio, rating, sync, importação, instalação de add-ons ou alterações de agendamento. Não fragmenta operações automaticamente para contornar limites.

## Conectar um cliente MCP

Exemplo de configuração, adaptando os caminhos para seu computador:

```json
{
  "mcpServers": {
    "flashcard-architect": {
      "command": "python",
      "args": [
        "/CAMINHO/DO/PROJETO/scripts/anki_mcp.py",
        "--session-file",
        "/CAMINHO/PRIVADO/session.json"
      ]
    }
  }
}
```

Ferramentas expostas: `anki_list_decks`, `anki_read_notes`, `anki_preview_maintenance` e `study_plan`. **Não há ferramenta `apply`**, rating, suspensão ou sincronização. Um texto malicioso em uma nota não pode criar essas ferramentas ou autorizar a janela local. O cliente de IA ainda pode enviar os resultados das leituras ao provedor dele: escolha o deck/cliente conforme a privacidade do material.

Sem `--session-file`, o MCP só consegue usar o planejador com dados fornecidos pelo próprio cliente. Nenhuma porta MCP é aberta. A API nativa fica exclusivamente em `127.0.0.1:8766`; a porta não é encaminhada automaticamente.

## Controles implementados

| Fronteira | Controle |
| --- | --- |
| Rede | Bind fixo em loopback; Host exato; rejeita qualquer Origin de navegador, CORS/preflight e redirecionamentos; não usa proxies |
| Credencial | Token aleatório por sessão; comparação resistente a diferenças de tempo; nunca na linha de comando, resposta MCP ou logs HTTP |
| Sessão | Ativação manual, um perfil/deck, até uma hora; encerrar/reabrir o perfil revoga a sessão. Revogação é conferida antes de cada chamada nativa |
| Mensagens | Limites de corpo/linha (256 KiB), resposta (4 MiB), leitura de socket (5 s) e taxa (60 pedidos/minuto); rejeita chaves JSON/cabeçalhos ambíguos e valores não finitos |
| Planos | Armazenados no servidor, ID aleatório, TTL de 5 minutos e até 20 prévias por sessão; não recebe um plano alterável do cliente |
| Aplicação | Consentimento local; comparação do estado real antes e depois do backup; plano consumido uma vez; sem repetição automática após falhas |
| Volume | Até 200 cartões no escopo, até 50 notas afetadas acumuladas por sessão e exclusão de no máximo 25% das notas do plano; operações incertas também consomem orçamento |
| Isolamento | Notas com cartões fora do deck e modelos compartilhados são bloqueados; cartões de decks filtrados exigem manutenção manual |
| Backup | APKG com mídia, configuração e agendamento; CRC/SHA-256 verificados antes de escrever; snapshots e journal locais |
| Anki | APIs oficiais no processo do Anki, `QueryOp`/`CollectionOp` serializados; sem SQL direto na coleção aberta |

No POSIX, o cliente confere dono/permissões 600, rejeita symlinks e usa abertura sem seguir symlink quando o sistema suporta. No Windows, a privacidade depende também das ACLs da pasta do perfil; não foi validada nesta entrega. O timeout de confirmação/operação é de 120 segundos; timeout de uma operação em andamento é **incerto**, não prova que nada ocorreu.

Backups ficam em `user_files/backups/` dentro da pasta do add-on. Para recuperar, siga as instruções de [manutenção experimental](EXPERIMENTAL.md#recuperação), incluindo importar agendamento. Após falha, examine `status` enquanto o plano ainda estiver válido e os arquivos `manifest.json`/`journal.json`. Encerrar uma sessão não desfaz escritas já concluídas. Não existe transação única envolvendo todo o lote e o filesystem.

A sessão expirada continua recusando pedidos; use **encerrar ponte** e depois iniciar novamente para renovar. Não habilite túneis ou bind público. Estes controles não isolam malware/processos com as mesmas permissões do usuário no sistema operacional e não substituem backup integral da coleção.

## Inspiração e diferenças

Consultamos o catálogo e a documentação do [AnkiMCP](https://github.com/ankimcp/anki-mcp-server), mas não copiamos sua implementação nem o empacotamos. Em vez de expor dezenas de operações, esta ponte concentra-se em leitura e prévias, com confirmação nativa para o subconjunto de manutenção implementado.

As precauções de rede seguem os princípios da [especificação MCP de transportes](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports). A execução usa os mecanismos de [operações em background do Anki](https://addon-docs.ankiweb.net/background-ops.html). Compatibilidade com um cliente MCP específico e uma versão do Anki deve ser validada localmente antes de usar dados importantes.

## O que foi testado

HTTP real em loopback; rejeição de origem/Host/token/header/JSON; tamanho/taxa/expiração; impossibilidade de um payload autorizar a si próprio; replay, cancelamento, orçamento e backup; processo MCP stdio com `python -S` (sem site-packages); coleções temporárias reais do Anki com edição/exclusão/restauração e isolamento de outro deck.

O contrato de confirmação do host foi exercitado com HTTP e backend Anki reais, mas **dispatcher e janela Qt simulados**. Não foi um teste visual do Anki Desktop, nem validação em Windows/macOS ou auditoria independente de segurança. Por isso o add-on permanece experimental.
