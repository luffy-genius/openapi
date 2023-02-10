#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Date: 2023/2/3
from Crypto.PublicKey import RSA

from examples.config import config
from openapi.providers.lenovo import calculate_signature, format_params

lenovo_pay_config = config['lenovopay']

data = {"mchNo": "1231313212asd", "payAmount": 100, "goodsName": "table", "goodsDec": "", "goodsCode": "1", "productCode": "COMMON_CASHIER", "attach": "{'x': 1}", "payNotify": "https://api.luffycity.com/pay", "mchId": "x", "appId": "x", "nonce": "40c6ad3ac938a7032d6ec315218dd08d", "timestamp": "1675410455", "version": "1.0", "signType": "RSA2"}
real_sign = 'aROFT8oFCKtKj8W7RSs27J8RJSkydK1BFmC9sInb4OBkOdBMram9U12PSzmtxQXNqg/P4qRjPw/E67uIQY0/pCT7hT/W9pMqknzu2rqpRe5X2viUL3Ar9882XTH6I6IAXbyhLZj4gvnXGcHO1g6rhP8pR6s9FCjek2C888I5HFLtCLuprQ7/RNdbkUs74VgLUN2G8vQzsar5iEENXdYFUUxJPxs8VBRYQq8TttTo+y7FXKI6tUvUK0gIQ3uhIG0NYnYl1bfYnUCz3XkaH3jIGarxC8a9k2so5PEJeRFk34aQuXTHJHjUqaMNSouLQ7sNJBRjohkKV9YVl1wocDd5Sw=='

with open(lenovo_pay_config['private_key_path']) as f:
    pri_key = RSA.importKey(f.read())
    content = format_params(data)
    sign = calculate_signature(
        content.encode(), pri_key
    )
    print(sign == real_sign)
