from openapi.providers.alipay import Client

from examples.config import config

print(config)
client = Client(**config['alipay'], is_sandbox=True)
client.add_webhook(config['openapi_webhook'])


if __name__ == '__main__':
    # pc-pay
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

    # mobile-pay
    mobile_pay_params = client.build_query_params(client.build_params(
        'alipay.trade.wap.pay',
        {
            'subject': 'popmart-molly',
            'out_trade_no': 'mobile123456',
            'total_amount': '999.99',
            'product_code': 'QUICK_WAP_WAY'
        },
        notify_url='http://47.94.172.250:9527/api/v1/pay/alipay/',
        return_url='http://47.94.172.250:9527/api/v1/pay/alipay/'
    ))
    mobile_pay_url = f'{client.API_BASE_URL}?{pc_pay_params}'
    print(mobile_pay_url)

    # query
    result = client.request(
        'get', 'alipay.trade.query',
        params={
            'out_trade_no': 'mobile123456',
            # 'trade_no': ''
        }
    )
    print(result)
