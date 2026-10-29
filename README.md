# 🧠 Flashcard Architect Agent (`v3.1.0` — Antigravity Native Edition)

> **Agente Especialista, Skill e Motor Python para Geração de Baralhos Anki (`.apkg`) Otimizados para o Algoritmo FSRS com Triagem Inteligente e Zero Dependência de APIs Externas.**

---

## 📌 Visão Geral

O **Flashcard Architect Agent** automatiza a transformação de materiais de estudo (**PDF, Markdown, DOCX, TXT e JSON**) em pacotes `.apkg` prontos para importação no Anki Desktop, AnkiWeb e AnkiDroid/AnkiMobile. 

Operando **100% nativamente no ecossistema Google Antigravity** (`agy` CLI, Antigravity IDE e Antigravity Desktop APP) com o modelo **Gemini 3.8 Flash (High Reasoning Effort)**, o projeto dispensa chaves pagas (`GEMINI_API_KEY`) e inclui um **Wizard Interativo Pré-Voo** que adapta a extração de imagens e a fidelidade textual ao seu objetivo (resumos teóricos, simulados literais ou revisão de erros).

---

## 📂 Estrutura do Repositório

```text
flashcard-architect-agent/
├── .gitignore                        # Proteção contra vazamento de mídias e .apkg locais
├── README.md                         # Documentação mestre e passo a passo completo
├── plugin.json                       # Manifesto oficial do Plugin Antigravity
├── prompt_agente.txt                 # Matriz de Prompts Mestres (Curadoria, Literal e Simulados)
├── agents/
│   └── flashcard-architect.md        # Definição do Agente (@flashcard-architect) com Wizard
├── skills/
│   └── flashcard-architect/
│       └── SKILL.md                  # Skill autônoma acionável pelo Antigravity
└── scripts/
    └── anki_generator.py             # Motor Python (Extração, CLI Interativa, IA e GenAnki)
```

---

## 🚀 Passo a Passo Completo de Instalação e Preparação

### Passo 1: Pré-requisitos do Sistema
1. **Python 3.10 ou superior** instalado (`python --version`).
2. **Google Antigravity CLI (`agy`)** instalado e autenticado no ambiente:
   ```bash
   agy --version
   ```
   *(Caso o comando `agy` não seja reconhecido no terminal, execute `agy install` no Antigravity IDE ou adicione o diretório binário do Antigravity ao `PATH` do seu sistema).*

### Passo 2: Clonar o Repositório
```bash
git clone https://github.com/Luan3451/flashcard-architect-agent.git
cd flashcard-architect-agent
```

### Passo 3: Instalar o Plugin/Agente no Antigravity (Opcional para uso via IDE/APP)
Para disponibilizar o comando `@flashcard-architect` e a skill globalmente no seu Antigravity IDE/APP:
```bash
agy plugin install .
```

### Passo 4: Instalação de Dependências Python (Automática ou Manual)
O script `scripts/anki_generator.py` possui **Auto-Bootstrap**: na primeira execução, ele detecta e instala automaticamente pacotes ausentes. Caso prefira instalar manualmente antes de rodar:
```bash
pip install genanki pymupdf python-docx Pillow
```

---

## 🧭 Como Funciona o Fluxo de Triagem (Wizard Interativo)

Ao iniciar o agente no chat (`@flashcard-architect`) ou rodar o script sem flags de bloqueio, o sistema realiza **4 perguntas rápidas** para provisionar o baralho na medida exata da sua necessidade:

1. **Modo de Fidelidade da Fonte:**
   - **Opção 1 (Curadoria & Recorrência):** Filtra o que é mais importante e reescreve em cartões enxutos.
   - **Opção 2 (Fidelidade Estrita / Literal):** Ideal para **provas, simulados e legislação** — mantém o texto-fonte intacto sem omitir detalhes.
   - **Opção 3 (Dissecação de Simulado):** Cria cartões focados nas alternativas erradas e pegadinhas da prova.
2. **Extração de Imagens e Anexos:**
   - Pergunta se o seu `.pdf`, `.md` ou `.docx` possui imagens/diagramas que devem ir para o Anki. Se você escolher **Não**, o motor de imagem (`PyMuPDF` / `Pillow`) nem é carregado, acelerando drasticamente o processamento.
3. **Estilo de Cartão:** Pergunta/Resposta clássica com Justificativa ou Híbrido com Cloze (`{{c1::...}}`).
4. **Densidade de Cartões:** Essencial (resumo rápido) ou Exaustiva (cobertura total do documento).

---

## 🛠️ Manual Passo a Passo de Execução

### Modo A: Pelo Antigravity IDE ou Desktop APP (Interface Visual)

1. Abra o seu projeto no **Antigravity IDE** ou **Antigravity Desktop APP**.
2. No painel de chat, chame o agente digitando:
   ```text
   @flashcard-architect Quero gerar um baralho a partir do arquivo provas/simulado_seguranca.pdf
   ```
3. O agente apresentará o **Menu Rápido de 4 Opções**. Responda apenas com os números (ex: `2, 1, 1, 2` para *Texto Literal de Prova + Com Imagens + Pergunta/Resposta + Cobertura Exaustiva*).
4. O agente executará o `anki_generator.py` em segundo plano e entregará o arquivo `.apkg` pronto na pasta de trabalho.

---

### Modo B: Pelo Terminal / Linha de Comando (Interativo ou Automatizado)

#### 1. Execução Guiada (Wizard no Terminal)
Basta informar o arquivo de entrada. O próprio terminal fará as perguntas de configuração:
```bash
python scripts/anki_generator.py --input "materiais/apostila_redes.pdf"
```

#### 2. Execução Direta para Provas/Simulados (Sem alterar texto-fonte + Com Imagens)
Para pular o questionário e rodar tudo em um único comando automatizado:
```bash
python scripts/anki_generator.py \
  --input "provas/simulado_redes.pdf" \
  --deck "Simulados::Redes e Segurança" \
  --mode strict \
  --media \
  --density high \
  --output simulado_redes.apkg
```

#### 3. Execução Rápida Somente Texto (Ignorando ferramentas de imagem)
Ideal para PDFs ou Markdowns puramente teóricos onde você quer velocidade máxima:
```bash
python scripts/anki_generator.py \
  --input "resumos/anotacoes_cloud.md" \
  --deck "Cloud::Conceitos Mais Cobrados" \
  --mode curated \
  --no-media \
  --output cloud_resumo.apkg
```

#### 4. Empacotamento Offline de JSON Pré-formatado (Sem uso de IA)
```bash
python scripts/anki_generator.py \
  --input "meus_cards.json" \
  --no-ai \
  --deck "Revisão Offline" \
  --output revisao.apkg
```

---

## ⚙️ Tabela Completa de Parâmetros CLI (`anki_generator.py`)

| Argumento | Flag Curta | Padrão | Descrição |
| :--- | :---: | :---: | :--- |
| `--input` | `-i` | *(Obrigatório)* | Caminho do arquivo fonte (`.pdf`, `.md`, `.docx`, `.txt`, `.json`) |
| `--deck` | `-d` | `"Meu Baralho Antigravity"` | Nome do baralho no Anki (suporta sub-decks com `::`) |
| `--output` | `-o` | `"flashcards.apkg"` | Caminho do pacote `.apkg` gerado |
| `--mode` | `-M` | *(Pergunta no Wizard)* | `curated` (recorrência/80-20), `strict` (fiel à fonte/provas) ou `exam` (foco em erros) |
| `--media` / `--no-media` | - | *(Pergunta no Wizard)* | Ativa (`--media`) ou desativa (`--no-media`) os extratores de imagem do PDF/MD/DOCX |
| `--density` | `-D` | `normal` | Granularidade dos cartões: `essential` (enxuto) ou `high` (exaustivo) |
| `--style` | - | `qa` | Estilo dos cartões: `qa` (Pergunta/Resposta) ou `hybrid` (com Cloze) |
| `--attachments` | `-a` | `None` | Pasta complementar de imagens e mídias externas |
| `--model` | `-m` | `gemini-3.8-flash-high` | Modelo acionado via Antigravity CLI (`agy`) |
| `--effort` | `-e` | `high` | Nível de esforço cognitivo (`low`, `medium`, `high`, `max`) |
| `--chunk-size` | `-c` | `10` | Quantidade de páginas/seções enviadas por lote à IA |
| `--non-interactive`| `-y` | `False` | Pula o questionário interativo usando os valores das flags ou padrões |
| `--no-ai` | `--offline` | `False` | Empacota diretamente um arquivo `.json` sem chamar a IA |

---

## 📥 Passo Final: Importação no Anki

1. Abra o **Anki Desktop** (ou envie o arquivo para o **AnkiDroid / AnkiMobile**).
2. Pressione `Ctrl + I` (**Arquivo → Importar**).
3. Selecione o arquivo `.apkg` gerado.
4. Todos os cartões serão adicionados ao baralho especificado com **Dark Mode nativo**, **imagens vinculadas** e **GUIDs determinísticos** (atualizações futuras do mesmo baralho preservam seu histórico FSRS).

---

## 🛠️ Resolução de Problemas (Troubleshooting)

* **`UnicodeEncodeError` no Windows:** O script força `sys.stdout` e `sys.stderr` para `UTF-8` automaticamente na inicialização.
* **`Command 'agy' not found`:** Certifique-se de que o Antigravity CLI está instalado e acessível no terminal com `agy --version`.
* **PDF muito denso dando timeout no lote:** Reduza a quantidade de páginas por lote adicionando `--chunk-size 5`.
* **Imagens de cabeçalho indesejadas em PDFs:** Caso o PDF contenha apenas texto relevante e logos repetitivos no topo da página, selecione a opção **Somente Texto (`--no-media`)** no questionário inicial.
