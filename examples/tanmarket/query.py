# 496831983505792

from openapi.providers.tanmarket import Client

from examples.config import config

client = Client(**config['tanmarket'])
client.add_webhook(config['openapi_webhook'])

# print(client.request('post', '/v3/common/customer/info', json={
#     'field': {
#         'fieldId': '微信号', 'values': '123'
#     }
# }))

# result = client.request('post', '/v3/clue/edit-field', json={
#     'customerId': 496831983505792,
#     'field': '描述', 'valueAsText': '哭哭哭'
# })
# print(result)

result = client.request('post', '/v3/customer-relation/edit-field', json={
    'customerId': 496831983505792, 'qwUserId': 'woJEYhCQAAG_I2LlJHPlfp9xJyZDfsGw',
    'field': '描述', 'valueAsText': '嗷嗷嗷'
})
print(result)

result = client.request('post', '/v3/customer/list-customer-of-search', json={
    'customerId': 496831983505792
})
print(result)
