"""Real temporary Anki collections; never access a user's profile."""
import importlib.util
import json
from pathlib import Path
import sys
import zipfile
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from bridge_service import BridgeService, Policy
from native_anki import NativeAnki
from build_native_addon import build


def test_addon_package_reproducible_and_has_no_credentials(tmp_path):
    first = build(tmp_path / 'one.ankiaddon'); second = build(tmp_path / 'two.ankiaddon')
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as package:
        assert '__init__.py' in package.namelist() and 'bridge_service.py' in package.namelist()
        assert all('session.json' not in name and 'user_files' not in name for name in package.namelist())
        compile(package.read('__init__.py'), 'addon', 'exec')
        released = Path(__file__).resolve().parents[1] / 'addons' / 'flashcard_architect_bridge.ankiaddon'
        with zipfile.ZipFile(released) as shipped:
            assert shipped.namelist() == package.namelist()
            for name in package.namelist():
                assert shipped.read(name) == package.read(name), 'rebuild add-on after source edits'


@pytest.mark.skipif(importlib.util.find_spec('anki') is None, reason='optional real Anki test dependency')
def test_native_api_preview_backup_modify_and_recover(tmp_path):
    from anki.collection import Collection
    from anki.import_export_pb2 import ImportAnkiPackageRequest, ImportAnkiPackageOptions
    source = Collection(str(tmp_path / 'live.anki2')); recovery = None
    try:
        deck = source.decks.id('Scoped'); other = source.decks.id('Other')
        ids = []
        for i, term in enumerate(['SSH', 'OSPF', 'VLAN', 'ACL']):
            n = source.new_note(source.models.by_name('Basic')); n['Front'] = term; n['Back'] = 'Study source'
            source.add_note(n, deck); ids.append(n.id)
        external = source.new_note(source.models.by_name('Basic')); external['Front'] = 'SSH external'; external['Back'] = 'Keep'
        source.add_note(external, other)
        api = NativeAnki(source, 'Profile')
        service = BridgeService(Policy('Profile', 'Scoped'), tmp_path / 'backups')
        preview = service.handle(api, 'preview', {'action': 'highlight', 'terms': ['OSPF']})
        assert not '<mark' in source.get_note(ids[1])['Front']
        result = service.handle(api, 'apply', {'plan_id': preview['plan_id']}, approved=True)
        assert result['state'] == 'completed' and '<mark' in source.get_note(ids[1])['Front']
        assert api.last_changes is not None
        removal = service.handle(api, 'preview', {'action': 'remove-topic', 'terms': ['SSH']})
        result = service.handle(api, 'apply', {'plan_id': removal['plan_id']}, approved=True)
        assert not source.find_notes('deck:Scoped SSH')
        assert source.get_note(external.id)['Front'] == 'SSH external'
        backup_dir = Path(result['backup'])
        manifest = json.loads((backup_dir / 'manifest.json').read_text())
        recovery = Collection(str(tmp_path / 'recovery.anki2'))
        recovery.import_anki_package(ImportAnkiPackageRequest(package_path=str(backup_dir / manifest['packages'][0]['file']),
            options=ImportAnkiPackageOptions(with_scheduling=True, with_deck_configs=True)))
        assert len(recovery.find_notes('deck:Scoped')) == 4
        assert recovery.find_notes('deck:Scoped SSH')
        styling = service.handle(api, 'preview', {'action': 'style', 'theme': 'paper'})
        assert styling['preview']['blocked']  # shared Basic model must not affect Other
    finally:
        source.close()
        if recovery: recovery.close()


@pytest.mark.skipif(importlib.util.find_spec('anki') is None, reason='optional real Anki dependency')
def test_native_adapter_checks_revocation_before_each_action(tmp_path):
    from anki.collection import Collection
    col = Collection(str(tmp_path / 'guard.anki2'))
    try:
        active = [True]
        native = NativeAnki(col, 'Profile', guard=lambda: active[0])
        assert native('getActiveProfile') == 'Profile'
        active[0] = False
        with pytest.raises(RuntimeError): native('deleteNotes', notes=[1])
    finally: col.close()


@pytest.mark.skipif(importlib.util.find_spec('anki') is None, reason='optional real Anki dependency')
def test_bridge_study_plan_uses_anki_due_state_without_rescheduling(tmp_path):
    from anki.collection import Collection
    col = Collection(str(tmp_path / 'study.anki2'))
    try:
        deck = col.decks.id('Study')
        ids = []
        for term in ['OSPF', 'VLAN']:
            note = col.new_note(col.models.by_name('Basic')); note['Front'] = term; note['Back'] = 'Review'
            col.add_note(note, deck); ids.append(note.id)
        card = col.get_note(ids[1]).cards()[0]
        card.type = 2; card.queue = 2; card.due = col.sched.today - 1; card.ivl = 10; card.reps = 4
        col.update_card(card)
        before = (card.due, card.ivl, card.reps)
        service = BridgeService(Policy('P', 'Study'), tmp_path / 'backups')
        goal = {'mode': 'exam', 'reference': 'Synthetic v1', 'front_language': 'en', 'explanation_language': 'pt-BR',
            'topics': [{'id': 'routing', 'terms': ['OSPF']}, {'id': 'switching', 'terms': ['VLAN']}]}
        result = service.handle(NativeAnki(col, 'P'), 'study_plan', {'goal': goal})
        assert result['suggested_queue'][0]['id'] == ids[1]
        after = col.get_card(card.id)
        assert (after.due, after.ivl, after.reps) == before
    finally: col.close()
