from unittest import TestCase

from openapi.providers.feishu.bot import Result as BotResult
from openapi.providers.feishu.open import Result as OpenResult


class FeiShuBotTest(TestCase):

    def test_result(self):
        r = BotResult(**{'StatusCode': 200})
        assert r.status_code == 200


class FeiShuOpenTest(TestCase):

    def test_result(self):
        r = OpenResult()
        assert r.msg == ''
