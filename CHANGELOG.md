# Changelog

## 0.13.0

- 新增按领域组织的统一媒体客户端 `MediaClient` 和泛型 `ModelResult[T]` 响应。
- 新增火山、百炼和 DeepSeek 文本优化，以及火山、百炼和飞影文本转语音。
- 新增翻译后语音合成组合调用。
- 新增火山引擎 Seedream、Seedance 和 OmniHuman 1.5 接入。
- 新增阿里云百炼 Wan Image、Wan I2V 和 Wan S2V 接入。
- 新增飞影 HiFly V2 图片/视频数字人克隆、公共数字人列表、音频和 TTS 成片接入。
- 新增异步任务持久化引用、状态归一化、轮询等待和查询重试。
- 凭证改用 `SecretStr` 并由业务显式注入；保留原有 `openapi.providers.aliyun.Client`。
- OmniHuman 的官方 `volcengine` SDK 通过 `media-generation` extra 可选安装，不影响旧 API 用户。
