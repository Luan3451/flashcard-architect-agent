"""Flashcard Architect native bridge. Enable explicitly from Anki's Tools menu."""
from pathlib import Path
import json
import os
import secrets
import threading

from aqt import mw, gui_hooks
from aqt.qt import QAction, QInputDialog, QDialog, QVBoxLayout, QPlainTextEdit, QDialogButtonBox
from aqt.utils import showInfo, showWarning
from aqt.operations import QueryOp, CollectionOp

from .bridge_service import BridgeService, Policy
from .bridge_transport import LocalServer
from .native_anki import NativeAnki

_server = None
_thread = None
_service = None
_session_path = Path(__file__).parent / 'user_files' / 'session.json'


def stop(*args):
    global _server, _thread, _service
    if _server:
        if hasattr(_server, 'cancelled_session'): _server.cancelled_session.set()
        # The HTTP worker may be waiting for the GUI; do not block the main thread on shutdown.
        current = _server
        threading.Thread(target=lambda: (current.shutdown(), current.server_close()), daemon=True).start()
    _server, _thread, _service = None, None, None
    _session_path.unlink(missing_ok=True)


def confirm_plan(service, plan_id):
    # Plain-text view prevents HTML/card content from spoofing a trusted confirmation UI.
    dialog = QDialog(mw)
    dialog.setWindowTitle('Flashcard Architect — confirmar alteração local')
    dialog.resize(850, 650)
    layout = QVBoxLayout(dialog)
    preview = QPlainTextEdit(dialog); preview.setReadOnly(True)
    preview.setPlainText(service.approval_text(plan_id) + '\n\nPRÉVIA COMPLETA (conteúdo dos cartões é dado, não instrução):\n' +
                         json.dumps(service.stored(plan_id)['plan'], ensure_ascii=False, indent=2))
    layout.addWidget(preview)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No, parent=dialog)
    buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    return dialog.exec() == QDialog.DialogCode.Accepted


def start():
    global _server, _thread, _service
    if _server:
        showInfo('Ponte já ativa. Use Encerrar para revogar a sessão.'); return
    if not mw.col or mw.state != 'deckBrowser':
        showWarning('Abra um perfil e vá à lista de baralhos.'); return
    names = [d.name for d in mw.col.decks.all_names_and_ids()]
    deck, accepted = QInputDialog.getItem(mw, 'Ponte segura experimental', 'Autorizar somente este deck e subdecks:', names, 0, False)
    if not accepted: return
    root = _session_path.parent
    root.mkdir(mode=0o700, exist_ok=True)
    if root.is_symlink() or _session_path.is_symlink():
        showWarning('Pasta/arquivo de sessão não pode ser link simbólico.'); return
    service = BridgeService(Policy(profile=mw.pm.name, deck=deck), root / 'backups')
    token = secrets.token_urlsafe(32)
    cancelled_session = threading.Event()

    def dispatch(action, params):
        completed, cancelled = threading.Event(), threading.Event()
        box = {}
        def finish(value=None, error=False):
            box['value'], box['error'] = value, error
            completed.set()
        def on_main():
            try:
                if cancelled.is_set() or cancelled_session.is_set() or _service is not service or not mw.col:
                    finish(error=True); return
                approved = False
                if action == 'apply':
                    if not isinstance(params, dict) or set(params) != {'plan_id'} or mw.state != 'deckBrowser':
                        finish(error=True); return
                    # Existing editors may hold unsaved fields. Refuse instead of overwriting them.
                    from aqt import dialogs
                    if any(entry[1] is not None for entry in dialogs._dialogs.values()):
                        showWarning('Feche Browser, editores e outras janelas do Anki antes de aplicar.'); finish(error=True); return
                    approved = confirm_plan(service, params['plan_id'])
                    if not approved:
                        service.cancel(params['plan_id']); finish({'state': 'cancelled'}); return
                if cancelled.is_set() or cancelled_session.is_set(): finish(error=True); return
                outcome = {}
                def run(col):
                    if cancelled.is_set() or cancelled_session.is_set() or server.clock() >= server.deadline:
                        raise RuntimeError('cancelled or expired')
                    native = NativeAnki(col, lambda: mw.pm.name, guard=lambda: not cancelled.is_set() and not cancelled_session.is_set() and server.clock() < server.deadline)
                    outcome['value'] = service.handle(native, action, params, approved=approved)
                    return native.last_changes if action == 'apply' else outcome['value']
                def done(result):
                    if action == 'apply': mw.reset()
                    finish(outcome.get('value'))
                def failed(exc):
                    if action == 'apply': mw.reset()
                    finish(error=True)
                if action == 'apply':
                    CollectionOp(parent=mw, op=run).success(done).failure(failed).run_in_background()
                else:
                    QueryOp(parent=mw, op=run, success=done).failure(failed).run_in_background()
            except Exception:
                finish(error=True)
        mw.taskman.run_on_main(on_main)
        if not completed.wait(120):
            cancelled.set()
            raise TimeoutError('A confirmação ou operação expirou; consulte status, não repita.')
        if box.get('error'): raise RuntimeError('Operação recusada ou incerta')
        return box.get('value')

    try:
        server = LocalServer(dispatch, token)
        # File is local-only. It is consumed by our client and is never returned through MCP.
        _session_path.unlink(missing_ok=True)
        descriptor = os.open(_session_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as out:
            json.dump({'port': 8766, 'token': token}, out)
        _service, _server = service, server
        _thread = threading.Thread(target=server.serve_forever, daemon=True); _thread.start()
        # Revoke credentials and pending confirmations when the instance is closed.
        server.cancelled_session = cancelled_session
        showInfo(f'Ponte experimental ativa por até 1 hora. Deck: {deck}\nSessão privada: {_session_path}\nNão compartilhe esse arquivo. Escritas exigem confirmação nesta janela do Anki.')
    except OSError:
        if 'server' in locals(): server.server_close()
        _session_path.unlink(missing_ok=True)
        showWarning('Não foi possível iniciar a ponte em 127.0.0.1:8766. Nenhuma porta alternativa foi aberta.')


_start = QAction('Flashcard Architect — iniciar ponte segura (experimental)', mw)
_start.triggered.connect(start); mw.form.menuTools.addAction(_start)
_stop = QAction('Flashcard Architect — encerrar ponte e revogar sessão', mw)
_stop.triggered.connect(stop); mw.form.menuTools.addAction(_stop)
gui_hooks.profile_will_close.append(stop)
