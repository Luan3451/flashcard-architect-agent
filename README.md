# 🧠 Flashcard Architect Agent (`v3.2.0` — Antigravity Native Edition)

> **Agente Especialista, Skill e Motor Python para Geração Autônoma de Baralhos Anki (`.apkg`) Otimizados para o Algoritmo FSRS com Ancoragem Geométrica de Diagramas, Auditoria de Simulados e Zero Dependência de APIs Externas.**

---

## 📌 Visão Geral

O **Flashcard Architect Agent v3.2.0** automatiza a transformação de materiais de estudo (**PDF, Markdown, DOCX, TXT e JSON**) em pacotes `.apkg` prontos para importação no Anki Desktop, AnkiWeb e AnkiDroid/AnkiMobile. 

Operando **100% nativamente no ecossistema Google Antigravity** (`agy` CLI, Antigravity IDE e Antigravity Desktop APP) com o modelo **Gemini 3.8 Flash (High Reasoning Effort)**, o projeto dispensa chaves pagas (`GEMINI_API_KEY`) e inclui inovações arquiteturais desenvolvidas para cenários reais de alta densidade (como simulados de certificações de TI, OAB e concursos):

1. **Ancoragem Geométrica de Diagramas (Y0)**: Lê a coordenada vertical (`bbox.y0`) de cada imagem e bloco de texto via PyMuPDF, posicionando o diagrama diretamente abaixo da questão correta (sem acúmulo no rodapé).
2. **Indexação Sequencial Global & Prefixo de Bateria**: Previne colisões de contexto em simulados com seções reiniciadas (Q1–Q18, Q1–Q24) atribuindo o identificador `[Pág. X | QY (Global #Z)]`.
3. **Filtro de Simulado e Auto-Tagging de Status**: Identifica automaticamente questões incorretas (`status::wrong`) e corretas (`status::correct`), permitindo gerar cartões apenas dos seus erros via `--filter wrong`.
4. **Relatório Analítico de Auditoria**: Gera automaticamente o arquivo `<output>_Relatorio_Auditoria.md` com métricas consolidadas de acertos, erros e diagramas mapeados.
5. **Preservação de Idioma Bilíngue (`--lang keep`)**: Mantém 100% das questões, alternativas e saídas de console no idioma oficial do exame (ex: Inglês da Cisco/AWS) enquanto entrega explicações detalhadas em Português no verso.
6. **Wizard Interativo de 5 Eixos**: Triagem rápida pré-voo respondida com Enter (padrões) ou em linha única (`1, 1, 1, 1, 1`).

---

## 📂 Estrutura do Repositório

```text
flashcard-architect-agent/
├── .gitignore                        # Proteção contra mídias e .apkg temporários
├── README.md                         # Documentação oficial e passo a passo
├── plugin.json                       # Manifesto v3.2.0 com permissões filesystem e shell
├── prompt_agente.txt                 # Matriz de Prompts Mestres (Curadoria, Literal e Erros)
├── agents/
│   └── flashcard-architect.md        # Agente @flashcard-architect com triagem de 5 eixos
├── skills/
│   └── flashcard-architect/
│       └── SKILL.md                  # Skill autônoma para Antigravity IDE e CLI
└── scripts/
    └── anki_generator.py             # Motor Python v3.2.0 (Extração Y0, Auditoria, IA e GenAnki)
```

---

## 🚀 Passo a Passo Completo de Instalação e Preparação

### Passo 1: Pré-requisitos do Sistema
1. **Python 3.10 ou superior** instalado (`python --version`).
2. **Google Antigravity CLI (`agy`)** instalado e autenticado no ambiente:
   ```bash
   agy --version
   ```

### Passo 2: Clonar o Repositório
```bash
git clone https://github.com/Luan3451/flashcard-architect-agent.git
cd flashcard-architect-agent
```

### Passo 3: Instalar o Plugin no Antigravity
Para disponibilizar o agente `@flashcard-architect` e a skill globalmente no seu Antigravity IDE/APP:
```bash
agy plugin install .
```

### Passo 4: Instalação de Dependências Python
O script `scripts/anki_generator.py` possui **Auto-Bootstrap**: na primeira execução, ele instala automaticamente as bibliotecas ausentes. Caso prefira provisionar manualmente:
```bash
pip install genanki pymupdf python-docx Pillow
```

---

## ⚡ Guia Rápido de Uso

### Opção A: Execução Interativa (Wizard 5-Eixos)
Basta executar o script apontando para o seu material. O sistema apresenta o menu de 5 perguntas:
```bash
python scripts/anki_generator.py --input simulado_ccna.pdf
```
*(Você pode pressionar Enter para aceitar todas as recomendações ou digitar `1, 1, 2, 1, 1` para focar somente em erros de simulado).*

### Opção B: Execução Zero-Touch (Automatizada por Linha de Comando)

#### 1. Simulado de TI com Foco Cirúrgico nos Erros (Inglês + Justificativa PT)
```bash
python scripts/anki_generator.py \
  --input ccna_erros.pdf \
  --deck "Certificacoes::Cisco::CCNA_200_301" \
  --mode strict \
  --filter wrong \
  --lang keep \
  --media \
  --non-interactive
```

#### 2. Resumo de Apostila Teórica (Modo Turbo Sem Imagens)
```bash
python scripts/anki_generator.py \
  --input apostila_redes.pdf \
  --deck "Redes::Fundamentos" \
  --mode curated \
  --no-media \
  --density high \
  --non-interactive
```

#### 3. Prova da OAB / Concurso Jurídico (Fidelidade Literal ao Texto)
```bash
python scripts/anki_generator.py \
  --input prova_oab.pdf \
  --deck "Direito::OAB_1a_Fase" \
  --mode strict \
  --lang pt \
  --non-interactive
```

---

## 📊 Relatório de Auditoria Gerado

Ao final de cada execução com simulados, o gerador grava automaticamente um relatório no formato Markdown (`<output>_Relatorio_Auditoria.md`) contendo:
- Total de páginas e questões detectadas
- Contagem e percentual de questões com tag `status::wrong` vs `status::correct`
- Diagramas e topologias ancoradas geometricamente por coordenada Y
- Prévia de cartões e instruções de criação de Baralhos Filtrados no Anki com FSRS

---

## 🛠️ Opções Completas de Linha de Comando (`--help`)

| Flag | Argumentos | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `-i, --input` | Caminho do arquivo | Auto-detect | Arquivo `.pdf`, `.md`, `.docx`, `.txt`, `.json` |
| `-d, --deck` | String | Estudos::... | Nome hierárquico do baralho no Anki (`::`) |
| `-o, --output` | Caminho `.apkg` | `<deck>.apkg` | Caminho do pacote Anki exportado |
| `-M, --mode` | `curated`, `strict`, `exam` | `curated` | Curadoria (80/20), Literal ou Foco em Pegadinhas |
| `--media` | Flag booleana | Ativo | Ativa extração e ancoragem de imagens |
| `--no-media` | Flag booleana | Inativo | Desativa motor de imagens (Modo Turbo) |
| `-F, --filter` | `all`, `wrong`, `correct` | `all` | Filtro de simulado (todas, apenas erros ou acertos) |
| `-L, --lang` | `keep`, `pt`, `en` | `keep` | Preservação bilíngue (`keep`), português ou inglês |
| `-D, --density` | `essential`, `high` | `high` | Quantidade de cartões (1-2 vs 3-6 por página) |
| `-S, --style` | `qa`, `hybrid` | `qa` | Formato Pergunta/Resposta clássico ou Híbrido com Cloze |
| `-m, --model` | Nome do modelo | `gemini-3.8-flash-high` | Modelo do Antigravity CLI |
| `-e, --effort` | `low`, `medium`, `high`, `xhigh` | `high` | Nível de esforço de raciocínio da inferência |
| `-y, --non-interactive` | Flag booleana | Inativo | Pula o wizard usando flags/padrões |
| `--no-report` | Flag booleana | Inativo | Não gera o arquivo `.md` de auditoria |
| `-v, --version` | N/A | N/A | Exibe a versão do Flashcard Architect |

---

## 📄 Licença

Distribuído sob licença MIT. Criado por **Luan3451**.
