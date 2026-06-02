[![PyPI version](https://badge.fury.io/py/testingbotclient.svg)](https://badge.fury.io/py/testingbotclient)

# testingbotclient

Python client for the TestingBot REST API

## Install

```shell
pip install testingbotclient
```

## TestingBot
[TestingBot](https://testingbot.com/) allows you to run Selenium tests in the cloud.
With access to over +2600 different browser/device combinations, you can run your browser and mobile tests in parallel on the TestingBot Grid.

## Getting Started

```python
import testingbotclient

tb = testingbotclient.TestingBotClient('key', 'secret')
```

Credentials can also be supplied via the `TESTINGBOT_KEY` / `TESTINGBOT_SECRET`
(or `TB_KEY` / `TB_SECRET`) environment variables, or a `~/.testingbot` file
containing `key:secret` — in which case you can construct the client with no
arguments:

```python
tb = testingbotclient.TestingBotClient()
```

An optional request timeout (seconds, default `60`) can be set; raise it for
large Storage uploads:

```python
tb = testingbotclient.TestingBotClient('key', 'secret', timeout=120)
```

Every API method raises `testingbotclient.TestingBotException` on a non-2xx
response. The exception carries the failing `.response` (with credentials
stripped from it):

```python
try:
    tb.tests.get_test('does-not-exist')
except testingbotclient.TestingBotException as e:
    print(e.response.status_code)
```

API reference: <https://testingbot.com/support/api>

## Tests — `tb.tests`

```python
# List tests (filters are all optional)
tb.tests.get_tests(offset=0, limit=10, since=None, browser_id=None,
                   group=None, build=None, skip_fields=None)
tb.tests.get_test_ids()
tb.tests.get_test(sessionId, skip_fields=None)

# Update a test's metadata after running it
tb.tests.update_test(sessionId, name=None, passed=None,
                     status_message=None, build=None)

tb.tests.stop_test(sessionId)
tb.tests.delete_test(sessionId)

# Create a record for a manual / external test result
tb.tests.create_test(name, success=None, status_message=None,
                     extra=None, build=None)
```

## Builds — `tb.build`

```python
tb.build.get_builds(offset=0, limit=10)
tb.build.get_tests_for_build(buildId)
tb.build.delete_build(buildId)
```

## Storage — `tb.storage`

Upload app binaries (`.apk` / `.ipa`) and reference them later via the returned
`tb://<appkey>` URL.

```python
tb.storage.upload_local_file(localFilePath)
tb.storage.upload_remote_file(remoteUrl)

# Replace the binary behind an existing app_url (the app_url stays the same)
tb.storage.replace_local_file(app_url, localFilePath)
tb.storage.replace_remote_file(app_url, remoteUrl)

tb.storage.get_stored_file(app_url)
tb.storage.get_stored_files(offset=0, limit=10)
tb.storage.remove_file(app_url)
```

## Browsers & devices — `tb.information`

```python
tb.information.get_browsers(type=None)          # type: 'webdriver' | 'rc'
tb.information.get_devices(platform=None)        # platform: 'android' | 'ios' | 'real_android' | 'real_ios'
tb.information.get_available_devices()
tb.information.get_device(deviceId)
```

## Screenshots — `tb.screenshots`

Capture a URL across multiple browsers.

```python
batch = tb.screenshots.take_screenshots(
    url, resolution, browsers,        # browsers: list of browser_id values
    wait_time=0, full_page=None, callback_url=None)
tb.screenshots.get_screenshots(offset=0, limit=10)
tb.screenshots.get_screenshot(screenshotId, exclude_ids=None)
```

## Codeless tests — `tb.lab`

Create, schedule, and run no-code (recorded) tests. `trigger` / `trigger_all`
return a `job_id` you poll with `tb.jobs`.

```python
tb.lab.get_tests(offset=0, limit=10)
tb.lab.get_test(testId)

# Create from a target URL, or import a Selenium IDE .side export
tb.lab.create_test(name=None, url=None, cron=None, screenshot=None, video=None,
                   idletimeout=None, screenresolution=None, ai_prompt=None, file=None)
tb.lab.update_test(testId, name=None, url=None, cron=None, enabled=None)
tb.lab.delete_test(testId)

tb.lab.trigger(testId, url=None)
tb.lab.trigger_all(url=None)

tb.lab.get_steps(testId, offset=0, limit=10)
tb.lab.set_steps(testId, steps)          # list of {order, cmd, locator, value}

tb.lab.schedule(testId, type, day=None, hour=None, cron_format=None)  # type: once|daily|weekly|custom
tb.lab.stop(testId, browser_id=None)

tb.lab.add_alert(testId, kind, level, content)   # kind: EMAIL|API|SMS, level: IMMEDIATELY|DAILY
tb.lab.update_alert(testId, kind=None, level=None, content=None)
tb.lab.add_report(testId, email, cron=None)
tb.lab.update_report(testId, email=None, cron=None)

tb.lab.get_browsers(testId)
tb.lab.set_browsers(testId, browser_ids)  # list or comma-separated string
```

## Codeless suites — `tb.labsuites`

Group Codeless tests so they can be triggered and reported on together.

```python
tb.labsuites.get_suites(offset=0, limit=10)
tb.labsuites.get_suite(suiteId)
tb.labsuites.create_suite(name, cron=None, screenshot=None, video=None,
                          idletimeout=None, screenresolution=None)
tb.labsuites.delete_suite(suiteId)
tb.labsuites.trigger(suiteId)            # returns a job_id

tb.labsuites.get_tests(suiteId, offset=0, limit=10)
tb.labsuites.add_tests(suiteId, test_ids)     # list or comma-separated string
tb.labsuites.remove_test(suiteId, testId)

tb.labsuites.get_browsers(suiteId)
tb.labsuites.set_browsers(suiteId, browser_ids)
```

## Jobs — `tb.jobs`

Poll asynchronous jobs returned by Codeless triggers.

```python
job = tb.lab.trigger(123)
tb.jobs.get_job(job['job_id'])
tb.jobs.wait_for_job(job['job_id'], timeout=600, interval=5)  # blocks until FINISHED
```

## Tunnels — `tb.tunnel`

```python
tb.tunnel.get_tunnels()
tb.tunnel.delete_tunnel(tunnelId)
```

## Team management — `tb.team`

```python
tb.team.get_concurrency()
tb.team.get_users(offset=0, limit=10)
tb.team.get_user(userId)
tb.team.create_user(email, password, first_name=None, last_name=None,
                    concurrency=None, concurrency_physical=None)
tb.team.update_user(userId, first_name=None, last_name=None, email=None,
                    password=None, credits=None, device_credits=None,
                    concurrency=None, concurrency_physical=None)
tb.team.get_client_key(userId)
tb.team.reset_keys(userId)
```

## Configuration — `tb.configuration`

```python
tb.configuration.get_ip_ranges()   # TestingBot IPs for firewall whitelisting
```

## User — `tb.user`

```python
tb.user.get_user_information()
tb.user.update_user_information(userInformation)
```

## Sharing

Calculate the authentication hash needed to share a test.
<https://testingbot.com/support/other/sharing>

```python
tb.get_share_link(sessionId)
```

## Test

Unit tests are mocked and need no credentials:

```shell
python -m unittest tests.test_unit
```

The live integration tests hit the real API and require `TB_KEY` and `TB_SECRET`:

```shell
python -m unittest tests.test_client
```

## More documentation

Check out the [TestingBot REST API](https://testingbot.com/support/api) for more information.
