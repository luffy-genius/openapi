#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Date: 2022/11/21
from openapi.providers.feishu.open import Client

from examples.config import config

feishu_open_config = config['feishu']['open']

client = Client(feishu_open_config['app_id'], feishu_open_config['secret'])

# 编辑表格
result = client.request(
    'post', f'/sheets/v2/spreadsheets/{feishu_open_config["table_id"]}/values_prepend',
    json={
        'valueRange': {
            'range': '45BW2x!A2:T2',
            'values': [
                [
                    'string', 10, 'http://www.xx.com', '1231313123', '123sflkadj'
                ]
            ]
        }
    }
)
print(result)
