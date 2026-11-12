import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import wave
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audio_experimental as audio
import anki_generator as engine


def write_wav(path):
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(22050)
        out.writeframes(b'\x00\x00' * 2205)


def test_audio_references_and_traversal(tmp_path):
    assert audio.audio_references('[sound:a.mp3]<audio><source src="b.wav"></audio><video src="c.mp4"></video>') == ['a.mp3', 'b.wav']
    for name in ('../a.mp3', 'C:\\a.wav', 'https://remote/a.mp3'):
        with pytest.raises(ValueError): audio.safe_media(tmp_path, name)


def test_audio_missing_empty_and_unavailable_decoder(tmp_path, monkeypatch):
    assert audio.inspect_audio(tmp_path / 'missing')['status'] == 'missing'
    path = tmp_path / 'empty'; path.touch()
    assert audio.inspect_audio(path)['status'] == 'empty'
    path.write_bytes(b'whatever')
    monkeypatch.setattr(shutil, 'which', lambda _: None)
    assert audio.inspect_audio(path)['status'] == 'unknown'


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg integration requires executable')
def test_real_decoder_valid_and_corrupt_audio(tmp_path):
    good = tmp_path / 'good.wav'; write_wav(good)
    assert audio.inspect_audio(good)['status'] == 'ok'
    bad = tmp_path / 'bad.mp3'; bad.write_bytes(b'not audio')
    assert audio.inspect_audio(bad)['status'] == 'undecodable'


def test_tts_packaging_and_cache(tmp_path):
    voice = tmp_path / 'voice.onnx'; voice.write_bytes(b'fixture')
    Path(str(voice) + '.json').write_text('{}')
    calls = []
    class Voice:
        def synthesize_wav(self, text, out):
            calls.append(text)
            out.setnchannels(1); out.setsampwidth(2); out.setframerate(22050)
            out.writeframes(b'\x00\x00' * 100)
    original = [{'id_conceito': 'dns_1', 'pergunta': 'DNS?', 'resposta': '<b>Nomes</b>', 'tags': []}]
    cards = engine.parse_cards(json.dumps(original), {})
    media = audio.narrate(cards, voice, tmp_path / 'media', voice=Voice())
    target = tmp_path / 'audio.apkg'
    engine.write_apkg(cards, media, 'Audio', target, 'paper')
    with zipfile.ZipFile(target) as archive:
        assert next(iter(media)) in json.loads(archive.read('media')).values()
    audio.narrate(engine.parse_cards(json.dumps(original), {}), voice, tmp_path / 'media', voice=Voice())
    assert calls == ['Nomes']


def test_speech_text_protects_cloze_and_omits_scripts():
    assert audio.speakable('<script>secret</script><p>DNS</p>[sound:a.wav]') == 'DNS'
    with pytest.raises(ValueError): audio.speakable('{{c1::resposta}}')


def test_sound_markup_requires_registered_safe_media():
    safe = 'fa_audio_' + 'a'*20 + '.wav'
    value, refs = engine.sanitize_html(f'[sound:../bad.mp3][sound:{safe}]', {safe})
    assert value == f'[sound:{safe}]' and refs == {safe}


def test_asr_outputs_timestamped_reviewable_text_and_local_only(tmp_path):
    source = tmp_path / 'lesson.wav'; write_wav(source)
    models = tmp_path / 'models'; models.mkdir()
    calls = []
    class ASR:
        def __init__(self, model, **kwargs): calls.append(kwargs)
        def transcribe(self, path, **kwargs):
            return iter([SimpleNamespace(start=0.0, end=1.5, text=' DNS resolve nomes. ')]), SimpleNamespace(language='pt')
    target = audio.transcribe(source, models, tmp_path / 'transcript', factory=ASR)
    assert '0.00s–1.50s' in target.read_text()
    assert calls[0]['local_files_only'] is True
    assert json.loads(target.with_suffix('.json').read_text())['review_required'] is True
    with pytest.raises(ValueError, match='já existe'):
        audio.transcribe(source, models, target.parent, factory=ASR)


def test_tts_requires_explicit_experimental_flag(tmp_path):
    source = tmp_path / 'cards.json'; source.write_text('[]')
    args = engine.parser().parse_args(['--input', str(source), '--tts-voice', 'voice.onnx', '--non-interactive'])
    with pytest.raises(ValueError, match='experimental-audio'): engine.run(args)
