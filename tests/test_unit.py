#!/usr/bin/env python

"""Mocked unit tests for testingbotclient.

These tests do NOT hit the network or require TestingBot credentials. They
install a fake requests.Session on the client and assert that every method
issues the correct HTTP verb, URL and body. Run with:

    python -m unittest test_unit
    python test_unit.py

The live, credential-requiring integration tests live in test_client.py.
"""

import os
import tempfile
import unittest

try:
    from unittest import mock
except ImportError:  # Python 2 fallback
    import mock

import testingbotclient
from testingbotclient import TestingBotClient, TestingBotException


class FakeResponse(object):
    def __init__(self, status_code=200, payload=None, text=''):
        self.status_code = status_code
        self._payload = {} if payload is None else payload
        self.text = text
        self.request = None

    def json(self):
        return self._payload


class FakeRequest(object):
    def __init__(self, headers):
        self.headers = headers


class FakeSession(object):
    """Records every call and returns queued (or default 200/{}) responses."""

    def __init__(self):
        self.calls = []
        self._responses = []
        self.default = FakeResponse(200, {})

    def queue(self, response):
        self._responses.append(response)

    def _next(self):
        return self._responses.pop(0) if self._responses else self.default

    def _record(self, method, url, kwargs):
        self.calls.append({'method': method, 'url': url, 'kwargs': kwargs})
        return self._next()

    def get(self, url, **kwargs):
        return self._record('GET', url, kwargs)

    def post(self, url, **kwargs):
        return self._record('POST', url, kwargs)

    def put(self, url, **kwargs):
        return self._record('PUT', url, kwargs)

    def delete(self, url, **kwargs):
        return self._record('DELETE', url, kwargs)


class ClientTestCase(unittest.TestCase):
    BASE = 'https://api.testingbot.com/v1/'

    def setUp(self):
        self.client = TestingBotClient('key', 'secret')
        self.session = FakeSession()
        self.client.session = self.session

    def queue(self, status_code=200, payload=None):
        self.session.queue(FakeResponse(status_code, payload))

    def last(self):
        return self.session.calls[-1]

    def assertCall(self, method, path, json_body=None, data=None):
        """Assert the most recent call matches verb + URL (and optional body).

        path begins with '/'. The client prepends api_url (which ends with '/'),
        so the built URL contains the historical 'v1//' double slash; BASE + path
        reproduces exactly what the client sends.
        """
        call = self.last()
        self.assertEqual(call['method'], method)
        self.assertEqual(call['url'], self.BASE + path)
        if json_body is not None:
            self.assertEqual(call['kwargs'].get('json'), json_body)
        if data is not None:
            self.assertEqual(call['kwargs'].get('data'), data)

    def assertTimeoutPassed(self):
        self.assertEqual(self.last()['kwargs'].get('timeout'), self.client.timeout)


# --------------------------------------------------------------------------- #
# Client wiring: auth, helpers, timeouts, session, exceptions
# --------------------------------------------------------------------------- #
class TestClientCore(ClientTestCase):
    def test_share_link(self):
        # md5("key:secret:test"), i.e. md5(key:secret:identifier) for this client
        self.assertEqual(self.client.get_share_link('test'),
                         'c5a98b42c97a46ec513467ed307fcb9c')

    def test_default_timeout(self):
        self.assertEqual(self.client.timeout, 60)

    def test_custom_timeout(self):
        self.assertEqual(TestingBotClient('k', 's', timeout=5).timeout, 5)

    def test_timeout_passed_to_request(self):
        self.client.get('/user')
        self.assertTimeoutPassed()

    def test_session_created(self):
        c = TestingBotClient('k', 's')
        self.assertIsNotNone(c.session)
        self.assertEqual(c.session.auth, ('k', 's'))

    def test_user_agent_header(self):
        c = TestingBotClient('k', 's')
        self.assertTrue(c.session.headers.get('User-Agent', '').startswith(
            'testingbotclient/'))

    def test_retry_adapter_configured(self):
        c = TestingBotClient('k', 's', max_retries=4)
        retries = c.session.get_adapter('https://api.testingbot.com/').max_retries
        self.assertEqual(retries.total, 4)
        self.assertIn(429, retries.status_forcelist)

    def test_context_manager_returns_self(self):
        with TestingBotClient('k', 's') as tb:
            self.assertIsInstance(tb, TestingBotClient)

    def test_close_closes_session(self):
        c = TestingBotClient('k', 's')
        closed = []
        c.session.close = lambda: closed.append(True)
        c.close()
        self.assertEqual(closed, [True])

    def test_paginate_dict_pages(self):
        pages = iter([{'data': [1, 2]}, {'data': [3, 4]}, {'data': [5]}])
        out = list(testingbotclient.paginate(lambda offset, limit: next(pages), limit=2))
        self.assertEqual(out, [1, 2, 3, 4, 5])

    def test_paginate_list_pages(self):
        pages = iter([[1, 2], [3]])
        out = list(testingbotclient.paginate(lambda offset, limit: next(pages), limit=2))
        self.assertEqual(out, [1, 2, 3])

    def test_non_2xx_raises(self):
        self.queue(403, {'error': 'readonly'})
        with self.assertRaises(TestingBotException):
            self.client.get('/user')

    def test_201_does_not_raise(self):
        self.queue(201, {'success': True})
        self.assertEqual(self.client.post('/x', {}), {'success': True})

    def test_exception_scrubs_authorization(self):
        resp = FakeResponse(401, {'error': 'unauth'}, text='unauth')
        resp.request = FakeRequest({'Authorization': 'Basic SECRET', 'X-Other': '1'})
        exc = TestingBotException('401', response=resp)
        self.assertNotIn('Authorization', exc.response.request.headers)
        self.assertIn('X-Other', exc.response.request.headers)
        self.assertIsNotNone(exc.response)
        self.assertEqual(exc.response.status_code, 401)

    def test_creds_from_testingbot_env(self):
        with mock.patch.dict(os.environ,
                             {'TESTINGBOT_KEY': 'ek', 'TESTINGBOT_SECRET': 'es'},
                             clear=True):
            c = TestingBotClient()
        self.assertEqual((c.testingbotKey, c.testingbotSecret), ('ek', 'es'))

    def test_creds_from_tb_env(self):
        with mock.patch.dict(os.environ,
                             {'TB_KEY': 'tk', 'TB_SECRET': 'ts'},
                             clear=True):
            c = TestingBotClient()
        self.assertEqual((c.testingbotKey, c.testingbotSecret), ('tk', 'ts'))

    def test_creds_from_dotfile_strips_newline_and_keeps_colon(self):
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, '.testingbot'), 'w') as f:
            f.write('mykey:my:secret\n')
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch('os.path.expanduser', return_value=tmpdir):
                c = TestingBotClient()
        self.assertEqual(c.testingbotKey, 'mykey')
        self.assertEqual(c.testingbotSecret, 'my:secret')


# --------------------------------------------------------------------------- #
# Existing resources
# --------------------------------------------------------------------------- #
class TestTests(ClientTestCase):
    def test_get_tests_defaults(self):
        self.queue(200, {'data': [{'session_id': 'a'}]})
        out = self.client.tests.get_tests()
        self.assertCall('GET', '/tests?offset=0&count=10')
        self.assertEqual(out, [{'session_id': 'a'}])

    def test_get_tests_pagination(self):
        self.queue(200, {'data': []})
        self.client.tests.get_tests(20, 5)
        self.assertCall('GET', '/tests?offset=20&count=5')

    def test_get_test_ids(self):
        self.queue(200, {'data': [{'session_id': 'a'}, {'session_id': 'b'}]})
        self.assertEqual(self.client.tests.get_test_ids(), ['a', 'b'])
        self.assertCall('GET', '/tests')

    def test_get_test(self):
        self.client.tests.get_test('sess-1')
        self.assertCall('GET', '/tests/sess-1')

    def test_get_test_numeric_id(self):
        self.client.tests.get_test(123)
        self.assertCall('GET', '/tests/123')

    def test_get_tests_filters(self):
        self.queue(200, {'data': []})
        self.client.tests.get_tests(0, 10, since=1700000000, browser_id=5,
                                    group='smoke', build='b1',
                                    skip_fields='logs,thumbs')
        self.assertCall('GET', '/tests?offset=0&count=10&since=1700000000'
                               '&browser_id=5&group=smoke&build=b1'
                               '&skip_fields=logs%2Cthumbs')

    def test_get_test_skip_fields(self):
        self.client.tests.get_test('sess-1', skip_fields=['steps', 'thumbs'])
        self.assertCall('GET', '/tests/sess-1?skip_fields=steps%2Cthumbs')

    def test_path_segment_encoded(self):
        # A slash in an id must be encoded so it can't break out of the path
        self.client.tests.get_test('a/b')
        self.assertCall('GET', '/tests/a%2Fb')

    def test_create_test(self):
        self.queue(200, {'success': True})
        out = self.client.tests.create_test('manual run', success=True,
                                            status_message='m', build='b1')
        self.assertCall('POST', '/tests', json_body={'test': {
            'name': 'manual run', 'success': True,
            'status_message': 'm', 'build': 'b1'}})
        self.assertEqual(out, {'success': True})

    def test_update_test_pass(self):
        self.queue(200, {'success': True})
        ok = self.client.tests.update_test('s', name='n', passed=True,
                                           status_message='m', build='b')
        self.assertCall('PUT', '/tests/s', data={
            'test[status_message]': 'm',
            'test[name]': 'n',
            'test[success]': '1',
            'build': 'b',
        })
        self.assertTrue(ok)

    def test_update_test_fail_flag(self):
        self.queue(200, {'success': True})
        self.client.tests.update_test('s', passed=False)
        # passed=False alone -> only test[success]='0', no stray keys
        self.assertCall('PUT', '/tests/s', data={'test[success]': '0'})

    def test_delete_test(self):
        self.queue(200, {'success': True})
        self.assertTrue(self.client.tests.delete_test('s'))
        self.assertCall('DELETE', '/tests/s')

    def test_stop_test_sends_empty_body(self):
        self.queue(200, {'success': True})
        self.assertTrue(self.client.tests.stop_test('s'))
        self.assertCall('PUT', '/tests/s/stop', data={})


class TestStorage(ClientTestCase):
    def test_upload_remote_file(self):
        self.client.storage.upload_remote_file('https://x/app.apk')
        self.assertCall('POST', '/storage', data={'url': 'https://x/app.apk'})

    def test_replace_remote_file(self):
        self.client.storage.replace_remote_file('tb://abc123', 'https://x/new.apk')
        self.assertCall('POST', '/storage/abc123', data={'url': 'https://x/new.apk'})

    def test_replace_local_file(self):
        fd, path = tempfile.mkstemp(suffix='.apk')
        os.write(fd, b'PK\x03\x04')
        os.close(fd)
        try:
            self.client.storage.replace_local_file('tb://abc123', path)
        finally:
            os.remove(path)
        call = self.last()
        self.assertEqual(call['method'], 'POST')
        self.assertEqual(call['url'], self.BASE + '/storage/abc123')
        self.assertIn('files', call['kwargs'])
        self.assertIn('file', call['kwargs']['files'])
        self.assertIsNone(call['kwargs'].get('data'))

    def test_get_stored_file_strips_scheme(self):
        self.client.storage.get_stored_file('tb://abc123')
        self.assertCall('GET', '/storage/abc123')

    def test_remove_file_strips_scheme(self):
        self.client.storage.remove_file('tb://abc123')
        self.assertCall('DELETE', '/storage/abc123')

    def test_get_stored_files(self):
        self.client.storage.get_stored_files()
        self.assertCall('GET', '/storage/?offset=0&count=10')

    def test_upload_local_file(self):
        fd, path = tempfile.mkstemp(suffix='.apk')
        os.write(fd, b'PK\x03\x04')
        os.close(fd)
        try:
            self.queue(200, {'app_url': 'tb://abc'})
            out = self.client.storage.upload_local_file(path)
        finally:
            os.remove(path)
        call = self.last()
        self.assertEqual(call['method'], 'POST')
        self.assertEqual(call['url'], self.BASE + '/storage')
        self.assertIn('files', call['kwargs'])
        self.assertEqual(out, {'app_url': 'tb://abc'})

    def test_upload_local_file_raises_on_error(self):
        # upload_local_file has its OWN inline status check (not client.post);
        # pin that a non-2xx raises.
        fd, path = tempfile.mkstemp(suffix='.apk')
        os.close(fd)
        try:
            self.queue(403, {'error': 'readonly'})
            with self.assertRaises(TestingBotException):
                self.client.storage.upload_local_file(path)
        finally:
            os.remove(path)


class TestInformation(ClientTestCase):
    def test_get_browsers(self):
        self.client.information.get_browsers()
        self.assertCall('GET', '/browsers')

    def test_get_browsers_type(self):
        self.client.information.get_browsers(type='rc')
        self.assertCall('GET', '/browsers?type=rc')

    def test_get_devices(self):
        self.client.information.get_devices()
        self.assertCall('GET', '/devices')

    def test_get_devices_platform(self):
        self.client.information.get_devices(platform='android')
        self.assertCall('GET', '/devices?platform=android')

    def test_get_available_devices(self):
        self.client.information.get_available_devices()
        self.assertCall('GET', '/devices/available')

    def test_get_device(self):
        self.client.information.get_device(42)
        self.assertCall('GET', '/devices/42')


class TestConfiguration(ClientTestCase):
    def test_get_ip_ranges(self):
        self.client.configuration.get_ip_ranges()
        self.assertCall('GET', '/configuration/ip-ranges')


class TestTunnel(ClientTestCase):
    def test_get_tunnels(self):
        self.client.tunnel.get_tunnels()
        self.assertCall('GET', '/tunnel/list')

    def test_delete_tunnel(self):
        self.client.tunnel.delete_tunnel(7)
        self.assertCall('DELETE', '/tunnel/7')


class TestBuild(ClientTestCase):
    def test_get_builds(self):
        self.client.build.get_builds()
        self.assertCall('GET', '/builds?offset=0&count=10')

    def test_get_tests_for_build(self):
        self.client.build.get_tests_for_build('mybuild')
        self.assertCall('GET', '/builds/mybuild')

    def test_delete_build(self):
        self.client.build.delete_build(5)
        self.assertCall('DELETE', '/builds/5')


class TestUser(ClientTestCase):
    def test_get_user_information(self):
        self.client.user.get_user_information()
        self.assertCall('GET', '/user')

    def test_update_user_information(self):
        # The client forwards the dict verbatim (no auto-nesting); the server
        # expects nested user[first_name]/user[last_name] keys and rejects others.
        body = {'user[first_name]': 'A', 'user[last_name]': 'B'}
        self.client.user.update_user_information(body)
        self.assertCall('PUT', '/user', data=body)


# --------------------------------------------------------------------------- #
# New resources
# --------------------------------------------------------------------------- #
class TestJobs(ClientTestCase):
    def test_get_job(self):
        self.client.jobs.get_job(42)
        self.assertCall('GET', '/jobs/42')

    def test_wait_for_job_polls_until_finished(self):
        self.queue(200, {'status': 'RUNNING'})
        self.queue(200, {'status': 'FINISHED', 'success': True})
        out = self.client.jobs.wait_for_job(42, interval=0)
        self.assertEqual(out['status'], 'FINISHED')
        self.assertEqual(len(self.session.calls), 2)
        self.assertCall('GET', '/jobs/42')

    def test_wait_for_job_times_out_after_polling(self):
        # Controlled clock: t=0 (deadline), t=0 (poll once), then t=100 (expired).
        def clock():
            yield 0
            yield 0
            while True:
                yield 100
        ticks = clock()
        self.queue(200, {'status': 'RUNNING'})
        with mock.patch('testingbotclient.time.time', lambda: next(ticks)):
            self.assertRaises(TestingBotException,
                              self.client.jobs.wait_for_job, 42, 10, 0)
        self.assertGreaterEqual(len(self.session.calls), 1)


class TestScreenshots(ClientTestCase):
    def test_get_screenshots(self):
        self.client.screenshots.get_screenshots(0, 5)
        self.assertCall('GET', '/screenshots?offset=0&count=5')

    def test_get_screenshot(self):
        self.client.screenshots.get_screenshot(7)
        self.assertCall('GET', '/screenshots/7')

    def test_get_screenshot_exclude_ids(self):
        self.client.screenshots.get_screenshot(7, exclude_ids=[1, 2])
        self.assertCall('GET', '/screenshots/7?excludeIds=1%2C2')

    def test_take_screenshots(self):
        self.client.screenshots.take_screenshots(
            'https://x.com', '1920x1080', [5, 7], wait_time=3, full_page=True,
            callback_url='https://cb')
        self.assertCall('POST', '/screenshots', json_body={
            'url': 'https://x.com',
            'resolution': '1920x1080',
            'browsers': [5, 7],
            'wait_time': 3,
            'full_page': True,
            'fullpage': True,
            'callback_url': 'https://cb',
        })

    def test_take_screenshots_defaults(self):
        # Default path: no full_page/fullpage/callback_url keys, wait_time=0.
        self.client.screenshots.take_screenshots('https://x.com', '1920x1080', [5, 7])
        self.assertCall('POST', '/screenshots', json_body={
            'url': 'https://x.com',
            'resolution': '1920x1080',
            'browsers': [5, 7],
            'wait_time': 0,
        })

    def test_take_screenshots_browser_triples(self):
        # The capability-triple form is forwarded unchanged.
        caps = [{'browser': 'chrome', 'version': 'latest', 'os': 'WIN10'}]
        self.client.screenshots.take_screenshots('https://x.com', '1920x1080', caps)
        self.assertEqual(self.last()['kwargs']['json']['browsers'], caps)


class TestTeam(ClientTestCase):
    def test_get_concurrency(self):
        self.client.team.get_concurrency()
        self.assertCall('GET', '/team-management')

    def test_get_users(self):
        self.client.team.get_users(0, 10)
        self.assertCall('GET', '/team-management/users?offset=0&count=10')

    def test_get_user(self):
        self.client.team.get_user(9)
        self.assertCall('GET', '/team-management/users/9')

    def test_create_user(self):
        self.client.team.create_user('a@b.com', 'pw', first_name='A',
                                     concurrency_physical=2)
        self.assertCall('POST', '/team-management/users', json_body={
            'email': 'a@b.com', 'password': 'pw',
            'first_name': 'A', 'concurrencyPhysical': 2,
        })

    def test_update_user(self):
        self.client.team.update_user(9, last_name='Z', credits=100,
                                     concurrency=4, concurrency_physical=2)
        self.assertCall('PUT', '/team-management/users/9', json_body={
            'last_name': 'Z', 'credits': 100,
            'concurrency': 4, 'concurrencyPhysical': 2})

    def test_get_client_key(self):
        self.client.team.get_client_key(9)
        self.assertCall('GET', '/team-management/users/9/client-key')

    def test_reset_keys(self):
        self.client.team.reset_keys(9)
        self.assertCall('POST', '/team-management/users/9/reset-keys',
                        json_body={})


class TestLabSuites(ClientTestCase):
    def test_get_suites(self):
        self.client.labsuites.get_suites()
        self.assertCall('GET', '/labsuites?offset=0&count=10')

    def test_get_suite(self):
        self.client.labsuites.get_suite(3)
        self.assertCall('GET', '/labsuites/3')

    def test_create_suite(self):
        self.queue(200, {'success': True, 'suite_id': 9})
        out = self.client.labsuites.create_suite('S', cron='0 9 * * *', video=True)
        self.assertCall('POST', '/labsuites', json_body={
            'suite': {'name': 'S', 'cron': '0 9 * * *', 'video': True}})
        self.assertEqual(out, {'success': True, 'suite_id': 9})

    def test_create_suite_all_fields(self):
        self.client.labsuites.create_suite(
            'S', cron='0 9 * * *', screenshot=True, video=False,
            idletimeout=120, screenresolution='1920x1080')
        self.assertCall('POST', '/labsuites', json_body={'suite': {
            'name': 'S', 'cron': '0 9 * * *', 'screenshot': True,
            'video': False, 'idletimeout': 120,
            'screenresolution': '1920x1080'}})

    def test_delete_suite(self):
        self.client.labsuites.delete_suite(3)
        self.assertCall('DELETE', '/labsuites/3')

    def test_trigger(self):
        self.client.labsuites.trigger(3)
        self.assertCall('POST', '/labsuites/3/trigger', json_body={})

    def test_get_tests(self):
        self.client.labsuites.get_tests(3, 0, 10)
        self.assertCall('GET', '/labsuites/3/tests?offset=0&count=10')

    def test_add_tests_list(self):
        self.client.labsuites.add_tests(3, [1, 2, 3])
        self.assertCall('POST', '/labsuites/3/tests',
                        json_body={'test_ids': '1,2,3'})

    def test_add_tests_string(self):
        self.client.labsuites.add_tests(3, '4,5')
        self.assertCall('POST', '/labsuites/3/tests',
                        json_body={'test_ids': '4,5'})

    def test_remove_test(self):
        self.client.labsuites.remove_test(3, 2)
        self.assertCall('DELETE', '/labsuites/3/tests/2')

    def test_get_browsers(self):
        self.client.labsuites.get_browsers(3)
        self.assertCall('GET', '/labsuites/3/browsers')

    def test_set_browsers(self):
        self.client.labsuites.set_browsers(3, [10, 11])
        self.assertCall('POST', '/labsuites/3/browsers',
                        json_body={'browser_ids': '10,11'})

    def test_set_browsers_string(self):
        self.client.labsuites.set_browsers(3, '10,11')
        self.assertCall('POST', '/labsuites/3/browsers',
                        json_body={'browser_ids': '10,11'})


class TestLab(ClientTestCase):
    def test_get_tests(self):
        self.client.lab.get_tests()
        self.assertCall('GET', '/lab?offset=0&count=10')

    def test_get_test(self):
        self.client.lab.get_test(8)
        self.assertCall('GET', '/lab/8')

    def test_create_test(self):
        self.client.lab.create_test(name='t', url='https://x.com',
                                    ai_prompt='check login')
        self.assertCall('POST', '/lab', json_body={
            'test': {'name': 't', 'url': 'https://x.com',
                     'ai_prompt': 'check login'}})

    def test_create_test_from_file(self):
        # .side import: multipart POST with files= and form-encoded test[] fields
        fd, path = tempfile.mkstemp(suffix='.side')
        os.write(fd, b'{}')
        os.close(fd)
        try:
            self.queue(200, {'success': True, 'lab_test_id': 5})
            out = self.client.lab.create_test(file=path, name='imported')
        finally:
            os.remove(path)
        call = self.last()
        self.assertEqual(call['method'], 'POST')
        self.assertEqual(call['url'], self.BASE + '/lab')
        self.assertIn('files', call['kwargs'])
        self.assertEqual(call['kwargs'].get('data'), {'test[name]': 'imported'})
        self.assertEqual(out, {'success': True, 'lab_test_id': 5})

    def test_update_test(self):
        self.client.lab.update_test(8, name='n', url='https://x',
                                    cron='0 9 * * *', enabled=True)
        self.assertCall('PUT', '/lab/8', json_body={'test': {
            'name': 'n', 'url': 'https://x', 'cron': '0 9 * * *',
            'enabled': True}})

    def test_update_test_partial(self):
        self.client.lab.update_test(8, enabled=False)
        self.assertCall('PUT', '/lab/8', json_body={'test': {'enabled': False}})

    def test_delete_test(self):
        self.client.lab.delete_test(8)
        self.assertCall('DELETE', '/lab/8')

    def test_trigger(self):
        self.client.lab.trigger(8, url='https://staging')
        self.assertCall('POST', '/lab/8/trigger',
                        json_body={'url': 'https://staging'})

    def test_trigger_no_url(self):
        self.client.lab.trigger(8)
        self.assertCall('POST', '/lab/8/trigger', json_body={})

    def test_trigger_all(self):
        self.client.lab.trigger_all()
        self.assertCall('POST', '/lab/trigger_all', json_body={})

    def test_get_steps(self):
        self.client.lab.get_steps(8, 0, 10)
        self.assertCall('GET', '/lab/8/steps?offset=0&count=10')

    def test_set_steps(self):
        steps = [{'order': 0, 'cmd': 'open', 'locator': '/', 'value': ''}]
        self.client.lab.set_steps(8, steps)
        self.assertCall('POST', '/lab/8/steps', json_body={'steps': steps})

    def test_schedule(self):
        self.client.lab.schedule(8, 'weekly', day='monday', hour='09:00')
        self.assertCall('POST', '/lab/8/schedule', json_body={
            'type': 'weekly', 'day': 'monday', 'hour': '09:00'})

    def test_schedule_custom_cron(self):
        self.client.lab.schedule(8, 'custom', cron_format='0 9 * * 1')
        self.assertCall('POST', '/lab/8/schedule', json_body={
            'type': 'custom', 'cronFormat': '0 9 * * 1'})

    def test_schedule_daily(self):
        self.client.lab.schedule(8, 'daily', hour='09:00')
        self.assertCall('POST', '/lab/8/schedule',
                        json_body={'type': 'daily', 'hour': '09:00'})

    def test_schedule_once(self):
        self.client.lab.schedule(8, 'once', day='2026-06-10', hour='09:00')
        self.assertCall('POST', '/lab/8/schedule', json_body={
            'type': 'once', 'day': '2026-06-10', 'hour': '09:00'})

    def test_add_alert(self):
        self.client.lab.add_alert(8, 'EMAIL', 'IMMEDIATELY', 'me@x.com')
        self.assertCall('POST', '/lab/8/alert', json_body={
            'kind': 'EMAIL', 'level': 'IMMEDIATELY', 'content': 'me@x.com'})

    def test_update_alert(self):
        self.client.lab.update_alert(8, kind='SMS', level='DAILY', content='+1555')
        self.assertCall('PUT', '/lab/8/alert', json_body={
            'kind': 'SMS', 'level': 'DAILY', 'content': '+1555'})

    def test_update_alert_partial(self):
        self.client.lab.update_alert(8, content='new@x.com')
        self.assertCall('PUT', '/lab/8/alert', json_body={'content': 'new@x.com'})

    def test_add_report(self):
        self.client.lab.add_report(8, 'me@x.com', cron='0 8 * * *')
        self.assertCall('POST', '/lab/8/report', json_body={
            'email': 'me@x.com', 'cron': '0 8 * * *'})

    def test_update_report(self):
        self.client.lab.update_report(8, email='new@x.com', cron='0 8 * * *')
        self.assertCall('PUT', '/lab/8/report', json_body={
            'email': 'new@x.com', 'cron': '0 8 * * *'})

    def test_stop(self):
        self.client.lab.stop(8, browser_id=10)
        self.assertCall('PUT', '/lab/8/stop', json_body={'browser_id': 10})

    def test_stop_all_browsers(self):
        self.client.lab.stop(8)
        self.assertCall('PUT', '/lab/8/stop', json_body={})

    def test_get_browsers(self):
        self.client.lab.get_browsers(8)
        self.assertCall('GET', '/lab/8/browsers')

    def test_set_browsers(self):
        self.client.lab.set_browsers(8, [10, 11])
        self.assertCall('POST', '/lab/8/browsers',
                        json_body={'browser_ids': '10,11'})

    def test_set_browsers_string(self):
        self.client.lab.set_browsers(8, '10,11')
        self.assertCall('POST', '/lab/8/browsers',
                        json_body={'browser_ids': '10,11'})


if __name__ == '__main__':
    unittest.main()
