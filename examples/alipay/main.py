from openapi.providers.alipay import Client


client = Client(
    app_id='2016081500252288',
    app_private_key_path='./resources/app_private_test2',
    app_cert_public_key_path='./resources/appCertPublicKey_2016081500252288_test.crt',
    alipay_root_cert_path='./resources/alipayRootCert_test.crt',
    alipay_cert_public_key_path='./resources/alipayCertPublicKey_RSA2_test.crt',
    is_sandbox=True
)


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
