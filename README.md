## OpenAPI

### 概述

`OpenAPI` 集成了各类第三方的 SDK。

### 安装

```
pip3 install openapipy
```

### 使用

#### 阿里云 OSS

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

真实供应商联调请使用仓库内的[独立示例包](examples/media_generation/README.md)。复制 `.env.example` 保存供应商配置，通过 `set -a; source examples/media_generation/.env; set +a` 导入系统环境变量；请求输入和参考参数直接在对应能力脚本顶部修改。再按文档逐项执行 `python -m examples.media_generation.<provider>.<capability>`。脚本不会一次性触发所有计费能力；异步任务会先保存 `TaskRef`，超时后可继续查询。

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
