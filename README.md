## OpenAPI

### 概述

`OpenAPI` 集成了各类第三方的 SDK：支付、开放平台与协同、电商与知识付费、视频云、短信、CRM、对象存储和统一媒体客户端。所有 provider 共享统一的 `BaseClient` / `BaseResult` 抽象：凭证由业务显式注入、access token 自动缓存与刷新、webhook 回调签名校验；媒体与存储模块额外提供机器可读的错误分类（重试 / 降级建议）与供应商中立的接口抽象。

| 分类 | Provider | 模块 | 说明 |
| --- | --- | --- | --- |
| 对象存储 | 阿里云 OSS | `openapi.providers.storages.aliyun_oss` | 上传、流式下载、分页列表、签名 URL，V4 签名 |
| 统一媒体 | 火山引擎 / 阿里云百炼 / 飞影 / SiliconFlow / DeepSeek | `openapi.providers.media_generation` | 文本、语音、图片、视频、数字人 |
| 支付 | 支付宝 | `openapi.providers.alipay` | 开放平台网关，RSA2 证书签名 |
| 支付 | 微信支付 | `openapi.providers.wechat.pay` | V2 XML 协议 |
| 支付 | 联想支付 | `openapi.providers.lenovo` | 云平台 REST，RSA 签名 |
| 开放平台 | 微信服务号 / 视频号 | `openapi.providers.wechat.open` | 网页授权、消息加解密 |
| 开放平台 | 飞书 | `openapi.providers.feishu.open` / `feishu.bot` | 开放平台与群组机器人 |
| 开放平台 | 小红书 | `openapi.providers.xhs` | ark 电商开放平台 |
| 电商 | 抖店 | `openapi.providers.doudian` | 抖音电商开放平台 |
| 知识付费 | 小鹅通 | `openapi.providers.xiaoetong` | 内容分销 |
| 知识付费 | 易知课堂 | `openapi.providers.yizhi` | 开放 API |
| 视频云 | Polyv | `openapi.providers.polyv` | 播放安全 token |
| 短信 | 赛邮 / 中网信 | `openapi.providers.sms.submail` / `sms.wgws` | 云通信短信 |
| CRM | 探马 / 云朵 | `openapi.providers.crm.tanmarket` / `crm.yunduo` | 客户线索管理 |
| 通用 | 阿里云 RPC | `openapi.providers.aliyun` | 通用 RPC 风格，HMAC-SHA1 签名 |

### 安装

```
pip3 install openapipy
```

阿里云 OSS 与火山 OmniHuman 依赖官方 SDK，通过 extra 安装：

```bash
pip install 'openapipy[aliyun-oss]'
pip install 'openapipy[media-generation]'
```

### 使用

#### 对象存储

`openapi.providers.storages.aliyun_oss` 提供框架无关的对象上传、下载、删除、查询、分页列表和 URL 处理，使用推荐的 V4 签名。OSS SDK 通过 extra 安装：

```bash
pip install 'openapipy[aliyun-oss]'
```

```python
from pydantic import SecretStr

from openapi.providers.storages.aliyun_oss import Client, OSSConfig

oss = Client(
    OSSConfig(
        access_key_id=SecretStr('your-access-key-id'),
        access_key_secret=SecretStr('your-access-key-secret'),
        endpoint='oss-cn-hangzhou-internal.aliyuncs.com',
        public_endpoint='oss-cn-hangzhou.aliyuncs.com',
        region='cn-hangzhou',
        bucket_name='your-bucket',
    )
)

key = oss.put_object('uploads/example.txt', b'hello', headers={'Content-Type': 'text/plain'})
print(oss.object_url(key))
print(oss.sign_url(key))
```

凭证、region 和 endpoint 必须由业务显式传入；库不会读取环境变量。`put_object()` 返回对象 key，`object_url()` 返回无签名公网 URL，私有对象应使用 `sign_url()`。未配置 `public_endpoint` 时，会从标准的 `*-internal.aliyuncs.com` 内网 endpoint 推导公网 endpoint。`iter_objects()` 自动处理 `ListObjectsV2` 分页。

业务层需要与具体云厂商解耦时，应依赖 `openapi.providers.storages.ObjectStorageClient`，并在应用组装位置注入 `storages.aliyun_oss.Client`。`ObjectMetadata` 和 `ObjectStorageError` 等中立类型也由 `storages` 包导出。未来腾讯云 COS、火山引擎 TOS 将作为并列 adapter 实现同一 interface；在第二个 adapter 落地前不提供只有转发作用的通用 Client 或注册表。

#### 统一媒体客户端

`openapi.providers.media_generation` 提供火山引擎、阿里云百炼、飞影、SiliconFlow 和 DeepSeek 的统一媒体接口。客户端按文本、语音、图片、视频、数字人、任务和组合工作流划分领域入口。凭证和文本模型由业务显式传入，SDK 不读取凭证环境变量。所有方法返回泛型 `ModelResult[T]`，原始供应商响应保存在 `result.data`。

OmniHuman 使用火山官方 SDK，需要额外安装：

```bash
pip install 'openapipy[media-generation]'
```

```python
from openapi.providers.media_generation import (
    AliyunConfig,
    DeepSeekConfig,
    ImageGenerationRequest,
    MediaClient,
    ModelProvider,
    TextOptimizationRequest,
)

media = MediaClient.create(
    AliyunConfig(api_key='your-bailian-api-key', workspace_id='your-workspace-id'),
    DeepSeekConfig(api_key='your-deepseek-api-key'),
)

text = media.text.optimize(
    TextOptimizationRequest(text='一段待润色的文案', model='your-deepseek-model'),
    provider=ModelProvider.DEEPSEEK,
)
print(text.output.text)

image = media.image.generate(
    ImageGenerationRequest(prompt='一幅极简主义山水画'),
    provider=ModelProvider.ALIYUN,
)
print(image.output.urls)
```

文本转语音、语音识别、声音复刻、图生图、图生视频、数字人和翻译后合成等能力按同一模式调用（`media.speech.synthesize(...)`、`media.video.from_image(...)`、`media.workflow.translate_to_speech(...)` 等），真实联调见[独立示例包](examples/media_generation/README.md)。

异步提交返回的 `TaskRef` 包含供应商、操作、任务 ID 和必要的模型信息，可序列化保存，并在服务重启后传给 `media.task.get()` 或 `media.task.wait()`。`wait()` 本地超时不会取消云端任务。单次请求的 `model` 会覆盖该次调用使用的模型，但不会修改客户端默认配置。

`ProviderAPIError` 提供标准 `code`、供应商原始 `provider_code`、`http_status`、`retryable`、`fallback_allowed` 和 `remote_task_may_exist`。业务层只应对明确允许的网络、限流、鉴权和服务故障进行降级；内容安全、非法输入和所有权错误不允许切换供应商。任务轮询失败或提交超时时，`remote_task_may_exist=True` 表示上层应记录为未知状态，不得立即改投备用模型。异步任务终态的 `ModelResult` 也包含 `error_kind`、`retryable` 和 `fallback_allowed`。

能力范围：

| 能力 | 火山引擎 | 阿里云百炼 | 飞影 | DeepSeek | SiliconFlow |
| --- | --- | --- | --- | --- | --- |
| 文本优化 / 翻译 | Ark | 兼容模式 | — | Chat Completions | — |
| 文本转语音 | 豆包语音 | Qwen-Audio / CosyVoice | HiFly V2 | — | create-speech |
| 文生图 / 图生图 | Seedream | Wan Image | — | — | — |
| 图生视频 | Seedance | Wan I2V | — | — | — |
| 数字人 | OmniHuman | Wan S2V | HiFly V2 | — | — |
| 图片 / 视频数字人克隆 | — | — | HiFly V2 | — | — |

`AudioConfig` 中的 `speech_rate`、`loudness_rate` 和 `pitch_rate` 使用统一浮点倍率，`1.0` 表示供应商默认值。语速和音高支持 `0.5`–`2.0`，响度支持 `0.1`–`2.0`。阿里云分别转换为 `rate`、`volume=round(50*loudness_rate)` 和 `pitch`，火山引擎分别转换为 `speed_ratio`、`volume_ratio` 和 `pitch_ratio`；飞影不支持这三个调节项。显式的 `AudioConfig` 值优先于 `parameters` 中的供应商透传值。

SiliconFlow 文本转语音调用官方 `/audio/speech` 接口：`base_url` 默认国内站 `https://api.siliconflow.cn/v1`，国际站通过 `base_url` 覆盖；模型由请求的 `model` 指定。请求级参考音频通过动态 `references` 传入（`reference_audio` + `reference_text`，音频为官方 `data:audio/*;base64,...` 形式），与 `voice` 互斥；已有持久音色通过 `default_voice` 使用，参考音频不再隐式创建持久音色。输出格式（`mp3`/`opus`/`wav`/`pcm`）、采样率及其与格式的组合（如 `mp3` 仅 `32000`/`44100`、`opus` 仅 `48000`）、语速（`0.25`–`4.0`）和增益（`-10`–`10` dB）由 SDK 集中校验；SDK 显式使用非流式响应。

语音的多语言能力是“合成传入的目标语言文本”，不会自动翻译；中文文案直接生成英文音频请使用 `media.workflow.translate_to_speech()`。组合调用会在翻译前检查语音供应商的能力、配置和音频选项，避免已知无法合成时仍发起翻译请求。SDK 不会自动转存供应商结果；业务可用 `media.download()` 下载临时 URL，大文件使用流式 `media.download_to(url, destination)` 避免整体载入内存，再通过注入的对象存储客户端持久化。下载的本地写盘失败以 `OSError` 上抛，远端 HTTP/网络错误统一分类为 `ProviderAPIError`。

#### 支付

##### 支付宝

> https://opendocs.alipay.com/open/270/105898

```python3
from openapi.providers.alipay import Client, Result
client = Client(
    app_id='2016081500252288',
    app_private_key_path='./resources/app_private_test2',
    app_cert_public_key_path='./resources/appCertPublicKey_2016081500252288_test.crt',
    alipay_root_cert_path='./resources/alipayRootCert_test.crt',
    alipay_cert_public_key_path='./resources/alipayCertPublicKey_RSA2_test.crt',
    is_sandbox=True
)

pc_pay_params = client.build_query_params(client.build_params(
    'alipay.trade.page.pay',
    {
        'subject': 'popmart-molly',
        'out_trade_no': 'pc123456',
        'total_amount': '999.99',
        'product_code': 'FAST_INSTANT_TRADE_PAY'
    },
    notify_url='http://47.94.172.250:9527/api/v1/pay/alipay/',
    return_url='http://47.94.172.250:9527/api/v1/pay/alipay/'
))
pc_pay_url = f'{client.API_BASE_URL}?{pc_pay_params}'
print(pc_pay_url)

result: Result = client.request(
    'get', 'alipay.trade.query',
    params={
        'out_trade_no': 'pc123456',
        # 'trade_no': ''
    }
)
print(result)
```

##### 微信支付

```python3
import json

from openapi.providers.wechat.pay import Client

wxpay_api = Client(
    app_id='app_id',
    mch_id='mch_id',
    api_key_path='api_key_path',
    is_sandbox=False
)

# 查询订单
result = wxpay_api.request(
    'post', '/pay/orderquery',
    data={
        # 'out_trade_no': '9wfafGR31rCytY68wSFcXCII',
        'transaction_id': '4200001591202211145504991626'
    }
)
print(result)

data = {
    'body': '米诺地尔町',
    'out_trade_no': '1232112359910',
    'total_fee': 1,
    'spbill_create_ip': '127.0.0.1',
    'notify_url': 'htt',
    'trade_type': 'NATIVE',
    'attach': json.dumps({'x': 1})
}

# 创建订单 -> pc
result = wxpay_api.request('post', '/pay/unifiedorder', data=data)
print(result)

# 创建订单 -> h5
data.update(trade_type='MWEB', out_trade_no='1231asd1222')
result = wxpay_api.request('post', '/pay/unifiedorder', data=data)
print(result)

# 创建订单 -> jsapi, 微信内
data.update(trade_type='JSAPI', out_trade_no='21321asd12311313', openid='ofwIAuEgpTZZwdPc1aort93xO')
result = wxpay_api.request('post', '/pay/unifiedorder', data=data)
print(result)
if result.result_code == wxpay_api.codes.SUCCESS:
    jsapi_data = wxpay_api.get_jsapi_data(result.data['prepay_id'])
    print(jsapi_data)
```

##### 联想支付

```python3
from openapi.providers.lenovo import Client, Result

client = Client(
    app_id='your_app_id',
    mch_id='your_mch_id',
    private_key_path='./resources/private_key.pem',
    public_key_path='./resources/public_key.pem',
)
# 发起请求（endpoint 为接口路径，数据由接口文档定义）
result: Result = client.request('/pay/create', data={'order_no': 'demo'})
print(result)
```

#### 开放平台与协同

##### 微信服务号 / 视频号

```python3
from openapi.providers.wechat.open import Client

client = Client(app_id='your_app_id', secret='your_secret')

# 网页授权地址 / 扫码登录地址
print(client.get_authorize_url(scope='snsapi_userinfo', state='state', redirect_uri='https://example.com/cb'))
print(client.get_qrcode_url(state='state', redirect_uri='https://example.com/cb'))

# 调用接口（endpoint 为公众号 / 视频号接口路径）
result = client.request('get', '/cgi-bin/user/info', params={'openid': 'openid'})
print(result)
```

##### 飞书

```python3
from openapi.providers.feishu.open import Client

client = Client(app_id='your_app_id', secret='your_secret')
result = client.request('get', '/contact/v3/users', params={'user_id_type': 'open_id'})
print(result)
```

群组机器人：

```python3
from openapi.providers.feishu.bot import Client as BotClient

bot = BotClient('your_bot_secret')
result = bot.request('post', 'v2/hook/your_hook_token', json={'msg_type': 'text', 'content': {'text': 'hello'}})
print(result)
```

##### 小红书

```python3
from openapi.providers.xhs import Client

client = Client(
    app_id='your_app_id',
    secret='your_secret',
    user_id='your_user_id',
    seller_id='your_seller_id',
)
# endpoint / action / 参数由小红书 ark 开放平台接口文档定义
result = client.request('post', '/ark/open_api/v3/common_controller', data={})
print(result)
```

#### 电商与知识付费

##### 抖店

> https://op.jinritemai.com/docs/api-docs/13/54

```python3
from openapi.providers.doudian import Client as DouDianClient, Result

client = DouDianClient('your_appid', 'your_secret', 'your_shop_id')
# 获取商品列表
result: Result = client.request('post', '/product/listV2', data={'page': 1, 'size': 10})
print(result)
```

##### 小鹅通

> https://api-doc.xiaoe-tech.com/?s=/2&page_id=420

```python3
from openapi.providers.xiaoetong import Client as XiaoetongClient, Result

client = XiaoetongClient('your_appid', 'your_secret', 'your_client_id')
# 获取分销人列表
result: Result = client.request('post', '/xe.distributor.list.get/1.0.0', data={})
print(result)
```

##### 易知课堂

```python3
from openapi.providers.yizhi import Client, Result

client = Client(app_id='your_app_id', secret='your_secret')
# endpoint 为易知课堂开放接口路径
result: Result = client.request('post', '/open-api/course/list', data={})
print(result)
```

#### 视频云

##### Polyv

> https://help.polyv.net/#/vod/api/playsafe/token/create_token

```python3
from openapi.providers.polyv import Client, Result

client = Client(user_id='your_user_id', secret='your_secret')
result: Result = client.request('post', '/playsafe/token/create_token', data={'vid': 'your_video_id'})
print(result)
```

#### 短信

##### 赛邮云

```python3
from openapi.providers.sms.submail import Client

client = Client(app_id='your_app_id', app_key='your_app_key')
result = client.request('post', '/message/xsend', data={'to': '138xxxx', 'project': 'your_project', 'vars': '{}'})
print(result)
```

##### 中网信

```python3
from openapi.providers.sms.wgws import Client

client = Client(app_id='your_app_id', app_key='your_app_key')
# endpoint 与参数由中网信短信接口文档定义
result = client.request('post', '/sms/send', data={})
print(result)
```

#### CRM

##### 探马

```python3
from openapi.providers.crm.tanmarket import Client as TanmarketClient

client = TanmarketClient(app_id='your_app_id', app_key='your_app_key')
result = client.request('post', '/api/lead/list', data={})
print(result)
```

##### 云朵

```python3
from openapi.providers.crm.yunduo import Client as YunduoClient

client = YunduoClient(company_id='your_company_id')
result = client.request('post', '/api/customer/list', sign_key='your_sign_key', sign_type='MD5', data={})
print(result)
```

#### 通用阿里云 RPC

适用于未单独封装的阿里云 OpenAPI 服务（HMAC-SHA1 签名）：

```python3
from openapi.providers.aliyun import Client, Result

client = Client('your_app_id', 'your_secret')
# 以 dysmsapi 短信为例（联调脚本见 examples/aliyun）
result: Result = client.request(
    'post',
    prefix='dysmsapi',
    action='SendSms',
    version='2017-05-25',
    params={'PhoneNumbers': '138xxxx', 'SignName': 'your_sign', 'TemplateCode': 'SMS_xxx', 'TemplateParam': '{}'},
)
print(result)
```

#### 联调示例

仓库的 `examples/` 目录按 provider 组织真实联调脚本，凭证与 webhook 等配置统一放在 `examples/config.yaml`（可复制为 `config.dev.yaml` 后填写）。媒体供应商的联调说明独立维护在 [examples/media_generation/README.md](examples/media_generation/README.md)。

### 支持

```
2022 By ZhichaoLiu.
```
