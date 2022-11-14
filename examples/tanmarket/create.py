from openapi.providers.crm.tanmarket import Client

from examples.config import config

tan_market_config = config['tanmarket']
filepath = tan_market_config.pop('filepath')
client = Client(**tan_market_config)
client.add_webhook(config['openapi_webhook'])

# For testing
result = client.request(
    'post', '/v3/echo',
    json={'hello': 'tanmarket'}
)
# print('>>>>', result)
# code=40417 data=None message='请求参数验证失败：电话号码重复'
# code=0 data=497186786844992 message='success'

if __name__ == '__main__':
    result = client.request('post', '/v3/add-clue', json={
        'customerName': 'liuzhichao-test3',
        'mobiles': ['18803561678'],
        'fields': [
            {
                'alias': '首次报名课程',
                'fieldValue': 'python集训营'
            },
            {
                'alias': '下单时间',
                'fieldValue': '2022-09-14 21:01:00'
            },
            # {
            #     'alias': '电话',
            #     'fieldValue': ['18803561681']
            # },
            {
                'alias': '性别',
                'fieldValue': 0
            },
            {
                'alias': '姓名',
                'fieldValue': '刘志超'
            },
            {
                'alias': '数分训练营',
                'fieldValue': 1
            },
            {
                'alias': '推广人',
                'fieldValue': 'alex'
            },
            {
                'alias': '渠道来源',
                'fieldValue': 0
            },
            {
                'alias': '微信号',
                'fieldValue': '123'
            },
            {
                'alias': '描述',
                'fieldValue': 'hhhh'
            },
            {
                'alias': '已购课程',
                'fieldValue': '测试课程'
            },
            {
                'alias': '购课总金额',
                'fieldValue': 0.12
            },
        ]
    })
    print(result)
