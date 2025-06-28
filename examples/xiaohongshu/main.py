from datetime import datetime

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.hashes import MD5, Hash
from openapi.providers.xhs import Client

from examples.config import config

# print(config)
client = Client(
    app_id=config['xhs']['app_id'], secret=config['xhs']['secret'],
    user_id=config['xhs']['user_id'], seller_id=config['xhs']['seller_id']
)
client.add_webhook(config['openapi_webhook'])
order_id = config['xhs']['test']['order_id']

info = config['xhs']['test']['info']
info['expires_at'] = datetime.fromtimestamp(info['expires_at'] / 1000)

# r = client.request(
#     'post', '/ark/open_api/v3/common_controller',
#     action='oauth.getAccessToken',
#     data={
#         'code': config['xhs']['code']
#     }
# )
# print(r)

# r = client.request(
#     'post', '/ark/open_api/v3/common_controller',
#     action='order.getOrderDetail',
#     data={
#         'orderId': order_id
#     }
# )
# address_id = r.data['openAddressId']
# print(r)

# r = client.request(
#     'post', '/ark/open_api/v3/common_controller',
#     action='order.getOrderReceiverInfo',
#     data={
#         'receiverQueries': {
#             'orderId': order_id,
#             'openAddressId': address_id
#         }
#     }
# )
# print(r)
# client.make_token(**info)

# r = client.request(
#     'post', '/ark/open_api/v3/common_controller',
#     action='data.batchDecrypt',
#     data={
#         'baseInfos': [
#             {
#                 'dataTag': order_id,
#                 'encryptedData': r.data['receiverInfos'][0]['receiverName']
#             },
#             {
#                 'dataTag': order_id,
#                 'encryptedData': r.data['receiverInfos'][0]['receiverPhone']
#             },
#         ],
#         'actionType': 2, 'appUserId': ''
#     }
# )
# print(r)


r = client.request(
    'post', '/ark/open_api/v3/common_controller',
    action='common.getCategories', data={'categoryId': '5a310e243f7d1712823ba480'}
)
print(r)


def calculate_signature(params, api_key):
    data = f'{params["path"]}?app-key={params["app-key"]}&timestamp={params["timestamp"]}'
    h = Hash(algorithm=MD5(), backend=default_backend())
    h.update(f'{data}{api_key}'.encode('utf-8'))
    return h.finalize().hex()


sign = calculate_signature(
    params={
        'path': '',
        'app-key': client.app_id,
        'timestamp': '17033916261',
    },
    api_key=client.secret
)
print(sign)
