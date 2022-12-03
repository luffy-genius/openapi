import pprint
from openapi.providers.crm.tanmarket import Client

from examples.config import config

tan_market_config = config['tanmarket']
filepath = tan_market_config.pop('filepath')
client = Client(**tan_market_config)
client.add_webhook(config['openapi_webhook'])

pprint.pprint(client.request('post', '/v3/profile-fields', json={}).data)

# /v3/profile-fields/map
FIELDS = [
    {
        'fieldId': '104220',
        'alias': '姓名'
    },
    {
        'fieldId': '105086',
        'alias': '下单时间'
    },
    {
        'fieldId': '104217',
        'alias': '电话'
    },
    {
        'fieldId': '104223',
        'alias': '性别'
    },
    {
        'fieldId': '105475',
        'alias': '数分训练营'
    },
    {
        'fieldId': '105476',
        'alias': 'Py训练营'
    },
    {
        'fieldId': '105091',
        'alias': '推广人'
    },
    {
        'fieldId': '105111',
        'alias': '微信号'
    },
    {
        'fieldId': '105158',
        'alias': '渠道来源'
    },
    {
        'fieldId': '105739',
        'alias': '首次报名课程'
    },
    {
        'fieldId': '104219',
        'alias': '描述'
    },
    {
        'fieldId': '106074',
        'alias': 'UID'
    },
    {
        'fieldId': '109145',
        'alias': '已购课程'
    },
    {
        'fieldId': '109146',
        'alias': '购课总金额'
    },
    {
        'fieldId': '105111',
        'alias': '微信'
    },
    {
        'fieldId': '114038',
        'alias': '新Py训练营'
    }
]

if __name__ == '__main__':
    result = client.request('post', '/v3/profile-fields/map', json=FIELDS[-1])
    print(result)
    for alias in FIELDS[-2:]:
        pass
        # print(alias)
        # result = client.request('post', '/v3/profile-fields/map', json=alias)
        # print(alias, result)
