import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import exam_coach as coach
import anki_generator as engine


def question():
    return {'id': 'ssh_1', 'stem': 'Which port? <literal>', 'options': ['A. 22', 'B. 23'],
            'answer': 'A. 22', 'source': 'SSH uses TCP 22. It encrypts administration traffic.', 'highlights': ['SSH', '22']}


def explanation():
    return {'concept': 'SSH oferece acesso remoto.', 'mechanism': 'O servidor aceita TCP 22 e estabelece uma sessão criptografada.',
            'evidence': 'SSH uses TCP 22.', 'review_reason': ''}


def test_one_question_one_card_and_exact_front():
    calls = []
    def invoke(prompt): calls.append(prompt); return json.dumps(explanation())
    cards, audit = coach.generate_questions([question()], invoke)
    assert len(calls) == len(cards) == 1
    assert cards[0]['pergunta'] == 'Which port? &lt;literal&gt;<br><br>A. 22<br>B. 23'
    assert '<details><summary>' in cards[0]['resposta']
    assert audit[0]['calls'] == 1 and not audit[0]['review_required']
    parsed = engine.parse_cards(json.dumps(cards, default=list), {})
    assert '<details>' in parsed[0]['resposta']


def test_missing_answer_or_false_evidence_requires_review():
    q = question(); q['answer'] = ''
    data = explanation(); data['evidence'] = 'Invented source'
    result = coach.validate_explanation(json.dumps(data), q)
    assert 'Gabarito não fornecido' in result['review_reason']
    assert 'Evidência ausente' in result['review_reason']
    card = coach.render_card(q, result)
    assert 'revisar' in card['tags'] and 'REVISAR' in card['resposta']


def test_model_html_is_escaped_and_cannot_change_question():
    data = explanation(); data['mechanism'] = '<img src="https://evil">'
    card = coach.render_card(question(), data)
    assert '<img' not in card['resposta'] and '&lt;img' in card['resposta']


def test_review_adds_exactly_one_call_and_keeps_source_in_both():
    calls = []
    def invoke(prompt): calls.append(prompt); return json.dumps(explanation())
    cards, audit = coach.generate_questions([question()], invoke, verify=True)
    assert len(calls) == 2 and audit[0]['calls'] == 2
    assert all(question()['source'] in prompt for prompt in calls)
    assert 'REVISÃO' in calls[1] and len(cards) == 1


def test_duplicate_ids_and_invalid_records_rejected_before_inference():
    with pytest.raises(ValueError): coach.question_records([question(), question()])
    bad = question(); bad['source'] = ''
    with pytest.raises(ValueError): coach.generate_questions([bad], lambda _: pytest.fail('must not invoke'))


def test_invalid_explanation_does_not_silently_create_cards():
    for raw in ('not JSON', '[]', '{"concept":"empty"}'):
        with pytest.raises(ValueError): coach.validate_explanation(raw, question())


def test_nonexistent_answer_is_flagged_instead_of_silently_accepted():
    q = question(); q['answer'] = 'C. invented'
    data = coach.validate_explanation(json.dumps(explanation()), q)
    assert 'Gabarito não corresponde' in data['review_reason']


def test_literal_exhibit_survives_without_rewriting_cli():
    q = question(); q['exhibit'] = 'R1(config)# ip ssh version 2\nR1# show ip ssh'
    card = coach.render_card(q, explanation())
    assert '<pre><code>' + q['exhibit'] + '</code></pre>' in card['pergunta']


def test_verified_checkpoint_avoids_calls_and_is_invalidated_by_model(tmp_path):
    calls = []
    def invoke(prompt): calls.append(prompt); return json.dumps(explanation())
    coach.generate_questions([question()], invoke, True, tmp_path, identity='model-a')
    assert len(calls) == 2
    cards, audit = coach.generate_questions([question()], invoke, True, tmp_path, identity='model-a')
    assert len(calls) == 2 and audit[0]['calls'] == 0 and audit[0]['cached']
    coach.generate_questions([question()], invoke, True, tmp_path, identity='model-b')
    assert len(calls) == 4


def test_corrupt_checkpoint_regenerates(tmp_path):
    invoke = lambda _: json.dumps(explanation())
    coach.generate_questions([question()], invoke, False, tmp_path)
    next(tmp_path.glob('*.json')).write_text('bad JSON')
    _, audit = coach.generate_questions([question()], invoke, False, tmp_path)
    assert audit[0]['calls'] == 1 and not audit[0]['cached']


def test_uncertain_answer_is_never_labelled_as_confirmed_correct():
    data = explanation(); data['review_reason'] = 'Gabarito contradiz a fonte.'
    card = coach.render_card(question(), data)
    assert 'Gabarito fornecido — REVISAR' in card['resposta']
    assert 'Correct answer' not in card['resposta']


def test_highlights_are_bounded_and_do_not_match_inside_other_terms():
    q = question(); q['highlights'] = ['IP']
    data = explanation(); data['concept'] = 'IP ' * 10; data['mechanism'] = 'RIP ' + 'IP ' * 10
    card = coach.render_card(q, data)
    assert card['resposta'].count('class="k-key"') == 8
    assert 'RIP' in card['resposta'] and 'R<span' not in card['resposta']
