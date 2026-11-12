import copy
import json
from pathlib import Path
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deck_maintenance as dm


class FakeAnki:
    def __init__(self, root):
        self.root = root
        self.profile = 'Teste'
        self.cards = {1: self.card(1, 10, 'Redes'), 2: self.card(2, 20, 'Outro')}
        self.notes = {10: self.note(10, [1]), 20: self.note(20, [2])}
        self.css = 'b {font-weight:bold}'
        self.mutations = []
        self.backup_ok = True
        self.exported = []
        self.fail_fields = False
    def card(self, cid, nid, deck):
        return {'cardId': cid, 'note': nid, 'deckName': deck, 'mod': 1, 'question': 'DNS?', 'answer': 'Nomes', 'modelName': 'Basic', 'css': 'original', 'queue': 2, 'due': 100, 'reps': 12}
    def note(self, nid, cards):
        return {'noteId': nid, 'cards': cards, 'modelName': 'Basic', 'fields': {'Front': {'value': '<b>DNS</b>?', 'order': 0}, 'Back': {'value': 'Nomes', 'order': 1}}, 'tags': ['redes'], 'mod': 1}
    def __call__(self, action, **kwargs):
        if action == 'deckNames': return ['Redes', 'Outro']
        if action == 'getActiveProfile': return self.profile
        if action == 'getMediaDirPath': return str(self.root)
        if action == 'findCards':
            if kwargs['query'].startswith('note:'): return sorted(self.cards)
            deck = json.loads(kwargs['query'][5:])
            return [cid for cid, c in self.cards.items() if c['deckName'] == deck]
        if action == 'cardsInfo': return copy.deepcopy([self.cards.get(cid, {}) for cid in kwargs['cards']])
        if action == 'notesInfo': return copy.deepcopy([self.notes.get(nid, {}) for nid in kwargs['notes']])
        if action == 'modelStyling': return {'css': self.css}
        if action == 'exportPackage':
            assert kwargs['includeSched'] is True
            if not self.backup_ok: return False
            with zipfile.ZipFile(kwargs['path'], 'w') as z:
                z.writestr('collection.anki2', 'backup-fixture-with-scheduling')
                z.writestr('media', '{}')
            self.exported.append(kwargs['path'])
            return True
        if action in {'deleteNotes', 'updateNoteFields', 'updateModelStyling'}:
            assert self.exported, 'mutation before backup'
            for path in self.exported: dm.verify_package(Path(path))
            self.mutations.append((action, kwargs))
            if action == 'updateNoteFields' and self.fail_fields: raise TimeoutError('unknown completion')
            if action == 'updateModelStyling': self.css = kwargs['model']['css']
            if action == 'updateNoteFields':
                for key, value in kwargs['note']['fields'].items():
                    self.notes[kwargs['note']['id']]['fields'][key]['value'] = value
            if action == 'deleteNotes':
                for nid in kwargs['notes']:
                    for cid in self.notes[nid]['cards']: self.cards.pop(cid)
                    self.notes.pop(nid)
            return None
        raise AssertionError(action)


def spec(action='remove-topic', decks=None):
    return {'action': action, 'decks': decks or ['Redes'], 'terms': ['DNS'], 'theme': 'paper'}


def test_preview_is_read_only_and_matches_whole_terms(tmp_path):
    api = FakeAnki(tmp_path)
    plan = dm.build_plan(api, spec())
    assert plan['delete_notes'] == [10] and plan['affected_cards'] == 1
    assert not api.exported and not api.mutations
    assert dm.contains_topic('Endereço IP', ['endereco']) == ['endereco']
    assert not dm.contains_topic('HTTP', ['IP'])


def test_backup_precedes_delete_and_preserves_other_deck(tmp_path):
    api = FakeAnki(tmp_path)
    plan = dm.build_plan(api, spec())
    directory = dm.apply_plan(api, plan, tmp_path / 'backups', plan['token'])
    assert 10 not in api.notes and 20 in api.notes
    before = json.loads((directory / 'before.json').read_text())
    assert before['notes'][0]['fields']['Front']['value'] == '<b>DNS</b>?'
    manifest = json.loads((directory / 'manifest.json').read_text())
    package = directory / manifest['packages'][0]['file']
    assert dm.verify_package(package) == manifest['packages'][0]['sha256']
    with zipfile.ZipFile(package) as archive:
        assert archive.read('collection.anki2') == b'backup-fixture-with-scheduling'
    assert json.loads((directory / 'journal.json').read_text())['status'] == 'completed'


@pytest.mark.parametrize('change', ['confirmation', 'fields', 'profile', 'plan'])
def test_stale_or_tampered_plan_cannot_mutate(tmp_path, change):
    api = FakeAnki(tmp_path)
    plan = dm.build_plan(api, spec())
    token = plan['token']
    if change == 'confirmation': token = 'wrong'
    elif change == 'fields': api.notes[10]['fields']['Front']['value'] = 'changed'
    elif change == 'profile': api.profile = 'Other'
    else: plan['delete_notes'] = [20]
    with pytest.raises(ValueError): dm.apply_plan(api, plan, tmp_path / 'backups', token)
    assert not api.mutations


def test_backup_failure_cancels_mutation(tmp_path):
    api = FakeAnki(tmp_path)
    api.backup_ok = False
    plan = dm.build_plan(api, spec())
    with pytest.raises(RuntimeError, match='backup'): dm.apply_plan(api, plan, tmp_path / 'backups', plan['token'])
    assert not api.mutations


def test_change_during_backup_cancels_mutation(tmp_path):
    api = FakeAnki(tmp_path)
    plan = dm.build_plan(api, spec())
    def changed(action, **kwargs):
        result = api(action, **kwargs)
        if action == 'exportPackage': api.notes[10]['mod'] += 1
        return result
    with pytest.raises(ValueError, match='durante backup'):
        dm.apply_plan(changed, plan, tmp_path / 'backups', plan['token'])
    assert not api.mutations


def test_shared_note_and_model_are_blocked(tmp_path):
    api = FakeAnki(tmp_path)
    api.notes[10]['cards'].append(2)
    plan = dm.build_plan(api, spec())
    assert not plan['delete_notes'] and plan['blocked']
    plan = dm.build_plan(api, spec('style'))
    assert not plan['model_updates'] and plan['blocked']
    plan = dm.build_plan(api, spec('highlight'))
    assert not plan['field_updates'] and plan['blocked']


def test_style_when_all_model_cards_in_scope(tmp_path):
    api = FakeAnki(tmp_path)
    plan = dm.build_plan(api, spec('style', ['Redes', 'Outro']))
    assert plan['model_updates'][0]['before'] == api.css
    assert 'FA maintenance theme' in plan['model_updates'][0]['css']
    dm.apply_plan(api, plan, tmp_path / 'backups', plan['token'])
    assert len(api.exported) == 2
    assert api.mutations[0][0] == 'updateModelStyling'


def test_highlight_preserves_attributes_cloze_sound_and_existing_marks():
    original = '<a title="DNS" href="https://dns.test">DNS</a> [sound:DNS.mp3]<code>DNS</code><mark>DNS</mark>&amp;'
    value = dm.highlight(original, ['DNS'])
    assert 'title="DNS" href="https://dns.test"' in value
    assert value.count('background:#ffe568') == 1
    assert '[sound:DNS.mp3]' in value
    cloze = '{{c1::<b>DNS</b>}}'
    assert dm.highlight(cloze, ['DNS']) == cloze
    assert dm.highlight('$DNS$', ['DNS']) == '$DNS$'
    assert '<code>DNS</code><mark>DNS</mark>&amp;' in value
    assert dm.highlight(value, ['DNS']) == value


def test_audio_missing_only_deletes_eligible_note(tmp_path):
    api = FakeAnki(tmp_path)
    api.cards[1]['question'] += '[sound:missing.mp3]'
    plan = dm.build_plan(api, spec('remove-broken-audio'))
    assert plan['delete_notes'] == [10]
    assert plan['audio']['missing.mp3']['status'] == 'missing'
    api.notes[10]['cards'] = [1, 3]
    api.cards[3] = api.card(3, 10, 'Redes')
    plan = dm.build_plan(api, spec('remove-broken-audio'))
    assert not plan['delete_notes'] and plan['blocked']


def test_external_audio_is_not_a_reason_to_delete(tmp_path):
    api = FakeAnki(tmp_path)
    api.cards[1]['answer'] = '<audio src="https://remote.test/a.mp3"></audio>'
    plan = dm.build_plan(api, spec('remove-broken-audio'))
    assert not plan['delete_notes']
    assert next(iter(plan['audio'].values()))['status'] == 'unknown'


def test_failed_write_is_journaled_and_not_retried(tmp_path):
    api = FakeAnki(tmp_path)
    api.fail_fields = True
    plan = dm.build_plan(api, spec('highlight'))
    with pytest.raises(RuntimeError, match='não repita'):
        dm.apply_plan(api, plan, tmp_path / 'backups', plan['token'])
    assert len(api.mutations) == 1
    journal = json.loads(next((tmp_path / 'backups').glob('*/journal.json')).read_text())
    assert journal['status'] == 'failed_or_uncertain' and journal['pending']


def test_invalid_backup_is_rejected(tmp_path):
    path = tmp_path / 'bad.apkg'
    with zipfile.ZipFile(path, 'w') as archive: archive.writestr('media', '{}')
    with pytest.raises(RuntimeError): dm.verify_package(path)


def test_audio_in_fields_when_anki_strips_playback_tags(tmp_path):
    api = FakeAnki(tmp_path)
    api.notes[10]['fields']['Back']['value'] += '[sound:missing.mp3]'
    plan = dm.build_plan(api, spec('remove-broken-audio'))
    assert plan['delete_notes'] == [10]
    assert plan['matches'][0]['basis'] == 'note_field_reference'
    api.notes[10]['cards'].append(3)
    api.cards[3] = api.card(3, 10, 'Redes')
    plan = dm.build_plan(api, spec('remove-broken-audio'))
    assert not plan['delete_notes'] and plan['blocked']
