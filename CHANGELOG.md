# Changelog

## 0.14.0

- 新增框架无关的 `openapi.providers.storages.aliyun_oss` 客户端，统一对象上传、流式下载、幂等删除、查询与分页列表。
- 新增对象存储领域包 `openapi.providers.storages`，导出供应商中立的 interface、元数据模型和异常分类，为腾讯云 COS、火山引擎 TOS 等后续 adapter 保留稳定 seam。
- 新增公网/CDN 对象 URL、签名 URL 和 URL 反解能力，统一供应商异常与对象元数据模型；`download_to()` 的本地磁盘错误不再误报为 OSS 供应商错误。
- OSS 客户端使用 `ProviderAuthV4` 和显式 region；`oss2` 通过 `openapipy[aliyun-oss]` extra 可选安装。
- 媒体生成错误新增统一错误码、重试/降级建议和“远程任务可能已存在”标记，内容安全、非法输入和所有权错误禁止跨供应商降级；供应商错误码按大小写、连字符与驼峰归一化后匹配。
- 新增 SiliconFlow 文本转语音（官方 `/audio/speech`）：请求级参考音频使用动态 references，不再隐式创建持久音色；`base_url` 默认国内站、国际站可覆盖；模型由请求指定，输出格式、采样率及其组合、语速与增益集中校验，显式使用非流式响应。
- 图片、图生视频和数字人请求增加强类型参数约束，禁止 `parameters` 覆盖标准字段；提示词扩写实际透传。Wan i2v 仅接受官方声明的 resolution/duration/prompt_extend/watermark，比例、seed 与负向提示均拒绝；Wan S2V 与 HiFly 数字人的清晰度与比例由供应商按素材推导；火山引擎图生视频分辨率发送时转为小写。
- HiFly 形象克隆素材拆分为 `image_file_id` / `video_file_id`，本地图片与视频分别路由到图片/视频克隆接口；`list_voices()` 增加 `kind` 参数，默认查询自克隆音色（`kind=2` 查询公共音色）。
- 阿里 ASR 转写改用 workspace API 根地址并将供应商参数嵌套至 `parameters`，遵循官方契约单次仅支持 1 个 URL；转写结果下载启用查询重试，已成功任务不再触发跨供应商降级。
- `MediaClient` 新增流式 `download_to()`，`download()` 的 HTTP/网络错误统一分类；翻译工作流完整保留原始异常的重试与降级元数据。

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
