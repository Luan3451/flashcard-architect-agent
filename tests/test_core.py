"""Offline regression tests. No API key, network or installed AI model needed."""
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import anki_generator as engine
from themes import THEMES, css_for_theme, note_model_id, templates


def test_sanitizer_blocks_remote_and_executable_html():
    source = '<b>Oi</b><script>alert(1)</script><img src="https://exemplo.org/tracker">' \
             '<img src="fa_aaaaaaaaaaaaaaaaaaaa.webp" onerror="steal()"><i>x</i>'
    safe, refs = engine.sanitize_html(source, {"fa_aaaaaaaaaaaaaaaaaaaa.webp"})
    assert 'alert' not in safe
    assert 'tracker' not in safe
    assert 'onerror' not in safe
    assert '<b>Oi</b>' in safe
    assert '<i>x</i>' in safe
    assert refs == {"fa_aaaaaaaaaaaaaaaaaaaa.webp"}


def test_sanitizer_rejects_missing_image():
    safe, refs = engine.sanitize_html('<img src="fa_aaaaaaaaaaaaaaaaaaaa.webp"><img src="/etc/passwd">', set())
    assert safe == ''
    assert not refs


def test_chunk_no_overlap_and_size_limits():
    blocks = ["A" * 410 + "\n\n" + "B" * 500, "\n" + "C" * 1700]
    chunks = engine.chunk_text(blocks, target_chars=850)
    assert all(len(x) <= 850 for x in chunks)
    assert "".join(chunks) == "".join(blocks)
    assert len(chunks) > 1


def test_parse_cards_deduplicates_and_keeps_cloze():
    values = [{"id_conceito": "test_001", "pergunta": "O que é DNS?", "resposta": "Resolução de nomes", "tags": ["redes"]},
              {"id_conceito": "test_002", "pergunta": "O que é DNS?", "resposta": "Nomes de domínio", "tags": []},
              {"pergunta": "Porta {{c1::53}}", "resposta": "DNS", "tags": []}]
    parsed = engine.parse_cards(json.dumps(values), {})
    assert len(engine.unique_cards(parsed)) == 2
    assert engine.CLOZE.search(parsed[-1]["pergunta"])


def test_theme_selection_and_anki_template_integrity():
    basic, cloze = templates()
    for theme in THEMES:
        css = css_for_theme(theme)
        assert '.night_mode' in css
        assert 'max-width: 100% !important' in css
        assert 'font-size: clamp' in css
    assert '{{Pergunta}}' in basic[0]['qfmt']
    assert '{{Resposta}}' in basic[0]['afmt']
    assert '{{cloze:Text}}' in cloze[0]['qfmt']
    assert len({note_model_id(t, "basic") for t in THEMES}) == len(THEMES)


def test_lossless_image_is_deterministic(tmp_path):
    Image = pytest.importorskip('PIL.Image')
    image = Image.new('RGB', (240, 120), (127, 30, 190))
    original = BytesIO()
    image.save(original, format='PNG')
    name = engine.save_image(original.getvalue(), tmp_path)
    assert name and name.endswith('.webp')
    assert engine.save_image(original.getvalue(), tmp_path) == name
    with Image.open(tmp_path / name) as new:
        assert new.tobytes() == image.tobytes()


def test_pdf_repeated_image_references_and_vector(tmp_path):
    fitz = pytest.importorskip('pymupdf')
    Image = pytest.importorskip('PIL.Image')
    img = Image.new('RGB', (240, 120), 'white')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    pdf = fitz.open()
    page = pdf.new_page(width=595, height=842)
    page.insert_text((40, 35), 'Question 1: Qual topologia?', fontsize=14)
    page.insert_image(fitz.Rect(40, 50, 270, 165), stream=buffer.getvalue())
    page.insert_text((40, 210), 'Question 2: Mesmo diagrama?', fontsize=14)
    page.insert_image(fitz.Rect(40, 225, 270, 340), stream=buffer.getvalue())
    # True PDF vector artwork (no image XRef)
    drawing = page.new_shape()
    drawing.draw_rect(fitz.Rect(40, 400, 220, 515))
    drawing.finish(color=(0, 0, 0), fill=(0.8, 1, 0.9))
    drawing.commit()
    source = tmp_path / 'demo.pdf'
    pdf.save(source)
    pdf.close()
    result = engine.extract_pdf(source, tmp_path / 'media', True, dpi=170)
    assert result.stats['pages'] == 1
    assert result.stats['images_placed'] >= 3
    assert result.stats['unique_images'] >= 2
    assert len(list(result.media.values())) == result.stats['unique_images']
    assert result.blocks[0].count('[Imagem:') >= 3
    assert 'bbox=' in result.blocks[0]


def test_provider_api_keys_required(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    with pytest.raises(ValueError, match='OPENAI_API_KEY'):
        engine.invoke_model('openai', 'gpt-5.4-mini', 'medium', 'abc', 60)
    with pytest.raises(ValueError, match='ANTHROPIC_API_KEY'):
        engine.invoke_model('anthropic', 'claude-haiku-5-5', 'medium', 'abc', 60)


def test_checkpoint_resume_avoids_second_api_call(monkeypatch, tmp_path):
    calls = []
    def fake_call(provider, model, effort, prompt, timeout):
        calls.append(prompt)
        return json.dumps([{'id_conceito': 'q_123', 'pergunta': 'Pergunta?', 'resposta': 'Resposta', 'tags': []}])
    monkeypatch.setattr(engine, 'invoke_model', fake_call)
    class Args:
        checkpoint_dir = str(tmp_path)
        mode = 'curated'; lang = 'pt'; density = 'high'; filter = 'all'
        resume = True; retries = 1; timeout = 60; verify_pass = False
    first = engine.generate(['input'], {}, 'openai', 'mock-model', 'medium', Args(), 'sha')
    second = engine.generate(['input'], {}, 'openai', 'mock-model', 'medium', Args(), 'sha')
    assert first == second
    assert len(calls) == 1


def test_no_silent_partial_export(monkeypatch, tmp_path):
    def fail(*args):
        raise RuntimeError('timeout')
    monkeypatch.setattr(engine, 'invoke_model', fail)
    monkeypatch.setattr(engine.time, 'sleep', lambda *_: None)
    class Args:
        checkpoint_dir = str(tmp_path)
        mode = 'curated'; lang = 'pt'; density = 'high'; filter = 'all'
        resume = True; retries = 1; timeout = 60; verify_pass = False
    with pytest.raises(RuntimeError, match='Não gerarei um baralho incompleto'):
        engine.generate(['a', 'b'], {}, 'openai', 'mock-model', 'medium', Args(), 'sha')


def test_packaged_apkg_has_media_and_theme(tmp_path):
    genanki = pytest.importorskip('genanki')
    from PIL import Image
    import zipfile
    media_dir = tmp_path / 'media'
    image = Image.new('RGB', (120, 120), 'white')
    b = BytesIO(); image.save(b, format='PNG')
    name = engine.save_image(b.getvalue(), media_dir)
    media = {name: media_dir / name}
    cards = engine.parse_cards(json.dumps([{
        'id_conceito': 'test_card_image',
        'pergunta': f'Qual topologia? <img src="{name}">',
        'resposta': '<span class="ans">Rede em estrela</span>',
        'tags': ['redes']
    }]), media)
    out = tmp_path / 'test.apkg'
    basic, cloze, used = engine.write_apkg(cards, media, 'Teste::Redes', out, 'atlas')
    assert (basic, cloze) == (1, 0)
    assert used == {name}
    with zipfile.ZipFile(out) as z:
        assert 'media' in z.namelist()
        media_index = json.loads(z.read('media'))
        assert name in media_index.values()
        assert any(x.startswith('collection.anki') for x in z.namelist())


def test_one_image_one_card_fallback_and_strict_media(tmp_path):
    name = 'fa_' + 'b'*20 + '.webp'
    cards = engine.parse_cards(json.dumps([{'pergunta': 'O que representa?', 'resposta': 'Fluxograma'}]), {})
    media = {name: tmp_path / name}
    with pytest.raises(ValueError, match='strict-media'):
        engine.assert_media_coverage(cards, media)
    engine.attach_unambiguous_image(cards, f'[Imagem: {name} | pág=1; bbox=(1,2,3,4)]', media)
    assert name in cards[0]['pergunta']
    engine.assert_media_coverage(cards, media)


def test_verify_pass_performs_independent_revision(monkeypatch, tmp_path):
    prompts = []
    def fake_call(provider, model, effort, prompt, timeout):
        prompts.append(prompt)
        return json.dumps([{'id_conceito': 'rev_1', 'pergunta': 'Qual serviço?',
                            'resposta': 'DNS', 'tags': []}])
    monkeypatch.setattr(engine, 'invoke_model', fake_call)
    class Args:
        checkpoint_dir = str(tmp_path)
        mode = 'strict'; lang = 'pt'; density = 'high'; filter = 'all'
        resume = True; retries = 0; timeout = 60; verify_pass = True
    result = engine.generate(['DNS é usado aqui.'], {}, 'openai', 'test-model',
                             'high', Args(), 'check')
    assert len(result) == 1
    assert len(prompts) == 2
    assert 'AUDITORIA INDEPENDENTE' in prompts[1]


def test_openai_api_payload_and_effort(monkeypatch):
    requests = []
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, limit):
            return json.dumps({'choices': [{'message': {'content': '[{"pergunta":"X","resposta":"Y"}]'}}]}).encode()
    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()
    monkeypatch.setenv('OPENAI_API_KEY', 'unit-test-secret')
    monkeypatch.setattr(engine, 'urlopen', fake_urlopen)
    result = engine.invoke_model('openai', 'gpt-5.4-mini', 'high', 'doc', 55)
    payload = json.loads(requests[0][0].data)
    assert '"pergunta"' in result
    assert payload['reasoning_effort'] == 'high'
    assert payload['model'] == 'gpt-5.4-mini'
    assert requests[0][1] == 55
    assert requests[0][0].full_url == 'https://api.openai.com/v1/chat/completions'


def test_anthropic_api_payload_and_effort(monkeypatch):
    requests = []
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, limit):
            return json.dumps({'content': [{'type': 'thinking', 'thinking': 'hidden'},
                                           {'type': 'text', 'text': '[]'}]}).encode()
    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse()
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'unit-test-secret')
    monkeypatch.setattr(engine, 'urlopen', fake_urlopen)
    result = engine.invoke_model('anthropic', 'claude-haiku-5-5', 'xhigh', 'doc', 60)
    payload = json.loads(requests[0].data)
    assert result == '[]'
    assert payload['output_config']['effort'] == 'xhigh'
    assert payload['max_tokens'] == 16000
    assert requests[0].full_url == 'https://api.anthropic.com/v1/messages'


def test_clis_never_bypass_permissions(monkeypatch):
    calls = []
    class Result:
        returncode = 0
        stdout = '[]'
        stderr = ''
    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Result()
    monkeypatch.setattr(engine.subprocess, 'run', fake_run)
    assert engine.invoke_model('agy', 'test-model', 'high', 'foo', 45) == '[]'
    assert engine.invoke_model('claude-cli', 'haiku', 'high', 'foo', 45) == '[]'
    agy, claude = calls
    assert '--sandbox' in agy[0]
    assert '--dangerously-skip-permissions' not in str(calls)
    assert '--tools' in claude[0] and claude[0][claude[0].index('--tools') + 1] == ''
    assert claude[1]['input'] == 'foo'
    assert agy[1]['cwd'] and claude[1]['cwd']


def test_extract_only_generates_web_chat_manifest(tmp_path):
    fitz = pytest.importorskip('pymupdf')
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((45, 45), 'Question 1: Qual alternativa está correta?', fontsize=12)
    source = tmp_path / 'prova.pdf'
    pdf.save(source); pdf.close()
    manifest_target = tmp_path / 'manifest.apkg'
    args = engine.parser().parse_args(['--input', str(source), '--output', str(manifest_target),
                                       '--extract-only', '--non-interactive'])
    result = engine.run(args)
    manifest = Path(result['manifest'])
    assert manifest.exists()
    data = json.loads(manifest.read_text(encoding='utf-8'))
    assert data['source'] == source.name
    assert data['stats']['pages'] == 1
    assert 'Question 1' in data['blocks'][0]


def test_recommended_provider_defaults():
    args = engine.parser().parse_args(['--input', 'material.pdf'])
    assert args.provider == 'agy' and args.effort == 'high'
    local = engine.parser().parse_args(['--input', 'material.pdf', '--provider', 'ollama'])
    assert engine.DEFAULT_MODELS[local.provider] == 'qwen3:8b'


@pytest.mark.parametrize('model,thinking', [('qwen3:8b', False), ('gemma3:12b', None)])
def test_ollama_local_structured_output_without_api_key(monkeypatch, model, thinking):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    requests = []
    raw = json.dumps([{'id_conceito': 'dns_1', 'pergunta': 'O que é DNS?',
                       'resposta': 'Sistema de nomes de domínio.', 'tags': ['redes']}])
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, limit):
            return json.dumps({'message': {'content': raw}, 'done_reason': 'stop'}).encode()
    def call(request, timeout):
        requests.append((request, timeout))
        return Response()
    monkeypatch.setattr(engine, 'urlopen', call)
    cards = engine.parse_cards(engine.invoke_model('ollama', model, 'high', 'Texto DNS', 1200), {})
    assert len(cards) == 1 and cards[0]['id_conceito'] == 'dns_1'
    request, timeout = requests[0]
    assert request.full_url == 'http://127.0.0.1:11434/api/chat'
    assert timeout == 1200 and not request.has_header('Authorization')
    payload = json.loads(request.data)
    assert payload['model'] == model and payload['stream'] is False
    assert payload['format']['type'] == 'array'
    assert payload['options']['num_ctx'] == 8192
    assert payload['options']['temperature'] == 0.2
    assert payload.get('think') is thinking
    assert 'reasoning_effort' not in payload


@pytest.mark.parametrize('response', [
    {'message': {'content': ''}},
    {'message': {'content': '[]'}, 'done_reason': 'length'},
])
def test_ollama_rejects_empty_or_truncated_output(monkeypatch, response):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, limit): return json.dumps(response).encode()
    monkeypatch.setattr(engine, 'urlopen', lambda *args, **kwargs: Response())
    with pytest.raises(RuntimeError):
        engine.invoke_model('ollama', 'qwen3:8b', 'high', 'texto', 60)


@pytest.mark.parametrize('missing_model', [False, True])
def test_ollama_errors_are_actionable_without_cloud_fallback(monkeypatch, missing_model):
    calls = []
    def fail(request, timeout):
        calls.append(request.full_url)
        if missing_model:
            raise engine.HTTPError(request.full_url, 404, 'not found', {}, None)
        raise engine.URLError('Connection refused')
    monkeypatch.setattr(engine, 'urlopen', fail)
    with pytest.raises(RuntimeError, match='ollama pull' if missing_model else 'ollama serve'):
        engine.invoke_model('ollama', 'qwen3:8b', 'high', 'texto', 60)
    assert calls == ['http://127.0.0.1:11434/api/chat']
