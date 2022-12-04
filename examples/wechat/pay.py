#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Date: 2022/11/14
import json

from openapi.providers.wechat.pay import Client

from examples.config import config

wechatpay_config = config['wechatpay']

wxpay_api = Client(
    app_id=wechatpay_config['app_id'],
    mch_id=wechatpay_config['mch_id'],
    api_key_path=wechatpay_config['api_key_path'],
    is_sandbox=False
)

# 查询订单
result = wxpay_api.request(
    'post', '/pay/orderquery',
    data={
        # 'out_trade_no': '9wfafGR31rCytY68wSFcXCII',
        'transaction_id': '4200001591202211145504991626'
    }
)
print(result)

data = {
    'body': '米诺地尔町',
    'out_trade_no': '1232112359910',
    'total_fee': 1,
    'spbill_create_ip': '127.0.0.1',
    'notify_url': 'htt',
    'trade_type': 'NATIVE',
    'attach': json.dumps({'x': 1})
}

# 创建订单 -> pc
# result = wxpay_api.request('post', '/pay/unifiedorder', data=data)
# print(result)

# 创建订单 -> mweb
# data.update(trade_type='MWEB', out_trade_no='1231asd1222')
# result = wxpay_api.request('post', '/pay/unifiedorder', data=data)
# print(result)

# 创建订单 -> jsapi
data.update(trade_type='JSAPI', out_trade_no='21321asd12311313', openid='ofwIAuEgpTZZwdPc1aort93xOdU8')
result = wxpay_api.request('post', '/pay/unifiedorder', data=data)
print(result)
if result.result_code == wxpay_api.codes.SUCCESS:
    jsapi_data = wxpay_api.get_jsapi_data(result.data['prepay_id'])
    print(jsapi_data)
