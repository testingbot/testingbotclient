#!/usr/bin/env python

from __future__ import annotations

import hashlib
import os
import time
from typing import Any, Callable, Iterator, List, Optional, Union

import requests
from requests.adapters import HTTPAdapter

try:
    from urllib.parse import urlencode, quote
except ImportError:  # Python 2 fallback
    from urllib import urlencode, quote

try:
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover
    Retry = None

try:
    from importlib.metadata import version as _pkg_version, PackageNotFoundError
except ImportError:  # Python < 3.8
    _pkg_version = None
    PackageNotFoundError = Exception

__all__ = ['TestingBotClient', 'TestingBotException', 'paginate']


def _user_agent() -> str:
    """User-Agent identifying this client and its installed version."""
    version = 'unknown'
    if _pkg_version is not None:
        try:
            version = _pkg_version('testingbotclient')
        except PackageNotFoundError:
            pass
    return 'testingbotclient/%s' % version


def _csv(values: Union[list, tuple, str]) -> str:
    """Join a list/tuple into a comma-separated string; pass strings through."""
    if isinstance(values, (list, tuple)):
        return ','.join(str(v) for v in values)
    return values


def _seg(value: Any) -> str:
    """URL-encode a single path segment (so ids/keys can't break the path)."""
    return quote(str(value), safe='')


def _query(params: dict) -> str:
    """Build a '?a=b&c=d' query string, dropping keys whose value is None."""
    clean = {k: v for k, v in params.items() if v is not None}
    return ('?' + urlencode(clean)) if clean else ''


def paginate(fetch: Callable[[int, int], Any], limit: int = 100) -> Iterator[Any]:
    """Yield every item across a paginated list endpoint.

    ``fetch(offset, limit)`` should call a list method, e.g.::

        for test in paginate(tb.build.get_builds):
            ...
        for test in paginate(lambda o, n: tb.tests.get_tests(o, n)):
            ...

    Works whether the method returns the raw list or the full ``{data, meta}``
    dict, and stops once a short (final) page is returned.
    """
    offset = 0
    while True:
        page = fetch(offset, limit)
        items = page['data'] if isinstance(page, dict) and 'data' in page else page
        if not items:
            return
        for item in items:
            yield item
        if len(items) < limit:
            return
        offset += len(items)


class TestingBotException(Exception):
    def __init__(self, *args, **kwargs):
        super(TestingBotException, self).__init__(*args)
        self.response = kwargs.get('response')
        # Strip the Basic-auth header from the retained response: anything that
        # logs or prints the exception's .response (e.g. e.response.request.headers)
        # would otherwise expose the API key and secret.
        if self.response is not None:
            request = getattr(self.response, 'request', None)
            headers = getattr(request, 'headers', None)
            if headers is not None:
                headers.pop('Authorization', None)


class TestingBotClient(object):
    def __init__(self, testingbotKey: Optional[str] = None, testingbotSecret: Optional[str] = None,
                 timeout: float = 60, max_retries: int = 3):
        self.testingbotKey = testingbotKey
        self.testingbotSecret = testingbotSecret
        if self.testingbotKey is None:
            self.testingbotKey = os.environ.get('TESTINGBOT_KEY', None)
            self.testingbotSecret = os.environ.get('TESTINGBOT_SECRET', None)
        if self.testingbotKey is None:
            self.testingbotKey = os.environ.get('TB_KEY', None)
            self.testingbotSecret = os.environ.get('TB_SECRET', None)

        if self.testingbotKey is None:
            path = os.path.join(os.path.expanduser('~'), '.testingbot')
            if os.path.exists(path):
                f = open(path, 'r')
                data = f.read().strip()
                self.testingbotKey, self.testingbotSecret = data.split(':', 1)
                f.close()

        self.information = Information(self)
        self.tests = Tests(self)
        self.user = User(self)
        self.storage = Storage(self)
        self.tunnel = Tunnel(self)
        self.build = Build(self)
        self.configuration = Configuration(self)
        self.jobs = Jobs(self)
        self.screenshots = Screenshots(self)
        self.team = TeamManagement(self)
        self.labsuites = LabSuites(self)
        self.lab = Lab(self)
        self.api_url = 'https://api.testingbot.com/v1/'
        self.timeout = timeout

        self.session = requests.Session()
        self.session.auth = (self.testingbotKey, self.testingbotSecret)
        self.session.headers.update({'User-Agent': _user_agent()})
        # Retry transient failures. urllib3's default allowed-methods set excludes
        # POST, so non-idempotent calls (create/trigger/upload) are never retried.
        if Retry is not None:
            retry = Retry(
                total=max_retries,
                backoff_factor=0.5,
                status_forcelist=(429, 500, 502, 503, 504),
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry)
            self.session.mount('https://', adapter)
            self.session.mount('http://', adapter)

    def _handle(self, response) -> Any:
        if response.status_code not in (200, 201):
            raise TestingBotException('{}: {}.\nTestingBot API Error'.format(
                response.status_code, response.text), response=response)
        return response.json()

    def post(self, url: str, data: Optional[dict] = None, json_body: Optional[dict] = None,
             files: Optional[dict] = None) -> Any:
        return self._handle(self.session.post(
            self.api_url + url, data=data, json=json_body, files=files, timeout=self.timeout))

    def delete(self, url: str) -> Any:
        return self._handle(self.session.delete(self.api_url + url, timeout=self.timeout))

    def put(self, url: str, data: Optional[dict] = None, json_body: Optional[dict] = None) -> Any:
        return self._handle(self.session.put(
            self.api_url + url, data=data, json=json_body, timeout=self.timeout))

    def get(self, url: str) -> Any:
        return self._handle(self.session.get(self.api_url + url, timeout=self.timeout))

    def get_share_link(self, identifier: Union[int, str]) -> str:
        return hashlib.md5(("%s:%s:%s" % (self.testingbotKey, self.testingbotSecret, identifier)).encode('utf-8')).hexdigest()

    def close(self) -> None:
        """Close the underlying HTTP session and its pooled connections."""
        self.session.close()

    def __enter__(self) -> 'TestingBotClient':
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class Tests(object):
    def __init__(self, client: TestingBotClient):
        self.client = client

    def get_test_ids(self) -> List[str]:
        """List all tests sessionId's belonging to the user."""
        tests = self.client.get('/tests')
        return [attr['session_id'] for attr in tests['data']]

    def get_tests(self, offset: int = 0, limit: int = 10, since: Optional[int] = None,
                  browser_id: Optional[Union[int, str]] = None, group: Optional[str] = None,
                  build: Optional[str] = None, skip_fields: Optional[Union[list, str]] = None) -> list:
        """List tests, optionally filtered.

        since: UNIX timestamp -> only tests updated at/after it (poll-friendly).
        browser_id / group / build: narrow to a browser, tag, or build.
        skip_fields: comma list (or list) of fields to omit (e.g. 'logs,thumbs').
        """
        params = {
            'offset': offset,
            'count': limit,
            'since': since,
            'browser_id': browser_id,
            'group': group,
            'build': build,
            'skip_fields': _csv(skip_fields) if skip_fields is not None else None,
        }
        tests = self.client.get('/tests' + _query(params))
        return tests["data"]

    def get_test(self, sessionId: Union[int, str], skip_fields: Optional[Union[list, str]] = None) -> Any:
        """Get meta-data for a specific test.

        skip_fields: comma list (or list) of fields to omit from the response
        (e.g. 'steps,thumbs,logs').
        """
        url = '/tests/%s' % _seg(sessionId)
        if skip_fields is not None:
            url += _query({'skip_fields': _csv(skip_fields)})
        return self.client.get(url)

    def create_test(self, name: str, success: Optional[bool] = None, status_message: Optional[str] = None,
                    extra: Optional[str] = None, build: Optional[str] = None) -> Any:
        """Create a test record (for logging manual or external test results)."""
        test = {'name': name}
        if success is not None:
            test['success'] = success
        if status_message is not None:
            test['status_message'] = status_message
        if extra is not None:
            test['extra'] = extra
        if build is not None:
            test['build'] = build
        return self.client.post('/tests', json_body={'test': test})

    def update_test(self, sessionId: Union[int, str], name: Optional[str] = None,
                    passed: Optional[bool] = None, status_message: Optional[str] = None,
                    build: Optional[str] = None) -> Any:
        """Update attributes for the specified test."""
        params = {}
        if status_message is not None:
            params['test[status_message]'] = status_message
        if name is not None:
            params['test[name]'] = name
        if passed is not None:
            params['test[success]'] = ('1' if passed else '0')
        if build is not None:
            params['build'] = build

        response = self.client.put('/tests/%s' % _seg(sessionId), params)
        return response['success']

    def delete_test(self, sessionId: Union[int, str]) -> Any:
        """Deletes a test."""
        response = self.client.delete('/tests/%s' % _seg(sessionId))
        return response['success']

    def stop_test(self, sessionId: Union[int, str]) -> Any:
        """Stops a test."""
        response = self.client.put('/tests/%s/stop' % _seg(sessionId), {})
        return response['success']


class Storage(object):
    def __init__(self, client: TestingBotClient):
        self.client = client

    def upload_local_file(self, filepath: str) -> Any:
        """Uploads a local file to TestingBot Storage."""
        with open(filepath, 'rb') as f:
            return self.client.post('/storage', files={'file': f})

    def upload_remote_file(self, remoteUrl: str) -> Any:
        return self.client.post('/storage', {'url': remoteUrl})

    def replace_local_file(self, app_url: str, filepath: str) -> Any:
        """Replace the binary stored under an existing app_url with a local file.

        The app_url (tb://<appkey>) stays the same, so deployed CI configs keep
        working ("always use the latest build").
        """
        appkey = app_url.replace("tb://", "")
        with open(filepath, 'rb') as f:
            return self.client.post('/storage/%s' % _seg(appkey), files={'file': f})

    def replace_remote_file(self, app_url: str, remoteUrl: str) -> Any:
        """Replace the binary stored under an existing app_url from a remote URL."""
        appkey = app_url.replace("tb://", "")
        return self.client.post('/storage/%s' % _seg(appkey), {'url': remoteUrl})

    def get_stored_file(self, app_url: str) -> Any:
        """Retrieves meta-data for a file previously uploaded to TestingBot Storage."""
        return self.client.get('/storage/%s' % _seg(app_url.replace("tb://", "")))

    def remove_file(self, app_url: str) -> Any:
        """Removes a file previously uploaded to TestingBot Storage."""
        return self.client.delete('/storage/%s' % _seg(app_url.replace("tb://", "")))

    def get_stored_files(self, offset: int = 0, limit: int = 10) -> Any:
        """Retrieves all files previously uploaded to TestingBot Storage."""
        return self.client.get('/storage/' + _query({'offset': offset, 'count': limit}))


class Information(object):
    def __init__(self, client: TestingBotClient):
        self.client = client

    def get_browsers(self, type: Optional[str] = None) -> Any:
        """Get details of all browsers currently supported on TestingBot.

        type: 'webdriver' (default) or 'rc' (legacy Selenium RC).
        """
        return self.client.get('/browsers' + _query({'type': type}))

    def get_devices(self, platform: Optional[str] = None) -> Any:
        """Get details of all devices currently on TestingBot.

        platform: filter to one OS family (android | ios | real_android | real_ios).
        """
        return self.client.get('/devices' + _query({'platform': platform}))

    def get_available_devices(self) -> Any:
        """Get details of all devices currently available on TestingBot"""
        return self.client.get('/devices/available')

    def get_device(self, deviceId: Union[int, str]) -> Any:
        """Get details of a specific device on TestingBot"""
        return self.client.get('/devices/%s' % _seg(deviceId))


class Tunnel(object):
    def __init__(self, client: TestingBotClient):
        self.client = client

    def get_tunnels(self) -> Any:
        """Get TestingBot Tunnels currently running"""
        return self.client.get('/tunnel/list')

    def delete_tunnel(self, tunnelId: Union[int, str]) -> Any:
        """Delete a specific TestingBot Tunnel"""
        return self.client.delete('/tunnel/%s' % _seg(tunnelId))


class Build(object):
    def __init__(self, client: TestingBotClient):
        self.client = client

    def get_builds(self, offset: int = 0, limit: int = 10) -> Any:
        """Get all builds"""
        return self.client.get('/builds' + _query({'offset': offset, 'count': limit}))

    def get_tests_for_build(self, buildId: Union[int, str]) -> Any:
        """Get tests for a specific build"""
        return self.client.get('/builds/%s' % _seg(buildId))

    def delete_build(self, buildId: Union[int, str]) -> Any:
        """Delete a specific build"""
        return self.client.delete('/builds/%s' % _seg(buildId))


class User(object):
    def __init__(self, client: TestingBotClient):
        self.client = client

    def get_user_information(self) -> Any:
        """Access current user information"""
        return self.client.get('/user')

    def update_user_information(self, newUser: dict) -> Any:
        """Update current user information"""
        return self.client.put('/user', newUser)


class Jobs(object):
    def __init__(self, client: TestingBotClient):
        self.client = client

    def get_job(self, jobId: Union[int, str]) -> Any:
        """Get the status of an asynchronous job (e.g. a Codeless trigger).

        Once the job's status is 'FINISHED' the response also carries the
        run results.
        """
        return self.client.get('/jobs/%s' % _seg(jobId))

    def wait_for_job(self, jobId: Union[int, str], timeout: float = 600, interval: float = 5) -> Any:
        """Poll a job until its status is 'FINISHED' and return it.

        Raises TestingBotException if it does not finish within timeout seconds.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = self.get_job(jobId)
            if job.get('status') == 'FINISHED':
                return job
            time.sleep(interval)
        raise TestingBotException('Timed out waiting for job %s' % jobId)


class Screenshots(object):
    def __init__(self, client: TestingBotClient):
        self.client = client

    def get_screenshots(self, offset: int = 0, limit: int = 10) -> Any:
        """List the screenshot batches previously taken."""
        return self.client.get('/screenshots' + _query({'offset': offset, 'count': limit}))

    def get_screenshot(self, screenshotId: Union[int, str],
                       exclude_ids: Optional[Union[list, str]] = None) -> Any:
        """Get the per-browser results for a single screenshot batch."""
        url = '/screenshots/%s' % _seg(screenshotId)
        if exclude_ids is not None:
            url += _query({'excludeIds': _csv(exclude_ids)})
        return self.client.get(url)

    def take_screenshots(self, url: str, resolution: str, browsers: list, wait_time: int = 0,
                         full_page: Optional[bool] = None, callback_url: Optional[str] = None) -> Any:
        """Queue a cross-browser screenshot batch for a URL.

        browsers is a list of browser_id values (see information.get_browsers).
        Returns the new batch; poll it with get_screenshot(id).
        """
        body = {
            'url': url,
            'resolution': resolution,
            'browsers': browsers,
            'wait_time': wait_time
        }
        if full_page is not None:
            # The server reads params[:full_page] while declaring the param as
            # `fullpage`; send both so this works regardless of which it uses.
            body['full_page'] = full_page
            body['fullpage'] = full_page
        if callback_url is not None:
            body['callback_url'] = callback_url
        return self.client.post('/screenshots', json_body=body)


class TeamManagement(object):
    def __init__(self, client: TestingBotClient):
        self.client = client

    def get_concurrency(self) -> Any:
        """Get allowed vs current concurrent session counts for the team."""
        return self.client.get('/team-management')

    def get_users(self, offset: int = 0, limit: int = 10) -> Any:
        """List the sub-accounts in the team (admin only)."""
        return self.client.get('/team-management/users' + _query({'offset': offset, 'count': limit}))

    def get_user(self, userId: Union[int, str]) -> Any:
        """Get a single team user."""
        return self.client.get('/team-management/users/%s' % _seg(userId))

    def create_user(self, email: str, password: str, first_name: Optional[str] = None,
                    last_name: Optional[str] = None, concurrency: Optional[int] = None,
                    concurrency_physical: Optional[int] = None) -> Any:
        """Create a new sub-account in the team."""
        body = {'email': email, 'password': password}
        if first_name is not None:
            body['first_name'] = first_name
        if last_name is not None:
            body['last_name'] = last_name
        if concurrency is not None:
            body['concurrency'] = concurrency
        if concurrency_physical is not None:
            body['concurrencyPhysical'] = concurrency_physical
        return self.client.post('/team-management/users', json_body=body)

    def update_user(self, userId: Union[int, str], first_name: Optional[str] = None,
                    last_name: Optional[str] = None, email: Optional[str] = None,
                    password: Optional[str] = None, credits: Optional[int] = None,
                    device_credits: Optional[int] = None, concurrency: Optional[int] = None,
                    concurrency_physical: Optional[int] = None) -> Any:
        """Update a team user's profile and credit allocation."""
        body = {}
        if first_name is not None:
            body['first_name'] = first_name
        if last_name is not None:
            body['last_name'] = last_name
        if email is not None:
            body['email'] = email
        if password is not None:
            body['password'] = password
        if credits is not None:
            body['credits'] = credits
        if device_credits is not None:
            body['device_credits'] = device_credits
        if concurrency is not None:
            body['concurrency'] = concurrency
        if concurrency_physical is not None:
            body['concurrencyPhysical'] = concurrency_physical
        return self.client.put('/team-management/users/%s' % _seg(userId), json_body=body)

    def get_client_key(self, userId: Union[int, str]) -> Any:
        """Get the API client key for a team user (admin only)."""
        return self.client.get('/team-management/users/%s/client-key' % _seg(userId))

    def reset_keys(self, userId: Union[int, str]) -> Any:
        """Rotate the API key and secret for a team user."""
        return self.client.post('/team-management/users/%s/reset-keys' % _seg(userId), json_body={})


class LabSuites(object):
    def __init__(self, client: TestingBotClient):
        self.client = client

    def get_suites(self, offset: int = 0, limit: int = 10) -> Any:
        """List your Codeless suites."""
        return self.client.get('/labsuites' + _query({'offset': offset, 'count': limit}))

    def get_suite(self, suiteId: Union[int, str]) -> Any:
        """Get a single Codeless suite."""
        return self.client.get('/labsuites/%s' % _seg(suiteId))

    def create_suite(self, name: str, cron: Optional[str] = None, screenshot: Optional[bool] = None,
                     video: Optional[bool] = None, idletimeout: Optional[int] = None,
                     screenresolution: Optional[str] = None) -> Any:
        """Create a new Codeless suite."""
        suite = {'name': name}
        if cron is not None:
            suite['cron'] = cron
        if screenshot is not None:
            suite['screenshot'] = screenshot
        if video is not None:
            suite['video'] = video
        if idletimeout is not None:
            suite['idletimeout'] = idletimeout
        if screenresolution is not None:
            suite['screenresolution'] = screenresolution
        return self.client.post('/labsuites', json_body={'suite': suite})

    def delete_suite(self, suiteId: Union[int, str]) -> Any:
        """Delete a Codeless suite (its tests are preserved)."""
        return self.client.delete('/labsuites/%s' % _seg(suiteId))

    def trigger(self, suiteId: Union[int, str]) -> Any:
        """Queue every test in the suite for an immediate run; returns a job_id."""
        return self.client.post('/labsuites/%s/trigger' % _seg(suiteId), json_body={})

    def get_tests(self, suiteId: Union[int, str], offset: int = 0, limit: int = 10) -> Any:
        """List the Codeless tests attached to a suite."""
        return self.client.get('/labsuites/%s/tests' % _seg(suiteId)
                               + _query({'offset': offset, 'count': limit}))

    def add_tests(self, suiteId: Union[int, str], test_ids: Union[list, str]) -> Any:
        """Attach Codeless tests to a suite (list or comma-separated string)."""
        return self.client.post('/labsuites/%s/tests' % _seg(suiteId), json_body={'test_ids': _csv(test_ids)})

    def remove_test(self, suiteId: Union[int, str], testId: Union[int, str]) -> Any:
        """Detach a Codeless test from a suite."""
        return self.client.delete('/labsuites/%s/tests/%s' % (_seg(suiteId), _seg(testId)))

    def get_browsers(self, suiteId: Union[int, str]) -> Any:
        """Get the browsers a suite runs on."""
        return self.client.get('/labsuites/%s/browsers' % _seg(suiteId))

    def set_browsers(self, suiteId: Union[int, str], browser_ids: Union[list, str]) -> Any:
        """Replace the browser set for a suite (list or comma-separated string)."""
        return self.client.post('/labsuites/%s/browsers' % _seg(suiteId), json_body={'browser_ids': _csv(browser_ids)})


class Lab(object):
    def __init__(self, client: TestingBotClient):
        self.client = client

    def get_tests(self, offset: int = 0, limit: int = 10) -> Any:
        """List your Codeless tests."""
        return self.client.get('/lab' + _query({'offset': offset, 'count': limit}))

    def get_test(self, testId: Union[int, str]) -> Any:
        """Get a single Codeless test."""
        return self.client.get('/lab/%s' % _seg(testId))

    def create_test(self, name: Optional[str] = None, url: Optional[str] = None, cron: Optional[str] = None,
                    screenshot: Optional[bool] = None, video: Optional[bool] = None,
                    idletimeout: Optional[int] = None, screenresolution: Optional[str] = None,
                    ai_prompt: Optional[str] = None, file: Optional[str] = None) -> Any:
        """Create a new Codeless test.

        Provide a `url` (then set_steps afterwards), or import a Selenium IDE
        `.side` export by passing `file` (a path to the .side file).
        """
        if file is not None:
            form = {}
            if name is not None:
                form['test[name]'] = name
            if url is not None:
                form['test[url]'] = url
            if cron is not None:
                form['test[cron]'] = cron
            if screenresolution is not None:
                form['test[screenresolution]'] = screenresolution
            if idletimeout is not None:
                form['test[idletimeout]'] = idletimeout
            if screenshot is not None:
                form['test[screenshot]'] = '1' if screenshot else '0'
            if video is not None:
                form['test[video]'] = '1' if video else '0'
            with open(file, 'rb') as f:
                return self.client.post('/lab', data=form, files={'file': f})
        test = {}
        if name is not None:
            test['name'] = name
        if url is not None:
            test['url'] = url
        if cron is not None:
            test['cron'] = cron
        if screenshot is not None:
            test['screenshot'] = screenshot
        if video is not None:
            test['video'] = video
        if idletimeout is not None:
            test['idletimeout'] = idletimeout
        if screenresolution is not None:
            test['screenresolution'] = screenresolution
        if ai_prompt is not None:
            test['ai_prompt'] = ai_prompt
        return self.client.post('/lab', json_body={'test': test})

    def update_test(self, testId: Union[int, str], name: Optional[str] = None, url: Optional[str] = None,
                    cron: Optional[str] = None, enabled: Optional[bool] = None) -> Any:
        """Update a Codeless test's metadata."""
        test = {}
        if name is not None:
            test['name'] = name
        if url is not None:
            test['url'] = url
        if cron is not None:
            test['cron'] = cron
        if enabled is not None:
            test['enabled'] = enabled
        return self.client.put('/lab/%s' % _seg(testId), json_body={'test': test})

    def delete_test(self, testId: Union[int, str]) -> Any:
        """Delete a Codeless test."""
        return self.client.delete('/lab/%s' % _seg(testId))

    def trigger(self, testId: Union[int, str], url: Optional[str] = None) -> Any:
        """Run a Codeless test immediately; returns a job_id."""
        body = {}
        if url is not None:
            body['url'] = url
        return self.client.post('/lab/%s/trigger' % _seg(testId), json_body=body)

    def trigger_all(self, url: Optional[str] = None) -> Any:
        """Run every Codeless test on the account; returns a job_id."""
        body = {}
        if url is not None:
            body['url'] = url
        return self.client.post('/lab/trigger_all', json_body=body)

    def get_steps(self, testId: Union[int, str], offset: int = 0, limit: int = 10) -> Any:
        """List the recorded steps of a Codeless test."""
        return self.client.get('/lab/%s/steps' % _seg(testId)
                               + _query({'offset': offset, 'count': limit}))

    def set_steps(self, testId: Union[int, str], steps: list) -> Any:
        """Replace the steps of a Codeless test.

        steps is a list of dicts: {'order':, 'cmd':, 'locator':, 'value':}.
        """
        return self.client.post('/lab/%s/steps' % _seg(testId), json_body={'steps': steps})

    def schedule(self, testId: Union[int, str], type: str, day: Optional[str] = None,
                 hour: Optional[str] = None, cron_format: Optional[str] = None) -> Any:
        """Set a Codeless test's schedule (type: once|daily|weekly|custom)."""
        body = {'type': type}
        if day is not None:
            body['day'] = day
        if hour is not None:
            body['hour'] = hour
        if cron_format is not None:
            body['cronFormat'] = cron_format
        return self.client.post('/lab/%s/schedule' % _seg(testId), json_body=body)

    def add_alert(self, testId: Union[int, str], kind: str, level: str, content: str) -> Any:
        """Add a failure alert (kind: EMAIL|API|SMS, level: IMMEDIATELY|DAILY)."""
        return self.client.post('/lab/%s/alert' % _seg(testId),
                                json_body={'kind': kind, 'level': level, 'content': content})

    def update_alert(self, testId: Union[int, str], kind: Optional[str] = None,
                     level: Optional[str] = None, content: Optional[str] = None) -> Any:
        """Update the failure alert on a Codeless test."""
        body = {}
        if kind is not None:
            body['kind'] = kind
        if level is not None:
            body['level'] = level
        if content is not None:
            body['content'] = content
        return self.client.put('/lab/%s/alert' % _seg(testId), json_body=body)

    def add_report(self, testId: Union[int, str], email: str, cron: Optional[str] = None) -> Any:
        """Add a recurring email report for a Codeless test."""
        body = {'email': email}
        if cron is not None:
            body['cron'] = cron
        return self.client.post('/lab/%s/report' % _seg(testId), json_body=body)

    def update_report(self, testId: Union[int, str], email: Optional[str] = None,
                      cron: Optional[str] = None) -> Any:
        """Update the email report config for a Codeless test."""
        body = {}
        if email is not None:
            body['email'] = email
        if cron is not None:
            body['cron'] = cron
        return self.client.put('/lab/%s/report' % _seg(testId), json_body=body)

    def stop(self, testId: Union[int, str], browser_id: Optional[Union[int, str]] = None) -> Any:
        """Force-stop a running Codeless test (optionally a single browser)."""
        body = {}
        if browser_id is not None:
            body['browser_id'] = browser_id
        return self.client.put('/lab/%s/stop' % _seg(testId), json_body=body)

    def get_browsers(self, testId: Union[int, str]) -> Any:
        """Get the browsers a Codeless test runs on."""
        return self.client.get('/lab/%s/browsers' % _seg(testId))

    def set_browsers(self, testId: Union[int, str], browser_ids: Union[list, str]) -> Any:
        """Replace the browser set for a Codeless test (list or comma string)."""
        return self.client.post('/lab/%s/browsers' % _seg(testId), json_body={'browser_ids': _csv(browser_ids)})


class Configuration(object):
    def __init__(self, client: TestingBotClient):
        self.client = client

    def get_ip_ranges(self) -> Any:
        """Get TestingBot's public IPv4 addresses (for firewall whitelisting)."""
        return self.client.get('/configuration/ip-ranges')
