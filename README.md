# 🧠 Flashcard Architect

> Plugin para **Antigravity CLI** — Transforma documentos de estudo em flashcards Anki de alta retenção com imagens, formatação dark mode e `.apkg` pronto para importar.

[![Antigravity Plugin](https://img.shields.io/badge/Antigravity-Plugin-blue)](https://github.com/Luan3451/flashcard-architect-agent)
[![Version](https://img.shields.io/badge/version-2.0.0-green)](https://github.com/Luan3451/flashcard-architect-agent)

---

## 🚀 Capacidades

| Recurso | Detalhes |
|---|---|
| 📄 **Formatos** | `PDF`, `DOCX`, `TXT`, `Markdown` |
| 🖼️ **Imagens** | Extrai de PDFs e DOCXs automaticamente, embutidas via `<img>` |
| 🎨 **Dark mode** | HTML/CSS nativo com fundo escuro, código verde, tipografia limpa |
| 🧠 **IA** | Gemini 2.5 Flash com system prompt otimizado para flashcards |
| 📦 **Saída** | `.apkg` pronto para importar no Anki com mídias embutidas |
| ⚙️ **FSRS** | Cards atômicos otimizados para repetição espaçada |
| 🔄 **Retry** | Retry automático com backoff em caso de erro do Gemini |
| ✅ **Validação** | Filtra cards incompletos ou malformados automaticamente |

---

## 📁 Estrutura do Plugin

```
flashcard-architect-agent/
├── plugin.json                          ← Manifesto (Antigravity CLI)
├── agents/
│   └── flashcard-architect.md           ← Agente especialista
├── skills/
│   └── flashcard-architect/
│       └── SKILL.md                     ← Skill com workflow completo
├── scripts/
│   └── anki_generator.py               ← Script Python CLI
├── prompt_agente.txt                    ← System prompt (AI Studio/Gems)
└── README.md
```

---

## ⚙️ Instalação

### Antigravity CLI

```bash
agy plugin install https://github.com/Luan3451/flashcard-architect-agent
```

Verifique:

```bash
agy plugin validate flashcard-architect
agy plugin list
```

### Dependências Python (para o script)

```bash
pip install PyMuPDF genanki google-generativeai python-docx
```

---

## 🛠️ Uso

### Opção 1: Script Python (gera o .apkg)

Configure a API key:

```cmd
set GEMINI_API_KEY=sua-api-key-aqui
```

Execute:

```bash
# PDF de simulado
python scripts/anki_generator.py --input "C:\Docs\simulado.pdf" --deck "Revisão Redes" --output revisao.apkg

# DOCX de anotações
python scripts/anki_generator.py --input anotacoes.docx --deck "Bio Celular"

# Markdown com chunk menor (para textos densos)
python scripts/anki_generator.py --input resumo.md --chunk-size 10

# Ver versão
python scripts/anki_generator.py --version
```

Depois importe: `Anki → Arquivo → Importar → [arquivo].apkg`

### Opção 2: Agente no Antigravity CLI

```bash
agy agent use flashcard-architect
```

---

## 💬 Prompts Recomendados

Após ativar o agente, use estes prompts como ponto de partida:

### 📄 Simulado PDF (foco em erros)

```
Analise o conteúdo extraído do arquivo simulado_redes.pdf.
Imagens extraídas: img_p1_0.png, img_p3_1.png, img_p12_0.png.
Foco: SOMENTE as questões que errei (marcadas como ERRADO).
Para cada erro: enunciado na frente + resposta correta com justificativa.

[COLE O TEXTO EXTRAÍDO]
```

### 📝 Anotações DOCX

```
Transforme estas anotações de biologia_celular.docx em flashcards atômicos.
Priorize: definições, processos e exemplos práticos.
Imagem: mitocondria.png (respiração celular).

[COLE O TEXTO]
```

### 🎯 Revisão focada em erros

```
Questões que errei no simulado de Segurança da Informação.
Para cada uma: card com enunciado + alternativa correta + justificativa.
Se tiver topologia/imagem, inclua <img src="...">.

[QUESTÕES ERRADAS]
```

### 📖 Markdown / TXT

```
Transforme o conteúdo abaixo em flashcards atômicos.
Priorize definições, listas e conceitos que exijam memorização ativa.
Formatação HTML dark mode obrigatória.

[CONTEÚDO]
```

---

## ⚠️ Segurança

- **Nunca** suba `GEMINI_API_KEY` para o repositório
- Use variável de ambiente: `set GEMINI_API_KEY=sua-chave` (Windows)
- O `.gitignore` protege `.env`, `*.apkg` e `anki_media/`

---

## 📄 Licença

MIT — use, modifique e distribua livremente.
