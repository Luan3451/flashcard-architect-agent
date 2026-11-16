"""Reproducible real-model A/B/C test on original public synthetic networking cases.

Default uses configured production providers. --llama-url is only for local CPU lab.
Model output is data, never executed. Scores require human/independent review.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlparse
from urllib.request import Request, build_opener, ProxyHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import anki_generator as engine
import exam_coach as coach


def run(cases, invoke, explanation_prompt=coach.explanation_prompt):
    rows = []
    for case in coach.question_records(cases):
        print('CASE', case['id'], flush=True)
        material = '\n'.join([case['stem'], *case['options'], 'Correct answer: ' + case.get('answer', ''), 'Source: ' + case['source']])
        prompt = engine.master_prompt('strict', 'keep', 'high', 'all', False) + '\n<documento>\n' + material + '\n</documento>'
        start = time.monotonic()
        raw = invoke(prompt)
        baseline = {'id': case['id'], 'strategy': 'direct', 'raw': raw, 'seconds': round(time.monotonic() - start, 3), 'calls': 1}
        try:
            baseline['cards'] = engine.parse_cards(raw, {})
            baseline['parse_ok'] = bool(baseline['cards'])
        except ValueError as exc:
            baseline['parse_ok'], baseline['error'] = False, str(exc)
        rows.append(baseline)
        print('  direct completed', baseline['seconds'], flush=True)
        start = time.monotonic()
        raw = invoke(explanation_prompt(case))
        parsed = coach.validate_explanation(raw, case)
        guided = {'id': case['id'], 'strategy': 'guided', 'raw': raw, 'cards': [coach.render_card(case, parsed)],
                  'seconds': round(time.monotonic() - start, 3), 'calls': 1, 'parse_ok': True}
        rows.append(guided)
        print('  guided completed', guided['seconds'], flush=True)
        start = time.monotonic()
        prompt = explanation_prompt(case) + '\nREVISÃO: confronte o candidato abaixo com a fonte. Corrija erros, preserve informações sustentadas e marque lacunas em review_reason. Responda com o MESMO esquema JSON.\nCANDIDATO:\n' + json.dumps(parsed, ensure_ascii=False)
        raw = invoke(prompt)
        parsed = coach.validate_explanation(raw, case)
        revised = {'id': case['id'], 'strategy': 'guided_review', 'raw': raw, 'cards': [coach.render_card(case, parsed)],
                   'seconds': round(guided['seconds'] + time.monotonic() - start, 3), 'calls': 2, 'parse_ok': True}
        rows.append(revised)
        print('  review completed', revised['seconds'], flush=True)
        yield rows[-3:]


def run_guided_only(cases, invoke):
    for q in coach.question_records(cases):
        print('CASE', q['id'], flush=True)
        started = time.monotonic()
        raw = invoke(coach.explanation_prompt(q))
        parsed = coach.validate_explanation(raw, q)
        yield [{'id': q['id'], 'strategy': 'evidence_first_ptbr', 'raw': raw,
                'explanation': parsed, 'cards': [coach.render_card(q, parsed)],
                'seconds': round(time.monotonic() - started, 3), 'calls': 1, 'parse_ok': True}]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases', type=Path, default=Path(__file__).with_name('network_cases.json'))
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--provider', choices=engine.DEFAULT_MODELS, default='ollama')
    p.add_argument('--model')
    p.add_argument('--llama-url', help='Local test endpoint, e.g. http://127.0.0.1:8767')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--max-tokens', type=int, default=700)
    p.add_argument('--profile', choices=['initial', 'current'], default='current')
    p.add_argument('--strategy', choices=['all', 'guided-only'], default='all')
    args = p.parse_args()
    if args.output.exists(): p.error('Output already exists')
    cases = json.loads(args.cases.read_text(encoding='utf-8'))
    model = args.model or engine.DEFAULT_MODELS[args.provider]
    if args.llama_url:
        uri = urlparse(args.llama_url)
        if uri.scheme != 'http' or uri.hostname not in {'127.0.0.1', 'localhost'} or uri.username or uri.password or uri.path not in {'', '/'}:
            p.error('llama-url must be a local loopback server')
        opener = build_opener(ProxyHandler({}))
        def invoke(prompt):
            payload = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.2,
                       'seed': args.seed, 'max_tokens': args.max_tokens, 'chat_template_kwargs': {'enable_thinking': False}}
            request = Request(args.llama_url.rstrip('/') + '/v1/chat/completions', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
            with opener.open(request, timeout=1200) as response: result = json.load(response)
            answer = result['choices'][0]
            if answer.get('finish_reason') == 'length': raise RuntimeError('Truncated response; increase max-tokens, do not score partial output')
            return answer['message']['content']
    else:
        invoke = lambda prompt: engine.invoke_model(args.provider, model, 'high', prompt, 1200)
    rows = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metadata = {'model': model, 'transport': 'llama.cpp local' if args.llama_url else args.provider,
                'seed': args.seed, 'temperature': 0.2 if args.llama_url else 'provider-default',
                'profile': coach.PROFILE_VERSION, 'scores': 'not automatically judged; review actual content'}
    if args.profile == 'initial':
        initial = Path(__file__).with_name('prompts').joinpath('exam-coach-1.txt').read_text().rstrip('\n')
        prompt_fn = lambda q: initial + '\nDADOS DA QUESTÃO:\n' + json.dumps({k: q.get(k, '') for k in ('stem', 'options', 'answer', 'source')}, ensure_ascii=False)
        metadata['profile'] = 'exam-coach-1'
    else:
        prompt_fn = coach.explanation_prompt
    batches = run_guided_only(cases, invoke) if args.strategy == 'guided-only' else run(cases, invoke, prompt_fn)
    for batch in batches:
        rows.extend(batch)
        args.output.write_text(json.dumps({'metadata': metadata, 'results': rows}, ensure_ascii=False, indent=2, default=list), encoding='utf-8')
    print(args.output)


if __name__ == '__main__': main()
