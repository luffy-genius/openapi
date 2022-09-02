from openapi.providers.wechat import Client

from examples.config import config

client = Client(**config['wechat'])

client.fetch_access_token()
