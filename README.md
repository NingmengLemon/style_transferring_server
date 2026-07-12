# 基于图像风格迁移的个性化数字艺术创作系统后端

本项目是课设后端部分，使用 FastAPI + PyTorch + VGG19 实现 HTTP 图像风格迁移服务，并遵守 [`docs/apis.md`](docs/apis.md) 中的前后端接口约定。

关联客户端项目：[style_transfer_harmonyos](https://github.com/SYYYYYYYYM/style_transfer_harmonyos)

## 项目文档

- [`docs/apis.md`](docs/apis.md)：HTTP API 文档，包含请求参数、响应结构、错误码和联调约定。
- [`docs/runtime_config.md`](docs/runtime_config.md)：系统运行配置文档，包含配置优先级、环境变量、目录约定、日志、部署场景和排障说明。
- [`docs/how_to_present.md`](docs/how_to_present.md)：项目展示/验收讲解稿，便于答辩时说明功能、算法、接口和工程化亮点。
- [`docs/raw_req.md`](docs/raw_req.md)：原始需求或需求整理材料。

## 功能

- `GET /api/health`：服务与模型状态检查。
- `GET /api/styles`：从本地 WikiArt 数据集挑选代表性内置风格，并生成可访问预览图。
- `POST /api/style-transfer`：上传内容图和内置 `style_id`，执行 VGG 神经风格迁移，返回结果图片 URL。
- `POST /api/custom-style-transfer`：上传内容图和用户自定义风格图，执行 VGG 神经风格迁移，返回结果图片 URL。
- `GET /static/*`：提供风格预览图和生成结果图访问。

## 技术栈

- FastAPI：HTTP API、CORS、中间件、统一异常处理和静态资源挂载。
- PyTorch / torchvision：加载 VGG19 特征提取网络并执行神经风格迁移。
- Pillow：图片读取、真实格式校验、EXIF 转正、缩放、平滑滤镜和保存。
- Pydantic / pydantic-settings：API 响应模型、参数校验和运行配置加载。
- Typer + Uvicorn：命令行启动服务。
- pytest：API 契约测试和配置测试。

## 目录约定

- WikiArt 数据集：`data/dataset/wikiart`，数据来源 <https://www.kaggle.com/datasets/steubk/wikiart>
- 运行输出目录：`data/outputs`
- 静态资源目录：`data/outputs/static`
- 生成图片目录：`data/outputs/static/results`
- 风格预览目录：`data/outputs/static/styles`
- 上传目录预留：`data/outputs/uploads`
- 自定义风格目录预留：`data/outputs/custom_styles`

目录由配置项 `data_dir` 派生，详细说明见 [`docs/runtime_config.md`](docs/runtime_config.md)。

## 启动

最小启动：

```powershell
uv run style-transferring-server
```

命令行支持覆盖常用配置，优先级高于环境变量和 JSON 配置文件：

```powershell
uv run style-transferring-server --host 127.0.0.1 --port 9000 --log-level DEBUG --log-json
uv run style-transferring-server --config my-config.json --no-warmup
```

查看全部参数：

```powershell
uv run style-transferring-server --help
```

也可以直接启动 ASGI 应用：

```powershell
uv run uvicorn style_transferring_server.app:app --host 0.0.0.0 --port 8000
```

服务默认监听：

```text
http://127.0.0.1:8000
```

局域网真机联调时通常使用：

```powershell
uv run style-transferring-server --host 0.0.0.0 --port 8000
```

然后客户端访问：

```text
http://<电脑局域网IP>:8000
```

## 配置

配置来源优先级从高到低：

```text
显式构造参数 > 环境变量（STYLE_SERVER_ 前缀）> JSON 配置文件 > 默认值
```

JSON 配置文件默认读取项目根目录的 `config.json`，可用 `STYLE_SERVER_CONFIG` 或 `--config` 指定其他路径。

示例：

```json
{
  "host": "0.0.0.0",
  "port": 8000,
  "max_upload_mb": 10,
  "timeout_s": 30,
  "preview_size": 512,
  "pretrained_vgg": true,
  "warmup": true,
  "data_dir": "data",
  "styles_config": "config/styles.json",
  "log_level": "INFO",
  "log_file": null,
  "log_json": false
}
```

常用配置字段：

| 字段 | 说明 | 默认 |
| ---- | ---- | ---- |
| `host` | 监听地址 | `0.0.0.0` |
| `port` | 监听端口 | `8000` |
| `max_upload_mb` | 最大上传大小（MB） | `10` |
| `timeout_s` | 单次推理超时秒数 | `30.0` |
| `preview_size` | 风格预览图长边像素 | `512` |
| `pretrained_vgg` | 是否加载 ImageNet 预训练 VGG19 | `true` |
| `warmup` | 是否启动时预热模型 | `true` |
| `data_dir` | 数据与输出根目录 | `data` |
| `styles_config` | 内置风格定义文件路径 | `config/styles.json` |
| `log_level` | 日志级别 | `INFO` |
| `log_file` | 日志文件路径（可选） | `null` |
| `log_json` | 是否输出 JSON 结构化日志 | `false` |

完整配置说明、环境变量示例和典型部署场景见 [`docs/runtime_config.md`](docs/runtime_config.md)。

## 风格配置

内置风格由外部文件 [`config/styles.json`](config/styles.json) 定义，无需改动路由代码即可增删候选风格。每个条目字段：

- `style_id`：风格唯一编号，前端调用 `/api/style-transfer` 时使用。
- `name` / `artist` / `description`：展示信息。
- `query`：优先用于匹配 WikiArt 文件名的关键字。
- `fallback_genre`：匹配失败时回退到的画派目录名。

当前候选风格包括：

| style_id | 名称 | 艺术家 |
| --- | --- | --- |
| `vangogh` | 梵高星空 | Vincent van Gogh |
| `picasso` | 毕加索立体主义 | Pablo Picasso |
| `monet` | 莫奈印象派 | Claude Monet |
| `kandinsky` | 康定斯基表现主义 | Wassily Kandinsky |
| `hokusai` | 葛饰北斋浮世绘 | Katsushika Hokusai |
| `munch` | 蒙克表现主义 | Edvard Munch |

服务启动时会按该文件从 WikiArt 数据集挑选代表作并生成预览图。最终 `/api/styles` 返回列表以本地数据集实际可匹配结果为准。

## 日志

统一 logger 名为 `style_transferring_server`，记录：

- 服务启动、目录创建、模型加载和 warmup。
- 每个 HTTP 请求的方法、路径、状态码、耗时和请求 ID。
- 每次风格迁移的风格、质量档位、参数、队列等待时间和推理耗时。

日志配置：

- 文本格式默认开启，便于开发查看。
- 设置 `log_json=true` 或使用 `--log-json` 输出单行 JSON，便于日志采集。
- 设置 `log_file` 或使用 `--log-file` 可同时写入文件。

更多日志说明见 [`docs/runtime_config.md`](docs/runtime_config.md)。

## 调用示例

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

获取内置风格列表：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/styles
```

使用内置风格执行风格迁移：

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/style-transfer" `
  -F "image=@data/dataset/wikiart/Impressionism/claude-monet_a-windmill-near-zaandam(1).jpg" `
  -F "style_id=vangogh" `
  -F "style_strength=80" `
  -F "content_weight=50" `
  -F "smoothness=30" `
  -F "quality=fast"
```

使用自定义风格图执行风格迁移：

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/custom-style-transfer" `
  -F "image=@content.jpg" `
  -F "style_image=@style.jpg" `
  -F "style_strength=75" `
  -F "content_weight=55" `
  -F "smoothness=25" `
  -F "quality=fast"
```

完整 API 请求、响应和错误码见 [`docs/apis.md`](docs/apis.md)。

## 参数说明

- `style_strength`：风格强度，范围 0-100，默认 70。它是控制风格浓淡的主参数；数值越大，内容约束越弱，风格覆盖越明显。
- `content_weight`：内容保留程度，范围 0-100，默认 50。在 `style_strength` 的基础上对内容约束做 0.2x 到 1.5x 缩放；越大越保留原图结构，越小越偏向风格图。
- `smoothness`：平滑程度，范围 0-100，默认 30。既参与 total variation loss，也在生成后应用 Pillow 平滑滤镜。
- `quality`：`fast`、`normal`、`hd`，默认 `fast`。质量档越高，参与推理的图片越大，优化越充分，耗时也越长。

### 风格强度的实现原理

神经风格迁移的视觉强度主要由 style/content 的损失权重比决定，而不是 `style_weight` 的绝对值。项目中 `style_strength` 主要通过指数级降低内容损失权重来放大风格效果。

当前实现使用较高的 `style_weight`，并配合 LBFGS + `strong_wolfe` line search 以及更充分的 LBFGS 内迭代，让强风格参数能够真正收敛显现。

## 性能说明

服务使用 CUDA 时会自动选择 GPU，否则使用 CPU。为了适配单机显存并避免并发 OOM，风格迁移请求在进程内串行执行。

启动时默认会用一张小图做一次 warmup，触发 cudnn autotune 与显存分配，从而减少首个真实请求的冷启动尖峰。

各质量档位的分辨率、外层步数与每步 LBFGS 内迭代次数：

| quality | 长边像素 | 外层步数 | LBFGS max_iter | GPU 稳态耗时参考 |
| ------- | ------- | ------- | -------------- | ------- |
| `fast`（默认） | 384 | 8 | 12 | ≈2.5s |
| `normal` | 448 | 12 | 16 | ≈5s |
| `hd` | 576 | 16 | 20 | ≈11s |

`normal` 与 `hd` 更容易接近或超过默认 `timeout_s`，若触发 `3006 inference timeout`，可调大 `timeout_s`，或优先使用 `fast` 档。

离线环境可将 `pretrained_vgg` 设为 `false`，但视觉效果会明显下降，更适合只演示接口流程。

## 错误码概览

| code | 说明 |
| --- | --- |
| `0` | 成功 |
| `1000` | 通用错误或参数错误 |
| `2001` | 图片为空 |
| `2002` | 图片不可读，或自定义风格图为空 |
| `2003` | 图片格式不支持 |
| `2004` | 图片超过大小限制 |
| `2005` | 图片尺寸异常 |
| `3001` | 内置风格 ID 不存在 |
| `3002` | 风格迁移参数错误 |
| `3003` | 模型加载失败 |
| `3004` | 模型推理失败 |
| `3005` | CUDA 显存不足 |
| `3006` | 推理超时 |

详细 HTTP 状态码、响应示例和联调排障见 [`docs/apis.md`](docs/apis.md)。

## 测试

运行测试：

```powershell
uv run pytest -q
```

测试为契约级用例，覆盖接口响应格式、状态码、错误码和配置加载优先级。为保证离线可跑且快速，测试通过桩替换真实推理，不加载预训练权重、不依赖完整 WikiArt 数据集与 GPU。

主要测试文件：

- [`tests/test_api_contract.py`](tests/test_api_contract.py)：API 契约测试。
- [`tests/test_config.py`](tests/test_config.py)：配置加载与风格候选解析测试。
- [`tests/conftest.py`](tests/conftest.py)：测试桩和测试客户端配置。

## 静态类型检查

```powershell
uv run --with pyright pyright src/style_transferring_server tests
```

仓库根目录的 [`pyrightconfig.json`](pyrightconfig.json) 已将类型检查指向项目 `.venv`，确保依赖能被正确解析。

## 推荐阅读顺序

1. 先读本文档，了解项目功能、启动方式和主要接口。
2. 再读 [`docs/apis.md`](docs/apis.md)，按接口契约完成前后端联调。
3. 需要部署或调整环境时读 [`docs/runtime_config.md`](docs/runtime_config.md)。
4. 需要答辩、验收或讲解项目时读 [`docs/how_to_present.md`](docs/how_to_present.md)。
