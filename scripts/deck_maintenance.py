"""Local AnkiConnect maintenance. Preview -> verified backup -> bounded mutation.

No automatic sync. Never opens or writes Anki's live SQLite database.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.request import Request, build_opener, ProxyHandler
import uuid
import zipfile

try:
    from .audio_experimental import audio_references, inspect_audio, safe_media
    from .themes import css_for_theme
except ImportError:
    from audio_experimental import audio_references, inspect_audio, safe_media
    from themes import css_for_theme

BAD_AUDIO = {'missing', 'empty', 'undecodable', 'no_audio'}
ACTIONS = {'remove-topic', 'remove-broken-audio', 'style', 'highlight'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def file_sha(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def write_json(path, data):
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8') as out:
        json.dump(data, out, ensure_ascii=False, indent=2)
        out.flush()
        os.fsync(out.fileno())
    temp.replace(path)


class AnkiClient:
    def __init__(self):
        self.key = os.environ.get('ANKICONNECT_API_KEY')
        self.opener = build_opener(ProxyHandler({}))  # loopback must not use cloud proxies

    def __call__(self, action, **params):
        payload = {'action': action, 'version': 6, 'params': params}
        if self.key:
            payload['key'] = self.key
        req = Request('http://127.0.0.1:8765', data=json.dumps(payload).encode(),
                      headers={'Content-Type': 'application/json'})
        # Mutations are never retried: a timeout can mean the action completed.
        with self.opener.open(req, timeout=300) as response:
            data = json.load(response)
        if data.get('error'):
            raise RuntimeError(f"AnkiConnect {action}: {data['error']}")
        return data['result']


def quote(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.skip += 1
        self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.skip = max(0, self.skip - 1)
        self.parts.append(' ')
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def plain(text):
    parser = PlainText()
    parser.feed(text)
    return ' '.join(''.join(parser.parts).split())


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


def contains_topic(text, terms):
    text = normalize(plain(text))
    return [term for term in terms if re.search(r'(?<!\w)' + re.escape(normalize(term)) + r'(?!\w)', text)]


class Highlighter(HTMLParser):
    """Preserve original tags/attributes and protect cloze, sound and code syntax."""
    def __init__(self, terms):
        super().__init__(convert_charrefs=False)
        self.pattern = re.compile(r'(?<!\w)(' + '|'.join(re.escape(t) for t in sorted(terms, key=len, reverse=True)) + r')(?!\w)', re.I)
        self.out, self.stack = [], []
    def handle_starttag(self, tag, attrs):
        self.out.append(self.get_starttag_text())
        if tag not in {'br', 'img', 'hr', 'input', 'source', 'meta', 'link', 'wbr'}:
            self.stack.append(tag)
    def handle_startendtag(self, tag, attrs):
        self.out.append(self.get_starttag_text())
    def handle_endtag(self, tag):
        self.out.append(f'</{tag}>')
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack) - 1 - self.stack[::-1].index(tag)]
    def handle_data(self, data):
        if any(t in self.stack for t in {'script', 'style', 'code', 'pre', 'mark', 'textarea', 'math'}) or any(t in data for t in ('{{', '[sound:', '\\(', '\\[')):
            self.out.append(data)
        else:
            self.out.append(self.pattern.sub(r'<mark style="background:#ffe568;color:#172337;font-weight:700">\1</mark>', data))
    def handle_entityref(self, name): self.out.append(f'&{name};')
    def handle_charref(self, name): self.out.append(f'&#{name};')
    def handle_comment(self, data): self.out.append(f'<!--{data}-->')
    def handle_decl(self, decl): self.out.append(f'<!{decl}>')


def highlight(text, terms):
    parser = Highlighter(terms)
    parser.feed(text)
    parser.close()
    return ''.join(parser.out)


def chunks(items, size=250):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def records(client, action, key, ids):
    result = []
    for batch in chunks(ids):
        result.extend(client(action, **{key: batch}))
    if len(result) != len(ids) or any(not item for item in result):
        raise RuntimeError('Coleção mudou durante a leitura; gere outra prévia')
    return result


def build_plan(client, spec):
    if spec['action'] not in ACTIONS:
        raise ValueError('Ação inválida')
    decks = sorted(set(spec['decks']))
    if not decks or any(deck not in client('deckNames') for deck in decks):
        raise ValueError('Selecione decks existentes explicitamente')
    terms = [term.strip() for term in spec.get('terms', []) if term.strip()]
    if spec['action'] in {'remove-topic', 'highlight'} and not terms:
        raise ValueError('Informe termos explícitos; não interpretamos comandos livres como exclusão')
    if len(terms) > 50 or any(len(t) > 200 for t in terms):
        raise ValueError('Limite de 50 termos de até 200 caracteres')
    ids = sorted(set(cid for deck in decks for cid in client('findCards', query='deck:' + quote(deck))))
    cards = records(client, 'cardsInfo', 'cards', ids)
    # Reject any unexpected search expansion. Subdecks are explicitly included.
    if any(not any(c['deckName'] == d or c['deckName'].startswith(d + '::') for d in decks) for c in cards):
        raise RuntimeError('Busca retornou cartões fora dos decks selecionados')
    notes = records(client, 'notesInfo', 'notes', sorted({c['note'] for c in cards}))
    profile = client('getActiveProfile')
    by_note = {n['noteId']: n for n in notes}
    selected = set(ids)
    shared = {n['noteId'] for n in notes if not set(n['cards']).issubset(selected)}
    snapshots = [{k: c.get(k) for k in ('cardId', 'note', 'deckName', 'mod', 'question', 'answer', 'modelName', 'css', 'queue', 'type', 'due', 'interval', 'reps', 'lapses')} for c in cards]
    plan = {'schema': 1, 'profile': profile, 'spec': spec, 'cards': snapshots, 'notes': notes,
            'delete_notes': [], 'field_updates': [], 'model_updates': [], 'matches': [], 'blocked': [], 'audio': {}}
    action = spec['action']
    if action == 'remove-topic':
        for note in notes:
            hits = contains_topic(' '.join(f['value'] for f in note['fields'].values()) + ' ' + ' '.join(note.get('tags', [])), terms)
            if hits:
                plan['matches'].append({'note': note['noteId'], 'cards': note['cards'], 'terms': hits,
                                        'preview': plain(' '.join(f['value'] for f in note['fields'].values()))[:300]})
                if note['noteId'] in shared:
                    plan['blocked'].append({'note': note['noteId'], 'reason': 'nota tem cartões em outro deck'})
                else:
                    plan['delete_notes'].append(note['noteId'])
    elif action == 'remove-broken-audio':
        root = Path(client('getMediaDirPath')).resolve()
        if not root.is_dir():
            raise ValueError('Execute na mesma máquina do Anki; pasta de mídia não acessível')
        bad_cards = set()
        for card in cards:
            names = audio_references(card['question'] + card['answer'])
            note = by_note[card['note']]
            basis = 'rendered_reference'
            uncertain_siblings = False
            if not names:
                # Modern Anki can strip playback tags from rendered HTML.
                names = audio_references(' '.join(f['value'] for f in note['fields'].values()))
                basis = 'note_field_reference'
                uncertain_siblings = len(note['cards']) > 1
            bad = []
            for name in names:
                if name not in plan['audio']:
                    try:
                        path = safe_media(root, name)
                        item = inspect_audio(path)
                        if path.is_file() and path.stat().st_size <= 100 * 1024 * 1024:
                            item['sha256'] = file_sha(path)
                    except ValueError:
                        item = {'status': 'unknown', 'reason': 'referência externa ou insegura'}
                    plan['audio'][name] = item
                if plan['audio'][name]['status'] in BAD_AUDIO:
                    bad.append(name)
            if bad:
                if uncertain_siblings:
                    plan['blocked'].append({'note': card['note'], 'reason': 'áudio em campos; associação a cartões irmãos não verificável'})
                else:
                    bad_cards.add(card['cardId'])
                plan['matches'].append({'card': card['cardId'], 'note': card['note'], 'broken_audio': bad, 'basis': basis})
        for note in notes:
            siblings = set(note['cards'])
            if siblings & bad_cards:
                if siblings.issubset(bad_cards) and note['noteId'] not in shared:
                    plan['delete_notes'].append(note['noteId'])
                else:
                    plan['blocked'].append({'note': note['noteId'], 'reason': 'nota tem cartão saudável ou fora do escopo'})
    elif action == 'highlight':
        for note in notes:
            fields = {name: highlight(f['value'], terms) for name, f in note['fields'].items()}
            fields = {name: value for name, value in fields.items() if value != note['fields'][name]['value']}
            if fields:
                if note['noteId'] in shared:
                    plan['blocked'].append({'note': note['noteId'], 'reason': 'nota compartilhada com outro deck'})
                else:
                    plan['field_updates'].append({'id': note['noteId'], 'fields': fields})
    else:
        theme = spec.get('theme', 'paper')
        for name in sorted({c['modelName'] for c in cards}):
            model_cards = set(client('findCards', query='note:' + quote(name)))
            expected = {c['cardId'] for c in cards if c['modelName'] == name}
            if not expected.issubset(model_cards):
                raise RuntimeError('Busca de modelo incompleta; operação cancelada')
            if not model_cards.issubset(selected):
                plan['blocked'].append({'model': name, 'reason': 'estilo compartilhado com cartões fora do escopo'})
                continue
            old = client('modelStyling', modelName=name)['css']
            marker = '/* FA maintenance theme */'
            base = old.split(marker)[0].rstrip()
            css = base + '\n' + marker + '\n' + css_for_theme(theme)
            if css != old:
                plan['model_updates'].append({'name': name, 'before': old, 'css': css})
    plan['delete_notes'].sort()
    plan['affected_cards'] = sum(len(by_note[n]['cards']) for n in plan['delete_notes'])
    plan['token'] = digest(plan)[:16]
    return plan


def verify_package(path):
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError('Backup não foi criado')
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if not names.intersection({'collection.anki2', 'collection.anki21', 'collection.anki21b'}) or 'media' not in names or archive.testzip():
            raise RuntimeError('Backup APKG inválido/incompleto; operação cancelada')
    return file_sha(path)


def backup(client, plan, root):
    root.mkdir(parents=True, exist_ok=True)
    directory = root / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:10])
    directory.mkdir(mode=0o700)
    manifest = {'profile': plan['profile'], 'created': datetime.now(timezone.utc).isoformat(), 'packages': [],
                'restore': 'Importe os APKG em um perfil temporário do Anki para verificar. Para estilo/campos, consulte before.json. Reimportar não é rollback atômico da coleção.'}
    write_json(directory / 'before.json', plan)
    write_json(directory / 'manifest.json', manifest)
    # Export top-level selected decks only: each package also contains its subdecks.
    decks = sorted(set(plan['spec']['decks']))
    for deck in decks:
        if any(deck.startswith(parent + '::') for parent in decks if parent != deck):
            continue
        path = directory / (hashlib.sha256(deck.encode()).hexdigest()[:16] + '.apkg')
        if client('exportPackage', deck=deck, path=str(path.resolve()), includeSched=True) is not True:
            raise RuntimeError('Anki recusou o backup; nenhuma alteração será aplicada')
        manifest['packages'].append({'deck': deck, 'file': path.name, 'sha256': verify_package(path), 'includeSched': True})
        write_json(directory / 'manifest.json', manifest)
    return directory


def apply_plan(client, plan, root, confirmation):
    lock = Path(tempfile.gettempdir()) / ('fa-maintenance-' + digest(plan.get('profile'))[:24] + '.lock')
    try:
        handle = lock.open('x')
    except FileExistsError as exc:
        raise RuntimeError(f'Manutenção já ativa ou interrompida. Verifique o processo antes de remover {lock}') from exc
    try:
        with handle:
            handle.write(str(os.getpid()))
        return _apply_plan(client, plan, root, confirmation)
    finally:
        lock.unlink(missing_ok=True)


def _apply_plan(client, plan, root, confirmation):
    if confirmation != plan.get('token'):
        raise ValueError('Confirmação deve ser o token exato da prévia')
    fresh = build_plan(client, plan['spec'])
    if fresh != plan:
        raise ValueError('Plano alterado ou coleção/mídia mudou; gere uma nova prévia')
    if not any(plan[k] for k in ('delete_notes', 'field_updates', 'model_updates')):
        raise ValueError('Nenhuma mudança elegível')
    directory = backup(client, plan, root)
    # Catch edits/reviews/profile switches during slow export before mutating anything.
    if build_plan(client, plan['spec']) != plan:
        raise ValueError(f'Coleção mudou durante backup; cancelado. Backup: {directory}')
    journal = {'status': 'applying', 'completed': [], 'pending': None}
    write_json(directory / 'journal.json', journal)
    operations = [('updateModelStyling', {'model': {'name': m['name'], 'css': m['css']}}) for m in plan['model_updates']]
    operations += [('updateNoteFields', {'note': note}) for note in plan['field_updates']]
    if plan['delete_notes']:
        operations.append(('deleteNotes', {'notes': plan['delete_notes']}))
    try:
        for action, params in operations:
            if client('getActiveProfile') != plan['profile']:
                raise RuntimeError('Perfil mudou; operação interrompida')
            journal['pending'] = {'action': action, 'params': params}
            write_json(directory / 'journal.json', journal)
            client(action, **params)
            if action == 'deleteNotes':
                remaining = client('notesInfo', notes=params['notes'])
                if any(remaining):
                    raise RuntimeError('Exclusão não foi confirmada')
            elif action == 'updateModelStyling':
                model = params['model']
                if client('modelStyling', modelName=model['name'])['css'] != model['css']:
                    raise RuntimeError('Estilo não foi confirmado')
            else:
                update = params['note']
                current = client('notesInfo', notes=[update['id']])
                if not current or not current[0] or any(current[0]['fields'][key]['value'] != value for key, value in update['fields'].items()):
                    raise RuntimeError('Alteração de campos não foi confirmada')
            journal['completed'].append(journal['pending'])
            journal['pending'] = None
            write_json(directory / 'journal.json', journal)
        journal['status'] = 'completed'
    except Exception as exc:
        journal['error_type'] = type(exc).__name__
        journal['status'] = 'failed_or_uncertain'
        write_json(directory / 'journal.json', journal)
        raise RuntimeError(f'Operação interrompida; não repita automaticamente. Consulte {directory}')
    write_json(directory / 'journal.json', journal)
    return directory


def main():
    parser = argparse.ArgumentParser(description='Manutenção EXPERIMENTAL via AnkiConnect local; exige backup antes de alterar')
    sub = parser.add_subparsers(dest='command', required=True)
    preview = sub.add_parser('preview')
    preview.add_argument('--deck', action='append', required=True)
    preview.add_argument('--action', choices=sorted(ACTIONS), required=True)
    preview.add_argument('--term', action='append', default=[])
    preview.add_argument('--theme', choices=['studio', 'atlas', 'paper', 'contrast'], default='paper')
    preview.add_argument('--plan', type=Path, required=True)
    apply = sub.add_parser('apply')
    apply.add_argument('--plan', type=Path, required=True)
    apply.add_argument('--confirm', required=True)
    apply.add_argument('--backup-dir', type=Path, default=Path('backups'))
    args = parser.parse_args()
    client = AnkiClient()
    try:
        if args.command == 'preview':
            if args.plan.exists():
                raise ValueError('Plano já existe; escolha outro nome')
            plan = build_plan(client, {'decks': args.deck, 'action': args.action, 'terms': args.term, 'theme': args.theme})
            args.plan.parent.mkdir(parents=True, exist_ok=True)
            write_json(args.plan, plan)
            print(f"Prévia: {args.plan}; notas a excluir: {len(plan['delete_notes'])}; cartões: {plan['affected_cards']}; bloqueios: {len(plan['blocked'])}; token: {plan['token']}")
        else:
            plan = json.loads(args.plan.read_text(encoding='utf-8'))
            print(f'Concluído. Backup e registro: {apply_plan(client, plan, args.backup_dir.resolve(), args.confirm)}')
    except (OSError, ValueError, RuntimeError, KeyError, zipfile.BadZipFile) as exc:
        parser.exit(1, f'Falha: {exc}\n')


if __name__ == '__main__':
    main()
