import json
from openapi.providers.feishu.bot import Client

from examples.config import config

bot = Client()
# result = bot.request(
#     'post',
#     config['feishu']['bot'],
#     json={
#         'msg_type': 'text',
#         'content': {'text': 'request example'}
#     }
# )
# print(result)
with open('card.json') as f:
    content = json.loads(f.read())['content']
    result = bot.request(
        'post',
        config['feishu']['bot'],
        json={
            'msg_type': 'interactive',
            'card': content
        }
    )
    print(result)
