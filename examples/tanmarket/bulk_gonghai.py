import openpyxl
from collections import namedtuple

from openapi.providers.crm.tanmarket import Client

from examples.config import config

Customer = namedtuple(
    'Customer',
    'type date reason belong lead created_at contact_at recently_at paid_at python_camp mobile '
    'username wechat memo1 memo2'
)

tan_market_config = config['tanmarket']
filepath = tan_market_config.pop('filepath')
client = Client(**tan_market_config)
client.add_webhook(config['openapi_webhook'])

workbook = openpyxl.load_workbook(filepath)
sheet = workbook.active
counter = 0
customers = []

for row in sheet.iter_rows(min_row=11296, values_only=True):
    customer = Customer(*row)
    if '删除' in customer.type:
        continue

    counter += 1
    result = client.request('post', '/v3/save-highseas', json=[
        {
            'fields': [
                # 姓名
                {
                    'id': 104220,
                    'value': [customer.username]
                },
                {
                    'id': 105086,
                    'value': [customer.created_at]
                },
                {
                    'id': 104217,
                    'value': [customer.mobile]
                },
                {
                    'id': 105739,
                    'value': [customer.python_camp or '']
                },
                {
                    'id': 104219,
                    'value': [
                        f'最近归属人：{customer.belong}, 微信：{customer.wechat or ""}'
                        f'{customer.memo1 or ""}, {customer.memo2 or ""}'
                    ]
                }
            ]
        }
    ])
    print(result)
    customers = []
    print('>>>', counter, customer)
print(counter)
