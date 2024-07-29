import json

import httpx

from openapi.providers.alipay import Client

from examples.config import config

settings = config['alipay-test']
client = Client(**settings, is_sandbox=True)
# client.add_webhook(config['openapi_webhook'])


if __name__ == '__main__':
    # query
    params = client.build_query_params(client.build_params(
        'alipay.data.bill.balance.query', data={},
        # 'alipay.data.bill.balancehis.query', data={'biz_month': '2023-05'}
        # 'alipay.data.dataservice.bill.downloadurl.query',
        # data={'bill_type': 'trade', 'bill_date': '2023-05'}
    ))
    request_url = f'{client.API_BASE_URL}?{params}'
    # print(request_url)
    # response = httpx.get(request_url)
    # print(response.json())
    # pc-pay
    pc_pay_params = client.build_query_params(client.build_params(
        'alipay.trade.page.pay',
        {
            'subject': 'popmart-molly',
            'out_trade_no': 'pc12345678',
            'total_amount': '100',
            'product_code': 'FAST_INSTANT_TRADE_PAY',
            'extend_params': json.dumps({'hb_fq_seller_percent': '100'})
        },
        notify_url='http://47.94.172.250:9527/api/v1/pay/alipay/',
        return_url='http://47.94.172.250:9527/api/v1/pay/alipay/'
    ))
    pc_pay_url = f'{client.API_BASE_URL}?{pc_pay_params}'
    print(pc_pay_url)

    # mobile-pay
    mobile_pay_params = client.build_query_params(client.build_params(
        'alipay.trade.wap.pay',
        {
            'subject': 'popmart-molly',
            'out_trade_no': 'mobile1234567',
            'total_amount': '0.01',
            'product_code': 'QUICK_WAP_WAY'
        },
        notify_url='http://47.94.172.250:9527/api/v1/pay/alipay/',
        return_url='http://47.94.172.250:9527/api/v1/pay/alipay/'
    ))
    mobile_pay_url = f'{client.API_BASE_URL}?{mobile_pay_params}'
    print(mobile_pay_url)

    # query
    result = client.request(
        'get', 'alipay.trade.query',
        params={
            # 'out_trade_no': '2023021922001494131437680153',
            'trade_no': '2023040322001494481429840718'
        }
    )
    print(result)
