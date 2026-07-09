# 基于图像风格迁移的个性化数字艺术创作系统后端

本项目是课设后端部分，使用 FastAPI + PyTorch + VGG19 实现 HTTP 图像风格迁移服务，并遵守 `docs/风格迁移项目API文档.md` 中的前后端接口约定。

## 功能

- `GET /api/health`：服务与模型状态检查。
- `GET /api/styles`：从本地 WikiArt 数据集挑选代表性风格，并生成可访问预览图。
- `POST /api/style-transfer`：接收用户图片和参数，执行 VGG 神经风格迁移，返回结果图片 URL。
- `GET /static/*`：提供风格预览图和生成结果图访问。

## 目录约定

- WikiArt 数据集：`data/dataset/wikiart` from <https://www.kaggle.com/datasets/steubk/wikiart>
- 运行输出目录：`data/outputs`
- 生成图片目录：`data/outputs/static/results`
- 风格预览目录：`data/outputs/static/styles`

## 启动

```powershell
uv run style-transferring-server
```

命令行支持覆盖常用配置（优先级高于环境变量和配置文件）：

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

## 配置

配置来源优先级从高到低：命令行参数 > 环境变量（前缀 `STYLE_SERVER_`）> JSON 配置文件 > 默认值。

JSON 配置文件默认读取项目根目录的 `config.json`，可用 `STYLE_SERVER_CONFIG` 或 `--config` 指定其他路径。示例：

```json
{
  "host": "0.0.0.0",
  "port": 8000,
  "max_upload_mb": 10,
  "timeout_s": 30,
  "pretrained_vgg": true,
  "warmup": true,
  "log_level": "INFO",
  "log_json": false,
  "styles_config": "config/styles.json"
}
```

可配置字段（环境变量为字段名大写并加 `STYLE_SERVER_` 前缀，如 `STYLE_SERVER_PORT`）：

| 字段 | 说明 | 默认 |
| ---- | ---- | ---- |
| `host` | 监听地址 | `0.0.0.0` |
| `port` | 监听端口 | `8000` |
| `max_upload_mb` | 最大上传大小(MB) | `10` |
| `timeout_s` | 单次推理超时秒数 | `30` |
| `preview_size` | 风格预览图长边像素 | `512` |
| `pretrained_vgg` | 是否加载预训练 VGG19 | `true` |
| `warmup` | 是否启动时预热模型 | `true` |
| `data_dir` | 数据与输出根目录 | `data` |
| `styles_config` | 风格定义文件路径 | `config/styles.json` |
| `log_level` | 日志级别 | `INFO` |
| `log_file` | 日志文件路径(可选) | 无 |
| `log_json` | 是否输出 JSON 结构化日志 | `false` |

## 风格配置

可选风格由外部文件 `config/styles.json` 定义，无需改动代码即可增删风格。每个条目字段：

- `style_id`：风格唯一编号（前端使用）。
- `name` / `artist` / `description`：展示信息。
- `query`：在 WikiArt `classes.csv` 的 `filename` 中匹配的关键字（命中具体作品）。
- `fallback_genre`：匹配失败时回退到的画派目录名。

服务启动时按此文件从 WikiArt 数据集挑选代表作并生成预览图。

## 日志

统一 logger 名为 `style_transferring_server`，记录服务启动、模型加载与预热、每个 HTTP 请求（方法、路径、状态码、耗时、请求 ID）以及每次风格迁移的参数与耗时。

- 文本格式（默认）便于开发查看；设 `log_json=true`（或 `--log-json`）输出单行 JSON，便于日志采集。
- 设 `log_file` 可同时写入文件。

## 调用示例

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

获取风格：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/styles
```

上传图片执行风格迁移：

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/style-transfer" `
  -F "image=@data/dataset/wikiart/Impressionism/claude-monet_a-windmill-near-zaandam(1).jpg" `
  -F "style_id=vangogh" `
  -F "style_strength=80" `
  -F "content_weight=50" `
  -F "smoothness=30" `
  -F "quality=fast"
```

## 参数说明

- `style_strength`：风格强度，范围 0-100，默认 70。**这是控制风格浓淡的主参数**：数值越大，风格覆盖越强、越偏离原图。
- `content_weight`：内容保留程度，范围 0-100，默认 50。在 `style_strength` 的基础上对内容约束做 0.5x~1.5x 微调。
- `smoothness`：平滑程度，范围 0-100，默认 30。
- `quality`：`fast`、`normal`、`hd`，默认 `fast`。质量档越高，优化越充分、风格越细腻，耗时也越长。

### 风格强度的实现原理

神经风格迁移的视觉强度**主要由 style/content 的损失权重比决定，而非 style_weight 的绝对值**。实测表明单纯抬高 style_weight 几乎不改变结果。因此 `style_strength` 通过**指数级降低 content_weight**（strength 0→100 对应 content_weight 约 2000→5，跨越有效动态范围）来放大风格，这才是有效杠杆。

此外，优化器采用 LBFGS + `strong_wolfe` line search 并在每个外层 step 内充分迭代，保证风格 loss 真正收敛。早期实现用 `max_iter=1` 且无 line search，优化远未收敛，加上强度只映射到无效的 style_weight，导致「强度拉满风格也不够浓」。

## 性能说明

服务使用 CUDA 时会自动选择 GPU，否则使用 CPU。为了适配 RTX4060 Laptop 显存并避免并发 OOM，风格迁移请求在进程内串行执行。

启动时会用一张小图做一次预热推理（warmup），触发 cudnn autotune 与显存分配，从而消除首个真实请求的冷启动尖峰。

各质量档位的分辨率、外层步数与每步 LBFGS 内迭代次数经 RTX4060 Laptop 实测校准。closure 评估总次数（≈步数 × 内迭代）配合 line search 决定收敛充分度。GPU 稳态耗时（不含冷启动，空载 GPU）：

| quality | 长边像素 | 外层步数 | LBFGS max_iter | 实测耗时 |
| ------- | ------- | ------- | -------------- | ------- |
| `fast`（默认） | 384 | 6 | 8 | ≈1.6s |
| `normal` | 448 | 8 | 10 | ≈3.4s |
| `hd` | 576 | 10 | 12 | ≈7.9s |

`fast` 满足实时预算（约 1.6s）。`normal` 与 `hd` 为高质量档，风格更充分细腻但耗时更高；`hd` 明显超过 2.5s，若默认 `timeout_s` 偏小可能触发 3006 超时，可按需调大。

相关配置项（`timeout_s`、`pretrained_vgg`、`warmup` 等）见上文 [配置](#配置) 章节。离线环境可将 `pretrained_vgg` 设为 `false`，但视觉效果会明显下降。

## 测试

```powershell
uv run python -m pytest -q
```

测试为契约级用例，覆盖三个接口的响应格式、状态码与错误分支。为保证离线可跑且快速，测试通过桩替换真实推理，不加载预训练权重、不依赖 WikiArt 数据集与 GPU。

## 静态类型检查

```powershell
uv run --with pyright pyright src/style_transferring_server tests
```

仓库根目录的 `pyrightconfig.json` 已将类型检查指向项目 `.venv`，确保依赖能被正确解析。
