"""Session-scoped bridge policy. Mutations only consume stored, UI-approved plans."""
from __future__ import annotations
import copy
from dataclasses import dataclass
import json
from pathlib import Path
import secrets
import threading
import time

try:
    from . import deck_maintenance as maintenance
    from .study_planner import plan_study
except ImportError:
    import deck_maintenance as maintenance
    from study_planner import plan_study


@dataclass(frozen=True)
class Policy:
    profile: str
    deck: str
    max_cards: int = 200
    max_changed_notes: int = 50
    max_delete_fraction: float = 0.25
    plan_ttl: float = 300


class BridgeService:
    def __init__(self, policy, backup_root, clock=time.monotonic):
        self.policy = policy
        self.backup_root = Path(backup_root).resolve()
        self.clock = clock
        self.plans = {}
        self.lock = threading.Lock()
        self.used_changes = 0

    def stored(self, plan_id):
        entry = self.plans.get(plan_id)
        if not entry or self.clock() > entry['expires']:
            raise ValueError('Plano inexistente ou expirado')
        return entry

    def cancel(self, plan_id):
        entry = self.stored(plan_id)
        if entry['state'] == 'pending': entry['state'] = 'cancelled'

    def approval_text(self, plan_id):
        entry = self.stored(plan_id)
        if entry['state'] != 'pending': raise ValueError('Plano já consumido')
        p = entry['plan']
        return (f"Perfil: {self.policy.profile}\nDeck e subdecks: {self.policy.deck}\n"
                f"Ação: {p['spec']['action']}\nTermos literais: {json.dumps(p['spec'].get('terms', []), ensure_ascii=False)}\nNotas excluídas: {len(p['delete_notes'])}; cartões: {p['affected_cards']}\n"
                f"Notas editadas: {len(p['field_updates'])}; modelos editados: {len(p['model_updates'])}\n"
                f"Backup obrigatório em: {self.backup_root}\n"
                'Confirma este plano após conferir a prévia? Não edite, revise ou sincronize durante a aplicação.')

    def handle(self, client, action, params, *, approved=False):
        if client('getActiveProfile') != self.policy.profile:
            raise ValueError('Perfil da sessão mudou; reinicie a ponte')
        allowed = {'list_decks': set(), 'read_notes': set(), 'preview': {'action', 'terms', 'theme'},
                   'apply': {'plan_id'}, 'status': {'plan_id'}, 'study_plan': {'goal', 'limit'}}
        if action not in allowed or not isinstance(params, dict) or set(params) - allowed[action]:
            raise ValueError('Operação ou parâmetros não permitidos')
        if action == 'list_decks': return {'decks': [self.policy.deck], 'profile': self.policy.profile}
        if action in {'read_notes', 'study_plan'}:
            ids = client('findCards', query='deck:' + maintenance.quote(self.policy.deck))
            if len(ids) > self.policy.max_cards: raise ValueError('Escopo excessivo')
            cards = maintenance.records(client, 'cardsInfo', 'cards', ids)
            self.check_scope(cards)
            notes = maintenance.records(client, 'notesInfo', 'notes', sorted({c['note'] for c in cards}))
            # A study suggestion is by note, not by sibling template; no scheduling changes.
            due_ids = set(client('findCards', query='deck:' + maintenance.quote(self.policy.deck) + ' is:due'))
            if not due_ids.issubset(set(ids)): raise ValueError('Busca de revisões fora do escopo')
            due_notes = {c['note'] for c in cards if c['cardId'] in due_ids}
            data = [{'id': n['noteId'], 'text': maintenance.plain(' '.join(f['value'] for f in n['fields'].values())),
                     'needs_review': 'revisar' in n.get('tags', []), 'due': n['noteId'] in due_notes} for n in notes]
            if action == 'read_notes': return {'notes': data, 'content_is_untrusted': True}
            if 'goal' not in params: raise ValueError('goal obrigatório')
            return plan_study(data, params['goal'], params.get('limit', 20))
        if action == 'status':
            entry = self.stored(params.get('plan_id'))
            return {'state': entry['state'], 'backup': entry.get('backup')}
        if action == 'preview':
            if params.get('action') not in {'highlight', 'style', 'remove-topic'}:
                raise ValueError('Ação de manutenção não habilitada na ponte')
            terms = params.get('terms', [])
            if not isinstance(terms, list) or not all(isinstance(t, str) and len(t) <= 200 for t in terms):
                raise ValueError('Termos inválidos')
            spec = {'action': params['action'], 'decks': [self.policy.deck], 'terms': terms, 'theme': params.get('theme', 'paper')}
            plan = maintenance.build_plan(client, spec)
            self.check_scope(plan['cards'])
            changed = len(plan['delete_notes']) + len(plan['field_updates'])
            if changed > self.policy.max_changed_notes: raise ValueError('Limite de alterações excedido')
            total = len(plan['notes'])
            if plan['delete_notes'] and len(plan['delete_notes']) / max(total, 1) > self.policy.max_delete_fraction:
                raise ValueError('Exclusão excede fração permitida; ajuste o escopo localmente')
            if plan['model_updates'] and total > self.policy.max_changed_notes:
                raise ValueError('Modelo afetaria notas demais')
            if len(self.plans) >= 20:
                expired = [key for key, value in self.plans.items() if self.clock() > value['expires']]
                for key in expired: del self.plans[key]
                if len(self.plans) >= 20: raise ValueError('Limite de prévias da sessão')
            plan_id = secrets.token_urlsafe(24)
            self.plans[plan_id] = {'plan': copy.deepcopy(plan), 'expires': self.clock() + self.policy.plan_ttl, 'state': 'pending'}
            return {'plan_id': plan_id, 'expires_in_seconds': self.policy.plan_ttl,
                'preview': {k: plan[k] for k in ('spec', 'affected_cards', 'delete_notes', 'field_updates', 'model_updates', 'matches', 'blocked')},
                'requires_confirmation_in_anki': True}
        # No client-supplied approval field, token, path, SQL or mutation body is accepted.
        if approved is not True: raise ValueError('Confirmação local no Anki obrigatória')
        if not self.lock.acquire(blocking=False): raise ValueError('Outra aplicação em andamento')
        try:
            entry = self.stored(params.get('plan_id'))
            if entry['state'] != 'pending': raise ValueError('Plano consumido; não repetir')
            plan = entry['plan']
            change_count = len(plan['delete_notes']) + len(plan['field_updates']) + (len(plan['notes']) if plan['model_updates'] else 0)
            if change_count == 0: raise ValueError('Plano sem alterações aplicáveis')
            if self.used_changes + change_count > self.policy.max_changed_notes:
                raise ValueError('Orçamento de alterações da sessão esgotado')
            self.used_changes += change_count  # uncertain operations still consume budget
            entry['state'] = 'applying'  # consume before any IO; timeouts never auto-retry
            try:
                plan = entry['plan']
                result = maintenance.apply_plan(client, plan, self.backup_root, plan['token'])
                entry.update(state='completed', backup=str(result))
                return {'state': entry['state'], 'backup': str(result)}
            except Exception:
                entry['state'] = 'failed_or_uncertain'
                raise
        finally:
            self.lock.release()

    def check_scope(self, cards):
        if len(cards) > self.policy.max_cards or any(c['deckName'] != self.policy.deck and not c['deckName'].startswith(self.policy.deck + '::') for c in cards):
            raise ValueError('Cartão fora do escopo autorizado')
