#!/usr/bin/env python

import base64
import sys
import json
import os
__version__ = '0.0.4'

is_py2 = sys.version_info[0] is 2

if is_py2:
    import httplib as http_client
else:
    import http.client as http_client


def json_loads(json_data):
    if not is_py2:
        json_data = json_data.decode(encoding='UTF-8')
    return json.loads(json_data)

class TestingBotException(Exception):
    def __init__(self, *args, **kwargs):
        super(TestingBotException, self).__init__(*args, **kwargs)

class TestingBotClient(object):
    def __init__(self, testingbotKey=None, testingbotSecret=None):
        self.testingbotKey = testingbotKey
        self.testingbotSecret = testingbotSecret
        if self.testingbotKey is None:
            self.testingbotKey = os.environ.get('TESTINGBOT_KEY', None)
            self.testingbotSecret = os.environ.get('TESTINGBOT_SECRET', None)

        if self.testingbotKey is None:
            path = os.path.join(os.path.expanduser('~'), '.testingbot')
            if os.path.exists(path):
                f = open(path, 'r')
                data = f.read()
                self.testingbotKey, self.testingbotSecret = data.split(':')
                f.close()

        self.headers = self.make_headers()
        self.information = Information(self)
        self.tests = Tests(self)
        self.user = User(self)

    def make_headers(self):
        base64string = self.get_encoded_auth_string()
        headers = {
            'Authorization': 'Basic %s' % base64string,
            'Content-Type' : 'application/x-www-form-urlencoded'
        }
        return headers

    def request(self, method, url, body=None):
        connection = http_client.HTTPSConnection('api.testingbot.com')
        # connection.set_debuglevel(1)
        connection.request(method, "/v1" + url, body, headers=self.headers)
        response = connection.getresponse()
        json_data = response.read()
        connection.close()
        if response.status != 200:
            raise TestingBotException('Failed to contact TestingBot API: %s | %s' %
                                 (response.status, "/v1" + url))
        return json_data

    def get_encoded_auth_string(self):
        auth_info = '%s:%s' % (self.testingbotKey, self.testingbotSecret)
        if is_py2:
            base64string = base64.b64encode(auth_info)[:-1]
        else:
            base64string = base64.b64encode(auth_info.encode(encoding='UTF-8')).decode(encoding='UTF-8')
        return base64string


class Tests(object):
    def __init__(self, client):
        self.client = client

    def get_test_ids(self):
        """List all tests sessionId's belonging to the user."""
        method = 'GET'
        url = '/tests'
        json_data = self.client.request(method, url)
        tests = json_loads(json_data)
        test_ids = [attr['session_id'] for attr in tests['data']]
        return test_ids

    def get_tests(self):
        """List all tests belonging to the user."""
        method = 'GET'
        url = '/tests'
        json_data = self.client.request(method, url)
        tests = json_loads(json_data)
        return tests["data"]

    def update_test(self, sessionId, name=None, passed=None, status_message=None):
        """Update attributes for the specified test."""
        params = []

        if status_message is not None:
            params.append('test[status_message]=%s' % status_message)
        if name is not None:
            params.append('test[name]=%s' % name)
        if passed is not None:
            params.append('test[success]=%s' % ('1' if passed else '0'))
        body = '&'.join(params)
        method = 'PUT'
        url = '/tests/%s' % sessionId
        json_data = self.client.request(method, url, body=body)
        response = json_loads(json_data)
        return response['success']

    def delete_test(self, sessionId):
        """Deletes a test."""
        method = 'DELETE'
        url = '/tests/%s' % sessionId
        json_data = self.client.request(method, url)
        response = json_loads(json_data)
        return response['success']

class Information(object):
    def __init__(self, client):
        self.client = client

    def get_browsers(self):
        """Get details of all browsers currently supported on TestingBot"""
        method = 'GET'
        url = '/browsers'
        json_data = self.client.request(method, url)
        browsers = json_loads(json_data)
        return browsers


class User(object):
    def __init__(self, client):
        self.client = client

    def get_user_information(self):
        """Access current user information"""
        method = 'GET'
        url = '/user'
        json_data = self.client.request(method, url)
        info = json_loads(json_data)
        return info