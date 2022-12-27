# 496831983505792

from openapi.providers.crm.tanmarket import Client

from examples.config import config

c = config['tanmarket']
c.pop('filepath')
client = Client(**c)
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

# result = client.request('post', '/v3/customer-relation/edit-field', json={
#     'customerId': 496831983505792, 'qwUserId': 'woJEYhCQAAG_I2LlJHPlfp9xJyZDfsGw',
#     'field': '描述', 'valueAsText': '嗷嗷嗷'
# })
# print(result)
#
# result = client.request('post', '/v3/customer/list-customer-of-search', json={
#     'customerId': 496831983505792
# })
# print(result)

# result = client.request('post', '/v3/common/user/info', json={
#     'mobile': 18803561683
# })
# print(result)


result = client.request('post', '/v3/customer/list-customer-of-search', json={
    'searchKey': 18099050926
})
print(result)
for item in result.data['data']:
    # print(item.keys())
    print(item.keys())
    print(item)

# Using
# result = client.request('post', '/v3/common/customer/info', json={
#     'field': {
#         'fieldId': '106074',
#         'values': '87a6f15cade25330062d363ef67a3382'
#     }
# })
# print(result)
