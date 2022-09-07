from openapi.providers.xiaoetong import Client

from examples.config import config

print(config)
client = Client(**config['xiaoetong'])
client.add_webhook(config['openapi_webhook'])


if __name__ == '__main__':
    print(client.request('post', '/xe.distributor.list.get/1.0.0', data={}))
