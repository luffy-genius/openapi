#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Date: 2023/2/3

import json
from openapi.providers.lenovo import (
    Client, calculate_signature, format_params,
)
from examples.config import config

lenovo_pay_config = config['lenovopay']

pay_data = {
    'mchNo': '1231313212asdaabbb',
    'payAmount': 1,
    'goodsName': 'table',
    'goodsDec': '',
    'goodsCode': '1',
    'productCode': 'COLLECT_CODE',
    'attach': json.dumps({'mobile': 1880561683}),
    'payNotify': 'http://47.94.238.32:8000/api/v1/pay/lenovo/'
}

client = Client(**lenovo_pay_config)
result = client.request('/pay/trade/direct/link', data=pay_data)
print(result)
