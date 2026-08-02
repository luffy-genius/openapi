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

脚本不自动加载 `.env`。文本、提示词、素材 URL、图片/视频选项、音频配置和供应商透传参数都定义在对应能力脚本顶部，可直接按需修改。示例中的 `cdn.example.com` 只是占位地址，真实联调前必须替换成供应商可访问的公网 URL；SDK 不会上传本地素材。未设置的可选模型沿用 SDK 默认值。

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
