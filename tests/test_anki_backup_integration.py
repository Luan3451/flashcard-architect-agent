"""Optional real Anki backend test; never opens a user's profile."""
import importlib.util
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from deck_maintenance import verify_package

pytestmark = pytest.mark.skipif(importlib.util.find_spec('anki') is None, reason='optional Anki backend not installed')


def test_real_anki_backup_restores_deleted_note_media_and_schedule(tmp_path):
    from anki.collection import Collection
    from anki.import_export_pb2 import ExportAnkiPackageOptions, ExportLimit, ImportAnkiPackageRequest, ImportAnkiPackageOptions
    source = Collection(str(tmp_path / 'source.anki2'))
    restored = None
    try:
        deck_id = source.decks.id('Backup Test')
        note = source.new_note(source.models.by_name('Basic'))
        note['Front'] = 'DNS? [sound:fixture.wav]'
        note['Back'] = 'Names'
        source.media.write_data('fixture.wav', b'original-media-bytes')
        source.add_note(note, deck_id)
        card = note.cards()[0]
        card.type = 2; card.queue = 2; card.ivl = 12; card.reps = 7; card.factor = 2500
        card.due = source.sched.today + 12
        source.update_card(card)
        package = tmp_path / 'backup.apkg'
        source.export_anki_package(out_path=str(package),
            options=ExportAnkiPackageOptions(with_scheduling=True, with_deck_configs=True, with_media=True, legacy=True),
            limit=ExportLimit(deck_id=deck_id))
        verify_package(package)
        source.remove_notes([note.id])
        assert source.note_count() == 0
        source.close()
        source = None
        restored = Collection(str(tmp_path / 'restored.anki2'))
        restored.import_anki_package(ImportAnkiPackageRequest(package_path=str(package), options=ImportAnkiPackageOptions(with_scheduling=True, with_deck_configs=True)))
        ids = restored.find_notes('deck:"Backup Test"')
        assert len(ids) == 1
        recovered = restored.get_note(ids[0])
        assert recovered['Back'] == 'Names'
        recovered_card = recovered.cards()[0]
        assert recovered_card.ivl == 12 and recovered_card.reps == 7
        assert (Path(restored.media.dir()) / 'fixture.wav').read_bytes() == b'original-media-bytes'
    finally:
        if source is not None: source.close()
        if restored is not None: restored.close()
