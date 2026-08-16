# 数字人

`openapi.providers.media_generation` 中支持数字人的三家供应商：火山引擎、阿里云百炼、飞影。统一入口为 `media.avatar` 领域：

- `media.avatar.render(DigitalHumanRequest, provider=...)` —— 生成数字人视频
- `media.avatar.validate_image(image, provider=...)` —— 生成前校验人像素材
- `media.avatar.clone(AvatarCloneRequest, provider=...)` —— 克隆形象（仅飞影）
- `media.avatar.list(page, size, provider=...)` —— 形象列表（仅飞影）
- `media.avatar.upload(FileUploadRequest, provider=...)` —— 上传本地素材（仅飞影）

请求模型 `DigitalHumanRequest` 定义在 `openapi/providers/media_generation/models.py`，不同供应商使用其中不同字段组合。

| 供应商 | 默认模型 | 生成方式 | 人像校验 | 形象克隆 |
| --- | --- | --- | --- | --- |
| 火山引擎 | `jimeng_realman_avatar_picture_omni_v15`（OmniHuman） | 图片 + 音频 | ✅ | — |
| 阿里云百炼 | `wan2.2-s2v`（Wan S2V） | 图片 + 音频 | ✅ | — |
| 飞影 | HiFly V2 | 形象 + 音频 / 形象 + 文本语音 | — | ✅ |

## 火山引擎 OmniHuman

- 输入：`image_url` + `audio_url`（公网 URL），支持 `prompt`、`seed` 和 `parameters` 透传
- 限制：输出分辨率与比例由原图推导，不支持自定义
- 人像校验：`jimeng_realman_avatar_object_detection`
- 凭证：access key / secret key（视觉智能接口）
- 官方文档：[数字人快速模式 OmniHuman](https://www.volcengine.com/docs/85621/1810469)（主体识别与视频生成）、[人像检测](https://www.volcengine.com/docs/85621/1829011)
- 示例：`examples/media_generation/volcengine/omnihuman.py`、`validate_digital_human_image.py`

## 阿里云百炼 Wan S2V

- 输入：`image_url` + `audio_url`（公网 URL）
- 限制：输出最高 720P、比例由原图推导；需北京地域和 workspace id
- 人像校验：`wan2.2-s2v-detect` 人脸检测
- 官方文档：[万相-数字人概览](https://help.aliyun.com/zh/model-studio/wan-s2v-overview/)、[wan2.2-s2v API 参考](https://help.aliyun.com/zh/model-studio/wan-s2v-api)
- 示例：`examples/media_generation/aliyun/digital_human.py`、`validate_digital_human_image.py`

## 飞影 HiFly V2

形象驱动，先克隆形象再生成：

- 生成：`avatar` 必填，两条路径二选一
  - `audio_url` 或 `file_id`：`/video/create_by_audio`
  - `text` + `voice`：`/video/create_by_tts`（文本转语音合成）
- 形象克隆：`create_avatar` 按图片（`/avatar/create_by_image`）或视频（`/avatar/create_by_video`）；本地素材先经 `media.avatar.upload` 上传拿 `file_id`
- 限制：不支持 `seed`、`resolution`、`ratio`，输出由素材推导；凭证为 token
- 官方文档：[飞影数字人 API V2](https://api.lingverse.co/hifly.html)（含形象创建、声音驱动、文本驱动、克隆等接口）
- 示例：`examples/media_generation/hifly/digital_human.py`、`clone_avatar.py`、`list_avatars.py`，完整链路（上传 → 克隆 → 复刻声音 → 生成）见 `examples/media_generation/workflows/digital_human_from_scratch.py`

## 通用说明

- 数字人生成均为异步任务：提交返回含 `TaskRef` 的 `ModelResult`，可序列化保存，服务重启后用 `media.task.wait()` 恢复轮询（本地超时不会取消云端任务）
- 失败统一抛 `ProviderAPIError`（含 `code`、`retryable`、`fallback_allowed`）；内容安全、人像不合规等错误不会跨供应商回退
