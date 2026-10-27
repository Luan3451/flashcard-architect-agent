# 🧠 Flashcard Architect Agent

> Especialista em transformar qualquer material de estudo em flashcards de alta retenção para o Anki.

Um agente otimizado para o **Gemini** e **Antigravity CLI** que extrai, organiza e converte materiais de estudo em flashcards com imagens embutidas, formatação HTML/CSS rich e saída `.apkg` pronta para importar.

---

## 🚀 Capacidades

| Recurso | Detalhes |
|---|---|
| 📄 **Formatos suportados** | `PDF`, `DOCX`, `TXT`, `Markdown` |
| 🖼️ **Gestão de imagens** | Extrai e embutidas automaticamente nos cards via `<img src="...">` |
| 🎨 **Formatação rica** | HTML/CSS nativo com dark mode, negritos, listas, blocos de código |
| 🧠 **IA especialista** | Gemini 2.5 Flash com system prompt otimizado para aprendizagem |
| 📦 **Saída estruturada** | JSON válido → `.apkg` pronto para importar no Anki |
| ⚙️ **FSRS Ready** | Cards atômicos (uma ideia por card) otimizados para repetição espaçada |

---

## ⚙️ Instalação

```bash
pip install PyMuPDF genanki google-generativeai python-docx
```

---

## 🛠️ Configuração e Uso

### 1. Configure o script

Edite `anki_generator.py`:

```python
GEMINI_API_KEY = "sua-api-key-gemini"   # https://aistudio.google.com/app/apikey
INPUT_PATH     = "meu_material.pdf"      # PDF, DOCX, TXT ou MD
DECK_NAME      = "Meu Deck de Revisão"
OUTPUT_APKG    = "flashcards.apkg"
```

### 2. Execute

```bash
python anki_generator.py
```

### 3. Importe no Anki

```
Anki → Arquivo → Importar → flashcards.apkg
```

---

## 🤖 Usar como Agente (Gemini / Antigravity CLI)

### Google AI Studio / Gemini Advanced (Gems)

1. Acesse [Google AI Studio](https://aistudio.google.com)
2. Crie um novo projeto ou Gem
3. Cole o conteúdo de `prompt_agente.txt` em **System Instructions**
4. Envie o texto extraído do seu material

### Antigravity CLI

1. Clone este repositório
2. Copie `agent.md` para o diretório de agentes do seu Antigravity CLI
3. Ative com: `agy agent use flashcard-architect`

---

## 📦 Exemplo

**Input:**
> "Aqui estão minhas anotações de Biologia Celular. Havia uma imagem chamada `mitocondria.png` na página 2. Gere os flashcards das questões que errei."

**Output (JSON):**
```json
[
  {
    "pergunta": "Qual organela realiza a respiração celular aeróbica?<br><br><img src=\"mitocondria.png\" style=\"max-width:100%; border-radius:8px;\">",
    "resposta": "<b>Mitocôndria</b><br><br><i>Justificativa:</i> É nela que ocorrem o <b>Ciclo de Krebs</b> e a <b>Cadeia Respiratória</b>, gerando a maior parte do <b>ATP</b> celular."
  }
]
```

---

## 📁 Estrutura do Repositório

```
flashcard-architect-agent/
├── SKILL.md              # Skill para o Antigravity CLI
├── agent.md              # Definição do agente (importar no Gemini/AGY)
├── prompt_agente.txt     # System prompt completo do especialista
├── anki_generator.py     # Script Python de extração e geração
└── README.md             # Esta documentação
```

---

## ⚠️ Segurança

- **Nunca** suba sua `GEMINI_API_KEY` para o repositório
- Use variáveis de ambiente: `export GEMINI_API_KEY="sua-chave"`
- Adicione `.env` ao seu `.gitignore`

---

## 📄 Licença

MIT — use, modifique e distribua livremente.
