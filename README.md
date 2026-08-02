## OpenAPI

### 概述

`OpenAPI` 集成了各类第三方的 SDK。

### 安装

```
pip3 install openapipy
```

### 使用

#### 统一媒体客户端

`openapi.providers.media_generation` 提供火山引擎、阿里云百炼、飞影和 DeepSeek 的统一媒体接口。客户端按文本、语音、图片、视频、数字人、任务和组合工作流划分领域入口。凭证和文本模型由业务显式传入，SDK 不读取凭证环境变量。所有方法返回泛型 `ModelResult[T]`，原始供应商响应保存在 `result.data`。

OmniHuman 使用火山官方 SDK，需要额外安装：

```bash
pip install 'openapipy[media-generation]'
```

```python
from openapi.providers.media_generation import (
    AliyunConfig,
    AudioConfig,
    DeepSeekConfig,
    ImageGenerationRequest,
    MediaClient,
    ModelProvider,
    TextOptimizationRequest,
    TextToSpeechRequest,
    TranslateToSpeechRequest,
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

audio = media.speech.synthesize(
    TextToSpeechRequest(
        text='Hello from the media client.',
        model='qwen-audio-3.0-tts-flash',
        voice='longanhuan_v3.6',
        language='en',
        audio_config=AudioConfig(format='wav', sample_rate=24000),
    ),
    provider=ModelProvider.ALIYUN,
)
print(audio.output.urls or [audio.output.audio_base64])

translated_audio = media.workflow.translate_to_speech(
    TranslateToSpeechRequest(
        text='今天天气很好。',
        source_language='Chinese',
        target_language='English',
        translation_model='your-deepseek-model',
        speech_model='qwen-audio-3.0-tts-flash',
        voice='longanhuan_v3.6',
    ),
    text_provider=ModelProvider.DEEPSEEK,
    speech_provider=ModelProvider.ALIYUN,
)
```

异步提交返回的 `TaskRef` 包含供应商、操作、任务 ID 和必要的模型信息，可序列化保存，并在服务重启后传给 `media.task.get()` 或 `media.task.wait()`。`wait()` 本地超时不会取消云端任务。单次请求的 `model` 会覆盖该次调用使用的模型，但不会修改客户端默认配置。

能力范围：

| 能力 | 火山引擎 | 阿里云百炼 | 飞影 | DeepSeek |
| --- | --- | --- | --- | --- |
| 文本优化 / 翻译 | Ark | 兼容模式 | — | Chat Completions |
| 文本转语音 | 豆包语音 | Qwen-Audio / CosyVoice | HiFly V2 | — |
| 文生图 / 图生图 | Seedream | Wan Image | — | — |
| 图生视频 | Seedance | Wan I2V | — | — |
| 数字人 | OmniHuman | Wan S2V | HiFly V2 | — |
| 图片 / 视频数字人克隆 | — | — | HiFly V2 | — |

`AudioConfig` 中的 `speech_rate`、`loudness_rate` 和 `pitch_rate` 使用统一浮点倍率，`1.0` 表示供应商默认值。语速和音高支持 `0.5`–`2.0`，响度支持 `0.1`–`2.0`。阿里云分别转换为 `rate`、`volume=round(50*loudness_rate)` 和 `pitch`，火山引擎分别转换为 `speed_ratio`、`volume_ratio` 和 `pitch_ratio`；飞影不支持这三个调节项。显式的 `AudioConfig` 值优先于 `parameters` 中的供应商透传值。

语音的多语言能力是“合成传入的目标语言文本”，不会自动翻译；中文文案直接生成英文音频请使用 `media.workflow.translate_to_speech()`。组合调用会在翻译前检查语音供应商的能力、配置和音频选项，避免已知无法合成时仍发起翻译请求。SDK 不上传本地文件、不下载或转存结果。完整示例见 [`examples/media_generation.py`](examples/media_generation.py)。

#### 支付宝

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

#### 微信

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

#### 抖店

> https://op.jinritemai.com/docs/api-docs/13/54

```python3
from openapi.providers.doudian import Client as DouDianClient, Result

client = DouDianClient('your_appid', 'your_secret', 'your_shop_id')
# 获取商品列表
result: Result = client.request('post', '/product/listV2', data={'page': 1, 'size': 10})
print(result)
```

#### 小鹅通

> https://api-doc.xiaoe-tech.com/?s=/2&page_id=420

```python3
from openapi.providers.xiaoetong import Client as XiaoetongClient, Result

client = XiaoetongClient('your_appid', 'your_secret', 'your_client_id')
# 获取分销人列表
result: Result = client.request('post', '/xe.distributor.list.get/1.0.0', data={})
print(result)
```

### 支持

```
2022 By ZhichaoLiu.
```
