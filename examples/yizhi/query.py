from openapi.providers.yizhi import Client

from examples.config import config

# print(config)
client = Client(**config['yizhi'])
client.add_webhook(config['openapi_webhook'])

result = client.request(
    'post', '/orderList',
    data={'page': '1', 'type': '1'}
)
print(result)
