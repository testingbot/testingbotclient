import os
import unittest

import testingbotclient

class TestTestingBotClient(unittest.TestCase):

    def setUp(self):
        self.tb = testingbotclient.TestingBotClient()

    def test_get_user_information(self):
        self.assertEqual(self.tb.user.get_user_information()['first_name'], "travisbot")

if __name__ == '__main__':
    unittest.main()