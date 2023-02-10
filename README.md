## OpenAPI

### 概述

`OpenAPI` 集成了各类第三方的 SDK。

### 安装

```
pip3 install openapipy
```

### 使用

#### 支付宝

> https://opendocs.alipay.com/open/270/105898

```python3
from openapi.providers.alipay import Client, Result
client = Client(
    app_id='2016081500252288',
    app_private_key_path='./resources/app_private_test2',
    app_cert_public_key_path='./resources/appCertPublicKey_2016081500252288_test.crt',
    alipay_root_cert_path='./resources/alipayRootCert_test.crt',
    alipay_cert_public_key_path='./resources/alipayCertPublicKey_RSA2_test.crt',
    is_sandbox=True
)

pc_pay_params = client.build_query_params(client.build_params(
    'alipay.trade.page.pay',
    {
        'subject': 'popmart-molly',
        'out_trade_no': 'pc123456',
        'total_amount': '999.99',
        'product_code': 'FAST_INSTANT_TRADE_PAY'
    },
    notify_url='http://47.94.172.250:9527/api/v1/pay/alipay/',
    return_url='http://47.94.172.250:9527/api/v1/pay/alipay/'
))
pc_pay_url = f'{client.API_BASE_URL}?{pc_pay_params}'
print(pc_pay_url)

result: Result = client.request(
    'get', 'alipay.trade.query',
    params={
        'out_trade_no': 'pc123456',
        # 'trade_no': ''
    }
)
print(result)
```

#### 微信

```python3
import json

from openapi.providers.wechat.pay import Client

wxpay_api = Client(
    app_id='app_id',
    mch_id='mch_id',
    api_key_path='api_key_path',
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
result = wxpay_api.request('post', '/pay/unifiedorder', data=data)
print(result)

# 创建订单 -> h5
data.update(trade_type='MWEB', out_trade_no='1231asd1222')
result = wxpay_api.request('post', '/pay/unifiedorder', data=data)
print(result)

# 创建订单 -> jsapi, 微信内
data.update(trade_type='JSAPI', out_trade_no='21321asd12311313', openid='ofwIAuEgpTZZwdPc1aort93xO')
result = wxpay_api.request('post', '/pay/unifiedorder', data=data)
print(result)
if result.result_code == wxpay_api.codes.SUCCESS:
    jsapi_data = wxpay_api.get_jsapi_data(result.data['prepay_id'])
    print(jsapi_data)
```

#### 抖店

> https://op.jinritemai.com/docs/api-docs/13/54

```python3
from openapi.providers.doudian import Client as DouDianClient, Result

client = DouDianClient('your_appid', 'your_secret', 'your_shop_id')
# 获取商品列表
result: Result = client.request('post', '/product/listV2', data={'page': 1, 'size': 10})
print(result)
```

#### 小鹅通

> https://api-doc.xiaoe-tech.com/?s=/2&page_id=420

```python3
from openapi.providers.xiaoetong import Client as XiaoetongClient, Result

client = XiaoetongClient('your_appid', 'your_secret', 'your_client_id')
# 获取分销人列表
result: Result = client.request('post', '/xe.distributor.list.get/1.0.0', data={})
print(result)
```

### 支持

```
2022 By ZhichaoLiu.
```