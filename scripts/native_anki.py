"""Internal adapter over Anki APIs. No HTTP arbitrary-action passthrough or SQL."""
from pathlib import Path


class NativeAnki:
    def __init__(self, collection, profile, max_cards=200, guard=lambda: True):
        self.col, self.profile, self.max_cards = collection, profile, max_cards
        self.last_changes = None
        self.guard = guard

    def __call__(self, action, **params):
        if not self.guard(): raise RuntimeError("Sessão revogada ou expirada")
        c = self.col
        if action == 'getActiveProfile': return self.profile() if callable(self.profile) else self.profile
        if action == 'deckNames': return [d.name for d in c.decks.all_names_and_ids()]
        if action == 'getMediaDirPath': return c.media.dir()
        if action == 'findCards':
            ids = list(c.find_cards(params['query']))
            if len(ids) > self.max_cards: raise ValueError('Escopo excede limite de cartões da sessão')
            return ids
        if action == 'notesInfo':
            if len(params['notes']) > self.max_cards: raise ValueError('Limite de notas')
            result = []
            for nid in params['notes']:
                try: n = c.get_note(nid)
                except Exception: result.append({}); continue
                result.append({'noteId': n.id, 'cards': [a.id for a in n.cards()], 'modelName': n.note_type()['name'],
                    'fields': {k: {'value': v, 'order': i} for i, (k, v) in enumerate(n.items())}, 'tags': list(n.tags), 'mod': n.mod})
            return result
        if action == 'cardsInfo':
            if len(params['cards']) > self.max_cards: raise ValueError('Limite de cartões')
            result = []
            for cid in params['cards']:
                card = c.get_card(cid); n = card.note(); model = n.note_type()
                if card.odid: raise ValueError('Cartões de baralho filtrado exigem manutenção manual')
                result.append({'cardId': card.id, 'note': card.nid, 'deckName': c.decks.get(card.did)['name'], 'mod': card.mod,
                    'modelName': model['name'], 'css': model['css'], 'question': card.question(), 'answer': card.answer(),
                    'queue': card.queue, 'type': card.type, 'due': card.due, 'interval': card.ivl, 'reps': card.reps, 'lapses': card.lapses})
            return result
        if action == 'modelStyling': return {'css': c.models.by_name(params['modelName'])['css']}
        if action == 'exportPackage':
            from anki.import_export_pb2 import ExportAnkiPackageOptions, ExportLimit
            deck = c.decks.by_name(params['deck'])
            if not deck: return False
            c.export_anki_package(out_path=params['path'],
                options=ExportAnkiPackageOptions(with_scheduling=True, with_deck_configs=True, with_media=True, legacy=True),
                limit=ExportLimit(deck_id=deck['id']))
            return True
        if action == 'deleteNotes':
            self.last_changes = c.remove_notes(params['notes']).changes
            return None
        if action == 'updateNoteFields':
            update = params['note']; n = c.get_note(update['id'])
            for key, value in update['fields'].items():
                if key not in dict(n.items()): raise ValueError('Campo desconhecido')
                n[key] = value
            self.last_changes = c.update_note(n); return None
        if action == 'updateModelStyling':
            update = params['model']; model = c.models.by_name(update['name'])
            model['css'] = update['css']; self.last_changes = c.models.update_dict(model); return None
        raise ValueError('Ação interna não permitida')
