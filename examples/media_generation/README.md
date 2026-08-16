# 媒体供应商真实联调示例

这些脚本只存在于源码仓库，不随 `openapipy` 安装包发布。每条命令只调用一项能力；运行计费能力即表示确认该次云端调用及可能产生的费用。

先在仓库根目录准备环境变量：

```bash
cp examples/media_generation/.env.example examples/media_generation/.env
# 编辑 .env，只填写本次脚本需要的凭证、模型、voice/avatar 等配置
set -a
source examples/media_generation/.env
set +a
```

脚本不自动加载 `.env`。文本、提示词、素材 URL、图片/视频选项、音频配置和供应商透传参数都定义在对应能力脚本顶部，可直接按需修改。示例中的 `cdn.example.com` 只是占位地址，真实联调前必须替换成供应商可访问的公网 URL；能力脚本不会自动上传本地素材，只有数字人工作流会显式调用 `media.avatar.upload` 上传本地文件。未设置的可选模型沿用 SDK 默认值。

异步任务会先把 `TaskRef` 写入 `MEDIA_OUTPUT_DIR`，再按照 `MEDIA_TASK_TIMEOUT` 和 `MEDIA_POLL_INTERVAL` 轮询；本地超时不会取消云端任务。

## DeepSeek

```bash
python -m examples.media_generation.deepseek.text_optimization
```

## 阿里云百炼

```bash
python -m examples.media_generation.aliyun.text_optimization
python -m examples.media_generation.aliyun.text_to_speech
python -m examples.media_generation.aliyun.text_to_image
python -m examples.media_generation.aliyun.image_to_image
python -m examples.media_generation.aliyun.image_to_video
python -m examples.media_generation.aliyun.validate_digital_human_image
python -m examples.media_generation.aliyun.digital_human
```

除图片校验外，百炼脚本需要 `MEDIA_ALIYUN_WORKSPACE_ID`。数字人能力当前要求北京地域。

## 火山引擎

```bash
python -m examples.media_generation.volcengine.text_optimization
python -m examples.media_generation.volcengine.text_to_speech
python -m examples.media_generation.volcengine.text_to_image
python -m examples.media_generation.volcengine.image_to_image
python -m examples.media_generation.volcengine.image_to_video
python -m examples.media_generation.volcengine.validate_digital_human_image
python -m examples.media_generation.volcengine.omnihuman
```

文本、图片和视频使用 Ark API key；语音使用 speech app ID/token；图片校验和 OmniHuman 使用 access key/secret key。OmniHuman 还需要安装 `openapipy[media-generation]`。

## 飞影 HiFly

```bash
python -m examples.media_generation.hifly.text_to_speech
python -m examples.media_generation.hifly.list_avatars
python -m examples.media_generation.hifly.clone_avatar
python -m examples.media_generation.hifly.digital_human
```

形象克隆必须在 `hifly/clone_avatar.py` 的 `IMAGE_URL` 和 `VIDEO_URL` 中恰好保留一个值。数字人若在 `hifly/digital_human.py` 中设置了 `AUDIO_URL` 会优先使用音频；将其设为 `None` 后，脚本改用 `TEXT` 和 `.env` 中的 `MEDIA_HIFLY_SPEECH_VOICE`。

## HiFly 完整数字人工作流

一条命令走完"上传素材 → 克隆形象 → 复刻声音 → 生成数字人视频"全流程，只需配置 `.env` 中的 `MEDIA_HIFLY_TOKEN`。素材支持公网 URL 或本地文件路径，在脚本顶部常量中切换：

```bash
python -m examples.media_generation.workflows.digital_human_from_scratch
```

| 常量 | 说明 |
|---|---|
| `AVATAR_IMAGE_URL` / `AVATAR_IMAGE_PATH` | 形象克隆来源（图片），二选一；本地图片上传后走 `image_file_id` |
| `AVATAR_VIDEO_URL` / `AVATAR_VIDEO_PATH` | 形象克隆来源（视频），与图片互斥；本地视频上传后走 `video_file_id` |
| `VOICE_AUDIO_URL` / `VOICE_AUDIO_PATH` | 声音样本来源，二选一 |
| `DIGITAL_HUMAN_TEXT` | 数字人口播文本 |
| `AVATAR_CLONE_MODEL` | 图片克隆模型，默认 2 |

数字人视频的清晰度与比例由 HiFly 按素材推导，不单独设置。中间每一步的 `TaskRef` 都会持久化到 `MEDIA_OUTPUT_DIR`，即使脚本中断也可用 `resume_task` 单独恢复。

## SiliconFlow

```bash
python -m examples.media_generation.siliconflow.text_to_speech
```

需要 `MEDIA_SILICONFLOW_API_KEY` 和 `MEDIA_SILICONFLOW_MODEL`；`MEDIA_SILICONFLOW_BASE_URL` 默认国内站 `https://api.siliconflow.cn/v1`，国际站显式覆盖。使用已有持久音色时把 `VOICE` 常量和 `MEDIA_SILICONFLOW_VOICE` 设为音色 URI；改用参考音频时置空 `VOICE`，设置 `REFERENCE_AUDIO_PATH` 与 `REFERENCE_TEXT`（参考音频与 `voice` 互斥）。

## DeepSeek 翻译后合成语音

设置 `MEDIA_WORKFLOW_SPEECH_PROVIDER` 为 `aliyun`、`volcengine` 或 `hifly`，填写对应语音凭证、模型和 voice，并在 `workflows/translate_to_speech.py` 修改翻译和语音参数：

```bash
python -m examples.media_generation.workflows.translate_to_speech
```

## 恢复异步任务

`MEDIA_TASK_REF` 可直接保存 TaskRef JSON，也可指向此前生成的 JSON 文件：

```bash
export MEDIA_TASK_REF=examples/media_generation/output/aliyun-image_to_video-example.json
python -m examples.media_generation.resume_task
```

恢复脚本只查询和等待，不会重新提交任务。成功时仅输出状态、文本、URL、avatar ID 等摘要；Base64 音频会解码写入输出目录，不会打印到终端。失败、非成功终态和超时均以非零状态退出。
