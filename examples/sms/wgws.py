from openapi.providers.sms.wgws import Client

from examples.config import config

client = Client(**config['sms']['wgws'])
client.add_webhook(config['openapi_webhook'])

content = ''
print(content)
# For testing
result = client.request(
    'post', '/wgws/OrderServlet',
    data={'content': content, 'calledNumber': f"{config['sms']['to']}"}
)
print(result)
print(result.error == client.codes.SUCCESS)
