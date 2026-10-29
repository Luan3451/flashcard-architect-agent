# 🧠 Flashcard Architect (Antigravity Native)

> Plugin e Agente Oficial para o **Google Antigravity** (CLI, IDE e APP) — Transforma documentos de estudo em flashcards Anki de alta retenção com imagens, formatação Dark Mode e pacote `.apkg` pronto para importar.

[![Antigravity Plugin](https://img.shields.io/badge/Antigravity-Plugin-blue)](https://github.com/Luan3451/flashcard-architect-agent)
[![Model](https://img.shields.io/badge/Model-Gemini%203.8%20Flash%20(High)-purple)](https://antigravity.google)
[![Version](https://img.shields.io/badge/version-3.0.0-green)](https://github.com/Luan3451/flashcard-architect-agent)
[![Zero External API](https://img.shields.io/badge/API-Zero%20External%20Keys-orange)](https://antigravity.google)

---

## ⚡ 100% Nativo no Ecossistema Antigravity

Diferente de geradores convencionais, esta versão foi completamente reengenheirada para operar **nativamente dentro do ecossistema Google Antigravity**:

- 🚫 **Sem APIs Externas**: Não requer Google AI Studio, chaves de API pagas ou variáveis de ambiente `GEMINI_API_KEY`.
- ⚡ **Modelo Gemini 3.8 Flash (High)**: Raciocínio profundo com alto poder de síntese e velocidade para Active Recall.
- 🖼️ **Coleta Avançada de Anexos**: Extração direta de imagens de PDFs, captura de links e arquivos referenciados em Markdown (`![alt](img)`), DOCX e diretórios de anexos.
- 📦 **Geração Direta de `.apkg`**: Monta o pacote final com banco de dados SQLite interno e pasta de mídias embutida para importação imediata no Anki.
- 🎨 **Dark Mode & FSRS**: Cartões estilizados para o tema escuro nativo do Anki com destaques em verde `#4af626` e azul `#58a6ff`, desenhados para o algoritmo FSRS.

---

## 📁 Estrutura do Repositório

```
flashcard-architect-agent/
├── plugin.json                          ← Manifesto oficial do Antigravity
├── agents/
│   └── flashcard-architect.md           ← Definição do agente especialista
├── skills/
│   └── flashcard-architect/
│       └── SKILL.md                     ← Workflow e documentação da skill
├── scripts/
│   └── anki_generator.py               ← Script Python com motor nativo Antigravity CLI
├── prompt_agente.txt                    ← System prompt para Antigravity IDE / Gems
└── README.md
```

---

## 🚀 Como Usar

### 1. Requisitos Locais

O script precisa apenas das bibliotecas para processar arquivos e gerar o pacote `.apkg`:

```bash
pip install PyMuPDF genanki python-docx
```

*(O Antigravity CLI `agy` já gerencia autenticação e quotas de modelo automaticamente).*

---

### 2. Formas de Execução

#### Opção A: Script CLI com Antigravity Automático

O script aciona o `agy` nativamente em segundo plano usando o **Gemini 3.8 Flash (High)**:

```bash
# Markdown com imagens e diretório de anexos:
python scripts/anki_generator.py --input "resumo.md" --attachments "./anexos" --deck "Redes de Computadores" --output redes.apkg

# PDF de Simulado (extrai esquemas e figuras por página):
python scripts/anki_generator.py --input "simulado.pdf" --deck "Simulado OAB/TI" --output simulado.apkg

# Documento DOCX com imagens embutidas:
python scripts/anki_generator.py --input "apostila.docx" --deck "Biologia Celular"

# JSON pré-estruturado (modo direto sem chamada de IA):
python scripts/anki_generator.py --input "cards.json" --no-ai --output deck.apkg
```

#### Opção B: No Antigravity IDE / Antigravity APP

1. No chat do Antigravity, acione o agente `@flashcard-architect`.
2. Forneça o arquivo (PDF, Markdown ou anotações).
3. O agente analisa o contexto, mapeia as imagens e gera o baralho `.apkg` no workspace.

---

## 🛠️ Parâmetros do Gerador (`anki_generator.py`)

| Parâmetro | Flag | Padrão | Descrição |
|-----------|------|--------|-----------|
| `--input` | `-i` | *(Obrigatório)* | Arquivo de entrada (`.pdf`, `.md`, `.docx`, `.txt`, `.json`) |
| `--deck` | `-d` | `"Meu Baralho Antigravity"` | Nome do baralho exibido no Anki |
| `--output` | `-o` | `"flashcards.apkg"` | Caminho do arquivo `.apkg` gerado |
| `--attachments` | `-a` | `None` | Pasta com imagens complementares para incluir |
| `--model` | `-m` | `gemini-3.8-flash-high` | Modelo utilizado no Antigravity CLI |
| `--effort` | `-e` | `high` | Nível de raciocínio (`low`, `medium`, `high`, `xhigh`, `max`) |
| `--chunk-size` | `-c` | `10` | Páginas ou blocos por lote de processamento |
| `--no-ai` | - | `False` | Importa diretamente cards estruturados em JSON |
| `--version` | `-v` | - | Exibe a versão instalada |

---

## 🖼️ Suporte a Mídias e Imagens

- **PDF**: PyMuPDF extrai automaticamente gráficos, tabelas e diagramas, vinculando-os ao contexto da página.
- **Markdown (.md)**: Detecta sintaxes `![alt](caminho)` e `<img src="caminho">`, buscando localmente nas pastas relativas, diretórios de anexos (`attachments/`, `media/`, `images/`) e copia tudo para o pacote final do Anki.
- **DOCX**: Extrai mídias embutidas nos relacionamentos XML do documento.
- **Dark Mode**: Imagens com cantos arredondados (`border-radius: 8px`) e bordas sutis para integração perfeita com o tema escuro.

---

## 📥 Importando no Anki

Após gerar o arquivo:
1. Abra o Anki desktop ou mobile.
2. Acesse **Arquivo → Importar** (ou pressione `Ctrl + I`).
3. Selecione o arquivo `.apkg` gerado.
4. Todos os cartões, mídias e estilos estarão prontos para estudo com o algoritmo FSRS!

---

## 📄 Licença

MIT License — Livre para uso pessoal, acadêmico e profissional.
