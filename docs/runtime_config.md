# 系统运行配置文档

本文档说明图像风格迁移后端的运行配置方式、配置优先级、可配置字段、目录约定、启动命令、日志配置和常见部署示例。

## 1. 配置目标

本项目运行配置主要解决以下问题：

- 服务监听在哪个地址和端口。
- 单次上传图片允许多大。
- VGG19 推理是否使用预训练权重、是否启动预热、推理超时时间是多少。
- 数据集、输出图片、风格预览图和临时目录放在哪里。
- 内置风格列表从哪个 JSON 文件读取。
- 日志级别、日志格式和日志文件如何配置。

配置实现集中在 [`src/style_transferring_server/config.py`](../src/style_transferring_server/config.py)，命令行启动入口在 [`src/style_transferring_server/cli.py`](../src/style_transferring_server/cli.py)。

## 2. 配置来源和优先级

项目使用 Pydantic Settings 加载配置。优先级从高到低为：

1. 显式构造参数：主要供测试或内部代码直接构造 `Settings(...)` 时使用。
2. 环境变量：统一使用 `STYLE_SERVER_` 前缀。
3. JSON 配置文件：默认读取项目根目录下的 `config.json`，也可以通过 `STYLE_SERVER_CONFIG` 或命令行 `--config` 指定。
4. 字段默认值：代码中定义的默认配置。

也就是说，同一个字段如果同时出现在 JSON 和环境变量里，环境变量会覆盖 JSON；如果通过命令行参数启动，命令行参数会写入环境变量，因此会覆盖 JSON 配置。

对应实现：

- [`Settings.model_config`](../src/style_transferring_server/config.py)：定义环境变量前缀 `STYLE_SERVER_`。
- [`Settings.settings_customise_sources()`](../src/style_transferring_server/config.py)：定义 `init > env > json > file_secret` 的加载顺序。
- [`serve()`](../src/style_transferring_server/cli.py)：将 CLI 参数写入 `STYLE_SERVER_*` 环境变量。

## 3. JSON 配置文件

默认 JSON 配置文件路径为项目根目录：

```text
config.json
```

如果要使用其他路径，可以二选一：

```powershell
$env:STYLE_SERVER_CONFIG = "my-config.json"
uv run style-transferring-server
```

或者：

```powershell
uv run style-transferring-server --config my-config.json
```

推荐配置示例：

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

说明：JSON 中未出现的字段会使用默认值。额外字段会被忽略，不会导致服务启动失败。

## 4. 环境变量配置

所有运行配置字段都可以用环境变量覆盖，变量名规则是：

```text
STYLE_SERVER_ + 字段名大写
```

例如：

| 字段 | 环境变量 |
| --- | --- |
| `host` | `STYLE_SERVER_HOST` |
| `port` | `STYLE_SERVER_PORT` |
| `timeout_s` | `STYLE_SERVER_TIMEOUT_S` |
| `pretrained_vgg` | `STYLE_SERVER_PRETRAINED_VGG` |
| `warmup` | `STYLE_SERVER_WARMUP` |
| `data_dir` | `STYLE_SERVER_DATA_DIR` |
| `styles_config` | `STYLE_SERVER_STYLES_CONFIG` |
| `log_level` | `STYLE_SERVER_LOG_LEVEL` |
| `log_file` | `STYLE_SERVER_LOG_FILE` |
| `log_json` | `STYLE_SERVER_LOG_JSON` |

PowerShell 示例：

```powershell
$env:STYLE_SERVER_PORT = "9000"
$env:STYLE_SERVER_LOG_LEVEL = "DEBUG"
$env:STYLE_SERVER_WARMUP = "0"
uv run style-transferring-server
```

布尔值建议使用：

- 开启：`1`、`true`、`True`。
- 关闭：`0`、`false`、`False`。

## 5. 命令行配置

项目提供 `style-transferring-server` 命令，注册位置在 [`pyproject.toml`](../pyproject.toml)。

最小启动：

```powershell
uv run style-transferring-server
```

查看帮助：

```powershell
uv run style-transferring-server --help
```

常用命令行参数：

| 参数 | 说明 | 等价环境变量 |
| --- | --- | --- |
| `--config` / `-c` | 指定 JSON 配置文件路径 | `STYLE_SERVER_CONFIG` |
| `--host` | 监听地址 | `STYLE_SERVER_HOST` |
| `--port` | 监听端口 | `STYLE_SERVER_PORT` |
| `--log-level` | 日志级别 | `STYLE_SERVER_LOG_LEVEL` |
| `--log-file` | 日志文件路径 | `STYLE_SERVER_LOG_FILE` |
| `--log-json` / `--no-log-json` | 是否输出 JSON 日志 | `STYLE_SERVER_LOG_JSON` |
| `--pretrained-vgg` / `--no-pretrained-vgg` | 是否加载预训练 VGG19 | `STYLE_SERVER_PRETRAINED_VGG` |
| `--warmup` / `--no-warmup` | 是否启动时预热模型 | `STYLE_SERVER_WARMUP` |
| `--reload` | 开发模式自动重载 | 仅传给 Uvicorn |

示例：

```powershell
uv run style-transferring-server --host 127.0.0.1 --port 9000 --log-level DEBUG
```

```powershell
uv run style-transferring-server --config config.local.json --no-warmup --log-json
```

开发模式自动重载：

```powershell
uv run style-transferring-server --reload
```

## 6. 全部配置字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `host` | string | `0.0.0.0` | 服务监听地址。开发机本地可用 `127.0.0.1`，局域网联调用 `0.0.0.0`。 |
| `port` | int | `8000` | 服务监听端口。 |
| `max_upload_mb` | int | `10` | 单个上传图片最大体积，单位 MB。内容图和自定义风格图都会受此限制。 |
| `timeout_s` | float | `30.0` | 单次风格迁移推理超时时间，超时返回 `3006`。 |
| `preview_size` | int | `512` | 内置风格预览图生成时的长边像素。 |
| `pretrained_vgg` | bool | `true` | 是否加载 ImageNet 预训练 VGG19 权重。关闭后可避免下载权重，但生成效果会明显下降。 |
| `warmup` | bool | `true` | 是否在启动时用小图预热模型，减少首个真实请求冷启动尖峰。 |
| `data_dir` | path | `data` | 数据集和运行输出根目录。 |
| `styles_config` | path | `config/styles.json` | 内置风格候选配置文件路径。 |
| `log_level` | enum | `INFO` | 日志级别，可选 `DEBUG`、`INFO`、`WARNING`、`ERROR`、`CRITICAL`。 |
| `log_file` | path/null | `null` | 日志文件路径。为空时只输出到标准输出。 |
| `log_json` | bool | `false` | 是否输出单行 JSON 结构化日志。 |

## 7. 运行目录约定

运行目录由 `data_dir` 派生，默认 `data_dir=data`。

| 目录属性 | 默认路径 | 用途 |
| --- | --- | --- |
| `data_dir` | `data` | 数据与输出根目录。 |
| `wikiart_dir` | `data/dataset/wikiart` | WikiArt 数据集目录。 |
| `output_dir` | `data/outputs` | 服务运行输出根目录。 |
| `static_dir` | `data/outputs/static` | FastAPI 挂载为 `/static` 的静态资源目录。 |
| `results_dir` | `data/outputs/static/results` | 风格迁移结果 PNG 图片目录。 |
| `style_static_dir` | `data/outputs/static/styles` | 内置风格预览图目录。 |
| `upload_dir` | `data/outputs/uploads` | 上传目录预留。 |
| `custom_styles_dir` | `data/outputs/custom_styles` | 自定义风格图片目录预留。 |

服务启动时会调用 [`ensure_runtime_dirs()`](../src/style_transferring_server/config.py)，自动创建运行输出目录，包括 `outputs`、`static`、`results`、`styles`、`uploads` 和 `custom_styles`。

## 8. WikiArt 数据集配置

内置风格列表依赖 WikiArt 数据集。默认数据集路径为：

```text
data/dataset/wikiart
```

项目期望的数据集来源：

```text
https://www.kaggle.com/datasets/steubk/wikiart
```

内置风格加载逻辑会根据 [`config/styles.json`](../config/styles.json) 中的 `query` 和 `fallback_genre` 匹配具体风格图片。如果本地数据集中找不到某个候选风格对应图片，该风格可能不会出现在 `/api/styles` 返回结果里。

如果要把数据集放到其他位置，可以改 `data_dir`，例如：

```json
{
  "data_dir": "E:/datasets/style_transfer_data"
}
```

此时 WikiArt 目录会变为：

```text
E:/datasets/style_transfer_data/dataset/wikiart
```

## 9. 内置风格配置

内置风格候选配置默认读取：

```text
config/styles.json
```

字段结构：

```json
{
  "styles": [
    {
      "style_id": "vangogh",
      "name": "梵高星空",
      "artist": "Vincent van Gogh",
      "description": "后印象派旋涡笔触和高饱和色彩风格",
      "query": "vincent-van-gogh_the-starry-night-1889",
      "fallback_genre": "Post_Impressionism"
    }
  ]
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `style_id` | 风格唯一 ID，前端调用 `/api/style-transfer` 时传入。 |
| `name` | 前端展示名称。 |
| `artist` | 艺术家名称。 |
| `description` | 风格描述。 |
| `query` | 优先用于匹配 WikiArt 文件名的关键字。 |
| `fallback_genre` | 文件名匹配失败时回退查找的画派目录。 |

可以通过配置项 `styles_config` 指定其他风格配置文件：

```json
{
  "styles_config": "config/styles.local.json"
}
```

## 10. 日志配置

日志配置实现位于 [`src/style_transferring_server/logging_config.py`](../src/style_transferring_server/logging_config.py)。项目统一 logger 名称为：

```text
style_transferring_server
```

默认文本日志格式：

```text
2026-07-12 11:00:00 INFO    [style_transferring_server] request received: method=GET path=/api/health ...
```

启用 JSON 日志：

```powershell
uv run style-transferring-server --log-json
```

或：

```json
{
  "log_json": true
}
```

写入日志文件：

```powershell
uv run style-transferring-server --log-file data/outputs/logs/server.log
```

或：

```json
{
  "log_file": "data/outputs/logs/server.log"
}
```

服务会自动创建日志文件所在目录。

## 11. 推理和性能相关配置

### 11.1 `pretrained_vgg`

默认值：`true`。

开启时使用 ImageNet 预训练 VGG19 权重，风格迁移效果更符合经典神经风格迁移预期。首次运行如果本机没有缓存权重，torchvision 可能需要联网下载。

离线演示时可临时关闭：

```powershell
uv run style-transferring-server --no-pretrained-vgg
```

注意：关闭后模型随机初始化或无预训练语义特征，视觉效果会明显下降，只适合离线调试接口流程。

### 11.2 `warmup`

默认值：`true`。

开启后服务启动阶段会用一张小图跑一次推理，提前触发 cudnn autotune 和显存分配，减少首个真实请求冷启动时间。

如果只想快速启动接口或测试配置，可以关闭：

```powershell
uv run style-transferring-server --no-warmup
```

### 11.3 `timeout_s`

默认值：`30.0`。

单次推理超过该时间会返回：

```json
{
  "code": 3006,
  "message": "inference timeout",
  "data": null
}
```

如果使用 `normal` 或 `hd` 档，或者 GPU 较慢，建议适当调大：

```json
{
  "timeout_s": 60
}
```

### 11.4 `max_upload_mb`

默认值：`10`。

上传内容图和自定义风格图都会检查文件体积。超过限制会返回 `2004 image exceeds size limit`。

## 12. 静态资源访问配置

FastAPI 会把 `static_dir` 挂载到 `/static`：

```text
data/outputs/static -> /static
```

因此：

| 本地文件 | HTTP 访问路径 |
| --- | --- |
| `data/outputs/static/results/result_xxx.png` | `/static/results/result_xxx.png` |
| `data/outputs/static/styles/vangogh.jpg` | `/static/styles/vangogh.jpg` |

前端展示图片时需要拼接服务地址：

```text
http://127.0.0.1:8000/static/results/result_xxx.png
```

## 13. 典型配置场景

### 13.1 本机开发

```powershell
uv run style-transferring-server --host 127.0.0.1 --port 8000 --log-level DEBUG --no-warmup
```

适合只在本机浏览器或本机客户端调用。

### 13.2 局域网真机联调

```powershell
uv run style-transferring-server --host 0.0.0.0 --port 8000
```

客户端访问：

```text
http://<电脑局域网IP>:8000
```

注意检查 Windows 防火墙是否允许该端口访问。

### 13.3 演示环境

建议使用 JSON 配置文件：

```json
{
  "host": "0.0.0.0",
  "port": 8000,
  "timeout_s": 60,
  "pretrained_vgg": true,
  "warmup": true,
  "log_level": "INFO",
  "log_json": false
}
```

启动：

```powershell
uv run style-transferring-server --config config.demo.json
```

### 13.4 离线接口演示

如果没有网络下载 VGG19 权重，只演示 API 流程：

```powershell
uv run style-transferring-server --no-pretrained-vgg --no-warmup
```

注意：这种方式不推荐用于展示最终生成效果。

### 13.5 结构化日志部署

```json
{
  "host": "0.0.0.0",
  "port": 8000,
  "log_level": "INFO",
  "log_json": true,
  "log_file": "data/outputs/logs/server.log"
}
```

适合后续接入日志采集系统。

## 14. 配置验证方式

### 14.1 启动后检查健康接口

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

正常返回：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "status": "running",
    "model_loaded": true,
    "device": "cuda"
  }
}
```

### 14.2 检查风格列表

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/styles
```

如果返回风格列表为空或缺少部分风格，优先检查：

- `data_dir` 是否指向正确位置。
- `data/dataset/wikiart` 是否存在。
- `styles_config` 是否指向正确 JSON 文件。
- `query` 或 `fallback_genre` 是否能匹配本地 WikiArt 文件。

### 14.3 运行测试

```powershell
uv run pytest -q
```

配置加载相关测试在 [`tests/test_config.py`](../tests/test_config.py)，会验证 JSON 配置、环境变量覆盖、显式构造参数覆盖和派生目录规则。

## 15. 常见问题

### 15.1 修改 JSON 后没有生效

优先检查是否存在同名环境变量。环境变量优先级高于 JSON，例如 `STYLE_SERVER_PORT` 会覆盖 JSON 中的 `port`。

### 15.2 使用 `--config` 后仍读取默认配置

确认命令行参数写在服务命令之后：

```powershell
uv run style-transferring-server --config config.demo.json
```

不要写成其他工具参数。

### 15.3 `/api/styles` 没有返回预期风格

内置风格需要本地 WikiArt 数据集支持。检查：

- `data/dataset/wikiart` 是否存在。
- 数据集目录结构是否包含 `classes.csv` 或对应画派目录。
- [`config/styles.json`](../config/styles.json) 中的 `query` 和 `fallback_genre` 是否能匹配到图片。

### 15.4 首次启动很慢

可能原因：

- 首次下载 VGG19 预训练权重。
- 开启 warmup 后启动阶段会先跑一次小图推理。
- CUDA 初始化和 cudnn autotune 需要时间。

调试时可临时使用：

```powershell
uv run style-transferring-server --no-warmup
```

### 15.5 `hd` 档容易超时

`hd` 档分辨率和 LBFGS 迭代更多，耗时更长。可以调大：

```json
{
  "timeout_s": 60
}
```

或者前端默认使用 `fast` 档。

## 16. 推荐提交到仓库的配置策略

建议：

- 将通用默认值保留在代码和文档中。
- 不提交包含个人绝对路径的 `config.json`。
- 如果需要示例配置，可以提交 `config.example.json`。
- 本机私有配置使用 `config.local.json`，并在启动时通过 `--config config.local.json` 指定。
- 日志文件、输出图片、数据集目录不应提交到 Git。
