"""Native bridge client: uses the add-on's private session file, no token in argv."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import stat
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


class BridgeClient:
    def __init__(self, session_file):
        path = Path(session_file)
        if path.is_symlink(): raise ValueError('Arquivo de sessão não pode ser link')
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(descriptor, 'r', encoding='utf-8') as source:
            mode = os.fstat(source.fileno())
            if not stat.S_ISREG(mode.st_mode) or mode.st_size > 4096:
                raise ValueError('Arquivo de sessão inválido')
            if os.name == 'posix' and (mode.st_uid != os.getuid() or stat.S_IMODE(mode.st_mode) & 0o077):
                raise ValueError('Sessão deve pertencer ao usuário e ter permissão 600')
            data = json.loads(source.read(4097))
        if set(data) != {'port', 'token'} or type(data['port']) is not int or data['port'] != 8766 or not isinstance(data['token'], str) or len(data['token']) < 32:
            raise ValueError('Configuração da sessão inválida')
        self.port, self.token = data['port'], data['token']
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def __call__(self, operation, **params):
        payload = json.dumps({'action': operation, 'params': params}, ensure_ascii=False, allow_nan=False).encode()
        if len(payload) > 262144: raise ValueError('Pedido excessivo')
        request = Request(f'http://127.0.0.1:{self.port}/api', data=payload,
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.token, 'X-FA-Bridge': '1'})
        # Never retry writes: an interrupted response is not proof of failure.
        try:
            with self.opener.open(request, timeout=180) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
        except HTTPError as exc:
            raise RuntimeError(f'Ponte recusou a operação (HTTP {exc.code}); verifique sessão/escopo no Anki. Não repita aplicações automaticamente.') from None
        if len(raw) > 4 * 1024 * 1024: raise RuntimeError('Resposta excessiva')
        return json.loads(raw)['result']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--session-file', type=Path, required=True)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('list-decks'); sub.add_parser('read-notes')
    preview = sub.add_parser('preview'); preview.add_argument('--action', choices=['highlight', 'style', 'remove-topic'], required=True)
    preview.add_argument('--term', action='append', default=[]); preview.add_argument('--theme', default='paper', choices=['studio', 'atlas', 'paper', 'contrast'])
    apply = sub.add_parser('apply'); apply.add_argument('--plan-id', required=True)
    status = sub.add_parser('status'); status.add_argument('--plan-id', required=True)
    a = p.parse_args()
    try:
        client = BridgeClient(a.session_file)
        if a.command == 'preview': result = client('preview', action=a.action, terms=a.term, theme=a.theme)
        elif a.command in {'apply', 'status'}: result = client(a.command, plan_id=a.plan_id)
        else: result = client(a.command.replace('-', '_'))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError, KeyError) as exc: p.exit(1, f'Falha: {exc}\n')


if __name__ == '__main__': main()
