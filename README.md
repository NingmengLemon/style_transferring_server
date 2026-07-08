# 基于图像风格迁移的个性化数字艺术创作系统后端

本项目是课设后端部分，使用 FastAPI + PyTorch + VGG19 实现 HTTP 图像风格迁移服务，并遵守 `docs/风格迁移项目API文档.md` 中的前后端接口约定。

## 功能

- `GET /api/health`：服务与模型状态检查。
- `GET /api/styles`：从本地 WikiArt 数据集挑选代表性风格，并生成可访问预览图。
- `POST /api/style-transfer`：接收用户图片和参数，执行 VGG 神经风格迁移，返回结果图片 URL。
- `GET /static/*`：提供风格预览图和生成结果图访问。

## 目录约定

- WikiArt 数据集：`data/dataset/wikiart`
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

服务使用 CUDA 时会自动选择 GPU，否则使用 CPU。为了适配 RTX4060 Laptop 显存并避免并发 OOM，风格迁移请求在进程内串行执行；`fast` 模式默认将长边限制到 384 像素并使用较少 LBFGS 迭代，兼顾演示速度和视觉效果。

可通过环境变量调整：

- `STYLE_SERVER_HOST`：监听地址，默认 `0.0.0.0`。
- `STYLE_SERVER_PORT`：端口，默认 `8000`。
- `STYLE_SERVER_MAX_UPLOAD_MB`：最大上传大小，默认 `10`。
- `STYLE_SERVER_TIMEOUT_S`：单次推理超时秒数，默认 `30`。
- `STYLE_SERVER_PRETRAINED_VGG`：是否加载 torchvision 预训练 VGG19，默认 `1`。离线环境可设为 `0`，但视觉效果会明显下降。
