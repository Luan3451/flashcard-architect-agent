import http.client
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from bridge_transport import LocalServer
from bridge_service import BridgeService, Policy
from anki_mcp import MCP
from bridge_client import BridgeClient
from test_maintenance import FakeAnki


@pytest.fixture
def server():
    calls = []
    host = LocalServer(lambda action, params: calls.append((action, params)) or {'safe': True}, 'a'*43, port=0)
    thread = threading.Thread(target=host.serve_forever, daemon=True); thread.start()
    yield host, calls
    host.shutdown(); host.server_close(); thread.join()


def request(server, payload=None, **changes):
    host, _ = server
    connection = http.client.HTTPConnection('127.0.0.1', host.server_address[1], timeout=5)
    body = json.dumps(payload or {'action': 'list_decks', 'params': {}}).encode()
    headers = {'Authorization': 'Bearer ' + 'a'*43, 'Content-Type': 'application/json', 'X-FA-Bridge': '1'}
    headers.update(changes)
    connection.request('POST', '/api', body=body, headers=headers)
    response = connection.getresponse(); code = response.status; response.read(); connection.close()
    return code


def test_transport_is_loopback_authenticated_and_browser_requests_are_rejected(server):
    assert server[0].server_address[0] == '127.0.0.1'
    assert request(server) == 200
    assert request(server, Authorization='Bearer wrong') == 401
    assert request(server, Origin='https://evil.example') == 403
    assert request(server, Host='evil.example') == 403
    assert len(server[1]) == 1


def test_session_expiry_payload_limits_and_rate_limits(server):
    host, calls = server
    host.deadline = host.clock() - 1
    assert request(server) == 401 and not calls
    host.deadline = host.clock() + 600
    assert request(server, {'action': 'list_decks', 'params': {'large': 'x'*262145}}) == 413
    host.requests.extend([host.clock()] * 60)
    assert request(server) == 429


def test_duplicate_headers_and_json_keys_are_rejected(server):
    host, calls = server
    for duplicate in ['Host', 'Authorization', 'Content-Length', 'Content-Type', 'X-FA-Bridge']:
        body = b'{"action":"list_decks","params":{}}'
        conn = http.client.HTTPConnection('127.0.0.1', host.server_address[1], timeout=5)
        conn.putrequest('POST', '/api', skip_host=True)
        headers = [('Host', f'127.0.0.1:{host.server_address[1]}'), ('Authorization', 'Bearer ' + 'a'*43),
            ('Content-Length', str(len(body))), ('Content-Type', 'application/json'), ('X-FA-Bridge', '1')]
        for key, value in headers: conn.putheader(key, value)
        conn.putheader(duplicate, next(v for k, v in headers if k == duplicate)); conn.endheaders(body)
        response = conn.getresponse(); assert response.status >= 400; response.read(); conn.close()
    assert not calls


def scoped_api(tmp_path):
    api = FakeAnki(tmp_path)
    # Four scoped notes; exactly one has the requested term.
    for i in (3, 4, 5):
        api.cards[i] = api.card(i, i*10, 'Redes')
        api.notes[i*10] = api.note(i*10, [i])
        api.notes[i*10]['fields']['Front']['value'] = 'Other topic'
    return api


def test_service_requires_ui_approval_and_plan_is_consumed_once(tmp_path):
    api = scoped_api(tmp_path); service = BridgeService(Policy('Teste', 'Redes'), tmp_path / 'backups')
    plan = service.handle(api, 'preview', {'action': 'remove-topic', 'terms': ['DNS']})
    with pytest.raises(ValueError): service.handle(api, 'apply', {'plan_id': plan['plan_id']})
    assert not api.mutations
    result = service.handle(api, 'apply', {'plan_id': plan['plan_id']}, approved=True)
    assert result['state'] == 'completed' and 10 not in api.notes and 20 in api.notes
    with pytest.raises(ValueError): service.handle(api, 'apply', {'plan_id': plan['plan_id']}, approved=True)


def test_scope_caps_ttl_and_parameter_injection(tmp_path):
    api = scoped_api(tmp_path); clock = [0]
    service = BridgeService(Policy('Teste', 'Redes'), tmp_path / 'backups', lambda: clock[0])
    for action in ['sync', 'deleteNotes', 'eval', 'setDueDate']:
        with pytest.raises(ValueError): service.handle(api, action, {})
    with pytest.raises(ValueError): service.handle(api, 'preview', {'action': 'remove-topic', 'terms': ['Nomes']})
    with pytest.raises(ValueError): service.handle(api, 'preview', {'action': 'highlight', 'terms': ['DNS'], 'decks': ['Outro']})
    result = service.handle(api, 'preview', {'action': 'highlight', 'terms': ['DNS']})
    clock[0] = 301
    with pytest.raises(ValueError): service.handle(api, 'apply', {'plan_id': result['plan_id']}, approved=True)
    assert not api.mutations


def test_cancelled_or_failed_plan_cannot_be_replayed(tmp_path):
    api = scoped_api(tmp_path); service = BridgeService(Policy('Teste', 'Redes'), tmp_path / 'backups')
    p = service.handle(api, 'preview', {'action': 'highlight', 'terms': ['DNS']})
    service.cancel(p['plan_id'])
    with pytest.raises(ValueError): service.handle(api, 'apply', {'plan_id': p['plan_id']}, approved=True)
    p = service.handle(api, 'preview', {'action': 'highlight', 'terms': ['DNS']}); api.backup_ok = False
    with pytest.raises(RuntimeError): service.handle(api, 'apply', {'plan_id': p['plan_id']}, approved=True)
    assert service.handle(api, 'status', {'plan_id': p['plan_id']})['state'] == 'failed_or_uncertain'
    assert not api.mutations


def test_session_file_secrets_not_passed_in_argv_or_returned_in_mcp_errors(tmp_path):
    path = tmp_path / 'session.json'; path.write_text(json.dumps({'port': 8766, 'token': 'x'*43})); path.chmod(0o600)
    client = BridgeClient(path)
    def fail(*args, **kwargs): raise RuntimeError('secret=' + client.token)
    mcp = MCP(fail)
    mcp.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'})
    result = mcp.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'anki_read_notes', 'arguments': {}}})
    assert 'x'*43 not in json.dumps(result) and result['result']['isError']
    path.chmod(0o644)
    if sys.platform != 'win32':
        with pytest.raises(ValueError): BridgeClient(path)


def test_mcp_exposes_no_apply_and_notifications_cannot_trigger_tools():
    calls = []; mcp = MCP(lambda *a, **k: calls.append(a))
    assert mcp.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})['error']['code'] == -32002
    mcp.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'initialize'})
    tools = mcp.handle({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/list'})['result']['tools']
    assert all('apply' not in tool['name'] and 'sync' not in tool['name'] for tool in tools)
    request = {'jsonrpc': '2.0', 'method': 'tools/call', 'params': {'name': 'anki_read_notes', 'arguments': {}}}
    assert mcp.handle(request) is None and not calls
    request['id'] = 4; request['params']['name'] = 'apply'
    assert mcp.handle(request)['error']['code'] == -32602


def test_real_stdio_protocol_process_without_sdk():
    messages = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'}, {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}]
    proc = subprocess.run([sys.executable, '-S', str(Path(__file__).resolve().parents[1] / 'scripts' / 'anki_mcp.py')],
        input='\n'.join(json.dumps(m) for m in messages)+'\n', text=True, capture_output=True, timeout=10)
    assert proc.returncode == 0
    output = [json.loads(line) for line in proc.stdout.splitlines()]
    assert len(output) == 2 and output[0]['result']['protocolVersion'] == '2025-11-25'


def test_duplicate_json_and_approval_payload_cannot_reach_dispatch(server):
    host, calls = server
    for body in [b'{"action":"list_decks","action":"apply","params":{}}', b'{"action":"list_decks","params":{"x":NaN}}']:
        conn = http.client.HTTPConnection('127.0.0.1', host.server_address[1], timeout=5)
        conn.request('POST', '/api', body, {'Authorization': 'Bearer '+'a'*43, 'Content-Type': 'application/json', 'X-FA-Bridge': '1'})
        response = conn.getresponse(); assert response.status == 400; response.read(); conn.close()
    assert not calls


def test_apply_payload_cannot_claim_its_own_approval(tmp_path):
    api = scoped_api(tmp_path); service = BridgeService(Policy('Teste', 'Redes'), tmp_path / 'backups')
    preview = service.handle(api, 'preview', {'action': 'highlight', 'terms': ['DNS']})
    with pytest.raises(ValueError):
        service.handle(api, 'apply', {'plan_id': preview['plan_id'], 'approved': True}, approved=False)
    assert not api.mutations


def test_legacy_transport_does_not_forward_secrets_on_redirect(server):
    from urllib.request import Request
    from urllib.error import HTTPError
    from deck_maintenance import AnkiClient
    from http.server import HTTPServer, BaseHTTPRequestHandler
    hits = []
    class Redirect(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            hits.append(self.path)
            self.send_response(307); self.send_header('Location', '/sink'); self.end_headers()
    host = HTTPServer(('127.0.0.1', 0), Redirect)
    thread = threading.Thread(target=host.serve_forever, daemon=True); thread.start()
    try:
        client = AnkiClient()
        with pytest.raises(HTTPError):
            client.opener.open(Request(f'http://127.0.0.1:{host.server_port}/start', data=b'secret-test'), timeout=5)
        assert hits == ['/start']
        with pytest.raises(ValueError): client('multi', actions=[])
    finally:
        host.shutdown(); host.server_close(); thread.join()


def test_session_file_symlink_is_rejected(tmp_path):
    path = tmp_path / 'session.json'; path.write_text(json.dumps({'port': 8766, 'token': 'a'*43})); path.chmod(0o600)
    link = tmp_path / 'alias.json'; link.symlink_to(path)
    with pytest.raises(ValueError): BridgeClient(link)


def test_session_budget_blocks_multiple_individually_small_plans(tmp_path):
    api = scoped_api(tmp_path)
    api.notes[30]['fields']['Front']['value'] = 'OSPF'
    service = BridgeService(Policy('Teste', 'Redes', max_changed_notes=1), tmp_path / 'backups')
    first = service.handle(api, 'preview', {'action': 'highlight', 'terms': ['DNS']})
    second = service.handle(api, 'preview', {'action': 'highlight', 'terms': ['OSPF']})
    service.handle(api, 'apply', {'plan_id': first['plan_id']}, approved=True)
    before = len(api.mutations)
    with pytest.raises(ValueError, match='Orçamento'):
        service.handle(api, 'apply', {'plan_id': second['plan_id']}, approved=True)
    assert len(api.mutations) == before
    assert '<mark' not in api.notes[30]['fields']['Front']['value']


def test_profile_changes_and_noop_plans_cannot_write(tmp_path):
    api = scoped_api(tmp_path)
    service = BridgeService(Policy('Outro', 'Redes'), tmp_path / 'backups')
    with pytest.raises(ValueError, match='Perfil'): service.handle(api, 'read_notes', {})
    service = BridgeService(Policy('Teste', 'Redes'), tmp_path / 'backups')
    plan = service.handle(api, 'preview', {'action': 'highlight', 'terms': ['ZZZ-missing']})
    with pytest.raises(ValueError, match='sem alterações'):
        service.handle(api, 'apply', {'plan_id': plan['plan_id']}, approved=True)
    assert not api.mutations
