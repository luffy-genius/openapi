from openapi.providers.kwai import Client, Token

from examples.config import config

client = Client(
    config['kuaishou']['app_key'],
    config['kuaishou']['secret'],
    config['kuaishou']['sign_secret'],
    config['kuaishou']['message_key']
)


if __name__ == '__main__':
    # 快手消息解密
    print(client.decrypt('2FXtJpaJ1ftNz39omFhoWQ=='))
    print(client.decrypt('jbaDDoPZu/61uO/SMXT2s/y5Jq1+ISvE1QSo1kGE/p8jxJwkTNrIYDjvmtAQlwYUaDiYBSQR+hCwJWx299xZyubTYLDgmzL45dIchVAOyqiSnqKJLwnaXU1+W0lsRfKnvuBQvQhd6ftubauZU0RfvvgpEli/qZug0WPZMahHqq7pym/16x4GbzSMy4NzSevZCuVvYNIHCYeGYj+DkR18hiyUj08nHm/9y+70lGjcwBp7KjQ92XjUX0hqteTTgr7rvSJC00xA9gV2XafJAKo7cvTI0NT56ivyh2sM/Jt+XA2zlB8GpdL2zoTnSZKBXFaM+LhsE2kNHYvlZnjbonq3JvuXSIBPXnt9DdEJgEXXg5pKju3RKLGrTDSmB1rVy7r7YnyobQ/r0w8N4sIUs3FEVlB4fAds9slOsr5kY3YwQ2DRxNmiubbpjfjipW3H2jtMmRPToKP/2BChl+P9KIZ41X1Xykldz/2vFVo87C0S4FkzXsCfQrMm7t4a4nx8ktmHIME9BW2ashkdM/AAlxK9Rwe0+F7GFJ7xHICQUBI8hVM='))

    # 授权获取 Token
    # client.request(
    #     'get', '/oauth2/access_token',
    #     params={
    #         'app_id': client.app_id, 'grant_type': 'code',
    #         'code': '',
    #         'app_secret': client.secret
    #     }
    # )

    client._token = Token(access_token=config['kuaishou']['test']['access_token'])
    # 获取订单详情
    result = client.request(
        'get', '/open/order/detail', action='open.order.detail',
        params={
            'oid': 2421300093168518
        }
    )
    print(result)
    # 解密
    result = client.request(
        'post', '/open/order/desensitise/batch', action='open.order.desensitise.batch',
        data={
            'batchDesensitiseList': [
                {
                    'encryptedData': result.data['orderAddress']['encryptedMobile'],
                    'bizId': 2421300093168518
                }
            ]
        }
    )
    print(result)
