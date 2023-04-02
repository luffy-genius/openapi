#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Date: 2023/4/2
import json
from openapi.providers.lenovo import Client
from examples.config import config

lenovo_pay_config = config['lenovopay']
client = Client(**lenovo_pay_config)
result = client.request('/pay/query/trade', data={
    'mchNo': '397120230402453989'
})
print(result)
