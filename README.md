# 🧠 Flashcard Architect (Zero-Touch Antigravity Edition)

> Plugin e Agente Oficial para o **Google Antigravity** (CLI, IDE e APP) — Pipeline autônomo Zero-Touch que transforma documentos de estudo em flashcards Anki de alta retenção com imagens WebP, Dark Mode nativo, suporte a Básicos e Cloze e sincronização invisível.

[![Antigravity Plugin](https://img.shields.io/badge/Antigravity-Plugin-blue)](https://github.com/Luan3451/flashcard-architect-agent)
[![Model](https://img.shields.io/badge/Model-Gemini%203.8%20Flash%20(High)-purple)](https://antigravity.google)
[![Version](https://img.shields.io/badge/version-3.1.0-green)](https://github.com/Luan3451/flashcard-architect-agent)
[![Zero Touch](https://img.shields.io/badge/Pipeline-Zero--Touch-brightgreen)](https://antigravity.google)

---

## ⚡ Diferenciais de Alta Confiabilidade (v3.1.0)

1. **Auto-Bootstrapper & Zero-Setup:** Cabeçalho PEP 723 com suporte a `uv` e auto-provisionamento transparente de bibliotecas (`genanki`, `pymupdf`, `Pillow`, `pydantic`, `json-repair`, `watchdog`, `rapidocr-onnxruntime`).
2. **Content-Addressed Storage (WebP):** Imagens convertidas para WebP e nomeadas pelo hash SHA-256 (`ag_<hash>.webp`), impedindo colisões e sobrescritas acidentais na pasta global `collection.media` do Anki.
3. **Deck IDs Determinísticos de 31 Bits:** Evita que baralhos com nomes diferentes sejam fundidos acidentalmente pelo Anki.
4. **Suporte Dual (Básico e Cloze):** Reconhece automaticamente notas `{{c1::omissão}}` e cria notas no modelo Cloze nativo.
5. **GUIDs Desacoplados via `id_conceito`:** Permite corrigir erros de digitação em perguntas sem perder o histórico do algoritmo FSRS.
6. **Suporte a Diagramas Vetoriais em PDF:** Captura fluxogramas e esquemas agrupados (`cluster_drawings`) e executa OCR offline quando o PDF for escaneado.
7. **Chunking com Janela Deslizante (15% Overlap):** Impede que enunciados de questões sejam cortados dos seus gabaritos e diagramas nas fronteiras de páginas.
8. **Integração com AnkiConnect e Auto-Open:** Injeta notas diretamente no Anki Desktop aberto e aciona a sincronização com o AnkiWeb (disponível no celular/tablet) sem intervenção manual.
9. **Modo Watchdog (--watch):** Monitora pastas Dropzone para processamento contínuo em segundo plano.

---

## 🚀 Como Usar

### Execução Simples (Zero Flags)
Basta colocar o arquivo de estudo no diretório e executar:

```bash
python scripts/anki_generator.py
```

O script auto-detecta o arquivo, agrupa com sobreposição, envia ao Gemini 3.8 Flash High no Antigravity CLI, empacota o `.apkg` e abre/sincroniza no Anki.

### Execução Personalizada
```bash
# Markdown com pasta de anexos:
python scripts/anki_generator.py --input "resumo.md" --attachments "./anexos"

# PDF de simulado:
python scripts/anki_generator.py --input "simulado.pdf"

# Modo Dropzone contínuo (Watchdog):
python scripts/anki_generator.py --watch --watch-dir "./inbox"
```

---

## 📄 Licença

MIT License — Livre para uso e distribuição.
