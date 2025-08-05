from unittest import TestCase

from openapi.providers.alipay import Result as AliPayResult, Code as AliPayCode
from openapi.providers.aliyun import Result as AliYunResult, Code as AliYunCode


class AliPayTest(TestCase):

    def test_result(self):
        r = AliPayResult()
        assert r.code == AliPayCode.SUCCESS


class AliYunTest(TestCase):

    def test_result(self):
        r = AliYunResult(request_id='123')
        assert r.code == AliYunCode.SUCCESS
        assert r.request_id == '123'
