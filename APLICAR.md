# Aplicar a atualização no repositório

O acesso do ChatGPT conseguiu ler o repositório, mas a tentativa de criar uma branch retornou `HTTP 403 Resource not accessible by integration`. Esta atualização foi preparada localmente; **não está no GitHub**.

1. Baixe o ZIP desta conversa e extraia os arquivos.
2. Abra um terminal no clone local de `Luan3451/flashcard-architect-agent`.
3. Crie uma branch: `git checkout -b feat/flashcard-architect-v4`.
4. **Faça backup** de `scripts/anki_generator.py`, `README.md`, `agents/flashcard-architect.md`, `skills/flashcard-architect/SKILL.md` e `plugin.json` se tiver modificações locais.
5. Copie o conteúdo da pasta extraída para a raiz do clone, substituindo os arquivos de mesmo nome. Não apague arquivos antigos não incluídos no ZIP.
6. Instale dependências e execute `python -m pytest -q`.
7. Teste com um PDF real e confira o relatório `.audit.json`, a visualização das imagens e os cartões no Anki antes de mesclar.
8. Faça commit e abra um pull request (`git add . && git commit -m "feat: portable LLM providers, geometry and Anki themes"`).

Não execute comandos sobre material de estudo sensível sem revisar as permissões de acesso aos provedores de IA. Se desejar ativar escrita pelo ChatGPT, revise a instalação do aplicativo GitHub nas configurações da integração e conceda `Contents: Read and write` e `Pull requests: Read and write` apenas aos repositórios desejados.
