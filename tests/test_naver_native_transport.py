"""Native Naver transport contract; synthetic credentials and local fakes only."""
import json
import inspect
import os
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
from typing import Optional, cast
import unittest
from unittest import mock

from tests.test_naver_blog_preauth import FakeLedger, FakeTransport
from tests.test_publishing_runtime import load_module


NAVER_BASE = 'http://127.0.0.1:8001'
LEGACY_BASE = 'http://127.0.0.1:8000'
NAVER_TOKEN = 'synthetic-naver-secret'
LEGACY_TOKEN = 'synthetic-legacy-secret'
WEBHOOK_TOKEN = 'synthetic-webhook-secret'
PRE_MUTATION_FAILURE = {
    'success': False, 'external_mutation_possible': False,
    'error': 'synthetic_pre_mutation_rejection',
}


class NativeTransportFixture(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = FakeLedger()
        self.transport = FakeTransport()
        self.transport.response = PRE_MUTATION_FAILURE
        self.request_patch = mock.patch.object(self.module, '_request_json', self.transport)
        self.request_patch.start()
        self.addCleanup(self.request_patch.stop)
        self.payload = {'blog_id': 'approved_blog', 'title': 'Native test',
                        'content': 'Exact approved body', 'tags': ['one', 'two', 'three']}

    def runtime(self, **kwargs):
        arguments = dict(
            receipt_root=Path(self.tmp.name) / 'receipts',
            webhook_base_url='https://n8n.donggu.site/webhook',
            webhook_token=WEBHOOK_TOKEN,
            publisher_api_base_url=LEGACY_BASE, publisher_api_token=LEGACY_TOKEN,
            ledger=self.ledger,
        )
        arguments.update(kwargs)
        return self.module.PublishingRuntime(**arguments)

    def plan(self, runtime, **kwargs):
        arguments = dict(channel='naver_blog', operation='publish', payload=self.payload,
                         topic='native', note_path='Blog/native.md', session_id='session',
                         turn_id='preview-turn', user_message_id=1)
        arguments.update(kwargs)
        return runtime.preview(**arguments)

    def execute(self, runtime, plan, **kwargs):
        arguments = dict(approval_text='발행해', session_id='session',
                         turn_id='approval-turn', user_message_id=2)
        arguments.update(kwargs)
        return runtime.execute(plan['receipt_id'], **arguments)

    def env_runtime(self, **kwargs):
        environment = dict(SNS_WEBHOOK_TOKEN=WEBHOOK_TOKEN, PUBLISHER_API_TOKEN=LEGACY_TOKEN,
                           HERMES_HOME=self.tmp.name,
                           SUPABASE_URL='https://fvfayignxybdyyravorg.supabase.co',
                           SUPABASE_SERVICE_KEY='synthetic-ledger-secret')
        environment.update(kwargs)
        with mock.patch.dict(os.environ, environment, clear=True):
            runtime = self.module.PublishingRuntime.from_env()
        runtime.ledger = self.ledger
        return runtime


class NaverNativeTransportTests(NativeTransportFixture):
    def test_missing_env_token_disables_only_naver(self):
        for index, environment in enumerate([
                {}, {'NAVER_PUBLISHER_API_TOKEN': ''}, {'NAVER_PUBLISHER_API_TOKEN': ' '},
                {'NAVER_PUBLISHER_API_BASE_URL': NAVER_BASE}]):
            with self.subTest(environment=environment):
                runtime = self.env_runtime(**environment)
                self.assertIsNone(runtime.naver_publisher_api_base_url)
                self.assertIsNone(runtime.naver_publisher_api_token)
                plan = self.plan(runtime, topic=f'missing-{index}')
                self.assertEqual('failed', self.execute(runtime, plan, user_message_id=10 + index)['status'])
        self.assertEqual([], self.ledger.reads)
        self.assertEqual([], self.transport.calls)

    def test_legacy_tistory_and_maily_keep_shared_route_and_token(self):
        for configured in (False, True):
            runtime = self.env_runtime(**({'NAVER_PUBLISHER_API_TOKEN': NAVER_TOKEN}
                                         if configured else {}))
            for index, channel in enumerate(('tistory', 'maily')):
                with self.subTest(naver_configured=configured, channel=channel):
                    payload = {key: value for key, value in self.payload.items() if key != 'blog_id'}
                    if channel == 'maily':
                        payload.update(subtitle='Synthetic subtitle', dry_run=True)
                    plan = self.plan(runtime, channel=channel, payload=payload)
                    result = self.execute(runtime, plan, user_message_id=20 + index + 2 * configured)
                    self.assertEqual('failed', result['status'])
                    _, url, request = self.transport.calls[-1]
                    self.assertEqual(LEGACY_BASE + '/publish-sync/' + channel, url)
                    self.assertEqual(LEGACY_TOKEN, request['headers']['X-API-Token'])
                    self.assertNotIn(NAVER_TOKEN, json.dumps(request))
                    self.assertEqual({'dry_run': channel == 'maily'}, request['body']['options'])
                    self.assertNotIn('dry_run', request['body'])
                    self.assertTrue(request['disable_proxy'])
        self.assertEqual(4, len(self.transport.calls))
        self.assertEqual([], self.ledger.writes)

    def test_real_maily_still_requires_separate_later_confirmation(self):
        runtime = self.env_runtime(NAVER_PUBLISHER_API_TOKEN=NAVER_TOKEN)
        payload = {'title': 'Synthetic newsletter', 'content': 'Body', 'subtitle': 'Subtitle'}
        plan = self.plan(runtime, channel='maily', payload=payload)
        with self.assertRaises(self.module.ReceiptError):
            self.execute(runtime, plan)
        self.assertEqual([], self.transport.calls)
        runtime.confirm_irreversible(plan['receipt_id'], confirmation_text='메일리 최종 발송 승인',
                                     session_id='session', turn_id='confirm-turn', user_message_id=3)
        self.assertEqual('failed', runtime.dispatch(plan['receipt_id'], session_id='session')['status'])
        self.assertEqual(1, len(self.transport.calls))
        self.assertEqual(LEGACY_BASE + '/publish-sync/maily', self.transport.calls[0][1])
        self.assertEqual(LEGACY_TOKEN, self.transport.calls[0][2]['headers']['X-API-Token'])

    def test_payload_cannot_override_transport_or_authority(self):
        runtime = self.env_runtime(NAVER_PUBLISHER_API_TOKEN=NAVER_TOKEN)
        for field in ('url', 'endpoint', 'publisher_api_base_url', 'naver_publisher_api_base_url',
                      'naver_publisher_api_token', 'headers', 'options'):
            with self.subTest(field=field):
                with self.assertRaises(self.module.ValidationError):
                    self.plan(runtime, payload={**self.payload, field: 'http://evil.test'})
        self.assertEqual([], self.transport.calls)
        self.assertEqual([], list(runtime.store.root.glob('*.json')))

    def test_dispatch_requires_existing_later_turn_approval(self):
        runtime = self.env_runtime(NAVER_PUBLISHER_API_TOKEN=NAVER_TOKEN)
        plan = self.plan(runtime)
        with self.assertRaises(self.module.ReceiptError):
            runtime.dispatch(plan['receipt_id'], session_id='session')
        for overrides in ({'session_id': 'other'}, {'turn_id': 'preview-turn'},
                          {'user_message_id': 1}, {'approval_text': '보류'}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(self.module.ApprovalError):
                    self.execute(runtime, plan, **overrides)
        self.assertEqual('planned', runtime.receipt_status(plan['receipt_id'])['state'])
        self.assertEqual([], self.ledger.reads)
        self.assertEqual([], self.transport.calls)

    def test_concurrent_naver_dispatch_makes_one_transport_call(self):
        runtime = self.env_runtime(NAVER_PUBLISHER_API_TOKEN=NAVER_TOKEN)
        plan = self.plan(runtime)
        runtime.approve(plan['receipt_id'], approval_text='발행해', session_id='session',
                        turn_id='approval-turn', user_message_id=2)
        barrier = threading.Barrier(2)

        def dispatch():
            barrier.wait(timeout=5)
            try:
                return runtime.dispatch(plan['receipt_id'], session_id='session')['status']
            except self.module.PublishingError:
                return 'blocked'

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: dispatch(), range(2)))
        self.assertCountEqual(['failed', 'blocked'], outcomes)
        self.assertEqual(1, len(self.transport.calls))
        self.assertEqual([], self.ledger.writes)

    def test_terminal_receipts_never_redispatch_after_route_configuration_changes(self):
        for index, state in enumerate(('completed', 'reconciliation_required', 'dispatching')):
            with self.subTest(state=state):
                runtime = self.runtime()
                plan = self.plan(runtime, topic=f'old-{state}')
                # Simulate a signed old receipt, not a new authorization.
                runtime.store.transition(runtime.store.load(plan['receipt_id']), state,
                                         result={'status': state}, payload=None)
                runtime.naver_publisher_api_base_url = NAVER_BASE
                runtime.naver_publisher_api_token = NAVER_TOKEN
                with self.assertRaises(self.module.ReceiptError):
                    runtime.dispatch(plan['receipt_id'], session_id='session')
                with self.assertRaises(self.module.PublishingError):
                    self.execute(runtime, plan, user_message_id=30 + index)
                restarted = self.runtime(naver_publisher_api_base_url=NAVER_BASE,
                                         naver_publisher_api_token=NAVER_TOKEN)
                with self.assertRaises(self.module.ReceiptError):
                    restarted.dispatch(plan['receipt_id'], session_id='session')
                if state != 'completed':
                    with self.assertRaises(self.module.ReceiptError):
                        self.plan(restarted, topic=f'old-{state}')
        self.assertEqual([], self.ledger.reads)
        self.assertEqual([], self.ledger.writes)
        self.assertEqual([], self.transport.calls)

    def test_naver_timeout_never_falls_back_or_retries(self):
        runtime = self.env_runtime(NAVER_PUBLISHER_API_TOKEN=NAVER_TOKEN)
        self.transport.response = self.module.TransportError('synthetic timeout', uncertain=True)
        plan = self.plan(runtime)
        result = self.execute(runtime, plan)
        self.assertEqual('reconciliation_required', result['status'])
        with self.assertRaises(self.module.ReceiptError):
            runtime.dispatch(plan['receipt_id'], session_id='session')
        with self.assertRaises(self.module.ReceiptError):
            self.plan(runtime)
        self.assertEqual(1, len(self.transport.calls))
        self.assertEqual(NAVER_BASE + '/publish-sync/naver_blog', self.transport.calls[0][1])
        self.assertEqual([], self.ledger.writes)

    def test_secrets_do_not_enter_preview_receipts_status_or_errors(self):
        runtime = self.env_runtime(NAVER_PUBLISHER_API_TOKEN=NAVER_TOKEN)
        plan = self.plan(runtime)
        result = self.execute(runtime, plan)
        exposed = json.dumps([plan, result, runtime.receipt_status(plan['receipt_id'])])
        exposed += ''.join(path.read_text() for path in runtime.store.root.glob('*.json'))
        exposed += ''.join(path.read_text() for path in runtime.store.root.glob('*.claim'))
        for secret in (NAVER_TOKEN, LEGACY_TOKEN, WEBHOOK_TOKEN, 'synthetic-ledger-secret'):
            self.assertNotIn(secret, exposed)

    def test_from_env_validates_explicit_naver_origin_even_without_token(self):
        for base in [LEGACY_BASE, 'http://host.docker.internal:8001',
                     'https://n8n.donggu.site/webhook', NAVER_BASE + '/',
                     ' ' + NAVER_BASE, '']:
            for token in [None, NAVER_TOKEN]:
                environment = {'NAVER_PUBLISHER_API_BASE_URL': base}
                if token is not None:
                    environment['NAVER_PUBLISHER_API_TOKEN'] = token
                with self.subTest(base=base, has_token=token is not None):
                    with self.assertRaises(self.module.ValidationError):
                        self.env_runtime(**environment)
        runtime = self.env_runtime(NAVER_PUBLISHER_API_BASE_URL=NAVER_BASE,
                                   NAVER_PUBLISHER_API_TOKEN=NAVER_TOKEN)
        self.assertEqual(NAVER_BASE, runtime.naver_publisher_api_base_url)

    def test_from_env_uses_optional_naver_token_with_fixed_default_origin(self):
        runtime = self.env_runtime(NAVER_PUBLISHER_API_TOKEN=NAVER_TOKEN)
        self.assertEqual(NAVER_BASE, runtime.naver_publisher_api_base_url)
        self.assertEqual(NAVER_TOKEN, runtime.naver_publisher_api_token)
        self.assertEqual(LEGACY_BASE, runtime.publisher_api_base_url)
        self.assertEqual(LEGACY_TOKEN, runtime.publisher_api_token)
        self.execute(runtime, self.plan(runtime))
        self.assertEqual(NAVER_BASE + '/publish-sync/naver_blog', self.transport.calls[0][1])
        self.assertEqual(NAVER_TOKEN, self.transport.calls[0][2]['headers']['X-API-Token'])

    def test_naver_origin_is_exact_in_production_and_local_only_in_tests(self):
        rejected = [LEGACY_BASE, 'http://localhost:8001', 'https://127.0.0.1:8001',
                    'http://127.0.0.1:8002', 'http://[::1]:8001',
                    'https://n8n.donggu.site/webhook', 'http://host.docker.internal:8001',
                    'http://192.168.1.1:8001', 'http://publisher.test:8001',
                    NAVER_BASE + '/', NAVER_BASE + '/publish-sync/naver_blog',
                    NAVER_BASE + '?', NAVER_BASE + '#', NAVER_BASE + '?token=' + NAVER_TOKEN,
                    'http://' + NAVER_TOKEN + '@127.0.0.1:8001',
                    ' ' + NAVER_BASE, NAVER_BASE + '\n', 'http://127.0.0.1:08001',
                    'http://127.0.0.1:8001\\evil', 'http://[broken']
        for base in rejected:
            with self.subTest(base=base):
                with self.assertRaises(self.module.ValidationError) as error:
                    self.runtime(naver_publisher_api_base_url=base,
                                 naver_publisher_api_token=NAVER_TOKEN)
                self.assertNotIn(NAVER_TOKEN, str(error.exception))
        for base in ['http://127.0.0.1:49152', 'http://localhost:49153']:
            runtime = self.runtime(allow_test_origins=True,
                                   webhook_base_url='http://127.0.0.1:9/webhook',
                                   naver_publisher_api_base_url=base,
                                   naver_publisher_api_token=NAVER_TOKEN)
            self.assertEqual(base, runtime.naver_publisher_api_base_url)
        for base in ['https://127.0.0.1:8001', 'http://evil.test:8001',
                     'http://host.docker.internal:8001', 'http://127.0.0.1.evil.test:8001',
                     'http://127.0.0.1:8001/path', 'http://127.0.0.1:8001#',
                     'http://127.0.0.1:65536', 'http://127.0.0.1:0',
                     'http://[broken', 'http://127.0.0.1:abc']:
            with self.subTest(test_base=base):
                with self.assertRaises(self.module.ValidationError):
                    self.runtime(allow_test_origins=True,
                                 webhook_base_url='http://127.0.0.1:9/webhook',
                                 naver_publisher_api_base_url=base,
                                 naver_publisher_api_token=NAVER_TOKEN)
        self.assertEqual([], self.transport.calls)

    def test_constructor_requires_paired_nonempty_naver_configuration(self):
        for base, token in [(NAVER_BASE, None), (None, NAVER_TOKEN),
                            (NAVER_BASE, ''), (NAVER_BASE, ' '),
                            ('', NAVER_TOKEN), (' ', NAVER_TOKEN)]:
            with self.subTest(base=base, token_missing=not token):
                with self.assertRaises(self.module.ValidationError) as error:
                    self.runtime(naver_publisher_api_base_url=base,
                                 naver_publisher_api_token=token)
                self.assertNotIn(NAVER_TOKEN, str(error.exception))
        self.assertEqual([], self.transport.calls)

    def test_dedicated_route_uses_naver_token_and_exact_approved_payload(self):
        parameters = inspect.signature(self.module.PublishingRuntime).parameters
        self.assertIn('naver_publisher_api_base_url', parameters)
        self.assertIn('naver_publisher_api_token', parameters)
        runtime = self.runtime(naver_publisher_api_base_url=NAVER_BASE,
                               naver_publisher_api_token=NAVER_TOKEN)
        plan = self.plan(runtime)
        result = self.execute(runtime, plan)
        self.assertEqual('failed', result['status'])
        self.assertEqual([('native', 'naver_blog')], self.ledger.reads)
        self.assertEqual([], self.ledger.writes)
        self.assertEqual(1, len(self.transport.calls))
        method, url, request = self.transport.calls[0]
        self.assertEqual('POST', method)
        self.assertEqual(NAVER_BASE + '/publish-sync/naver_blog', url)
        self.assertEqual(self.payload, request['body'])
        self.assertTrue(request['disable_proxy'])
        self.assertEqual(NAVER_TOKEN, request['headers']['X-API-Token'])
        self.assertEqual(plan['receipt_id'], request['headers']['X-Idempotency-Key'])
        self.assertNotIn('X-SNS-Token', request['headers'])
        self.assertNotIn(LEGACY_TOKEN, json.dumps(request))
        self.assertNotIn(WEBHOOK_TOKEN, json.dumps(request))

    def test_missing_dedicated_config_fails_before_ledger_or_transport(self):
        runtime = self.runtime()
        plan = self.plan(runtime)
        self.assertEqual([], self.ledger.reads)
        self.assertEqual([], self.transport.calls)
        result = self.execute(runtime, plan)
        self.assertEqual('failed', result['status'])
        self.assertEqual([], self.ledger.reads)
        self.assertEqual([], self.ledger.writes)
        self.assertEqual([], self.transport.calls)
        self.assertEqual('failed', runtime.receipt_status(plan['receipt_id'])['state'])
        self.assertIn('Naver', result['error'])
        with self.assertRaises(self.module.PublishingError):
            runtime.dispatch(plan['receipt_id'], session_id='session')
        self.assertEqual([], self.transport.calls)


class LocalBoundaryServer(ThreadingHTTPServer):
    calls: list
    redirect_to: Optional[str]


class LocalBoundaryHandler(BaseHTTPRequestHandler):
    """Ephemeral backend: rejects before mutation, or returns a redirect to a trap."""
    def log_message(self, format, *args):
        pass

    def _respond(self):
        size = int(self.headers.get('Content-Length', '0'))
        body = json.loads(self.rfile.read(size)) if size else None
        server = cast(LocalBoundaryServer, self.server)
        server.calls.append((self.command, self.path, dict(self.headers), body))
        redirect = server.redirect_to
        self.send_response(307 if redirect else 200)
        if redirect:
            self.send_header('Location', redirect)
        raw = json.dumps(PRE_MUTATION_FAILURE).encode('utf-8')
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    do_POST = _respond
    do_GET = _respond


class NaverNativeHttpBoundaryTests(NativeTransportFixture):
    def server(self):
        server = LocalBoundaryServer(('127.0.0.1', 0), LocalBoundaryHandler)
        server.calls = []
        server.redirect_to = None
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        return server, f'http://127.0.0.1:{server.server_port}'

    def boundary_runtime(self, naver_base, legacy_base):
        # Remove only the transport fake: exercise urllib, not any real service.
        self.request_patch.stop()
        return self.runtime(
            webhook_base_url=legacy_base + '/webhook',
            publisher_api_base_url=legacy_base,
            naver_publisher_api_base_url=naver_base,
            naver_publisher_api_token=NAVER_TOKEN,
            allow_test_origins=True, timeout=5,
        )

    def test_live_http_uses_only_naver_backend_and_bypasses_inherited_proxy(self):
        backend, base = self.server()
        trap, trap_base = self.server()
        runtime = self.boundary_runtime(base, trap_base)
        plan = self.plan(runtime)
        # Empty bypass list plus a captured proxy ensures ProxyHandler({}) matters.
        environment = {'HTTP_PROXY': trap_base, 'http_proxy': trap_base,
                       'HTTPS_PROXY': trap_base, 'https_proxy': trap_base,
                       'ALL_PROXY': trap_base, 'all_proxy': trap_base,
                       'NO_PROXY': '', 'no_proxy': ''}
        with mock.patch.dict(os.environ, environment, clear=True):
            result = self.execute(runtime, plan)
        self.assertEqual('failed', result['status'])
        self.assertEqual('synthetic_pre_mutation_rejection', result['error'])
        self.assertEqual(1, len(backend.calls))
        method, path, headers, body = backend.calls[0]
        headers = {key.lower(): value for key, value in headers.items()}
        self.assertEqual(('POST', '/publish-sync/naver_blog'), (method, path))
        self.assertEqual(NAVER_TOKEN, headers['x-api-token'])
        self.assertEqual(plan['receipt_id'], headers['x-idempotency-key'])
        self.assertNotIn('x-sns-token', headers)
        self.assertEqual(self.payload, body)
        self.assertEqual([], trap.calls)
        self.assertEqual([], self.ledger.writes)
        self.assertEqual('failed', runtime.receipt_status(plan['receipt_id'])['state'])
        with self.assertRaises(self.module.ReceiptError):
            runtime.dispatch(plan['receipt_id'], session_id='session')
        self.assertEqual(1, len(backend.calls))

    def test_live_http_redirect_never_leaks_token_or_calls_shared_fallback(self):
        backend, base = self.server()
        trap, trap_base = self.server()
        backend.redirect_to = trap_base + '/redirect-target'
        runtime = self.boundary_runtime(base, trap_base)
        plan = self.plan(runtime)
        result = self.execute(runtime, plan)
        self.assertEqual('failed', result['status'])
        self.assertEqual('HTTP 307', result['error'])
        self.assertEqual(1, len(backend.calls))
        self.assertEqual([], trap.calls)
        self.assertEqual([], self.ledger.writes)
        self.assertNotIn(NAVER_TOKEN, json.dumps(result))
        with self.assertRaises(self.module.ReceiptError):
            runtime.dispatch(plan['receipt_id'], session_id='session')
        self.assertEqual(1, len(backend.calls))
