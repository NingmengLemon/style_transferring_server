# 项目展示讲解稿

一个基于 FastAPI + PyTorch + VGG19 的图像风格迁移后端服务。

## 1. 一句话介绍项目

本项目是“基于图像风格迁移的个性化数字艺术创作系统”的 Python 后端。客户端上传一张内容图片，可以选择服务端内置艺术风格，也可以上传自定义风格图；后端使用 VGG19 神经风格迁移生成艺术化图片，并返回生成图片的静态访问地址。

技术栈：

- FastAPI：提供 HTTP 接口，入口在 [`src/style_transferring_server/app.py`](../src/style_transferring_server/app.py)。
- PyTorch / torchvision：加载 VGG19 并执行神经风格迁移，核心在 [`src/style_transferring_server/transfer.py`](../src/style_transferring_server/transfer.py)。
- Pillow：负责图片读取、格式校验、EXIF 转正、缩放、平滑滤镜和结果保存。
- Pydantic：定义配置、参数和响应模型，见 [`src/style_transferring_server/schemas.py`](../src/style_transferring_server/schemas.py) 和 [`src/style_transferring_server/config.py`](../src/style_transferring_server/config.py)。
- Typer + Uvicorn：提供命令行启动方式，见 [`src/style_transferring_server/cli.py`](../src/style_transferring_server/cli.py)。

## 2. 项目目录怎么讲

可以按“文档、配置、服务入口、算法、测试”这条线介绍：

- [`README.md`](../README.md)：项目说明、启动方式、配置项、接口示例、性能说明和测试命令。
- [`docs/apis.md`](apis.md)：当前真实 HTTP API 契约文档，包含 `/api/custom-style-transfer`。
- [`docs/how_to_present.md`](how_to_present.md)：答辩或验收时的讲解提纲，也就是本文档。
- [`config/styles.json`](../config/styles.json)：内置风格候选配置，目前包含 `vangogh`、`picasso`、`monet`、`kandinsky`、`hokusai`、`munch` 六个候选风格。
- [`pyproject.toml`](../pyproject.toml)：项目依赖、命令行脚本、测试配置和 PyTorch CUDA 源配置。
- [`src/style_transferring_server/app.py`](../src/style_transferring_server/app.py)：FastAPI 应用、路由、中间件、异常处理和静态资源挂载。
- [`src/style_transferring_server/transfer.py`](../src/style_transferring_server/transfer.py)：模型加载、图片校验、VGG 特征提取、Gram 矩阵、LBFGS 优化和结果保存。
- [`src/style_transferring_server/styles.py`](../src/style_transferring_server/styles.py)：内置风格配置加载、WikiArt 图片匹配和预览图生成。
- [`src/style_transferring_server/config.py`](../src/style_transferring_server/config.py)：配置来源优先级、运行目录、上传限制、日志和模型预热开关。
- [`src/style_transferring_server/constants.py`](../src/style_transferring_server/constants.py)：API 路径、错误码、图片约束、默认参数等常量。
- [`src/style_transferring_server/responses.py`](../src/style_transferring_server/responses.py)：统一响应和统一异常处理。
- [`tests/`](../tests)：契约测试和配置测试，保证接口响应结构、状态码、错误码和配置优先级稳定。

## 3. 启动流程怎么讲

常用启动命令：

```powershell
uv run style-transferring-server
```

也可以覆盖配置：

```powershell
uv run style-transferring-server --host 127.0.0.1 --port 9000 --log-level DEBUG --log-json
uv run style-transferring-server --config my-config.json --no-warmup
```

启动链路：

1. [`pyproject.toml`](../pyproject.toml) 注册命令 `style-transferring-server`，指向 `style_transferring_server.cli:main`。
2. [`src/style_transferring_server/cli.py`](../src/style_transferring_server/cli.py) 接收命令行参数。
3. CLI 将命令行参数写入环境变量，优先级高于 JSON 配置和默认值。
4. CLI 调用 `uvicorn.run()` 启动 `style_transferring_server.app:app`。
5. [`create_app()`](../src/style_transferring_server/app.py) 创建 FastAPI 应用、注册 CORS、日志中间件、异常处理器和路由。
6. [`lifespan()`](../src/style_transferring_server/app.py) 在服务启动时创建运行目录、加载风格索引、加载 VGG19，并按配置决定是否 warmup。

可以强调：这个项目不是一次性脚本，而是一个完整 HTTP 后端服务，支持命令行参数、环境变量、JSON 配置文件三层配置来源。

## 4. 对外接口怎么讲

当前项目实际提供 5 类接口：

### 4.1 健康检查

接口：`GET /api/health`

作用：检查服务是否运行、模型是否加载成功、当前推理设备是 CPU 还是 CUDA。

返回示例：

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

实现要点：如果模型尚未加载，健康检查会尝试按需加载一次；如果加载失败，返回业务错误码 `3003`。

### 4.2 获取内置风格列表

接口：`GET /api/styles`

作用：返回服务端当前可用的内置艺术风格列表。候选风格来自 [`config/styles.json`](../config/styles.json)，但最终是否可用取决于本地 WikiArt 数据集中能否匹配到图片。

返回字段：

- `style_id`：前端调用内置风格迁移接口时使用的唯一 ID。
- `name`：中文展示名称。
- `artist`：艺术家名称。
- `description`：风格说明。
- `preview_url`：风格预览图相对地址。

可以这样讲：风格列表不是写死在接口里的，而是外部 JSON 配置驱动。新增内置风格主要改 [`config/styles.json`](../config/styles.json)，无需改路由代码。

### 4.3 使用内置风格执行风格迁移

接口：`POST /api/style-transfer`

Content-Type：`multipart/form-data`

请求字段：

- `image`：内容图，必填，支持 jpg、jpeg、png。
- `style_id`：内置风格 ID，必填，来自 `/api/styles` 返回值。
- `style_strength`：风格强度，0-100，默认 70。
- `content_weight`：内容保留程度，0-100，默认 50。
- `smoothness`：平滑程度，0-100，默认 30。
- `quality`：质量档位，`fast` / `normal` / `hd`，默认 `fast`。

接口流程：

1. 根据 `style_id` 从风格注册表查找内置风格。
2. 找不到时返回 `3001 style not found`。
3. 校验 `style_strength`、`content_weight`、`smoothness` 和 `quality`，非法时返回 `3002`。
4. 读取并校验上传图片。
5. 调用风格迁移服务生成图片。
6. 将结果保存到 `data/outputs/static/results`，并返回 `/static/results/...png`。

成功响应核心字段：

```json
{
  "result_url": "/static/results/result_xxx.png",
  "time_ms": 2300,
  "parameters": {
    "style_strength": 80,
    "content_weight": 50,
    "smoothness": 30,
    "quality": "fast"
  }
}
```

### 4.4 使用自定义风格图执行风格迁移

接口：`POST /api/custom-style-transfer`

这是项目实际新增的亮点接口。它不依赖内置 `style_id`，而是由用户同时上传内容图和风格图。

请求字段：

- `image`：内容图，必填。
- `style_image`：用户上传的风格图，必填。
- `style_strength`：风格强度，0-100，默认 70。
- `content_weight`：内容保留程度，0-100，默认 50。
- `smoothness`：平滑程度，0-100，默认 30。
- `quality`：质量档位，默认 `fast`。

和 `/api/style-transfer` 的区别：

- `/api/style-transfer` 使用服务端内置风格，需要传 `style_id`。
- `/api/custom-style-transfer` 使用本次上传的 `style_image`，不需要 `style_id`。
- 两者复用同一套 VGG19 风格迁移算法、参数校验、图片校验、串行锁和结果保存逻辑。

验收时可以强调：内置风格适合快速选择，自定义风格让用户可以上传任意参考图，扩展了个性化创作能力。

### 4.5 静态资源访问

接口前缀：`GET /static/{path}`

用途：

- `/static/styles/...`：访问内置风格预览图。
- `/static/results/...`：访问生成结果图。

前端拿到 `result_url` 后，需要拼接服务地址，例如：

```text
http://127.0.0.1:8000 + /static/results/result_xxx.png
```

## 5. 风格列表加载逻辑怎么讲

风格管理在 [`src/style_transferring_server/styles.py`](../src/style_transferring_server/styles.py)。核心职责：

1. 读取 [`config/styles.json`](../config/styles.json) 中的候选风格。
2. 根据 `query` 在 WikiArt `classes.csv` 或图片文件名中匹配具体作品。
3. 如果精确匹配不到，再根据 `fallback_genre` 到对应画派目录中兜底选择图片。
4. 找到图片后生成长边为配置值的 JPEG 预览图。
5. 对前端只暴露 `style_id`、`name`、`artist`、`description`、`preview_url`，隐藏本地文件路径。

当前候选内置风格：

| style_id | 名称 | 艺术家 |
| --- | --- | --- |
| `vangogh` | 梵高星空 | Vincent van Gogh |
| `picasso` | 毕加索立体主义 | Pablo Picasso |
| `monet` | 莫奈印象派 | Claude Monet |
| `kandinsky` | 康定斯基表现主义 | Wassily Kandinsky |
| `hokusai` | 葛饰北斋浮世绘 | Katsushika Hokusai |
| `munch` | 蒙克表现主义 | Edvard Munch |

## 6. 风格迁移核心算法怎么讲

核心类是 [`StyleTransferService`](../src/style_transferring_server/transfer.py)，它封装了模型加载、输入校验、算法推理和结果保存。

### 6.1 自动选择运行设备

服务启动时通过 `torch.cuda.is_available()` 判断是否有 CUDA：

- 有 CUDA 就使用 GPU。
- 没有 CUDA 就自动退回 CPU。

健康检查会返回实际设备，便于前端或验收时确认运行环境。

### 6.2 加载 VGG19 特征提取网络

项目使用 torchvision 的 VGG19，只取 `features` 部分作为固定特征提取器，并将所有参数 `requires_grad` 设为 `False`。

重点讲法：这里不是训练 VGG19，而是借助 ImageNet 预训练 VGG19 的卷积层来提取内容特征和风格特征。真正被优化的是生成图片本身。

### 6.3 图片校验

上传图片校验包括：

- 内容不能为空。
- 大小不能超过 `max_upload_mb`，默认 10 MB。
- 扩展名只允许 jpg、jpeg、png。
- Pillow `verify()` 校验真实图片内容，防止伪造后缀。
- 真实格式只接受 JPEG 或 PNG。
- 宽高必须在 16 px 到 12000 px 之间。
- 使用 `ImageOps.exif_transpose()` 处理手机照片 EXIF 方向。

这部分体现服务端鲁棒性，不是简单接收文件后直接跑模型。

### 6.4 特征提取和 Gram 矩阵

算法使用 VGG19 的多层特征：

- 内容层：第 21 层。
- 风格层：第 0、5、10、19、28 层。

浅层更关注颜色、边缘和纹理，深层更关注结构和语义。风格图的每个风格层会计算 Gram 矩阵，用于表示通道之间的相关性，也就是纹理、笔触和颜色分布。

一句话解释：内容图提供结构，风格图提供纹理统计，Gram 矩阵负责衡量“风格像不像”。

### 6.5 优化生成图

优化流程：

1. 将内容图和风格图缩放到质量档位对应尺寸。
2. 提取内容图特征和风格图特征。
3. 计算风格图各层 Gram 矩阵。
4. 生成图初始为内容图的拷贝。
5. 使用 `torch.optim.LBFGS` 优化生成图像素，而不是优化模型参数。
6. 损失函数由内容损失、风格损失和总变分损失组成。
7. 每个外层 step 后将像素 clamp 到 0 到 1。
8. 超过 `timeout_s` 返回 `3006 inference timeout`。
9. 输出 tensor 转成图片，并根据 `smoothness` 应用 Pillow 平滑滤镜。
10. 保存 PNG 结果并返回 `result_url`。

一句话总结算法：VGG19 固定不动，优化的是生成图片，让它既保留内容图结构，又接近风格图的纹理统计。

## 7. 参数设计怎么讲

### 7.1 style_strength

`style_strength` 范围 0 到 100，是控制风格浓淡的主参数。

项目不是简单线性增加 `style_weight`，而是主要通过指数级降低内容损失权重来改变 style/content 损失比。当前映射大致是：

- strength = 0：内容约束强，结果接近原图。
- strength = 50：中段已经明显风格化。
- strength = 100：内容约束很弱，风格覆盖最明显。

### 7.2 content_weight

`content_weight` 范围 0 到 100，用于在 `style_strength` 的基础上二次调节内容保留程度。

当前逻辑是把基础内容权重按 0.2x 到 1.5x 缩放：

- 值越高，越保留原图结构。
- 值越低，风格越容易覆盖内容。

### 7.3 smoothness

`smoothness` 范围 0 到 100，有两层作用：

- 参与 total variation loss，减少优化过程中的噪点。
- 生成后使用 Pillow 平滑滤镜，让结果更柔和。

### 7.4 quality

`quality` 有三档：

| quality | 长边像素 | 外层步数 | LBFGS max_iter | README 实测耗时 |
| --- | --- | --- | --- | --- |
| `fast` | 384 | 8 | 12 | 约 2.5s |
| `normal` | 448 | 12 | 16 | 约 5s |
| `hd` | 576 | 16 | 20 | 约 11s |

讲法：质量越高，参与推理的图片越大，优化更充分，细节更好，但耗时也更长，必要时要调大 `timeout_s`。

## 8. 并发、性能和工程化怎么讲

项目的性能和稳定性设计点：

1. 自动选择 CUDA 或 CPU。
2. 启动时可 warmup，提前触发 cudnn autotune 和显存分配，降低首个真实请求冷启动尖峰。
3. 风格迁移请求通过 `asyncio.Lock` 串行执行，避免多请求同时占用显存导致 OOM。
4. 真实推理放到后台线程执行，避免阻塞 FastAPI 事件循环。
5. 捕获 CUDA OOM，并返回 `3005 CUDA out of memory`，不会直接崩服务。
6. 内置风格迁移和自定义风格迁移复用同一个底层算法管线。
7. 日志中间件为每个请求生成 request_id，记录方法、路径、状态码、耗时和迁移参数。
8. 支持文本日志、JSON 日志和文件日志，便于开发调试和部署采集。

验收时可以说：由于神经风格迁移是显存密集型任务，本项目主动牺牲单进程并发换稳定性，更适合课程设计展示、单机部署和小规模联调。

## 9. 错误码和统一响应怎么讲

所有业务接口使用统一响应结构：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

失败时：

```json
{
  "code": 3001,
  "message": "style not found",
  "data": null
}
```

错误码集中定义在 [`src/style_transferring_server/constants.py`](../src/style_transferring_server/constants.py)：

- `1000`：通用错误或参数错误。
- `2001`：图片为空。
- `2002`：图片不可读，或自定义风格图为空。
- `2003`：图片格式不支持。
- `2004`：图片太大。
- `2005`：图片尺寸非法。
- `3001`：内置风格不存在。
- `3002`：迁移参数非法。
- `3003`：模型加载失败。
- `3004`：推理失败。
- `3005`：CUDA 显存不足。
- `3006`：推理超时。

另外还有一个特殊点：未匹配到的接口会被映射成 HTTP 418，返回 `code=1000`、`message=YOU ARE A TEAPOT`，对应测试里也覆盖了这个分支。

## 10. 测试怎么讲

测试分两类：

### 10.1 API 契约测试

在 [`tests/test_api_contract.py`](../tests/test_api_contract.py)，覆盖：

- 健康检查成功。
- 风格列表响应结构。
- 内置风格迁移成功。
- PNG 上传成功。
- 风格不存在返回 `3001`。
- 参数越界返回 `3002`。
- quality 非法返回 `3002`。
- 扩展名不支持返回 `2003`。
- 图片损坏返回 `2002`。
- 缺少 image 字段返回 `1000`。
- 自定义风格迁移成功。
- 自定义风格图缺失返回 `1000`。
- 自定义风格图为空返回 `2002 style image is required`。
- 自定义风格迁移 quality 非法返回 `3002`。
- 未匹配接口返回 HTTP 418。

### 10.2 配置和风格解析测试

在 [`tests/test_config.py`](../tests/test_config.py)，覆盖：

- JSON 配置加载。
- 环境变量覆盖 JSON。
- 构造参数优先级最高。
- 派生目录正确。
- 风格候选解析。

### 10.3 为什么测试不跑真实模型

[`tests/conftest.py`](../tests/conftest.py) 做了桩替换：

- 禁用预训练 VGG 和 warmup，避免下载模型和 GPU 依赖。
- 注入虚拟风格，避免依赖完整 WikiArt 数据集。
- 替换真实推理过程，让测试快速稳定。

验收时可以说：测试重点是接口契约和错误码稳定性，不是评估 GPU 生成效果，所以用桩隔离重资源依赖，保证离线也能跑。

运行测试：

```powershell
uv run pytest -q
```

静态类型检查：

```powershell
uv run --with pyright pyright src/style_transferring_server tests
```

## 11. 建议讲解顺序

1. 项目目标：上传内容图，选择内置风格或上传自定义风格图，生成艺术化结果。
2. 技术栈：FastAPI 提供接口，PyTorch + VGG19 做神经风格迁移，Pillow 处理图片。
3. 系统流程：客户端 → HTTP 接口 → 参数和图片校验 → 风格图准备 → VGG 特征提取 → LBFGS 优化 → 保存结果 → 返回 URL。
4. 接口：健康检查、风格列表、内置风格迁移、自定义风格迁移、静态资源访问。
5. 风格配置：内置风格由 JSON 配置和 WikiArt 数据集驱动。
6. 核心算法：VGG19 特征、Gram 矩阵、内容损失、风格损失、总变分损失、LBFGS 优化。
7. 参数：style_strength、content_weight、smoothness、quality 如何影响效果和耗时。
8. 工程化：统一响应、错误码、CORS、日志、配置优先级、预热、串行锁、防 OOM。
9. 测试：契约测试覆盖接口和错误分支，配置测试覆盖配置优先级。

## 12. 验收时可直接背的版本

“我们这个项目实现的是一个图像风格迁移后端服务。客户端可以上传一张内容图片，选择内置风格 ID，比如梵高、莫奈，也可以上传一张自定义风格图。后端用 FastAPI 接收 multipart 请求，先校验图片格式、大小、真实内容和参数范围，然后准备风格图。核心算法使用 PyTorch 加载 VGG19 的特征提取层，内容图提取内容特征，风格图通过多层特征的 Gram 矩阵表示纹理和笔触。生成图初始为内容图，然后使用 LBFGS 优化生成图本身，让它同时满足内容损失、风格损失和总变分平滑损失。最后服务端把 PNG 结果保存到 static/results 目录，并返回 result_url、time_ms 和实际参数。项目还实现了统一 code/message/data 响应、业务错误码、内置风格 JSON 配置、自定义风格上传、GPU/CPU 自动选择、启动预热、串行锁防显存溢出、请求日志和契约测试。”

## 13. 如果老师问“你的亮点是什么”

可以回答：

1. 接口契约清晰：统一 `code/message/data`，错误码集中定义，契约测试覆盖主要成功和失败分支。
2. 支持两种风格来源：既支持内置 WikiArt 风格，也支持用户上传自定义风格图。
3. 风格配置可扩展：内置风格由 [`config/styles.json`](../config/styles.json) 驱动，新增候选风格不需要修改接口代码。
4. 算法不是简单滤镜：使用 VGG19 特征、Gram 矩阵和 LBFGS 优化实现神经风格迁移。
5. 参数可控：`style_strength`、`content_weight`、`smoothness`、`quality` 分别控制风格强度、内容保留、平滑程度和质量耗时。
6. 工程化完整：支持配置优先级、日志、CORS、静态资源挂载、异常处理、模型预热和测试。
7. 性能稳定性有考虑：自动使用 GPU，串行锁防 OOM，CUDA OOM 和超时都有明确错误码。

## 14. 如果老师问“为什么用 VGG19”

可以答：

“VGG19 的卷积层结构规整，浅层可以提取颜色、边缘、纹理等低级特征，深层可以提取更抽象的内容结构，所以经典神经风格迁移经常用 VGG19 作为固定特征提取器。我们不训练 VGG19，只用它计算内容损失和风格损失，真正被优化的是生成图片。”

对应代码主要在 [`src/style_transferring_server/transfer.py`](../src/style_transferring_server/transfer.py) 的模型加载、特征提取和优化逻辑。

## 15. 如果老师问“style_strength 怎么实现”

可以答：

“style_strength 没有简单线性乘 style_weight。项目里主要通过指数级降低 content_weight 来改变风格损失和内容损失的比例。style_strength 越高，内容约束越弱，风格越明显；style_strength 越低，内容约束越强，结果越接近原图。当前实现还配合较高的 style_weight、strong_wolfe line search 和更充分的 LBFGS 内迭代，让风格强度真正显现。”

## 16. 如果老师问“自定义风格迁移怎么实现”

可以答：

“自定义风格迁移接口是 `/api/custom-style-transfer`。它和内置风格迁移共用同一套底层算法，只是风格图来源不同。内置接口通过 `style_id` 找到服务端风格图，自定义接口直接读取用户上传的 `style_image`。两张图都会经过同样的格式、大小、真实图片内容和尺寸校验，然后转成 tensor 输入 VGG19，后续 Gram 矩阵、LBFGS 优化和结果保存流程完全复用。”

## 17. 如果老师问“怎么保证接口稳定”

可以答：

“我们有契约测试，测试不依赖真实 GPU 和 WikiArt 数据集，而是通过 monkeypatch 注入虚拟风格和桩推理。测试重点验证接口响应结构、HTTP 状态码和业务错误码，例如风格不存在、参数越界、图片损坏、缺少字段、自定义风格图缺失、非法 quality 以及不存在接口等分支。”

对应测试在 [`tests/test_api_contract.py`](../tests/test_api_contract.py)，测试桩在 [`tests/conftest.py`](../tests/conftest.py)。
