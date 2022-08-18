## OpenAPI

### 概述

`OpenAPI` 集成了各类第三方的 SDK。

### 安装

```
pip3 install git+https://github.com/luffy-genius/openapi.git
```

### 使用

#### 抖店

```python3
from openapi.providers.doudian import Client as DouDianClient, Result

client = DouDianClient('your_appid', 'your_secret', 'your_shop_id')
result: Result = client.request('post', '/product/listV2', data={'page': 1, 'size': 10})
print(result)
```

#### 小鹅通

```python3
from openapi.providers.xiaoetong import Client as XiaoetongClient, Result

client = XiaoetongClient('your_appid', 'your_secret', 'your_client_id')
result: Result = client.request('post', '/xe.distributor.list.get/1.0.0', data={})
print(result)
```

### 支持

```
2022 By ZhichaoLiu.
```