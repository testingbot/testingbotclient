import testingbotclient

tb = testingbotclient.TestingBotClient(
           'key',
           'secret'
       )
print tb.tests.update_test("sessionId", 'mytest', True, 'test is ok')
print tb.tests.delete_test("sessionId")
print tb.information.get_browsers()
print tb.user.get_user_information()