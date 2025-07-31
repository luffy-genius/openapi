from unittest import TestCase

from openapi.providers.alipay import Result as AliPayResult, Code as AliPayCode


class FeiShuBotTest(TestCase):

    def test_result(self):
        r = AliPayResult()
        assert r.code == AliPayCode.SUCCESS
