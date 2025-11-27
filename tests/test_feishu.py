from unittest import TestCase

from openapi.providers.feishu.bot import Result as BotResult
from openapi.providers.feishu.open import Result as OpenResult
from openapi.providers.feishu.open import Token as OpenToken


class FeiShuBotTest(TestCase):

    def test_result(self):
        r = BotResult(**{'StatusCode': 200})
        assert r.status_code == 200


class FeiShuOpenTest(TestCase):

    def test_result(self):
        r = OpenResult()
        assert r.msg == ''

    def test_token(self):
        t = OpenToken(access_token='1', )
        assert t.access_token == '1'
