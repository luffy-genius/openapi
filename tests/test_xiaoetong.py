from unittest import TestCase

from openapi.providers.xiaoetong import Result


class FeiShuBotTest(TestCase):

    def test_result(self):
        r = Result()
        assert r.msg == ''
