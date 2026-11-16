"""Quality gates: synthetic fixtures, including previously exportable empty answers."""
import json
from pathlib import Path
import sqlite3
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import anki_generator as engine
import exam_coach as coach
import quality as qc


def card(front='SSH?', back='TCP 22', uid='ssh_1'):
    return {'pergunta': front, 'resposta': back, 'id_conceito': uid, 'tags': [], 'images': set()}


@pytest.mark.parametrize('empty', ['', ' ', '<script>bad()</script>', '<style>body{}</style>', '<p>&nbsp;</p>', '<span>\u200b</span>', '<div><br></div>', '[sound:unknown.wav]'])
def test_reject_empty_after_cleaning_without_dropping_valid_siblings(empty):
    data = [card(), card(back=empty, uid='invalid_2')]
    with pytest.raises(qc.QualityError) as caught:
        engine.parse_cards(json.dumps(data, default=list), {})
    assert caught.value.issues[0]['item'] == 2
    assert caught.value.issues[0]['field'] == 'resposta'


@pytest.mark.parametrize('invalid', [None, 'not a card', 1, {'pergunta': 'SSH?', 'resposta': None}])
def test_invalid_items_are_never_silently_skipped(invalid):
    with pytest.raises(qc.QualityError):
        engine.parse_cards(json.dumps([card(), invalid], default=list), {})


def test_valid_media_only_field_is_allowed(tmp_path):
    name = 'fa_' + 'a' * 20 + '.webp'
    value = card(front=f'<img src="{name}">')
    parsed = engine.parse_cards(json.dumps([value], default=list), {name: tmp_path / name})
    assert len(parsed) == 1
    assert not qc.field_issues(parsed[0]['pergunta'], parsed[0]['resposta'], {name})


def test_approved_audio_can_be_the_only_answer(tmp_path):
    name = 'fa_audio_' + 'b' * 20 + '.wav'
    parsed = engine.parse_cards(json.dumps([card(back=f'[sound:{name}]')], default=list), {name: tmp_path / name})
    assert len(parsed) == 1
    assert not qc.field_issues(parsed[0]['pergunta'], parsed[0]['resposta'], {name})


def test_direct_export_cannot_bypass_empty_field_check(tmp_path):
    target = tmp_path / 'old.apkg'
    target.write_bytes(b'preserve prior package')
    with pytest.raises(qc.QualityError):
        engine.write_apkg([card(back='<script>bad()</script>')], {}, 'Test', target, 'paper')
    assert target.read_bytes() == b'preserve prior package'
    report = json.loads(target.with_suffix('.quality.json').read_text())
    assert report['status'] == 'rejected' and report['errors'] == 1


def test_cli_pipeline_saves_rejection_report(tmp_path):
    source = tmp_path / 'input.json'; target = tmp_path / 'result.apkg'
    source.write_text(json.dumps([card(back='<script>bad()</script>')], default=list))
    args = engine.parser().parse_args(['--input', str(source), '--output', str(target), '--no-ai', '--non-interactive'])
    with pytest.raises(qc.QualityError): engine.run(args)
    assert not target.exists()
    assert json.loads(target.with_suffix('.quality.json').read_text())['status'] == 'rejected'


def test_quality_report_cannot_overwrite_input(tmp_path):
    source = tmp_path / 'result.quality.json'; source.write_text('original input')
    args = engine.parser().parse_args(['--input', str(source), '--output', str(tmp_path / 'result.apkg'), '--non-interactive'])
    with pytest.raises(ValueError, match='sobrescrever'): engine.run(args)
    assert source.read_text() == 'original input'


@pytest.mark.parametrize('front,expected', [
    ('SSH usa {{c1::22}}; porta 22.', '22'),
    ('{{c1::IP}} é um protocolo. IP faz parte da resposta.', 'ip'),
    ('{{c1::DNS}} e {{c2::DNS}}.', 'dns'),
    ('{{c1::DNS::DNS}}.', 'dns'),
    ('{{c1::atenção}}: atenção.', 'atenção'),
    ('{{c1::22}} e &#50;&#50;.', '22'),
])
def test_cloze_leaks_include_short_answers_hints_and_unicode(front, expected):
    assert any(i['code'] == 'cloze_answer_leak' and i['answer'] == expected for i in qc.cloze_issues(front))


@pytest.mark.parametrize('front', [
    '{{c1::DNS}} e {{c1::DNS}}.',
    '{{c2::22}} é a porta do SSH.',
    '{{c1::IP}} com RIP.',
    '{{c1::DNS::protocolo}} resolve nomes.',
])
def test_legal_clozes_are_not_blocked_or_falsely_flagged(front):
    assert qc.cloze_issues(front) == []


def test_back_side_answer_is_not_a_front_side_leak():
    assert not qc.audit_cards([card('{{c1::DNS}} resolve nomes.', 'DNS: resposta no verso')])


@pytest.mark.parametrize('front', ['{{c1::}}', '{{c0::DNS}}', '{{c1::DNS', '{{c1::a}} {{c2::b', '{{c1::a {{c2::b}}'])
def test_invalid_clozes_are_hard_errors(front):
    assert any(i['severity'] == 'error' for i in qc.cloze_issues(front))


@pytest.mark.parametrize('front', ['{{c1::a {{c2::b}}}}', '{{c1::2001:db8::/32}}'])
def test_complex_cloze_is_manual_review_instead_of_incorrect_partial_verdict(front):
    issues = qc.cloze_issues(front)
    assert issues and all(i['severity'] == 'warning' for i in issues)
    assert issues[0]['code'] == 'cloze_complex_syntax'


def test_cloze_media_is_not_mistaken_for_empty_answer():
    name = 'fa_' + 'a'*20 + '.webp'
    assert not qc.cloze_issues('{{c1::<img src="' + name + '">}}', media={name})


def test_leak_warns_tags_note_and_keeps_guid(tmp_path):
    import genanki
    target = tmp_path / 'warning.apkg'
    engine.write_apkg([card('{{c2::22}} é porta 22.')], {}, 'Test', target, 'paper')
    report = json.loads(target.with_suffix('.quality.json').read_text())
    assert report['status'] == 'review_required'
    with zipfile.ZipFile(target) as archive:
        database = tmp_path / 'collection.anki2'; database.write_bytes(archive.read('collection.anki2'))
    with sqlite3.connect(database) as con:
        guid, tags = con.execute('select guid,tags from notes').fetchone()
        assert guid == genanki.guid_for('Test', 'ssh_1') and 'revisar' in tags
        assert con.execute('select ord from cards').fetchone()[0] == 1


def test_html_comparisons_and_presentational_tags_are_preserved():
    text, _ = engine.sanitize_html('<b>Tempo</b> &lt;115 ms e &gt;50 ms.', set())
    assert text == '<b>Tempo</b> &lt;115 ms e &gt;50 ms.'


def test_number_and_unit_checks_are_conservative_and_dimension_aware():
    assert not qc.numeric_source_issues('O tempo é 50 ms.', 'The timer is 50 msec.')
    assert not qc.numeric_source_issues('O tempo é 50 milissegundos.', 'The timer is 50 ms.')
    assert qc.numeric_source_issues('O tempo é 50 s.', 'The timer is 50 ms.')[0]['code'] == 'number_unit_not_in_source'
    assert qc.numeric_source_issues('SSH usa 2222.', 'SSH uses TCP 22.')[0]['code'] == 'number_not_in_source'
    assert qc.numeric_source_issues('Taxa 10 MBps.', 'Rate 10 Mbps.')[0]['code'] == 'number_unit_not_in_source'
    assert not qc.numeric_source_issues('SSH usa TCP 22.', 'SSH uses TCP 22.')
    assert not qc.numeric_mentions('192.0.2.1 2001:db8::/32 g0/1 802.1Q /24')
    assert qc.numeric_source_issues('0.05 s', '50 ms')  # equivalent mathematically; requires review, never auto-converted


def test_exam_coach_marks_numeric_drift_without_changing_answer_or_calls():
    q = {'id': 'timer_1', 'stem': 'Which timer?', 'options': ['A. 50 ms'], 'answer': 'A. 50 ms', 'source': 'The timer is 50 ms.'}
    response = {'concept': 'Temporizador', 'mechanism': 'O tempo é 50 s.', 'evidence': 'The timer is 50 ms.', 'review_reason': ''}
    calls = []
    def invoke(prompt): calls.append(prompt); return json.dumps(response)
    cards, audit = coach.generate_questions([q], invoke)
    assert len(calls) == 1 and audit[0]['review_required']
    assert '50 ms' in cards[0]['resposta'] and 'revisar' in cards[0]['tags']
    assert 'Número/unidade' in cards[0]['resposta']
    checked = coach.validate_explanation(json.dumps(audit[0]['explanation']), q)
    assert checked['review_reason'].count('Número/unidade') == 1


def test_strict_quality_blocks_warnings_but_review_only_still_works(tmp_path):
    source = tmp_path / 'input.json'; target = tmp_path / 'result.apkg'
    source.write_text(json.dumps([card('{{c2::22}} é porta 22.')], default=list))
    argv = ['--input', str(source), '--output', str(target), '--no-ai', '--non-interactive', '--strict-quality']
    with pytest.raises(qc.QualityError): engine.run(engine.parser().parse_args(argv))
    assert not target.exists()
    assert json.loads(target.with_suffix('.quality.json').read_text())['status'] == 'rejected'
    result = engine.run(engine.parser().parse_args(argv + ['--review-only']))
    assert result['status'] == 'pending_review' and not target.exists()
    assert 'revisar' in json.loads(Path(result['review']).read_text())[0]['tags']


def test_strict_quality_recognizes_exam_coach_review_tag(tmp_path):
    uncertain = card(); uncertain['tags'] = ['exam_coach', 'revisar']
    with pytest.raises(qc.QualityError):
        engine.write_apkg([uncertain], {}, 'Test', tmp_path / 'review.apkg', 'paper', strict_quality=True)


def test_warning_report_confirms_successful_export(tmp_path):
    target = tmp_path / 'warning.apkg'
    engine.write_apkg([card('{{c1::IP}} usa IP.')], {}, 'Test', target, 'paper')
    report = json.loads(target.with_suffix('.quality.json').read_text())
    assert report['package_created'] and report['warnings'] == 1


def test_answer_correction_preserves_guid(tmp_path):
    def get_guid(back, filename):
        path = tmp_path / filename
        engine.write_apkg([card(back=back)], {}, 'Test', path, 'paper')
        with zipfile.ZipFile(path) as archive:
            db = path.with_suffix('.sqlite'); db.write_bytes(archive.read('collection.anki2'))
        with sqlite3.connect(db) as con:
            return con.execute('select guid from notes').fetchone()[0]
    assert get_guid('Antigo', 'a.apkg') == get_guid('Corrigido', 'b.apkg')


def test_strict_gate_runs_before_expensive_tts(tmp_path, monkeypatch):
    import audio_experimental
    monkeypatch.setattr(audio_experimental, 'narrate', lambda *args, **kwargs: pytest.fail('TTS must not run on rejected cards'))
    source = tmp_path / 'input.json'
    source.write_text(json.dumps([card('{{c1::22}} é porta 22.')], default=list))
    args = engine.parser().parse_args(['--input', str(source), '--output', str(tmp_path / 'result.apkg'), '--no-ai',
        '--non-interactive', '--strict-quality', '--experimental-audio', '--tts-voice', 'not-loaded.onnx'])
    with pytest.raises(qc.QualityError): engine.run(args)


def test_model_generated_empty_field_reports_chunk_and_prevents_partial_deck(tmp_path, monkeypatch):
    source = tmp_path / 'source.txt'; source.write_text('A source with sufficient text.')
    target = tmp_path / 'result.apkg'
    monkeypatch.setattr(engine, 'invoke_model', lambda *args: json.dumps([card(), card(back='<script>bad()</script>', uid='bad_2')], default=list))
    args = engine.parser().parse_args(['--input', str(source), '--output', str(target), '--provider', 'ollama',
        '--retries', '0', '--checkpoint-dir', str(tmp_path / 'cache'), '--non-interactive'])
    with pytest.raises(qc.QualityError): engine.run(args)
    report = json.loads(target.with_suffix('.quality.json').read_text())
    assert report['issues'][0]['chunk'] == 1 and report['issues'][0]['item'] == 2
    assert not target.exists() and not list((tmp_path / 'cache').glob('*.json'))
