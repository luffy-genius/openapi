#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Date: 2022/11/14
from openapi.providers.wechat_pay import Client

from examples.config import config

wechatpay_config = config['wechatpay']

wxpay_api = Client(
    app_id=wechatpay_config['app_id'],
    mch_id=wechatpay_config['mch_id'],
    api_key_path=wechatpay_config['api_key_path'],
    is_sandbox=False
)

result = wxpay_api.request(
    'post', '/pay/orderquery',
    data={
        # 'out_trade_no': '9wfafGR31rCytY68wSFcXCII',
        'transaction_id': '4200001591202211145504991626'
    }
)
print(result)
