from openapi.providers.wechat.open import Client

from examples.config import config

print(config)
client = Client(**config['wechat'])
client.add_webhook(config['openapi_webhook'])

# 网络检测
result = client.request('post', '/callback/check', data={})
print(result)
print(result.errcode == client.codes.SUCCESS_CODE)

# 发送模板消息
result = client.request(
    'post', '/message/template/send',
    data={
        'touser': 'ofwIAuOwpNTVRDBK82KRuH7xhpXo',
        'template_id': 'juLkJRq6c2aijf0W9AZcf2pbfVbAl5qvsd8vD9D4HLI',
        'data': {
            'first': {'value': f'您的学生 谷爱凌 同学，已开通新模块：'},
            'keyword1': {'value': 'Python开发'},
            'keyword2': {'value': '2022-09-03 15:34'},
            'remark': {'value': '开通模块：第一模块'}
        },
        'url': None,
        'miniprogram': None
    }
)
print(result)
print(result.errcode == client.codes.SUCCESS_CODE)
