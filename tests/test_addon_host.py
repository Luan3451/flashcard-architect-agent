"""Exercise native host over real HTTP/Anki with a simulated Qt dispatcher.

This validates the confirmation contract, not actual desktop window behavior.
"""
import importlib.util
import json
from pathlib import Path
import sys
import types
import urllib.request
import zipfile
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_native_addon import build
from bridge_transport import LocalServer

pytestmark = pytest.mark.skipif(importlib.util.find_spec('anki') is None, reason='optional Anki dependency')


def test_host_cannot_bypass_local_confirmation(tmp_path, monkeypatch):
    from anki.collection import Collection
    col = Collection(str(tmp_path / 'collection.anki2'))
    deck = col.decks.id('Scoped')
    note = col.new_note(col.models.by_name('Basic')); note['Front'] = 'OSPF'; note['Back'] = 'Protocol'
    col.add_note(note, deck)
    root = tmp_path / 'addon'; root.mkdir()
    with zipfile.ZipFile(build(tmp_path / 'bridge.ankiaddon')) as archive: archive.extractall(root)
    consent = [False]; prompts = []
    class Signal:
        def connect(self, fn): pass
    class Action:
        def __init__(self, *args): self.triggered = Signal()
    class Operation:
        def __init__(self, parent, op, success=None): self.op, self.ok, self.bad = op, success, None
        def success(self, fn): self.ok = fn; return self
        def failure(self, fn): self.bad = fn; return self
        def run_in_background(self):
            try: result = self.op(col)
            except Exception as exc: self.bad(exc)
            else: self.ok(result)
    mw = types.SimpleNamespace(col=col, state='deckBrowser', pm=types.SimpleNamespace(name='P'),
        taskman=types.SimpleNamespace(run_on_main=lambda fn: fn()), reset=lambda: None,
        form=types.SimpleNamespace(menuTools=types.SimpleNamespace(addAction=lambda _: None)))
    aqt = types.ModuleType('aqt'); aqt.mw = mw; aqt.gui_hooks = types.SimpleNamespace(profile_will_close=[])
    aqt.dialogs = types.SimpleNamespace(_dialogs={})
    qt = types.ModuleType('aqt.qt'); qt.QAction = Action
    qt.QInputDialog = types.SimpleNamespace(getItem=lambda *args: ('Scoped', True))
    for name in ('QDialog', 'QVBoxLayout', 'QPlainTextEdit', 'QDialogButtonBox'): setattr(qt, name, object)
    utils = types.ModuleType('aqt.utils')
    utils.showInfo = utils.showWarning = lambda *args: None
    utils.askUser = lambda text, **kwargs: prompts.append(text) or consent[0]
    ops = types.ModuleType('aqt.operations'); ops.QueryOp = ops.CollectionOp = Operation
    for name, module in [('aqt', aqt), ('aqt.qt', qt), ('aqt.utils', utils), ('aqt.operations', ops)]: monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location('fa_test_host', root / '__init__.py', submodule_search_locations=[str(root)])
    addon = importlib.util.module_from_spec(spec); monkeypatch.setitem(sys.modules, 'fa_test_host', addon); spec.loader.exec_module(addon)
    monkeypatch.setattr(addon, 'confirm_plan', lambda service, plan_id: prompts.append(service.approval_text(plan_id)) or consent[0])
    monkeypatch.setattr(addon, 'LocalServer', lambda dispatch, token: LocalServer(dispatch, token, port=0))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        addon.start(); server = addon._server
        session = json.loads((root / 'user_files' / 'session.json').read_text())
        def call(operation, **params):
            req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api',
                data=json.dumps({'action': operation, 'params': params}).encode(),
                headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '+session['token'], 'X-FA-Bridge': '1'})
            with opener.open(req, timeout=10) as response: return json.load(response)['result']
        preview = call('preview', action='highlight', terms=['OSPF'])
        assert call('apply', plan_id=preview['plan_id'])['state'] == 'cancelled'
        assert col.get_note(note.id)['Front'] == 'OSPF' and len(prompts) == 1
        preview = call('preview', action='highlight', terms=['OSPF'])
        consent[0] = True
        result = call('apply', plan_id=preview['plan_id'])
        assert result['state'] == 'completed' and '<mark' in col.get_note(note.id)['Front']
        assert Path(result['backup']).is_dir() and len(prompts) == 2
    finally:
        thread = addon._thread
        addon.stop()
        if thread: thread.join(timeout=2)
        col.close()
