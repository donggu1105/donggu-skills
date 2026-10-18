"""Experimental PREAUTH adapter tests: fake transport/ledger, no live systems."""
import copy
import importlib
import json
from pathlib import Path
import socket
import tempfile
from typing import Any
import unittest
from unittest import mock

from tests.test_publishing_runtime import load_module
from tests.test_native_plugin_packages import load_package, FakeContext, ROOT


class FakeLedger:
    def __init__(self):
        self.reads = []
        self.writes = []
        self.existing = None

    def find_active_optional(self, topic, channel):
        self.reads.append((topic, channel))
        return self.existing

    def record_publish(self, **row):
        self.writes.append(row)


class FakeTransport:
    """An explicit boundary fake; unspecified responses fail, never call HTTP."""
    def __init__(self):
        self.calls = []
        self.response: Any = None

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, copy.deepcopy(kwargs)))
        if isinstance(self.response, Exception):
            raise self.response
        if self.response is None:
            raise AssertionError('test must explicitly configure a fake response')
        return copy.deepcopy(self.response)


class NaverBlogPreauthTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = FakeLedger()
        self.transport = FakeTransport()
        patcher = mock.patch.object(self.module, '_request_json', self.transport)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.runtime = self.module.PublishingRuntime(
            receipt_root=Path(self.tmp.name) / 'receipts',
            webhook_base_url='http://127.0.0.1:9/webhook', webhook_token='fake-webhook',
            publisher_api_base_url='http://127.0.0.1:9', publisher_api_token='fake-publisher',
            naver_publisher_api_base_url='http://127.0.0.1:10',
            naver_publisher_api_token='fake-naver-publisher',
            ledger=self.ledger, allow_test_origins=True,
        )
        self.payload = {'blog_id': 'approved_blog', 'title': 'A title',
                        'content': 'Exact body', 'tags': ['FDE', 'AI', '업무']}

    def preview(self, **overrides):
        arguments = dict(channel='naver_blog', operation='publish', payload=self.payload,
                         topic='demo', note_path='Blog/demo.md', session_id='session',
                         turn_id='preview-turn', user_message_id=1)
        arguments.update(overrides)
        return self.runtime.preview(**arguments)

    def execute(self, plan, **overrides):
        arguments = dict(approval_text='발행해', session_id='session',
                         turn_id='approval-turn', user_message_id=2)
        arguments.update(overrides)
        return self.runtime.execute(plan['receipt_id'], **arguments)

    def success_response(self, **overrides):
        self.transport.response = dict(success=True,
                                       url='https://blog.naver.com/approved_blog/123',
                                       post_id='123', **overrides)

    def test_registered_preview_schema_advertises_experimental_naver_blog(self):
        package = load_package(ROOT / 'donggu-sns', 'naver_schema_test')
        context = FakeContext()
        package.register(context)
        preview = next(item['schema'] for item in context.tools
                       if item['name'] == 'donggu_publishing_preview')
        self.assertIn('naver_blog', preview['parameters']['properties']['channel']['enum'])
        self.assertIn('PREAUTH', preview['description'])
        self.assertIn('NOT DEPLOYED', preview['description'])
        self.assertIn('blog_id', preview['parameters']['properties']['payload']['description'])

    def test_preview_counts_cover_and_inline_images_in_exact_payload(self):
        self.payload.update(
            content='![Inline](https://img.test/inline.png)\n## Section\n![Again](https://img.test/inline.png)',
            cover_image='https://img.test/cover.png')
        plan = self.preview()
        self.assertEqual(self.payload, plan['preview']['payload'])
        self.assertEqual(2, plan['preview']['image_count'])
        self.assertEqual(['lead', 'Section'], [image['section'] for image in plan['preview']['inline_images']])
        self.assertEqual([], self.transport.calls)

    def test_preview_enforces_backend_request_bounds_without_normalization(self):
        invalid = [('blog_id', '_blog'), ('blog_id', '-blog'), ('blog_id', 'a' * 51),
                   ('title', 'a' * 101), ('content', 'a' * 100001),
                   ('tags', [f'tag-{i}' for i in range(31)])]
        for field, value in invalid:
            with self.subTest(field=field):
                with self.assertRaises(self.module.ValidationError):
                    self.preview(payload={**self.payload, field: value})
        bounded = {**self.payload, 'blog_id': 'A' * 50, 'title': 'a' * 100,
                   'content': 'a' * 100000, 'tags': [f'tag-{i}' for i in range(30)]}
        self.assertEqual(bounded, self.preview(payload=bounded)['preview']['payload'])
        self.assertEqual([], self.transport.calls)
        self.assertEqual([], self.ledger.reads)

    def test_unknown_backend_outcome_requires_reconciliation_without_ledger_write(self):
        responses = [
            {'success': False},
            {'success': False, 'external_mutation_possible': None},
            {'success': False, 'external_mutation_possible': 'false'},
            {'success': False, 'external_mutation_possible': 0},
            {'external_mutation_possible': False},
            {'success': 'false', 'external_mutation_possible': False},
            {'success': 0, 'external_mutation_possible': False},
        ]
        for index, response in enumerate(responses):
            with self.subTest(response=response):
                self.transport.response = response
                plan = self.preview(topic=f'unknown-{index}')
                self.assertEqual('reconciliation_required',
                                 self.execute(plan, user_message_id=index + 2)['status'])
                self.assertEqual([], self.ledger.writes)

    def test_naver_result_rejects_post_ids_over_backend_limit(self):
        identifier = '1' * 21
        self.transport.response = dict(success=True,
            url='https://blog.naver.com/approved_blog/' + identifier, post_id=identifier)
        result = self.execute(self.preview())
        self.assertEqual('reconciliation_required', result['status'])
        self.assertEqual([], self.ledger.writes)

    def test_postview_exact_query_is_canonicalized_before_ledger(self):
        for index, query in enumerate(('blogId=approved_blog&logNo=123',
                                        'logNo=123&blogId=approved_blog')):
            self.transport.response = dict(success=True, post_id='123',
                url='https://blog.naver.com/PostView.naver?' + query)
            plan = self.preview(topic=f'postview-{index}')
            result = self.execute(plan, user_message_id=index + 2)
            self.assertEqual('completed', result['status'])
            self.assertEqual('https://blog.naver.com/approved_blog/123', result['url'])
            self.assertEqual(result['url'], self.ledger.writes[-1]['url'])

    def test_target_mismatch_or_invalid_identifiers_never_write_success_ledger(self):
        urls = [
            'https://blog.naver.com/other_blog/123',
            'http://blog.naver.com/approved_blog/123',
            'https://evil.test/approved_blog/123',
            'https://blog.naver.com.evil.test/approved_blog/123',
            'https://m.blog.naver.com/approved_blog/123',
            'https://blog.naver.com:443/approved_blog/123',
            'https://u@blog.naver.com/approved_blog/123',
            'https://blog.naver.com/approved_blog/0',
            'https://blog.naver.com/approved_blog/0123',
            'https://blog.naver.com/approved_blog/-123',
            'https://blog.naver.com/approved_blog/１２３',
            'https://blog.naver.com/approved_blog/123/',
            'https://blog.naver.com/approved_blog/123?blogId=other',
            'https://blog.naver.com/approved_blog/123#fragment',
            'https://blog.naver.com/approved_blog/123?',
            'https://blog.naver.com/approved_blog/123#',
            'https://blog.naver.com/approved_blog/../123',
            'https://blog.naver.com/approved_blog/%2e%2e/123',
            'https://blog.naver.com/approved_blog%2fother/123',
            'https://blog.naver.com/approved_blog\\\\other/123',
            ' https://blog.naver.com/approved_blog/123',
            'https://blog.naver.com/approved_blog/123\n',
            'https://blog.naver.com/approved_blog/1\t23',
            None,
        ]
        responses = [dict(success=True, url=url, post_id='123') for url in urls]
        responses += [dict(success=True, url='https://blog.naver.com/approved_blog/123',
                           post_id=value) for value in ('124', '', None, 123, True, '0123', '123\n')]
        for index, response in enumerate(responses):
            with self.subTest(response=response):
                self.transport.response = response
                plan = self.preview(topic=f'mismatch-{index}')
                result = self.execute(plan, user_message_id=index + 2)
                self.assertEqual('reconciliation_required', result['status'])
                self.assertEqual([], self.ledger.writes)
                self.assertEqual('reconciliation_required',
                                 self.runtime.receipt_status(plan['receipt_id'])['state'])

    def test_missing_naver_publisher_fails_without_shared_or_webhook_fallback(self):
        self.runtime.naver_publisher_api_base_url = None
        self.runtime.naver_publisher_api_token = None
        plan = self.preview()
        result = self.execute(plan)
        self.assertEqual('failed', result['status'])
        self.assertEqual('failed', self.runtime.receipt_status(plan['receipt_id'])['state'])
        self.assertEqual([], self.transport.calls)
        self.assertEqual([], self.ledger.reads)
        self.assertEqual([], self.ledger.writes)

    def test_full_lifecycle_uses_only_loopback_exact_payload_and_fake_ledger(self):
        self.payload.update(category='Notes', cover_image='https://img.test/cover.png')
        plan = self.preview()
        self.success_response()
        result = self.execute(plan)
        self.assertEqual('completed', result['status'])
        self.assertEqual([('demo', 'naver_blog')], self.ledger.reads)
        self.assertEqual([dict(topic='demo', channel='naver_blog', note_path='Blog/demo.md',
                               post_id='123', url='https://blog.naver.com/approved_blog/123')],
                         self.ledger.writes)
        self.assertEqual(1, len(self.transport.calls))
        method, url, request = self.transport.calls[0]
        self.assertEqual('POST', method)
        self.assertEqual('http://127.0.0.1:10/publish-sync/naver_blog', url)
        self.assertEqual(self.payload, request['body'])
        self.assertTrue(request['disable_proxy'])
        self.assertEqual('fake-naver-publisher', request['headers']['X-API-Token'])
        self.assertEqual(plan['receipt_id'], request['headers']['X-Idempotency-Key'])
        self.assertNotIn('X-SNS-Token', request['headers'])
        self.assertEqual('completed', self.runtime.receipt_status(plan['receipt_id'])['state'])
        with self.assertRaises(self.module.PublishingError):
            self.execute(plan)
        self.assertEqual(1, len(self.transport.calls))

    def test_preview_rejects_invalid_blog_id_without_normalizing_it(self):
        invalid = ['', ' ', '../other', '..', 'a/b', 'a\\\\b', '%2e%2e',
                   'blog?x=1', 'blog#fragment', ' blog', 'blog ', 'blog\n',
                   '한글', 'a' * 65, None, True, 123]
        for blog_id in invalid:
            with self.subTest(blog_id=blog_id):
                with self.assertRaisesRegex(self.module.ValidationError, 'blog_id'):
                    self.preview(payload={**self.payload, 'blog_id': blog_id})
        self.assertEqual([], list(self.runtime.store.root.glob('*.json')))
        self.assertEqual([], self.transport.calls)
        self.assertEqual([], self.ledger.reads)

    def test_preview_binds_exact_blog_id_without_network_or_ledger(self):
        plan = self.preview()
        self.assertEqual('planned', plan['status'])
        self.assertEqual(self.payload, plan['preview']['payload'])
        receipt = self.runtime.store.load(plan['receipt_id'])
        self.assertEqual(self.payload, receipt['payload'])
        other = self.preview(payload={**self.payload, 'blog_id': 'another_blog'})
        self.assertNotEqual(plan['payload_sha256'], other['payload_sha256'])
        self.assertEqual([], self.transport.calls)
        self.assertEqual([], self.ledger.reads)
        self.assertEqual([], self.ledger.writes)
