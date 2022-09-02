from openapi.providers.wechat import Client

client = Client(app_id='', secret='')

client.fetch_access_token()
