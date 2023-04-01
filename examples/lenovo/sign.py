#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Date: 2023/2/6
from openapi.providers.lenovo import Client
from examples.config import config

lenovo_pay_config = config['lenovopay']
client = Client(**lenovo_pay_config)

response = {
    'mchNo': '1231313212asdaabb',
    'tradeNo': 1047326995117440,
    'serialsNo': '2023020422001432721427426469',
    'payFee': 1,
    'payTime': '2023-02-04 00:52:18',
    'payStatus': '1',
    'attach': '{"mobile": 1880561683}',
    'appId': client.app_id,
    'mchId': client.mch_id,
    'sign': 'iMT2Z/0iT9w+kcdlypXrlYlvVUyb2dCJJ2xv2N0K3HVqFp1wf26ab70QVSY7WpFrQYumo6uZQk9TZy2Al/6U5iIGtECuacy9fxgws+m2VsgpSRGTx6axFAdiD0ILaFYmNfcKi3vu5thBbOOF6p4NKOhs3gy7/bXOnvDlcS6qZxbgjtugKTVPfPuJXWmDs29COLAQUfhuwaGVq6wMBzEVkFKt73G5kt//7zLwkraipcnlsZP4ih5Knqsqhkvvnk/uD1K6rEPqHe0GIDtFlg3j0n+hPvNudVCxU3MPEOiM2puUrm4krZwfBJhiIY/JWZGxUUUWRk0vjD+9g1SrpI9bCg==',
    'signType': 'RSA2',
    'version': '1.0',
    'charSet': 'UTF-8',
    'nonce': 'cjx48mj4vr'
}

print(client.check_signature(response))
