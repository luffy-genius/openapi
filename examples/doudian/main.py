from openapi.providers.doudian import Client

from examples.config import config

client = Client(**config['doudian'])
client.add_webhook(config['openapi_webhook'])


if __name__ == '__main__':
    result = client.request('post', '/order/orderDetail', data={'shop_order_id': '4978168757401566318'})
    print(result)
