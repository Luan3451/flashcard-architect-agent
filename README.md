# 🧠 Flashcard Architect Agent

> Plugin para o **Antigravity CLI** — Especialista em transformar qualquer material de estudo em flashcards de alta retenção para o Anki.

[![Antigravity Plugin](https://img.shields.io/badge/Antigravity-Plugin-blue)](https://github.com/Luan3451/flashcard-architect-agent)
[![Version](https://img.shields.io/badge/version-1.1.0-green)](https://github.com/Luan3451/flashcard-architect-agent)

---

## 🚀 Capacidades

| Recurso | Detalhes |
|---|---|
| 📄 **Formatos suportados** | `PDF`, `DOCX`, `TXT`, `Markdown` |
| 🖼️ **Gestão de imagens** | Extrai e embutidas automaticamente nos cards via `<img src="...">` |
| 🎨 **Formatação rica** | HTML/CSS nativo com dark mode, negritos, listas, blocos de código |
| 🧠 **IA especialista** | Gemini 2.5 Flash com system prompt otimizado para aprendizagem |
| 📦 **Saída estruturada** | JSON válido → `.apkg` pronto para importar no Anki |
| ⚙️ **FSRS Ready** | Cards atômicos otimizados para repetição espaçada |

---

## 📁 Estrutura do Plugin

```
flashcard-architect-agent/
├── plugin.json                          ← Manifesto do plugin (Antigravity)
├── agents/
│   └── flashcard-architect.md           ← Definição do agente
├── skills/
│   └── flashcard-architect/
│       └── SKILL.md                     ← Skill completa com workflow
├── scripts/
│   └── anki_generator.py                ← Script Python de extração e geração
├── prompt_agente.txt                    ← System prompt puro (para AI Studio/Gems)
└── README.md                            ← Esta documentação
```

---

## ⚙️ Instalação no Antigravity CLI

```bash
agy plugin install https://github.com/Luan3451/flashcard-architect-agent
```

> Quando solicitado, confirme com **Y** (o comando está na Deny List de segurança do AGY por padrão).

Verifique a instalação:

```bash
agy plugin validate flashcard-architect
agy plugin list
```

---

## 🛠️ Configuração e Uso do Script Python

### 1. Instalar dependências

```bash
pip install PyMuPDF genanki google-generativeai python-docx
```

### 2. Configurar variáveis de ambiente (recomendado)

**Windows:**
```cmd
set GEMINI_API_KEY=sua-api-key-gemini
```

**Linux/macOS:**
```bash
export GEMINI_API_KEY="sua-api-key-gemini"
```

Ou edite diretamente no topo do `scripts/anki_generator.py`:
```python
GEMINI_API_KEY = "sua-api-key-gemini"   # https://aistudio.google.com/app/apikey
INPUT_PATH     = "caminho/para/seu/arquivo.pdf"
DECK_NAME      = "Meu Deck de Revisão"
OUTPUT_APKG    = "flashcards.apkg"
```

### 3. Executar

```bash
python scripts/anki_generator.py
```

### 4. Importar no Anki

```
Anki → Arquivo → Importar → flashcards.apkg
```

---

## 💬 Prompts Recomendados Após Instalação

Após instalar e ativar o agente com `agy agent use flashcard-architect`, use os prompts abaixo como ponto de partida:

---

### 📄 Para PDF com questões de simulado

```
Analise o seguinte conteúdo extraído do arquivo [NOME_DO_ARQUIVO.pdf].
Imagens extraídas automaticamente pelo script: [img_p1_0.png, img_p3_1.png, ...]
Foco principal: as questões marcadas como ERRADO ou que não soube responder.
Quebre cada conceito em cards atômicos e siga todas as regras de formatação HTML/CSS dark mode.

[COLE AQUI O TEXTO EXTRAÍDO]
```

---

### 📝 Para DOCX / anotações de aula

```
Aqui estão minhas anotações do documento [NOME_DO_ARQUIVO.docx] sobre [TEMA].
Organize os conceitos mais importantes em flashcards atômicos.
Destaque definições, fórmulas e exemplos práticos usando a formatação HTML correta.

[COLE AQUI O TEXTO EXTRAÍDO]
```

---

### 📖 Para TXT / Markdown

```
Transforme o conteúdo abaixo (extraído de [arquivo.md]) em flashcards.
Priorize: definições, listas numeradas, exemplos e qualquer conceito que exija memorização ativa.
Use cards atômicos e formatação HTML compatível com dark mode.

[COLE AQUI O CONTEÚDO]
```

---

### 🎯 Para revisão focada em erros

```
Abaixo estão apenas as questões que ERREI no simulado de [TEMA].
Para cada questão:
1. Crie um card com o enunciado completo na frente
2. Na resposta, coloque a alternativa correta + justificativa do porquê as outras estão erradas
3. Se houver referência a imagem (nome indicado no texto), inclua a tag <img> correta

[COLE AQUI AS QUESTÕES QUE ERROU]
```

---

## ⚠️ Segurança

- **Nunca** suba sua `GEMINI_API_KEY` para o repositório
- Use variáveis de ambiente: `set GEMINI_API_KEY=sua-chave` (Windows)
- O `.gitignore` já está configurado para ignorar `.env` e arquivos sensíveis

---

## 📄 Licença

MIT — use, modifique e distribua livremente.
