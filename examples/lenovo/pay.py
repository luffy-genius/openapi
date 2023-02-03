#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Date: 2023/2/3

import json
from openapi.providers.lenovo import Client
from examples.config import config

lenovo_pay_config = config['lenovopay']

pay_data = {
    'mchNo': '1231313212asdaa',
    'payAmount': 100,
    'goodsName': 'table',
    'goodsDec': '',
    'goodsCode': '1',
    'productCode': 'COMMON_CASHIER',
    'attach': json.dumps({'x': 1}),
    'payNotify': 'https://api.luffycity.com/pay'
}

client = Client(**lenovo_pay_config)
result = client.request('/pay/trade/direct/link', data=pay_data)
print(result)
