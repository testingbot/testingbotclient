#!/usr/bin/env python

import base64
import sys
import json
import os
import requests
from requests.auth import HTTPBasicAuth
import hashlib
import time

try:
    from urllib.parse import urlencode
except ImportError:  # Python 2 fallback
    from urllib import urlencode

try:
    from importlib.metadata import version as _pkg_version, PackageNotFoundError
except ImportError:  # Python < 3.8
    _pkg_version = None
    PackageNotFoundError = Exception


def _user_agent():
    """User-Agent identifying this client and its installed version."""
    version = 'unknown'
    if _pkg_version is not None:
        try:
            version = _pkg_version('testingbotclient')
        except PackageNotFoundError:
            pass
    return 'testingbotclient/%s' % version


def _csv(values):
    """Join a list/tuple into a comma-separated string; pass strings through."""
    if isinstance(values, (list, tuple)):
        return ','.join(str(v) for v in values)
    return values


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
    def __init__(self, testingbotKey=None, testingbotSecret=None, timeout=60):
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

    def post(self, url, data=None, json_body=None, files=None):
        response = self.session.post(self.api_url + url, data=data, json=json_body, files=files, timeout=self.timeout)
        if response.status_code not in [200, 201]:
            raise TestingBotException('{}: {}.\nTestingBot API Error'.format(
                response.status_code, response.text), response=response)
        return response.json()

    def delete(self, url):
        response = self.session.delete(self.api_url + url, timeout=self.timeout)
        if response.status_code not in [200, 201]:
            raise TestingBotException('{}: {}.\nTestingBot API Error'.format(
                response.status_code, response.text), response=response)
        return response.json()

    def put(self, url, data=None, json_body=None):
        response = self.session.put(self.api_url + url, data=data, json=json_body, timeout=self.timeout)
        if response.status_code not in [200, 201]:
            raise TestingBotException('{}: {}.\nTestingBot API Error'.format(
                response.status_code, response.text), response=response)
        return response.json()

    def get(self, url):
        response = self.session.get(self.api_url + url, timeout=self.timeout)
        if response.status_code not in [200, 201]:
            raise TestingBotException('{}: {}.\nTestingBot API Error'.format(
                response.status_code, response.text), response=response)
        return response.json()

    def get_share_link(self, identifier):
        return hashlib.md5(("%s:%s:%s" % (self.testingbotKey, self.testingbotSecret, identifier)).encode('utf-8')).hexdigest()


class Tests(object):
    def __init__(self, client):
        self.client = client

    def get_test_ids(self):
        """List all tests sessionId's belonging to the user."""
        url = '/tests'
        tests = self.client.get(url)
        test_ids = [attr['session_id'] for attr in tests['data']]
        return test_ids

    def get_tests(self, offset=0, limit=10, since=None, browser_id=None,
                  group=None, build=None, skip_fields=None):
        """List tests, optionally filtered.

        since: UNIX timestamp -> only tests updated at/after it (poll-friendly).
        browser_id / group / build: narrow to a browser, tag, or build.
        skip_fields: comma list (or list) of fields to omit (e.g. 'logs,thumbs').
        """
        params = {'offset': offset, 'count': limit}
        if since is not None:
            params['since'] = since
        if browser_id is not None:
            params['browser_id'] = browser_id
        if group is not None:
            params['group'] = group
        if build is not None:
            params['build'] = build
        if skip_fields is not None:
            params['skip_fields'] = _csv(skip_fields)
        tests = self.client.get('/tests?' + urlencode(params))
        return tests["data"]

    def get_test(self, sessionId, skip_fields=None):
        """Get meta-data for a specific test.

        skip_fields: comma list (or list) of fields to omit from the response
        (e.g. 'steps,thumbs,logs').
        """
        url = '/tests/%s' % sessionId
        if skip_fields is not None:
            url += '?skip_fields=%s' % _csv(skip_fields)
        return self.client.get(url)

    def create_test(self, name, success=None, status_message=None, extra=None, build=None):
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

    def update_test(self, sessionId, name=None, passed=None, status_message=None, build=None):
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

        url = '/tests/%s' % sessionId
        response = self.client.put(url, params)
        return response['success']

    def delete_test(self, sessionId):
        """Deletes a test."""
        url = '/tests/%s' % sessionId
        response = self.client.delete(url)
        return response['success']

    def stop_test(self, sessionId):
        """Stops a test."""
        url = '/tests/%s/stop' % sessionId
        response = self.client.put(url, {})
        return response['success']

class Storage(object):
    def __init__(self, client):
        self.client = client

    def upload_local_file(self, filepath):
        """Uploads a local file to TestingBot Storage."""
        with open(filepath, 'rb') as f:
            response = self.client.session.post(
                self.client.api_url + "/storage",
                files={'file': f},
                timeout=self.client.timeout
            )
        if response.status_code not in [200, 201]:
            raise TestingBotException('{}: {}.\nTestingBot API Error'.format(
                response.status_code, response.text), response=response)
        return response.json()

    def upload_remote_file(self, remoteUrl):
        return self.client.post("/storage", { 'url': remoteUrl })

    def replace_local_file(self, app_url, filepath):
        """Replace the binary stored under an existing app_url with a local file.

        The app_url (tb://<appkey>) stays the same, so deployed CI configs keep
        working ("always use the latest build").
        """
        appkey = app_url.replace("tb://", "")
        with open(filepath, 'rb') as f:
            return self.client.post('/storage/%s' % appkey, files={'file': f})

    def replace_remote_file(self, app_url, remoteUrl):
        """Replace the binary stored under an existing app_url from a remote URL."""
        appkey = app_url.replace("tb://", "")
        return self.client.post('/storage/%s' % appkey, {'url': remoteUrl})

    def get_stored_file(self, app_url):
        """Retrieves meta-data for a file previously uploaded to TestingBot Storage."""
        return self.client.get("/storage/" + app_url.replace("tb://", ""))

    def remove_file(self, app_url):
        """Removes a file previously uploaded to TestingBot Storage."""
        return self.client.delete("/storage/" + app_url.replace("tb://", ""))

    def get_stored_files(self, offset = 0, limit = 10):
        """Retrieves all files previously uploaded to TestingBot Storage."""
        return self.client.get("/storage/?count=" + str(limit) + "&offset=" + str(offset))

class Information(object):
    def __init__(self, client):
        self.client = client

    def get_browsers(self, type=None):
        """Get details of all browsers currently supported on TestingBot.

        type: 'webdriver' (default) or 'rc' (legacy Selenium RC).
        """
        url = '/browsers'
        if type is not None:
            url += '?type=%s' % type
        browsers = self.client.get(url)
        return browsers

    def get_devices(self, platform=None):
        """Get details of all devices currently on TestingBot.

        platform: filter to one OS family (android | ios | real_android | real_ios).
        """
        url = '/devices'
        if platform is not None:
            url += '?platform=%s' % platform
        devices = self.client.get(url)
        return devices

    def get_available_devices(self):
        """Get details of all devices currently available on TestingBot"""
        url = '/devices/available'
        devices = self.client.get(url)
        return devices

    def get_device(self, deviceId):
        """Get details of a specific device on TestingBot"""
        url = '/devices/%s' % deviceId
        device = self.client.get(url)
        return device

class Tunnel(object):
    def __init__(self, client):
        self.client = client

    def get_tunnels(self):
        """Get TestingBot Tunnels currently running"""
        return self.client.get('/tunnel/list')

    def delete_tunnel(self, tunnelId):
        """Delete a specific TestingBot Tunnel"""
        return self.client.delete('/tunnel/%s' % tunnelId)

class Build(object):
    def __init__(self, client):
        self.client = client

    def get_builds(self, offset = 0, limit = 10):
        """Get all builds"""
        return self.client.get('/builds?offset=' + str(offset) + '&count=' + str(limit))

    def get_tests_for_build(self, buildId):
        """Get tests for a specific build"""
        return self.client.get('/builds/%s' % buildId)

    def delete_build(self, buildId):
        """Delete a specific build"""
        return self.client.delete('/builds/%s' % buildId)


class User(object):
    def __init__(self, client):
        self.client = client

    def get_user_information(self):
        """Access current user information"""
        url = '/user'
        info = self.client.get(url)
        return info

    def update_user_information(self, newUser):
        """Update current user information"""
        url = '/user'
        info = self.client.put(url, newUser)
        return info


class Jobs(object):
    def __init__(self, client):
        self.client = client

    def get_job(self, jobId):
        """Get the status of an asynchronous job (e.g. a Codeless trigger).

        Once the job's status is 'FINISHED' the response also carries the
        run results.
        """
        return self.client.get('/jobs/%s' % jobId)

    def wait_for_job(self, jobId, timeout=600, interval=5):
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
    def __init__(self, client):
        self.client = client

    def get_screenshots(self, offset=0, limit=10):
        """List the screenshot batches previously taken."""
        return self.client.get('/screenshots?offset=%s&count=%s' % (offset, limit))

    def get_screenshot(self, screenshotId, exclude_ids=None):
        """Get the per-browser results for a single screenshot batch."""
        url = '/screenshots/%s' % screenshotId
        if exclude_ids is not None:
            url += '?excludeIds=%s' % _csv(exclude_ids)
        return self.client.get(url)

    def take_screenshots(self, url, resolution, browsers, wait_time=0, full_page=None, callback_url=None):
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
    def __init__(self, client):
        self.client = client

    def get_concurrency(self):
        """Get allowed vs current concurrent session counts for the team."""
        return self.client.get('/team-management')

    def get_users(self, offset=0, limit=10):
        """List the sub-accounts in the team (admin only)."""
        return self.client.get('/team-management/users?offset=%s&count=%s' % (offset, limit))

    def get_user(self, userId):
        """Get a single team user."""
        return self.client.get('/team-management/users/%s' % userId)

    def create_user(self, email, password, first_name=None, last_name=None, concurrency=None, concurrency_physical=None):
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

    def update_user(self, userId, first_name=None, last_name=None, email=None, password=None,
                    credits=None, device_credits=None, concurrency=None, concurrency_physical=None):
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
        return self.client.put('/team-management/users/%s' % userId, json_body=body)

    def get_client_key(self, userId):
        """Get the API client key for a team user (admin only)."""
        return self.client.get('/team-management/users/%s/client-key' % userId)

    def reset_keys(self, userId):
        """Rotate the API key and secret for a team user."""
        return self.client.post('/team-management/users/%s/reset-keys' % userId, json_body={})


class LabSuites(object):
    def __init__(self, client):
        self.client = client

    def get_suites(self, offset=0, limit=10):
        """List your Codeless suites."""
        return self.client.get('/labsuites?offset=%s&count=%s' % (offset, limit))

    def get_suite(self, suiteId):
        """Get a single Codeless suite."""
        return self.client.get('/labsuites/%s' % suiteId)

    def create_suite(self, name, cron=None, screenshot=None, video=None, idletimeout=None, screenresolution=None):
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

    def delete_suite(self, suiteId):
        """Delete a Codeless suite (its tests are preserved)."""
        return self.client.delete('/labsuites/%s' % suiteId)

    def trigger(self, suiteId):
        """Queue every test in the suite for an immediate run; returns a job_id."""
        return self.client.post('/labsuites/%s/trigger' % suiteId, json_body={})

    def get_tests(self, suiteId, offset=0, limit=10):
        """List the Codeless tests attached to a suite."""
        return self.client.get('/labsuites/%s/tests?offset=%s&count=%s' % (suiteId, offset, limit))

    def add_tests(self, suiteId, test_ids):
        """Attach Codeless tests to a suite (list or comma-separated string)."""
        return self.client.post('/labsuites/%s/tests' % suiteId, json_body={'test_ids': _csv(test_ids)})

    def remove_test(self, suiteId, testId):
        """Detach a Codeless test from a suite."""
        return self.client.delete('/labsuites/%s/tests/%s' % (suiteId, testId))

    def get_browsers(self, suiteId):
        """Get the browsers a suite runs on."""
        return self.client.get('/labsuites/%s/browsers' % suiteId)

    def set_browsers(self, suiteId, browser_ids):
        """Replace the browser set for a suite (list or comma-separated string)."""
        return self.client.post('/labsuites/%s/browsers' % suiteId, json_body={'browser_ids': _csv(browser_ids)})


class Lab(object):
    def __init__(self, client):
        self.client = client

    def get_tests(self, offset=0, limit=10):
        """List your Codeless tests."""
        return self.client.get('/lab?offset=%s&count=%s' % (offset, limit))

    def get_test(self, testId):
        """Get a single Codeless test."""
        return self.client.get('/lab/%s' % testId)

    def create_test(self, name=None, url=None, cron=None, screenshot=None, video=None,
                    idletimeout=None, screenresolution=None, ai_prompt=None, file=None):
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

    def update_test(self, testId, name=None, url=None, cron=None, enabled=None):
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
        return self.client.put('/lab/%s' % testId, json_body={'test': test})

    def delete_test(self, testId):
        """Delete a Codeless test."""
        return self.client.delete('/lab/%s' % testId)

    def trigger(self, testId, url=None):
        """Run a Codeless test immediately; returns a job_id."""
        body = {}
        if url is not None:
            body['url'] = url
        return self.client.post('/lab/%s/trigger' % testId, json_body=body)

    def trigger_all(self, url=None):
        """Run every Codeless test on the account; returns a job_id."""
        body = {}
        if url is not None:
            body['url'] = url
        return self.client.post('/lab/trigger_all', json_body=body)

    def get_steps(self, testId, offset=0, limit=10):
        """List the recorded steps of a Codeless test."""
        return self.client.get('/lab/%s/steps?offset=%s&count=%s' % (testId, offset, limit))

    def set_steps(self, testId, steps):
        """Replace the steps of a Codeless test.

        steps is a list of dicts: {'order':, 'cmd':, 'locator':, 'value':}.
        """
        return self.client.post('/lab/%s/steps' % testId, json_body={'steps': steps})

    def schedule(self, testId, type, day=None, hour=None, cron_format=None):
        """Set a Codeless test's schedule (type: once|daily|weekly|custom)."""
        body = {'type': type}
        if day is not None:
            body['day'] = day
        if hour is not None:
            body['hour'] = hour
        if cron_format is not None:
            body['cronFormat'] = cron_format
        return self.client.post('/lab/%s/schedule' % testId, json_body=body)

    def add_alert(self, testId, kind, level, content):
        """Add a failure alert (kind: EMAIL|API|SMS, level: IMMEDIATELY|DAILY)."""
        return self.client.post('/lab/%s/alert' % testId,
                                json_body={'kind': kind, 'level': level, 'content': content})

    def update_alert(self, testId, kind=None, level=None, content=None):
        """Update the failure alert on a Codeless test."""
        body = {}
        if kind is not None:
            body['kind'] = kind
        if level is not None:
            body['level'] = level
        if content is not None:
            body['content'] = content
        return self.client.put('/lab/%s/alert' % testId, json_body=body)

    def add_report(self, testId, email, cron=None):
        """Add a recurring email report for a Codeless test."""
        body = {'email': email}
        if cron is not None:
            body['cron'] = cron
        return self.client.post('/lab/%s/report' % testId, json_body=body)

    def update_report(self, testId, email=None, cron=None):
        """Update the email report config for a Codeless test."""
        body = {}
        if email is not None:
            body['email'] = email
        if cron is not None:
            body['cron'] = cron
        return self.client.put('/lab/%s/report' % testId, json_body=body)

    def stop(self, testId, browser_id=None):
        """Force-stop a running Codeless test (optionally a single browser)."""
        body = {}
        if browser_id is not None:
            body['browser_id'] = browser_id
        return self.client.put('/lab/%s/stop' % testId, json_body=body)

    def get_browsers(self, testId):
        """Get the browsers a Codeless test runs on."""
        return self.client.get('/lab/%s/browsers' % testId)

    def set_browsers(self, testId, browser_ids):
        """Replace the browser set for a Codeless test (list or comma string)."""
        return self.client.post('/lab/%s/browsers' % testId, json_body={'browser_ids': _csv(browser_ids)})


class Configuration(object):
    def __init__(self, client):
        self.client = client

    def get_ip_ranges(self):
        """Get TestingBot's public IPv4 addresses (for firewall whitelisting)."""
        return self.client.get('/configuration/ip-ranges')