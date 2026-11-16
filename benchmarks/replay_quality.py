"""Reprocess archived public model outputs through QC; performs no new inference."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import anki_generator as engine
import exam_coach as coach
import quality


def replay():
    root = Path(__file__).parent
    cases = {q['id']: q for name in ('network_cases.json', 'heldout_cases.json')
             for q in json.loads((root / name).read_text(encoding='utf-8'))}
    rows = []
    for name in ('initial-seed42.json', 'final-seed42.json', 'heldout-seed7.json'):
        data = json.loads((root / 'results' / name).read_text(encoding='utf-8'))
        for record in data['results']:
            if record['strategy'] == 'direct':
                findings = quality.audit_cards(engine.parse_cards(record['raw'], {}))
            else:
                q = cases[record['id']]
                result = coach.validate_explanation(record['raw'], q)
                findings = quality.numeric_source_issues(result['concept'] + '\n' + result['mechanism'], q['source'])
                findings += quality.audit_cards([coach.render_card(q, result)])
            rows.append({'artifact': name, 'id': record['id'], 'strategy': record['strategy'], 'issues': findings})
    return {'policy': 'deterministic-qc-1',
            'method': 'Replay of 22 existing real-model responses; no new inference, no semantic judge.',
            'checked': len(rows),
            'rows_with_warnings': sum(any(i['severity'] == 'warning' for i in r['issues']) for r in rows),
            'rows_with_errors': sum(any(i['severity'] == 'error' for i in r['issues']) for r in rows), 'results': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(replay(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
