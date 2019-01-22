[![Build Status](https://travis-ci.org/testingbot/testingbotclient.svg?branch=master)](https://travis-ci.org/testingbot/testingbotclient)

# testingbotclient

Python client for TestingBot REST API

## Install

```shell
pip install testingbotclient
```

## TestingBot
[TestingBot](https://testingbot.com/) allows you to run your Selenium tests in the cloud.
With access to over 400 different browser combinations, you can run your tests in parallel on their Selenium grid.

## Using the client

```python
import testingbotclient

tb = testingbotclient.TestingBotClient(
            'key',
            'secret'
        )
print tb.tests.update_test("webdriverSessionId", 'my test name', False, 'test failure error')
```

It is also possible to use `TESTINGBOT_KEY` and `TESTINGBOT_SECRET` environment variables instead of specifying these in the TestingBotClient constructor. Or use a `~/.testingbot` file with `key:secret`.

## Running tests

This library is only intended to query the TestingBot API.
Below is a simple example which runs a Selenium Webdriver test on TestingBot and reports its name/success state back to TestingBot via this library:

```python
import unittest
import sys

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from testingbotclient import TestingBotClient

class TestTestingBotClient(unittest.TestCase):

    def setUp(self):
		desired_cap = {'platform': 'Windows', 'browserName': 'firefox', 'version': 'latest' }

		self.driver = webdriver.Remote(
		    command_executor='http://key:secret@hub.testingbot.com/wd/hub',
		    desired_capabilities=desired_cap)

    def test_google_example(self):
		self.driver.get("http://www.google.com")
		if not "Google" in self.driver.title:
		    raise Exception("Unable to load google page!")
		elem = self.driver.find_element_by_name("q")
		elem.send_keys("TestingBot")
		elem.submit()

    def tearDown(self):
		self.driver.quit()
		status = sys.exc_info() == (None, None, None)
		tb_client = TestingBotClient('key', 'secret')
		tb_client.tests.update_test(self.driver.session_id, self._testMethodName, status)

if __name__ == '__main__':
    unittest.main()
```

For more information on running Selenium RC/WebDriver tests with Python, please see [Python WebDriver Examples](https://testingbot.com/support/getting-started/python.html)


## More documentation

Check out the [TestingBot REST API](https://testingbot.com/support/api) for more information.

## License

The MIT License (MIT)

Copyright (c) TestingBot.com

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.