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

也可以直接启动 ASGI 应用：

```powershell
uv run uvicorn style_transferring_server.app:app --host 0.0.0.0 --port 8000
```

服务默认监听：

```text
http://127.0.0.1:8000
```

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

- `style_strength`：风格强度，范围 0-100，默认 70。
- `content_weight`：内容保留程度，范围 0-100，默认 50。
- `smoothness`：平滑程度，范围 0-100，默认 30。
- `quality`：`fast`、`normal`、`hd`，默认 `fast`。

## 性能说明

服务使用 CUDA 时会自动选择 GPU，否则使用 CPU。为了适配 RTX4060 Laptop 显存并避免并发 OOM，风格迁移请求在进程内串行执行。

启动时会用一张小图做一次预热推理（warmup），触发 cudnn autotune 与显存分配，从而消除首个真实请求的冷启动尖峰。

各质量档位的分辨率与迭代次数经 RTX4060 Laptop 实测校准，GPU 稳态耗时（不含冷启动，空载 GPU）：

| quality | 长边像素 | LBFGS 迭代 | 实测耗时 |
| ------- | ------- | --------- | ------- |
| `fast`（默认） | 384 | 18 | ≈0.5s |
| `normal` | 448 | 22 | ≈0.9s |
| `hd` | 640 | 40 | ≈2.9s |

`fast` 与 `normal` 稳定满足需求要求的“单张 < 2.5s”；`hd` 为尽力而为的高质量档，在空载 GPU 上约 2.9s，略高于预算，若 GPU 被其他进程占用可能触发 3006 超时。

可通过环境变量调整：

- `STYLE_SERVER_HOST`：监听地址，默认 `0.0.0.0`。
- `STYLE_SERVER_PORT`：端口，默认 `8000`。
- `STYLE_SERVER_MAX_UPLOAD_MB`：最大上传大小，默认 `10`。
- `STYLE_SERVER_TIMEOUT_S`：单次推理超时秒数，默认 `30`。
- `STYLE_SERVER_PRETRAINED_VGG`：是否加载 torchvision 预训练 VGG19，默认 `1`。离线环境可设为 `0`，但视觉效果会明显下降。
- `STYLE_SERVER_WARMUP`：是否在启动时预热模型，默认 `1`。设为 `0` 可加快启动，但首个请求会较慢。

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
