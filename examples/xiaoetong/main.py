from openapi.providers.xiaoetong import Client

from examples.config import config

# print(config)
client = Client(**config['xiaoetong'])
client.add_webhook(config['openapi_webhook'])

invited_result = client.request(
    'post', '/xe.distributor.customer.get/1.0.0',
    data={'uid': 'u_63453bb9e3555_9AQFzrH6iz'}
)
print(invited_result)


client.request(
    'post', '/xe.order.detail/1.0.0',
    data={'order_id': 'o_1665481738_63453c0a983e0_95395219'}
)
