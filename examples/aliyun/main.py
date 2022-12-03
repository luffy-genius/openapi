import json
from openapi.providers.aliyun import Client

from examples.config import config

print(config['aliyun'])
client = Client(**config['aliyun'])
client.add_webhook(config['openapi_webhook'])


if __name__ == '__main__':
    # Send sms
    # result = client.request(
    #     'get', 'dysmsapi', 'SendSms', '2017-05-25',
    #     params={
    #         'PhoneNumbers': '',
    #         'SignName': '',
    #         'TemplateCode': '',
    #         'TemplateParam': json.dumps({'code': '123456'})
    #     }
    # )
    # print(result)

    # Vod
    result = client.request(
        'get', 'vod.cn-shanghai', 'GetVideoPlayAuth', '2017-03-21',
        params={
            'VideoId': '7b07afb2b01b4353a1e7f929b66cc667',
            'AuthInfoTimeout': '1800',
        }
    )
    print(result)
