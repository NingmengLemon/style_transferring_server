\# 个性化数字艺术创作系统 HTTP API 文档

\## 1. 项目说明

项目名称：

> 基于图像风格迁移的个性化数字艺术创作系统设计与实现

系统采用客户端-服务端分离架构：

```

HarmonyOS ArkTS App

&#x20;       |

&#x20;       | HTTP

&#x20;       |

Python FastAPI + PyTorch

&#x20;       |

&#x20;       |

VGG Neural Style Transfer

```

\### 客户端职责

\* 用户图片选择

\* 风格选择

\* 参数调整

\* 调用风格迁移接口

\* 展示生成结果

\* 下载图片

\* 本地保存历史作品

\### Python 服务端职责

\* 加载 VGG 风格迁移模型

\* 接收图片和参数

\* 执行图像风格迁移

\* 保存生成图片

\* 返回生成结果地址

\---

\# 2. 基础信息

\## 服务地址

开发环境：

```

http://<server-ip>:8000

```

例如：

```

http://192.168.1.100:8000

```

\---

\## 请求格式

普通 JSON 请求：

```

Content-Type: application/json

```

图片上传请求：

```

Content-Type: multipart/form-data

```

\---

\# 3. 统一响应格式

所有接口统一返回：

\## 成功

```json

{

&#x20;   "code": 0,

&#x20;   "message": "success",

&#x20;   "data": {}

}

```

\## 失败

```json

{

&#x20;   "code": 1000,

&#x20;   "message": "error message",

&#x20;   "data": null

}

```

字段说明：

| 字段      | 类型     | 说明   |

| ------- | ------ | ---- |

| code    | int    | 状态码  |

| message | string | 描述信息 |

| data    | object | 返回数据 |

\---

\# 4. 状态码设计

\## 通用错误

| code | HTTP状态码 | 说明     |

| ---- | ------- | ------ |

| 0    | 200     | 请求成功   |

| 1000 | 400     | 参数错误   |

| 1001 | 401     | 未授权    |

| 1002 | 404     | 资源不存在  |

| 1003 | 405     | 请求方法错误 |

| 1004 | 413     | 请求数据过大 |

| 1005 | 415     | 格式不支持  |

\---

\## 图片相关错误

| code | HTTP状态码 | 说明       |

| ---- | ------- | -------- |

| 2001 | 400     | 未上传图片    |

| 2002 | 400     | 图片无法读取   |

| 2003 | 415     | 图片格式不支持  |

| 2004 | 413     | 图片超过大小限制 |

| 2005 | 400     | 图片尺寸异常   |

支持格式：

```

jpg

jpeg

png

```

建议限制：

```

最大 10MB

```

\---

\## 风格迁移相关错误

| code | HTTP状态码 | 说明      |

| ---- | ------- | ------- |

| 3001 | 400     | 风格ID不存在 |

| 3002 | 400     | 参数范围错误  |

| 3003 | 500     | 模型加载失败  |

| 3004 | 500     | 模型推理失败  |

| 3005 | 503     | GPU资源不足 |

| 3006 | 504     | 推理超时    |

\---

\# 5. API列表

| 接口                  | 方法   | 说明     |

| ------------------- | ---- | ------ |

| /api/health         | GET  | 服务状态检查 |

| /api/styles         | GET  | 获取风格列表 |

| /api/style-transfer | POST | 执行风格迁移 |

| /static/\*           | GET  | 访问生成图片 |

\---

\# API 1：健康检查

\## GET /api/health

\### 功能

检查 Python 后端服务和模型状态。

\---

\## 请求

```http

GET /api/health

```

\---

\## 响应

成功：

```json

{

&#x20;   "code":0,

&#x20;   "message":"success",

&#x20;   "data":{

&#x20;       "status":"running",

&#x20;       "model\_loaded":true,

&#x20;       "device":"cuda"

&#x20;   }

}

```

字段：

| 字段           | 说明     |

| ------------ | ------ |

| status       | 服务运行状态 |

| model\_loaded | 模型是否加载 |

| device       | 运行设备   |

\---

\## 失败

模型加载失败：

```json

{

&#x20;   "code":3003,

&#x20;   "message":"model loading failed",

&#x20;   "data":null

}

```

\---

\# API 2：获取风格列表

\## GET /api/styles

\### 功能

获取系统支持的艺术风格。

风格来源：

```

WikiArt Dataset

```

\---

\## 请求

```http

GET /api/styles

```

\---

\## 返回

```json

{

&#x20;   "code":0,

&#x20;   "message":"success",

&#x20;   "data":{

&#x20;       "styles":\[

&#x20;           {

&#x20;               "style\_id":"vangogh",

&#x20;               "name":"梵高星空",

&#x20;               "artist":"Vincent van Gogh",

&#x20;               "description":"旋涡笔触和高饱和色彩风格",

&#x20;               "preview\_url":

&#x20;               "/static/styles/vangogh.jpg"

&#x20;           },

&#x20;           {

&#x20;               "style\_id":"picasso",

&#x20;               "name":"毕加索立体主义",

&#x20;               "artist":"Pablo Picasso",

&#x20;               "description":"几何分解和抽象结构风格",

&#x20;               "preview\_url":

&#x20;               "/static/styles/picasso.jpg"

&#x20;           }

&#x20;       ]

&#x20;   }

}

```

\---

\## 返回字段

| 字段          | 类型     | 说明     |

| ----------- | ------ | ------ |

| style\_id    | string | 风格唯一编号 |

| name        | string | 风格名称   |

| artist      | string | 艺术家    |

| description | string | 风格描述   |

| preview\_url | string | 风格预览图  |

\---

\# API 3：图像风格迁移

\## POST /api/style-transfer

\### 功能

上传内容图像，并根据指定风格生成艺术作品。

\---

\## 请求方式

```

multipart/form-data

```

\---

\## 请求参数

| 参数             | 类型     | 必须 | 说明     |

| -------------- | ------ | -- | ------ |

| image          | file   | 是  | 内容图像   |

| style\_id       | string | 是  | 风格ID   |

| style\_strength | int    | 否  | 风格强度   |

| content\_weight | int    | 否  | 内容保留程度 |

| smoothness     | int    | 否  | 细节平滑程度 |

| quality        | string | 否  | 生成质量   |

\---

\## 参数约束

\### style\_strength

范围：

```

0 \~ 100

```

默认：

```

70

```

\---

\### content\_weight

范围：

```

0 \~ 100

```

默认：

```

50

```

\---

\### smoothness

范围：

```

0 \~ 100

```

默认：

```

30

```

\---

\### quality

可选：

```

fast

normal

hd

```

默认：

```

fast

```

\---

\## 请求示例

```

image:

photo.jpg



style\_id:

vangogh



style\_strength:

80



content\_weight:

50



smoothness:

30



quality:

fast

```

\---

\# 后端处理流程

```

接收图片



↓



读取style\_id



↓



加载对应风格图片



↓



图像预处理



↓



VGG特征提取



↓



计算内容损失和风格损失



↓



生成艺术图像



↓



保存结果



↓



返回图片地址

```

\---

\# 成功响应

```json

{

&#x20;   "code":0,

&#x20;   "message":"success",

&#x20;   "data":{

&#x20;       "result\_url":

&#x20;       "/static/results/result001.png",



&#x20;       "time\_ms":2300,



&#x20;       "parameters":{

&#x20;           "style\_strength":80,

&#x20;           "content\_weight":50,

&#x20;           "smoothness":30,

&#x20;           "quality":"fast"

&#x20;       }

&#x20;   }

}

```

\---

\## 返回字段

| 字段         | 类型     | 说明     |

| ---------- | ------ | ------ |

| result\_url | string | 生成图片地址 |

| time\_ms    | int    | 生成耗时   |

| parameters | object | 实际使用参数 |

\---

\# 失败情况

\## 1. 未上传图片

响应：

```json

{

&#x20;   "code":2001,

&#x20;   "message":"image is required",

&#x20;   "data":null

}

```

\---

\## 2. 图片格式错误

响应：

```json

{

&#x20;   "code":2003,

&#x20;   "message":"only jpg/png/jpeg supported",

&#x20;   "data":null

}

```

\---

\## 3. 风格不存在

响应：

```json

{

&#x20;   "code":3001,

&#x20;   "message":"style not found",

&#x20;   "data":null

}

```

\---

\## 4. 参数错误

例如：

```

style\_strength=150

```

响应：

```json

{

&#x20;   "code":3002,

&#x20;   "message":"style\_strength must between 0 and 100",

&#x20;   "data":null

}

```

\---

\## 5. 模型推理失败

响应：

```json

{

&#x20;   "code":3004,

&#x20;   "message":"style transfer failed",

&#x20;   "data":null

}

```

\---

\## 6. GPU显存不足

响应：

```json

{

&#x20;   "code":3005,

&#x20;   "message":"CUDA out of memory",

&#x20;   "data":null

}

```

\---

\## 7. 推理超时

响应：

```json

{

&#x20;   "code":3006,

&#x20;   "message":"inference timeout",

&#x20;   "data":null

}

```

\---

\# API 4：访问生成图片

\## GET /static/{path}

\### 功能

客户端根据返回 URL 获取生成图片。

例如：

```http

GET /static/results/result001.png

```

\---

\## 返回

```

Content-Type:image/png

```

返回图片二进制数据。

\---

\# 6. 客户端本地历史作品数据结构

历史记录不存储在 Python 服务端。

由 HarmonyOS 本地保存。

\## Work对象

```json

{

&#x20;   "work\_id":"work001",

&#x20;   "input\_image\_path":

&#x20;   "/local/input001.jpg",



&#x20;   "result\_image\_path":

&#x20;   "/local/result001.png",



&#x20;   "style\_id":"vangogh",



&#x20;   "style\_name":"梵高星空",



&#x20;   "parameters":{

&#x20;       "style\_strength":80,

&#x20;       "content\_weight":50,

&#x20;       "smoothness":30,

&#x20;       "quality":"fast"

&#x20;   },



&#x20;   "created\_time":

&#x20;   "2026-07-08 18:00:00"

}

```

\---

\# 7. 客户端调用流程

```

App启动



↓



GET /api/health



↓



GET /api/styles



↓



用户选择图片



↓



用户选择风格



↓



调整参数



↓



POST /api/style-transfer



↓



获取result\_url



↓



展示生成图片



↓



保存本地历史记录

```

\---

\# 8. 联调约定

\## 服务端固定：

接口路径：

```

POST /api/style-transfer

```

字段：

```

style\_id

style\_strength

content\_weight

smoothness

quality

```

返回：

```

result\_url

time\_ms

parameters

```

\---

\## 客户端固定：

只依赖：

```

API地址

请求字段

返回字段

```

\---

\# 9. 最小可交付接口

实际开发只需要实现：

```

GET  /api/health



GET  /api/styles



POST /api/style-transfer



GET  /static/\*

```

即可完成完整 App 流程。

```

```
