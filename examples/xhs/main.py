from datetime import datetime
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

r = client.request(
    'post', '/ark/open_api/v3/common_controller',
    action='order.getOrderDetail',
    data={
        'orderId': 'P718870545250225361'
    }
)
address_id = r.data['openAddressId']
print(address_id)

# r = client.request(
#     'post', '/ark/open_api/v3/common_controller',
#     action='order.getOrderReceiverInfo',
#     data={
#         'accessToken': config['xhs']['token'],
#         'receiverQueries': {
#             'orderId': 'P718870545250225361',
#             'openAddressId': address_id
#         }
#     }
# )
# print(r)
# client.make_token(**info)

r = client.request(
    'post', '/ark/open_api/v3/common_controller',
    action='data.batchDecrypt',
    data={
        'baseInfos': [
            {
                'dataTag': order_id,
                'encryptedData': '#O/TUHCniXiCEbZKi06W0NE3aCHmiw6hlDxi1wabfz2U=#O/TUHCniXiCEbZKi06W0NAP/QQxFlmN4IBXB3iu5Csc1kGKQhS693psz9eci0XbEFlowN4IyD9VUDhL2eX2k5h2kTY53vwktNnxKVy83nWw=#2##'
            },
            {
                'dataTag': order_id,
                'encryptedData': '#O/TUHCniXiCEbZKi06W0NHqMLy7peAQiu8VRjWCmJVA=#O/TUHCniXiCEbZKi06W0NAP/QQxFlmN4IBXB3iu5Csc1kGKQhS693psz9eci0XbEV2DSoCHAYct0sQIvVGxQz6zf/OswYhtN4W9+jxWAnsc=#3##'
            },
        ],
        'actionType': 2, 'appUserId': ''
    }
)
print(r)

