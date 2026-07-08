# 风格迁移项目 HTTP API 文档

> 项目：基于图像风格迁移的个性化数字艺术创作系统设计与实现  
> 服务端：FastAPI + PyTorch + VGG19 神经风格迁移  
> 客户端：HarmonyOS ArkTS App 或其他 HTTP 客户端

## 1. 文档说明

本文档用于客户端与 Python 后端联调，描述当前服务端已经提供的 HTTP 接口、请求参数、响应结构、错误码和典型调用流程。

当前后端采用前后端分离架构：

```text
HarmonyOS ArkTS App / Web / 其他客户端
        |
        | HTTP
        v
Python FastAPI 服务
        |
        | PyTorch + VGG19
        v
神经风格迁移结果图像
```

### 1.1 客户端职责

- 选择或拍摄内容图像。
- 获取后端支持的艺术风格列表。
- 选择风格并调整风格迁移参数。
- 调用风格迁移接口上传图片。
- 展示后端返回的生成图片。
- 下载或本地保存历史作品。

### 1.2 服务端职责

- 维护可用风格列表与风格预览图。
- 接收内容图像和参数。
- 校验图片格式、大小、尺寸与参数范围。
- 使用 VGG19 执行神经风格迁移。
- 保存生成结果图片。
- 返回生成图片访问地址与实际使用参数。

## 2. 基础信息

### 2.1 服务地址

开发环境默认监听：

```text
http://<server-ip>:8000
```

本机调试示例：

```text
http://127.0.0.1:8000
```

局域网真机调试示例：

```text
http://192.168.1.100:8000
```

实际地址由服务端运行环境决定，默认端口为 `8000`。

### 2.2 接口前缀

业务接口统一使用 `/api` 前缀：

```text
/api/health
/api/styles
/api/style-transfer
```

静态资源通过 `/static` 访问：

```text
/static/styles/{style_id}.jpg
/static/results/{result_file}.png
```

### 2.3 请求类型

| 场景 | Content-Type | 说明 |
| --- | --- | --- |
| 普通查询接口 | `application/json` 或无请求体 | 例如健康检查、风格列表 |
| 图片上传接口 | `multipart/form-data` | 用于上传图片和表单参数 |

### 2.4 跨域策略

当前服务端允许跨域访问，便于 App、Web 或其他客户端联调。

## 3. 统一响应格式

所有业务接口返回统一 JSON 结构。

### 3.1 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

### 3.2 失败响应

```json
{
  "code": 1000,
  "message": "error message",
  "data": null
}
```

### 3.3 字段说明

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `code` | int | 是 | 业务状态码，`0` 表示成功 |
| `message` | string | 是 | 响应说明或错误说明 |
| `data` | object / null | 是 | 成功时为业务数据，失败时为 `null` |

## 4. 错误码

### 4.1 通用错误码

| code | HTTP 状态码 | 说明 | 常见场景 |
| --- | --- | --- | --- |
| `0` | `200` | 请求成功 | 接口正常返回 |
| `1000` | `400` / `500` | 通用错误或参数错误 | 表单字段缺失、类型错误、未捕获异常 |

> 说明：FastAPI 表单校验失败会统一映射为 `1000`，例如缺少必填的 `image` 或 `style_id` 字段。

### 4.2 图片相关错误码

| code | HTTP 状态码 | 说明 | message 示例 |
| --- | --- | --- | --- |
| `2001` | `400` | 未上传图片或图片内容为空 | `image is required` |
| `2002` | `400` | 图片无法读取或内容损坏 | `image cannot be read` |
| `2003` | `415` | 图片格式不支持 | `only jpg/png/jpeg supported` |
| `2004` | `413` | 图片超过大小限制 | `image exceeds size limit` |
| `2005` | `400` | 图片尺寸异常 | `invalid image size` |

图片限制：

| 项目 | 约束 |
| --- | --- |
| 支持扩展名 | `jpg`、`jpeg`、`png` |
| 支持真实格式 | JPEG、PNG |
| 默认最大体积 | 10 MB |
| 最小尺寸 | 宽高均不小于 16 px |
| 最大尺寸 | 宽高均不大于 12000 px |

### 4.3 风格迁移相关错误码

| code | HTTP 状态码 | 说明 | message 示例 |
| --- | --- | --- | --- |
| `3001` | `400` | 风格 ID 不存在 | `style not found` |
| `3002` | `400` | 参数范围或枚举值错误 | `style_strength must between 0 and 100` |
| `3003` | `500` | 模型加载失败 | `model loading failed` |
| `3004` | `500` | 模型推理失败 | `style transfer failed` |
| `3005` | `503` | GPU 显存不足 | `CUDA out of memory` |
| `3006` | `504` | 推理超时 | `inference timeout` |

## 5. API 总览

| 接口 | 方法 | Content-Type | 说明 |
| --- | --- | --- | --- |
| `/api/health` | GET | 无请求体 | 服务与模型状态检查 |
| `/api/styles` | GET | 无请求体 | 获取可选艺术风格列表 |
| `/api/style-transfer` | POST | `multipart/form-data` | 上传图片并执行风格迁移 |
| `/static/{path}` | GET | 无请求体 | 访问风格预览图或生成结果图 |

## 6. API 详情

## 6.1 健康检查

### 基本信息

```http
GET /api/health
```

用于检查后端服务是否可用，以及 VGG19 模型是否已经加载成功。

### 请求参数

无。

### 成功响应

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

### data 字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | 服务运行状态，正常为 `running` |
| `model_loaded` | boolean | 模型是否已成功加载 |
| `device` | string | 推理设备，例如 `cuda` 或 `cpu` |

### 失败响应示例

模型加载失败：

```json
{
  "code": 3003,
  "message": "model loading failed",
  "data": null
}
```

## 6.2 获取风格列表

### 基本信息

```http
GET /api/styles
```

用于获取服务端当前可用的艺术风格。风格图来源于 WikiArt 数据集，并由服务端生成静态预览图。

### 请求参数

无。

### 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "styles": [
      {
        "style_id": "vangogh",
        "name": "梵高星空",
        "artist": "Vincent van Gogh",
        "description": "后印象派旋涡笔触和高饱和色彩风格",
        "preview_url": "/static/styles/vangogh.jpg"
      },
      {
        "style_id": "picasso",
        "name": "毕加索立体主义",
        "artist": "Pablo Picasso",
        "description": "几何分解、平面化与抽象结构风格",
        "preview_url": "/static/styles/picasso.jpg"
      }
    ]
  }
}
```

### data 字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `styles` | array | 可用风格列表 |

### styles 数组元素说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `style_id` | string | 风格唯一 ID，调用风格迁移接口时使用 |
| `name` | string | 风格中文名称 |
| `artist` | string | 艺术家名称 |
| `description` | string | 风格描述 |
| `preview_url` | string | 风格预览图相对 URL |

### 当前内置候选风格

服务端会根据本地 WikiArt 数据集实际可用文件加载风格，因此最终返回列表以接口结果为准。候选风格包括：

| style_id | 名称 | 艺术家 |
| --- | --- | --- |
| `vangogh` | 梵高星空 | Vincent van Gogh |
| `picasso` | 毕加索立体主义 | Pablo Picasso |
| `monet` | 莫奈印象派 | Claude Monet |
| `kandinsky` | 康定斯基表现主义 | Wassily Kandinsky |
| `hokusai` | 葛饰北斋浮世绘 | Katsushika Hokusai |
| `munch` | 蒙克表现主义 | Edvard Munch |

## 6.3 图像风格迁移

### 基本信息

```http
POST /api/style-transfer
Content-Type: multipart/form-data
```

上传一张内容图像，指定艺术风格和参数，服务端返回生成后的艺术图片 URL。

### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `image` | file | 是 | 无 | 内容图像文件，支持 jpg、jpeg、png |
| `style_id` | string | 是 | 无 | 风格 ID，来自 `/api/styles` 返回值 |
| `style_strength` | int | 否 | `70` | 风格强度，越大越接近风格图 |
| `content_weight` | int | 否 | `50` | 内容保留权重，越大越保留原图结构 |
| `smoothness` | int | 否 | `30` | 平滑程度，越大细节越柔和 |
| `quality` | string | 否 | `fast` | 质量档位，可选 `fast`、`normal`、`hd` |

### 参数约束

| 参数 | 允许值 |
| --- | --- |
| `style_strength` | 0 到 100 的整数 |
| `content_weight` | 0 到 100 的整数 |
| `smoothness` | 0 到 100 的整数 |
| `quality` | `fast`、`normal`、`hd` |

### 质量档位说明

| quality | 处理长边上限 | 迭代次数 | 说明 |
| --- | --- | --- | --- |
| `fast` | 384 px | 18 | 默认档位，优先保证速度 |
| `normal` | 448 px | 22 | 平衡速度与效果 |
| `hd` | 640 px | 40 | 高质量档，耗时可能明显增加 |

> 注意：返回图片始终为 PNG 格式；输入图片会按质量档位缩放后参与推理。

### 请求示例：curl

```bash
curl -X POST "http://127.0.0.1:8000/api/style-transfer" \
  -F "image=@photo.jpg" \
  -F "style_id=vangogh" \
  -F "style_strength=80" \
  -F "content_weight=50" \
  -F "smoothness=30" \
  -F "quality=fast"
```

### 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "result_url": "/static/results/result_8dfb8a6f4c0345f391f1d2d2a47c2a73.png",
    "time_ms": 2300,
    "parameters": {
      "style_strength": 80,
      "content_weight": 50,
      "smoothness": 30,
      "quality": "fast"
    }
  }
}
```

### data 字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `result_url` | string | 生成图片的相对访问地址 |
| `time_ms` | int | 本次处理耗时，单位毫秒 |
| `parameters` | object | 服务端实际使用的参数 |

### parameters 字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `style_strength` | int | 实际使用的风格强度 |
| `content_weight` | int | 实际使用的内容保留权重 |
| `smoothness` | int | 实际使用的平滑程度 |
| `quality` | string | 实际使用的质量档位 |

### 失败响应示例

未上传图片或图片字段缺失：

```json
{
  "code": 1000,
  "message": "parameter error",
  "data": null
}
```

图片内容为空：

```json
{
  "code": 2001,
  "message": "image is required",
  "data": null
}
```

图片无法读取：

```json
{
  "code": 2002,
  "message": "image cannot be read",
  "data": null
}
```

图片格式不支持：

```json
{
  "code": 2003,
  "message": "only jpg/png/jpeg supported",
  "data": null
}
```

风格不存在：

```json
{
  "code": 3001,
  "message": "style not found",
  "data": null
}
```

参数超出范围：

```json
{
  "code": 3002,
  "message": "style_strength must between 0 and 100",
  "data": null
}
```

质量档位非法：

```json
{
  "code": 3002,
  "message": "quality must be fast, normal or hd",
  "data": null
}
```

推理超时：

```json
{
  "code": 3006,
  "message": "inference timeout",
  "data": null
}
```

## 6.4 访问静态资源

### 基本信息

```http
GET /static/{path}
```

用于访问风格预览图或生成结果图。

### 访问风格预览图

```http
GET /static/styles/vangogh.jpg
```

返回：

```text
Content-Type: image/jpeg
```

### 访问生成结果图

```http
GET /static/results/result_8dfb8a6f4c0345f391f1d2d2a47c2a73.png
```

返回：

```text
Content-Type: image/png
```

## 7. 客户端推荐调用流程

```text
App 启动
  |
  v
GET /api/health
  |
  |-- 失败：提示服务不可用或模型加载失败
  |
  v
GET /api/styles
  |
  |-- 展示风格列表和预览图
  |
  v
用户选择图片
  |
  v
用户选择 style_id 并调整参数
  |
  v
POST /api/style-transfer
  |
  |-- 失败：根据 code 展示错误提示
  |
  v
拼接服务地址 + result_url
  |
  v
展示生成图片 / 下载 / 保存历史记录
```

## 8. 客户端本地历史作品建议结构

历史记录不存储在 Python 服务端，建议客户端本地保存。

```json
{
  "work_id": "work001",
  "input_image_path": "/local/input001.jpg",
  "result_image_url": "http://127.0.0.1:8000/static/results/result_8dfb8a6f4c0345f391f1d2d2a47c2a73.png",
  "style_id": "vangogh",
  "style_name": "梵高星空",
  "parameters": {
    "style_strength": 80,
    "content_weight": 50,
    "smoothness": 30,
    "quality": "fast"
  },
  "time_ms": 2300,
  "created_time": "2026-07-08 18:00:00"
}
```

字段建议：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `work_id` | string | 客户端生成的历史作品 ID |
| `input_image_path` | string | 原始图片本地路径 |
| `result_image_url` | string | 生成图片完整 URL |
| `style_id` | string | 使用的风格 ID |
| `style_name` | string | 使用的风格名称 |
| `parameters` | object | 生成时使用的参数 |
| `time_ms` | int | 服务端返回的处理耗时 |
| `created_time` | string | 客户端保存时间 |

## 9. 联调约定

### 9.1 服务端固定约定

必须稳定提供以下接口：

```text
GET  /api/health
GET  /api/styles
POST /api/style-transfer
GET  /static/{path}
```

`POST /api/style-transfer` 固定请求字段：

```text
image
style_id
style_strength
content_weight
smoothness
quality
```

`POST /api/style-transfer` 固定返回字段：

```text
result_url
time_ms
parameters
```

### 9.2 客户端固定约定

客户端只依赖以下内容：

- 服务地址。
- API 路径。
- 请求字段名。
- 响应字段名。
- 业务错误码。

客户端展示图片时，需要将服务地址与相对 URL 拼接：

```text
http://<server-ip>:8000 + /static/results/xxx.png
```

示例：

```text
http://127.0.0.1:8000/static/results/result_8dfb8a6f4c0345f391f1d2d2a47c2a73.png
```

## 10. 最小可交付接口

完成完整 App 流程至少需要实现并联通以下接口：

```text
GET  /api/health
GET  /api/styles
POST /api/style-transfer
GET  /static/{path}
```

其中：

- `/api/health` 用于启动时检查服务状态。
- `/api/styles` 用于渲染风格选择列表。
- `/api/style-transfer` 用于生成艺术图片。
- `/static/{path}` 用于访问风格预览图和生成结果图。
