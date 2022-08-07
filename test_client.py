import os
import unittest
import uuid
import testingbotclient

class TestTestingBotClient(unittest.TestCase):

    def setUp(self):
        self.tb = testingbotclient.TestingBotClient()

    def test_get_user_information(self):
        self.assertTrue(self.tb.user.get_user_information()['first_name'])

    def test_upload_file(self):
        response = self.tb.storage.upload_local_file("./tests/resources/sample.apk")
        self.assertTrue(response.get("app_url") != None)

    def test_upload_remote_file(self):
        response = self.tb.storage.upload_remote_file("https://testingbot.com/appium/sample.apk")
        self.assertTrue(response.get("app_url") != None)

    def test_upload_and_delete_file(self):
        files = self.tb.storage.get_stored_files()
        current_count = files.get("meta").get("total")
        response = self.tb.storage.upload_local_file("./tests/resources/sample.apk")
        app_url = response.get("app_url")
        meta_data = self.tb.storage.get_stored_file(app_url)
        self.assertEqual(meta_data.get("app_url"), app_url)

        files = self.tb.storage.get_stored_files()
        self.assertEqual(files.get("meta").get("total"), current_count + 1)

        self.tb.storage.remove_file(app_url)

        try:
            self.tb.storage.get_stored_file(app_url)
        except testingbotclient.TestingBotException:
            pass
        else:
            self.fail('ExpectedException not raised')

    def test_get_test(self):
        sessionId = "6344353dcee24694bf39d5ee5e6e5b11"
        test_meta = self.tb.tests.get_test(sessionId)
        self.assertEqual(test_meta.get("session_id"), sessionId)

    def test_get_tests(self):
        test_meta = self.tb.tests.get_tests(0, 6)
        self.assertEqual(len(test_meta), 6)

        test_meta = self.tb.tests.get_tests()
        self.assertEqual(len(test_meta), 10)

    def test_update_test(self):
        sessionId = "6344353dcee24694bf39d5ee5e6e5b11"
        new_status_message = uuid.uuid4().hex.upper()[0:6]
        self.tb.tests.update_test(sessionId, status_message=new_status_message)
        test_meta = self.tb.tests.get_test(sessionId)
        self.assertEqual(test_meta.get("status_message"), new_status_message)

    def test_share_link(self):
        self.assertEqual(self.tb.get_share_link("test"), "344ebf07233168c4882adf953a8a8c9b")

if __name__ == '__main__':
    unittest.main()