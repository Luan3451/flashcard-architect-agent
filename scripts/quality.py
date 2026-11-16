"""Deterministic checks; warnings are review signals, not semantic verdicts.

No model calls, guessed corrections, contiguous-cloze requirement or arbitrary exec.
"""
from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata

SOUND = re.compile(r'\[sound:([^\]\r\n]+)\]')
CLOZE = re.compile(r'\{\{c(\d+)::(.*?)\}\}', re.S)
START = re.compile(r'\{\{c\d+::')


class QualityError(ValueError):
    def __init__(self, issues):
        self.issues = issues
        errors = [i for i in issues if i['severity'] == 'error']
        label = ' IDs de conceito repetidos.' if any(i['code'] == 'duplicate_concept_id' for i in errors) else ''
        detail = '; '.join(f"item {i.get('item', '?')}: {i['code']}" for i in errors[:8])
        super().__init__(f'Qualidade: {len(errors)} erro(s); exportação cancelada.{label} {detail}')


def issue(code, severity, *, item=None, field=None, **details):
    return {'code': code, 'severity': severity, 'item': item, 'field': field, **details}


class Visible(HTMLParser):
    def __init__(self, media=(), media_tokens=False):
        super().__init__(convert_charrefs=True)
        self.parts, self.suppressed, self.has_media = [], 0, False
        self.media = set(media)
        self.media_tokens = media_tokens
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'iframe', 'object', 'svg'}:
            self.suppressed += 1
        if not self.suppressed:
            if tag in {'br', 'p', 'div', 'li', 'pre', 'tr'}:
                self.parts.append(' ')
            if tag == 'img' and dict(attrs).get('src') in self.media:
                self.has_media = True
                if self.media_tokens:
                    self.parts.append(' [media ' + dict(attrs)['src'] + '] ')
    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'iframe', 'object', 'svg'}:
            self.suppressed = max(0, self.suppressed - 1)
        elif tag in {'p', 'div', 'li', 'pre', 'tr'}:
            self.parts.append(' ')
    def handle_data(self, data):
        if self.suppressed:
            return
        if any(name in self.media for name in SOUND.findall(data)):
            self.has_media = True
        self.parts.append(SOUND.sub(lambda m: ' [media ' + m.group(1) + '] ' if self.media_tokens and m.group(1) in self.media else '', data))


def visible(html, media=(), media_tokens=False):
    parser = Visible(media, media_tokens)
    parser.feed(html)
    parser.close()
    return ''.join(parser.parts), parser.has_media


def nonblank(text):
    # Space-only markup and zero-width formatting must not count as an answer.
    return any(not c.isspace() and unicodedata.category(c) != 'Cf' for c in text)


def field_issues(front, back, media=(), item=None):
    findings = []
    for field, value in [('pergunta', front), ('resposta', back)]:
        if not isinstance(value, str):
            findings.append(issue('field_not_text', 'error', item=item, field=field))
        else:
            text, has_media = visible(value, media)
            if not nonblank(text) and not has_media:
                findings.append(issue('empty_after_sanitization', 'error', item=item, field=field))
    return findings


def normalize(text):
    return ' '.join(unicodedata.normalize('NFC', text).casefold().split())


def cloze_issues(front, item=None, media=()):
    findings = []
    # Parse after decoding HTML so entities cannot conceal literal answer leaks.
    text, _ = visible(front, media, media_tokens=True)
    depth = 0
    for token in re.finditer(r'\{\{c\d+::|\}\}', text):
        if token.group().startswith('{{'):
            depth += 1
        elif depth:
            depth -= 1
    if depth:
        return [issue('cloze_unclosed', 'error', item=item, field='pergunta')]
    matches = list(CLOZE.finditer(text))
    if START.search(text) and not matches:
        return [issue('cloze_unclosed', 'error', item=item, field='pergunta')]
    if not matches:
        return findings
    # Nested clozes and double-colon ambiguity need manual review, not a partial regex verdict.
    complex_syntax = any('{{' in m.group(2) or m.group(2).count('::') > 1 or
                         (m.group(2).count('::') == 1 and ':' in m.group(2).split('::')[0])
                         for m in matches)
    if complex_syntax:
        return [issue('cloze_complex_syntax', 'warning', item=item, field='pergunta',
                      message='Cloze aninhado ou separadores ambíguos; vazamento não verificado automaticamente.')]
    if len(matches) != len(list(START.finditer(text))):
        findings.append(issue('cloze_unclosed', 'error', item=item, field='pergunta'))
    answers = []
    for m in matches:
        index = int(m.group(1))
        answer, _, hint = m.group(2).partition('::')
        if index < 1:
            findings.append(issue('cloze_invalid_index', 'error', item=item, field='pergunta'))
        if not nonblank(answer):
            findings.append(issue('cloze_empty_answer', 'error', item=item, field='pergunta', index=index))
        answers.append((index, normalize(answer), hint))
    for index, answer, _ in sorted(set(answers)):
        if not answer:
            continue
        def shown(m):
            other = int(m.group(1))
            value, _, hint = m.group(2).partition('::')
            return hint if other == index else value
        question_side = normalize(CLOZE.sub(shown, text))
        if re.search(r'(?<!\w)' + re.escape(answer) + r'(?!\w)', question_side):
            findings.append(issue('cloze_answer_leak', 'warning', item=item, field='pergunta',
                                  index=index, answer=answer))
    return findings


def audit_cards(cards, media=()):
    findings, ids = [], set()
    if not cards:
        return [issue('no_cards', 'error')]
    for index, card in enumerate(cards, 1):
        if not isinstance(card, dict):
            findings.append(issue('card_not_object', 'error', item=index))
            continue
        findings.extend(field_issues(card.get('pergunta'), card.get('resposta'), media, item=index))
        uid = card.get('id_conceito')
        if not isinstance(uid, str) or not uid:
            findings.append(issue('missing_concept_id', 'error', item=index))
        elif uid in ids:
            findings.append(issue('duplicate_concept_id', 'error', item=index))
        else:
            ids.add(uid)
        if isinstance(card.get('pergunta'), str):
            findings.extend(cloze_issues(card['pergunta'], item=index, media=media))
        if isinstance(card.get('tags'), list) and 'revisar' in card['tags'] and not any(i['item'] == index and i['severity'] == 'warning' for i in findings):
            findings.append(issue('review_tag_present', 'warning', item=index))
    return findings


def ensure_no_errors(findings):
    if any(i['severity'] == 'error' for i in findings):
        raise QualityError(findings)


def write_report(path: Path, findings, *, cards=None, exported=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {'schema': 1, 'status': 'rejected' if any(i['severity'] == 'error' for i in findings) else
            'review_required' if findings else 'passed',
            'errors': sum(i['severity'] == 'error' for i in findings),
            'warnings': sum(i['severity'] == 'warning' for i in findings),
            'cards': cards, 'package_created': exported, 'issues': findings,
            'limits': 'Verificações mecânicas e heurísticas; não provam correção factual.'}
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)
    return data


# Conservative lexical units. No automatic conversions or interpretation of numeric context.
UNITS = {'ms': 'ms', 'msec': 'ms', 'milliseconds': 'ms', 'millisecond': 'ms', 'milissegundos': 'ms', 'milissegundo': 'ms',
         's': 's', 'sec': 's', 'seconds': 's', 'second': 's', 'segundos': 's', 'segundo': 's',
         'min': 'min', 'minutes': 'min', 'minutos': 'min', 'h': 'h',
         'Hz': 'Hz', 'kHz': 'kHz', 'MHz': 'MHz', 'GHz': 'GHz',
         'bps': 'bps', 'Kbps': 'Kbps', 'Mbps': 'Mbps', 'Gbps': 'Gbps',
         'KB': 'KB', 'MB': 'MB', 'GB': 'GB', 'MBps': 'MBps', 'GBps': 'GBps', '%': '%'}
UNITS_PATTERN = '|'.join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
NUMERIC = re.compile(r'(?<![\w:/])(?<!\d[.,])([+-]?\d+(?:[.,]\d+)?)(?:[ \u00a0]*(' + UNITS_PATTERN + r'))?(?![\w:/]|[.,]\d)')


def numeric_mentions(text):
    return {(m.group(1), UNITS.get(m.group(2), '')) for m in NUMERIC.finditer(text)}


def numeric_source_issues(explanation, source):
    source_mentions = numeric_mentions(source)
    values = {value for value, _ in source_mentions}
    findings = []
    for value, unit in sorted(numeric_mentions(explanation)):
        if value not in values:
            findings.append(issue('number_not_in_source', 'warning', value=value, unit=unit))
        elif unit and (value, unit) not in source_mentions:
            findings.append(issue('number_unit_not_in_source', 'warning', value=value, unit=unit))
    return findings
