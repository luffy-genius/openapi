from typing import Dict
from openapi.providers.wechat.open import Client, Result

from examples.config import config


class OrderDetailResult(Result):
    order: Dict


client = Client(**config['wechat_channels'])
# client.add_webhook(config['openapi_webhook'])
result = client.request(
    'POST', endpoint='/channels/ec/order/get',
    data={
        'order_id': '3713399872155682304'
    }, is_oauth=False, result_processor=OrderDetailResult
)
print(result)
