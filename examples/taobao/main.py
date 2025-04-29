from openapi.providers.taobao import Client, calculate_signature
from examples.config import config

app_key = config['taobao']['app_key']
secret = config['taobao']['secret']

d = {
    'app_key': app_key,
    'method': 'taobao.trade.fullinfo.get',
    'v': '2.0',
    'timestamp': '2024-01-09 00:00:03',
    'partner_id': 'top-apitools',
    'session': '6100a040fa611a381b3cd37eca8a1c31df1ff56c6970e642212108025244',
    'format': 'json',
    'sign_method': 'md5',
    'fields': 'tid,type,status,payment,orders,promotion_details',
    'tid': '3725362658812595205'
}
print(calculate_signature(d, secret))

client = Client(app_id=app_key, secret=secret)
r = client.request(
    'get', 'taobao.trade.fullinfo.get',
    data={
        'fields': 'tid,type,status,payment,orders,promotion_details',
        'tid': '3725362658812595205'
    }
)
print(r)
