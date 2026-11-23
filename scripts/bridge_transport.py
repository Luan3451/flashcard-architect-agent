"""Authenticated loopback-only HTTP for the native add-on, standard library only."""
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import secrets
import time

MAX_BODY = 262144


class LocalServer(HTTPServer):
    allow_reuse_address = False
    def __init__(self, dispatch, token, port=8766, lifetime=3600, clock=time.monotonic):
        self.dispatch, self.token, self.clock = dispatch, token, clock
        self.deadline, self.requests = clock() + lifetime, deque()
        super().__init__(('127.0.0.1', port), Handler)
    def get_request(self):
        sock, address = super().get_request(); sock.settimeout(5); return sock, address


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'
    def log_message(self, *args): pass  # never log bearer tokens, cards or parameters
    def reply(self, code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode()
        if len(data) > 4 * 1024 * 1024:
            code, data = 413, b'{"error":"response_too_large"}'
        self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store'); self.send_header('Connection', 'close')
        self.send_header('Content-Length', str(len(data))); self.end_headers()
        self.wfile.write(data)
    def do_GET(self): self.reply(405, {'error': 'method_not_allowed'})
    def do_OPTIONS(self): self.reply(405, {'error': 'browser_access_disabled'})
    def do_POST(self):
        server = self.server; now = server.clock()
        while server.requests and now - server.requests[0] >= 60: server.requests.popleft()
        if len(server.requests) >= 60:
            self.reply(429, {'error': 'rate_limited'}); return
        server.requests.append(now)
        expected_host = f'127.0.0.1:{server.server_address[1]}'
        # Reject duplicate/framing headers rather than choosing an attacker-controlled interpretation.
        if (self.path != '/api' or self.client_address[0] != '127.0.0.1' or
            self.headers.get_all('Host') != [expected_host] or self.headers.get_all('Origin') or
            self.headers.get_all('Transfer-Encoding') or self.headers.get_all('X-FA-Bridge') != ['1']):
            self.reply(403, {'error': 'origin_or_host_rejected'}); return
        auth = self.headers.get_all('Authorization', [])
        if now >= server.deadline or len(auth) != 1 or not secrets.compare_digest(auth[0].encode('utf-8'), ('Bearer ' + server.token).encode('utf-8')):
            self.reply(401, {'error': 'unauthorized_or_expired'}); return
        length = self.headers.get_all('Content-Length', [])
        if len(length) != 1 or not length[0].isascii() or not length[0].isdigit() or not 0 < int(length[0]) <= MAX_BODY:
            self.reply(413, {'error': 'invalid_body_length'}); return
        if self.headers.get_all('Content-Type') != ['application/json']:
            self.reply(415, {'error': 'json_required'}); return
        try:
            body = self.rfile.read(int(length[0]))
            if len(body) != int(length[0]): raise ValueError('short body')
            request = json.loads(body, object_pairs_hook=unique_object, parse_constant=lambda _: reject_constant())
            if not isinstance(request, dict) or set(request) != {'action', 'params'} or not isinstance(request['action'], str):
                raise ValueError('request shape')
            result = server.dispatch(request['action'], request['params'])
            self.reply(200, {'result': result})
        except (ValueError, KeyError, TypeError, RecursionError):
            self.reply(400, {'error': 'request_rejected'})
        except Exception:
            # Mutation may already have happened; caller must inspect plan status/journal, never retry.
            self.reply(409, {'error': 'failed_or_uncertain_check_status'})


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def reject_constant():
    raise ValueError('non-finite JSON value')
