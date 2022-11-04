from datetime import datetime

from openapi.providers.crm.tanmarket import Client

from examples.config import config

tan_market_config = config['tanmarket']
filepath = tan_market_config.pop('filepath')
client = Client(**tan_market_config)
client.add_webhook(config['openapi_webhook'])

update_fields = {
    'customerId': 501250113003712,
    'fields': [
        {
            'alias': '描述',
            'values': [
                '8天路飞Python训练营'
            ]
        },
        {
            'alias': '推广人',
            'values': [
                '未知'
            ]
        },
        {
            'alias': '渠道来源',
            'values': ['小鹅通']
        },
        {
            'alias': '下单时间',
            'values': [datetime.now().strftime('%Y-%m-%d %X')]
        },
        {
            'alias': '数分训练营',
            'values': ['S020']
        }
    ]
}

update_result = client.request(
    'post', '/v3/customer/update-by-id',
    json=update_fields
)
print(update_result)
