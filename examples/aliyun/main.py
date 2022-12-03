import json
from openapi.providers.aliyun import Client

from examples.config import config

print(config['aliyun'])
client = Client(**config['aliyun'])
client.add_webhook(config['openapi_webhook'])


if __name__ == '__main__':
    result = client.request(
        'get', 'dysmsapi', 'SendSms', '2017-05-25',
        params={
            'PhoneNumbers': '',
            'SignName': '',
            'TemplateCode': '',
            'TemplateParam': json.dumps({'code': '123456'})
        }
    )
    print(result)
