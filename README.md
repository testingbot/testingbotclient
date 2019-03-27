[![Build Status](https://travis-ci.org/testingbot/testingbotclient.svg?branch=master)](https://travis-ci.org/testingbot/testingbotclient)
[![PyPI version](https://badge.fury.io/py/testingbotclient.svg)](https://badge.fury.io/py/testingbotclient)

# testingbotclient

Python client for TestingBot REST API

## Install

```shell
pip install testingbotclient
```

## TestingBot
[TestingBot](https://testingbot.com/) allows you to run Selenium tests in the cloud.
With access to over +1500 different browser/device combinations, you can run your browser and mobile tests in parallel on the TestingBot Selenium grid.

## Getting Started

```python
import testingbotclient

tb = testingbotclient.TestingBotClient('key', 'secret')
```

It is also possible to use `TESTINGBOT_KEY` and `TESTINGBOT_SECRET` environment variables instead of specifying these in the TestingBotClient constructor. Or use a `~/.testingbot` file with `key:secret`.


*All API methods can throw these exceptions:*

```python
TestingBotException(errorMessage)
```

### getBrowsers
Retrieves collection of available browsers
<https://testingbot.com/support/api>


```python
testingbotclient.information.get_browsers()
```

### updateTest
Update meta-data for a test
<https://testingbot.com/support/api#updatetest>

- `String` status_message
- `boolean` success
- `String` build
- `String` name


```python
testingbotclient.tests.update_test(sessionId, status_message=.., passed=1|0, build=.., name=..)
```

### stopTest
Stops a running test
<https://testingbot.com/support/api#stoptest>


```python
testingbotclient.tests.stop_test(sessionId)
```

### deleteTest
Deletes a test from TestingBot
<https://testingbot.com/support/api#deletetest>


```python
testingbotclient.tests.delete_test(sessionId)
```

### getTest
Retrieves information regarding a test
<https://testingbot.com/support/api#singletest>


```python
testingbotclient.tests.get_test(sessionId)
```

### getTests
Retrieves a collection of tests
<https://testingbot.com/support/api#tests>


```python
testingbotclient.tests.get_tests(offset=0, limit=30)
```

### getBuilds
Retrieves a collection of builds
<https://testingbot.com/support/api#builds>


```python
testingbotclient.build.get_builds(offset=0, limit=30)
```

### getTestsForBuild
Retrieves a collection of tests for a specific build
<https://testingbot.com/support/api#singlebuild>


```python
testingbotclient.build.get_tests_for_build(buildId)
```

### getUserConfig
Retrieves information about the current user
<https://testingbot.com/support/api#user>


```python
testingbotclient.user.get_user_information()
```

### getTunnels
Retrieves tunnels for the current user
<https://testingbot.com/support/api#apitunnellist>


```python
testingbotclient.tunnel.get_tunnels()
```

### deleteTunnel
Deletes/stops a specific tunnel for the current user
<https://testingbot.com/support/api#apitunneldelete>


```python
testingbotclient.tunnel.delete_tunnel(sessionId)
```

### uploadToStorage - Local File
Uploads a local file to TestingBot Storage
<https://testingbot.com/support/api#upload>


```python
testingbotclient.storage.upload_local_file(localFilePath)
```

### uploadToStorage - Remote File
Uploads a remote file to TestingBot Storage
<https://testingbot.com/support/api#upload>


```python
testingbotclient.storage.upload_remote_file(localFilePath)
```

### getStorageFile
Retrieves meta-data from a previously stored file
<https://testingbot.com/support/api#uploadfile>


```python
testingbotclient.storage.get_stored_file(appUrl)
```

### getStorageFiles
Retrieves meta-data from previously stored files
<https://testingbot.com/support/api#filelist>


```python
testingbotclient.storage.get_stored_files(appUrl)
```

### deleteStorageFile
Deletes a file previously stored in TestingBot Storage
<https://testingbot.com/support/api#filedelete>


```python
testingbotclient.storage.remove_file(appUrl)
```

### get_share_link
Calculates the authenticationHash necessary to share tests
<https://testingbot.com/support/other/sharing>


```python
testingbotclient.get_share_link(sessionId)
```

## Test

```python
python test_travis.py
```

## More documentation

Check out the [TestingBot REST API](https://testingbot.com/support/api) for more information.