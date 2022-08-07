#!/usr/bin/env python

import base64
import sys
import json
import os
import requests
from requests.auth import HTTPBasicAuth
import hashlib

__version__ = '0.0.9'

class TestingBotException(Exception):
    def __init__(self, *args, **kwargs):
        super(TestingBotException, self).__init__(*args)
        self.response = kwargs.get('response')

class TestingBotClient(object):
    def __init__(self, testingbotKey=None, testingbotSecret=None):
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
                data = f.read()
                self.testingbotKey, self.testingbotSecret = data.split(':')
                f.close()

        self.information = Information(self)
        self.tests = Tests(self)
        self.user = User(self)
        self.storage = Storage(self)
        self.tunnel = Tunnel(self)
        self.build = Build(self)
        self.api_url = 'https://api.testingbot.com/v1/'

    def post(self, url, data):
        response = requests.post(self.api_url + url, data=data, auth=(self.testingbotKey, self.testingbotSecret))
        if response.status_code not in [200, 201]:
            raise TestingBotException('{}: {}.\nTestingBot API Error'.format(
                response.status_code, response.text), response=response)
        return response.json()

    def delete(self, url):
        response = requests.delete(self.api_url + url, auth=(self.testingbotKey, self.testingbotSecret))
        if response.status_code not in [200, 201]:
            raise TestingBotException('{}: {}.\nTestingBot API Error'.format(
                response.status_code, response.text), response=response)
        return response.json()

    def put(self, url, data):
        response = requests.put(self.api_url + url, data=data, auth=(self.testingbotKey, self.testingbotSecret))
        if response.status_code not in [200, 201]:
            raise TestingBotException('{}: {}.\nTestingBot API Error'.format(
                response.status_code, response.text), response=response)
        return response.json()

    def get(self, url):
        response = requests.get(self.api_url + url, auth=(self.testingbotKey, self.testingbotSecret))
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
        tests = self.client.get(method, url)
        test_ids = [attr['session_id'] for attr in tests['data']]
        return test_ids

    def get_tests(self, offset = 0, limit = 30):
        """List all tests belonging to the user."""
        url = '/tests?offset=' + str(offset) + '&count=' + str(limit)
        tests = self.client.get(url)
        return tests["data"]

    def get_test(self, sessionId):
        """Get meta-data for a specific test"""
        return self.client.get('/tests/' + sessionId)

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
        response = self.client.put(url)
        return response['success']

class Storage(object):
    def __init__(self, client):
        self.client = client

    def upload_local_file(self, filepath):
        """Uploads a local file to TestingBot Storage."""
        return requests.post(self.client.api_url + "/storage", files={'file': open(filepath, 'rb')}, auth=(self.client.testingbotKey, self.client.testingbotSecret)).json()

    def upload_remote_file(self, remoteUrl):
        return self.client.post("/storage", { 'url': remoteUrl })

    def get_stored_file(self, app_url):
        """Retrieves meta-data for a file previously uploaded to TestingBot Storage."""
        return self.client.get("/storage/" + app_url.replace("tb://", ""))

    def remove_file(self, app_url):
        """Removes a file previously uploaded to TestingBot Storage."""
        return self.client.delete("/storage/" + app_url.replace("tb://", ""))

    def get_stored_files(self, offset = 0, limit = 30):
        """Retrieves all files previously uploaded to TestingBot Storage."""
        return self.client.get("/storage/?count=" + str(limit) + "&offset=" + str(offset))

class Information(object):
    def __init__(self, client):
        self.client = client

    def get_browsers(self):
        """Get details of all browsers currently supported on TestingBot"""
        url = '/browsers'
        browsers = self.client.get(url)
        return browsers

    def get_devices(self):
        """Get details of all devices currently on TestingBot"""
        url = '/devices'
        devices = self.client.get(url)
        return devices

    def get_available_devices(self):
        """Get details of all devices currently available on TestingBot"""
        url = '/devices/available'
        devices = self.client.get(url)
        return devices

    def get_device(self, deviceId):
        """Get details of a specific device on TestingBot"""
        url = '/devices/' + deviceId
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
        return self.client.delete('/tunnel/' + tunnelId)

class Build(object):
    def __init__(self, client):
        self.client = client

    def get_builds(self, offset = 0, limit = 30):
        """Get all builds"""
        return self.client.get('/builds?offset=' + str(offset) + '&count=' + str(limit))

    def get_tests_for_build(self, buildId):
        """Get tests for a specific build"""
        return self.client.get('/builds/' + buildId)

    def delete_build(self, buildId):
        """Delete a specific build"""
        return self.client.delete('/builds/' + buildId)


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
        info = self.client.put(url)
        return info