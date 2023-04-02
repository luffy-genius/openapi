#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Date: 2023/2/3

import json
from openapi.providers.lenovo import Client
from examples.config import config

lenovo_pay_config = config['lenovopay']

pay_data = {
    'mchNo': '397120230402453989',
    'payAmount': 1,
    'goodsName': 'table',
    'goodsDec': '',
    'goodsCode': '1',
    'productCode': 'COLLECT_CODE',
    'attach': json.dumps({'mobile': 18803561683}),
    'payNotify': 'http://47.94.238.32:8000/api/v1/pay/lenovo/'
}

client = Client(**lenovo_pay_config)
result = client.request('/pay/trade/direct/link', data=pay_data)
print(result)
