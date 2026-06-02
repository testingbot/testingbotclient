import testingbotclient

# Credentials can also come from TESTINGBOT_KEY / TESTINGBOT_SECRET env vars
# or a ~/.testingbot file containing "key:secret".
tb = testingbotclient.TestingBotClient('key', 'secret')

# Update a test's result after running it
print(tb.tests.update_test('sessionId', name='my test', passed=True,
                           status_message='all good'))

# Fetch tests, available browsers, and your account info
print(tb.tests.get_tests(offset=0, limit=10))
print(tb.information.get_browsers())
print(tb.user.get_user_information())

# Upload an app to TestingBot Storage
# print(tb.storage.upload_local_file('/path/to/app.apk'))

# Trigger a Codeless test and wait for the result
# job = tb.lab.trigger(123)
# print(tb.jobs.wait_for_job(job['job_id']))
