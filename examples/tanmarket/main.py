from openapi.providers.tanmarket import Client

from examples.config import config

client = Client(**config['tanmarket'])
client.add_webhook(config['openapi_webhook'])

response = client.request(
    'post', '/echo',
    json={'hello': 'tanmarket'}
)
print(response.json())
