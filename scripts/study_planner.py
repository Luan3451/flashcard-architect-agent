"""Goal-bound lexical topics and a suggested study queue, never Anki scheduling.

Pure standard library. No learned semantic classifier or claim of retention gains.
"""
from __future__ import annotations
import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata


class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}: self.hidden += 1
        if tag in {'p', 'br', 'div', 'li', 'pre'}: self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in {'script', 'style'}: self.hidden = max(0, self.hidden - 1)
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


def normalized(text):
    parser = Text(); parser.feed(text)
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', ''.join(parser.parts).casefold()) if not unicodedata.combining(c)).split())


def matches(text, term):
    return bool(re.search(r'(?<!\w)' + re.escape(normalized(term)) + r'(?!\w)', text))


def validate_goal(goal):
    if not isinstance(goal, dict) or set(goal) - {'mode', 'front_language', 'explanation_language', 'reference', 'topics'}:
        raise ValueError('Goal inválido ou campos desconhecidos')
    if not isinstance(goal.get('mode'), str) or goal['mode'] not in {'language', 'exam', 'general'}:
        raise ValueError('mode: language, exam ou general')
    for key in ('front_language', 'explanation_language'):
        if not isinstance(goal.get(key), str) or not re.fullmatch(r'[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?', goal[key]):
            raise ValueError('Informe idiomas explicitamente, por exemplo en e pt-BR')
    if goal['mode'] == 'exam' and (not isinstance(goal.get('reference'), str) or not goal['reference'].strip()):
        raise ValueError('Prova exige referência/versionamento de escopo fornecido pelo usuário')
    topics = goal.get('topics')
    if not isinstance(topics, list) or not 1 <= len(topics) <= 50:
        raise ValueError('Informe entre 1 e 50 temas')
    ids = set()
    for topic in topics:
        if not isinstance(topic, dict) or set(topic) - {'id', 'terms', 'exclude', 'weight'}:
            raise ValueError('Tema inválido')
        if not isinstance(topic.get('id'), str) or not re.fullmatch(r'[a-z0-9_-]{1,60}', topic['id']) or topic['id'] in ids:
            raise ValueError('IDs de tema inválidos/repetidos')
        ids.add(topic['id'])
        for key in ('terms', 'exclude'):
            terms = topic.get(key, [])
            if not isinstance(terms, list) or len(terms) > 30 or not all(isinstance(t, str) and 1 <= len(t.strip()) <= 100 and bool(normalized(t)) for t in terms):
                raise ValueError('Termos inválidos')
        if not topic.get('terms'):
            raise ValueError('Tema exige termos explícitos')
        if type(topic.get('weight', 1)) not in (int, float) or not 0 < topic.get('weight', 1) <= 10:
            raise ValueError('Peso deve estar entre 0 e 10')
    return goal


def plan_study(cards, goal, limit=20):
    validate_goal(goal)
    if not isinstance(cards, list) or len(cards) > 200 or type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError('Limites: 200 cartões e fila de 1 a 200 itens')
    clusters = {t['id']: [] for t in goal['topics']}
    excluded, seen = [], set()
    for card in cards:
        if not isinstance(card, dict) or not isinstance(card.get('id'), (str, int)) or isinstance(card['id'], bool) or card['id'] in seen:
            raise ValueError('Cartão precisa de ID único')
        seen.add(card['id'])
        if any(k in card and type(card[k]) is not bool for k in ('due', 'needs_review')):
            raise ValueError('due/needs_review devem ser booleanos')
        if not isinstance(card.get('text'), str) or len(card['text']) > 50000:
            raise ValueError('Texto de cartão inválido ou excessivo')
        # Language metadata is declared; this module never silently translates or guesses language.
        if card.get('front_language', goal['front_language']) != goal['front_language'] or card.get('explanation_language', goal['explanation_language']) != goal['explanation_language']:
            excluded.append({'id': card['id'], 'reason': 'language_metadata_mismatch'}); continue
        text = normalized(card['text'])
        scores = []
        for topic in goal['topics']:
            if any(matches(text, t) for t in topic.get('exclude', [])): continue
            hits = sorted({normalized(t) for t in topic['terms'] if matches(text, t)})
            if hits: scores.append((len(hits), topic['id'], hits))
        scores.sort(reverse=True)
        if not scores or (len(scores) > 1 and scores[0][0] == scores[1][0]):
            excluded.append({'id': card['id'], 'reason': 'no_match' if not scores else 'ambiguous_topics'}); continue
        _, topic_id, hits = scores[0]
        clusters[topic_id].append({'id': card['id'], 'matched_terms': hits,
            'due': card.get('due') is True, 'needs_review': card.get('needs_review') is True})
    # Interleave the suggested queue using weighted fair allocation, not Anki due dates.
    queues = {k: sorted(v, key=lambda c: (not c['due'], not c['needs_review'], str(c['id']))) for k, v in clusters.items()}
    weights = {t['id']: t.get('weight', 1) for t in goal['topics']}
    used, order = Counter(), []
    while len(order) < limit and any(queues.values()):
        available = [key for key in queues if queues[key]]
        # Existing due cards always precede not-due items across topics.
        due = [key for key in available if queues[key][0]['due']]
        available = due or available
        key = min(available, key=lambda k: ((used[k] + 1) / weights[k], k))
        selected = queues[key].pop(0); used[key] += 1
        order.append({'id': selected['id'], 'topic': key, 'due': selected['due']})
    return {'schema': 1, 'mode': goal['mode'], 'declared_languages': {'front': goal['front_language'], 'explanation': goal['explanation_language']},
        'reference': goal.get('reference'), 'clusters': clusters, 'uncovered_topics': [key for key, items in clusters.items() if not items], 'unclassified': excluded, 'suggested_queue': order,
        'limits': 'Correspondência lexical explicável; não comprova fidelidade factual/idioma. Não altera FSRS, notas, tags ou agendamento.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cards', type=Path, required=True); p.add_argument('--goal', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--limit', type=int, default=20)
    a = p.parse_args()
    if a.output.exists(): p.error('Saída já existe')
    try:
        result = plan_study(json.loads(a.cards.read_text(encoding='utf-8')), json.loads(a.goal.read_text(encoding='utf-8')), a.limit)
        a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    except (OSError, ValueError) as exc: p.exit(1, f'Falha: {exc}\n')


if __name__ == '__main__': main()
