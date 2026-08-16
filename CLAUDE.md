# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`openapipy` (PyPI name; imported as `openapi`) is a dependency-light Python library (httpx + pydantic v2, Python >= 3.10) of third-party API clients for Chinese platforms: payments (Alipay, WeChat Pay V2, Lenovo), open platforms (WeChat MP/channels, Feishu, Xiaohongshu), e-commerce (doudian, xiaoetong, yizhi), video cloud (Polyv), SMS (submail, wgws), CRM (tanmarket, yunduo), generic Aliyun RPC, Aliyun OSS object storage, and a unified multi-provider media generation client (Volcengine, Aliyun Bailian, HiFly, DeepSeek, SiliconFlow).

`README.md` is the user-facing API reference (written in Chinese) — update it when adding providers or changing usage. `CHANGELOG.md` is maintained per release, also in Chinese. The library never reads credentials from environment variables; business code must inject them explicitly.

## Commands

```bash
# install dev deps (project venv at .venv already exists)
pip install -r requirements.txt

# lint — CI lints ./openapi only; examples/ is excluded from ruff (pyproject.toml)
.venv/bin/ruff check openapi
.venv/bin/ruff format openapi   # single quotes, line-length 120

# tests — stdlib unittest, discovery via tests/__init__.py; run from repo root
python3 -m unittest                                # all (same as CI)
python3 -m unittest tests.test_media_generation    # one module
python3 -m unittest tests.test_aliyun_oss.ConfigTests.test_x   # single test

# release — bump __version__ in openapi/__init__.py, push tag v* → CI publishes sdist to PyPI
python3 setup.py sdist
```

The classic-provider tests (`test_ali.py`, `test_feishu.py`, `test_xiaoetong.py`) mostly mock httpx; media generation and OSS tests are thorough and pure unit tests. `examples/` scripts run against real services using `examples/config.yaml` (copy to `config.dev.yaml`; media examples use `.env` + `python -m examples.media_generation...`) and are never packaged or linted.

## Architecture

### Classic providers (`openapi/providers/` top-level files)

Each provider is a single module defining `Code` (a `TextChoices`/`IntegerChoices` enum of provider error codes), `Result(BaseResult)` and `Client(BaseClient)`. The shared base is `openapi/providers/base.py`:

- `BaseClient._request()` wraps httpx (10s timeout), masks sensitive keys (`secret`, `app_key`, …) in an optional Feishu-webhook log of every request, and returns the raw `httpx.Response` (or `None` on transport error).
- `BaseClient.access_token` lazily calls `fetch_access_token()`; the returned `Token` is cached with a validity margin, and `check_token()`/`refresh_access_token()` can be overridden per provider.
- Signature schemes are per-provider helper functions in the same module (RSA2 certs for Alipay, MD5 signing + XML body for WeChat Pay V2 via `openapi/utils.py`'s `dict_to_xml`/`xml_to_dict`, RSA for Lenovo, HMAC-SHA1 for generic Aliyun RPC), plus `check_signature()`/`callback()` for webhook verification where supported.

### Media generation (`openapi/providers/media_generation/`) — layered SDK

- `MediaClient.create(*configs)` (`client.py`/`factory.py`) constructs a `ProviderRegistry` where each provider config maps to an **adapter** (`adapters/`) registered per **capability** (text, speech, speech transcription, voice clone/design/list, file upload, image, video, image validation, digital human, avatar clone/list, task). Duplicate provider configs are rejected.
- **Domains** (`domains/`) are the public entry points (`media.text`, `media.speech`, `media.image`, `media.video`, `media.avatar`, `media.task`, `media.workflow`); they coerce request dicts to pydantic models (`validation.py`) and dispatch through the registry to the adapter's capability method. **Capabilities** (`capabilities/`) are typing Protocols only — adapters implement them without inheriting.
- All request/output models live in `models.py`, including generic `ModelResult[T]` (raw provider response in `.data`) and serializable `TaskRef` (provider + operation + task id + model) for async task polling across service restarts.
- `exceptions.py` normalizes provider failures into `ProviderAPIError` with `code`, `retryable`, `fallback_allowed`, `remote_task_may_exist` via marker-based classification (`classify_provider_error`). Content-safety/ownership/invalid-input errors must NOT fall back to another provider; `remote_task_may_exist=True` means the caller must treat the remote task as unknown state.
- `transport/http.py` (`ProviderTransport`) centralizes HTTP calls, secret redaction in errors/logs, and query retry.

### Object storage (`openapi/providers/storages/`)

`storages/__init__.py` exports provider-neutral types: `ObjectStorageClient` (a runtime-checkable Protocol), `ObjectMetadata`, and `ObjectStorageError` hierarchy. `aliyun_oss.Client` is currently the only adapter (V4 signature, explicit region/endpoint/credentials, `oss2` SDK behind the `aliyun-oss` extra). Business code should depend on the Protocol and receive the concrete client via injection; no generic registry/forwarding client exists until a second adapter lands.

### Enums

`openapi/enums.py` provides `Choices`/`IntegerChoices`/`TextChoices` (Django-style) — members may be declared as `NAME = value, '中文label'` and get `.label`, `.choices`, `.names`, `.values` class properties.

## Conventions

- Ruff select F/E/I/B/N/TID, ignores `E721`/`N818`; single quotes, line length 120 (`pyproject.toml`).
- Provider code is self-contained: one provider = one module (classic) or one adapter + capability registrations (media generation); no cross-provider shared request helpers except `base.py`, `utils.py`, and `enums.py`.
- Docs and changelog entries are written in Chinese; code identifiers and comments are English.
- Media generation adapters must route every failure through `ProviderAPIError.from_provider_response` (or `with_message`) so retry/fallback metadata is preserved; keep `remote_task_may_exist=True` on submission timeout/polling failures.
