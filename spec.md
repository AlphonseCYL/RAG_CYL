# frontend_cyl / backend_cyl 分离开发规范

本文档用于约束 `frontend_cyl/` 与 `backend_cyl/` 的独立开发。目标不是复刻主项目的所有目录形态，而是按主项目已验证的业务闭环，逐步在两个薄副本中实现可联调、可验收、可维护的前后端分离版本。

## 共同边界

- `frontend_cyl` 与 `backend_cyl` 必须通过 HTTP API 通信，前端不得直接读取后端数据库、Redis、Elasticsearch 或本地 storage 文件。
- 后端接口必须使用 Bearer JWT 鉴权保护用户数据；前端保存 token 后，除注册登录外的业务请求都必须携带 `Authorization: Bearer <token>`。
- 接口错误优先返回 FastAPI 标准 `detail`，复杂错误可返回对象形式的 `detail`，但要保持前端可读：`message`、`failed_files`、`duplicate_files` 等字段应稳定。
- SSE 聊天接口只输出 `data: ...` 行；前端只解析 `data:`，后端新增事件时必须保持 JSON 行协议兼容。
- 删除能力必须遵守根目录 `AGENTS.md`：禁止递归批量删除。需要删文件时，只能删除一个明确路径的文件；会话删除仅删除数据库记录，不得顺手递归清理目录。
- `.env` 中的真实密钥、密码、Token 不得写入本文档、提交信息或记忆；规范只记录变量名和用途。

## 目标闭环

薄副本最终按以下顺序复现主项目能力：

1. 用户注册、登录、当前用户查询。
2. 登录后进入工作台并创建会话。
3. 历史会话列表、打开会话、删除会话。
4. 加载历史消息，重登后可恢复聊天记录。
5. 聊天页发送问题，通过 SSE 流式显示回答、思考内容、引用文档和推荐问题。
6. 当前会话快速解析上传，内容写 Redis 并参与当前会话聊天。
7. 长期知识库上传，文件落盘、解析切片、embedding、写入 Elasticsearch，并写 `knowledgebases`。
8. 知识库召回内容与快速解析内容一起进入回答上下文。

## frontend_cyl 规范

### 技术栈与运行

- 使用 Vite + React 18 + TypeScript + Ant Design。
- 后端地址统一从 `VITE_API_BASE` 读取，默认可为 `http://localhost:8001`。
- 常用命令：
  - `npm run dev`
  - `npm run build`
  - `npm run preview`

### 页面与状态

- 首屏应是已登录用户的工作台，不做营销页。
- 未登录时显示登录/注册入口；登录成功后保存 `access_token` 与用户名。
- 已登录后展示：
  - 左侧会话列表；
  - 新建会话按钮；
  - 当前会话聊天窗口；
  - 当前会话快速解析上传；
  - 长期知识库上传入口；
  - 用户信息与退出登录。
- 会话状态以服务端为准。刷新页面或重新登录后，必须通过 `GET /get_sessions` 和 `GET /get_messages` 恢复列表与消息，不把本地 state 当作历史来源。
- 删除会话后，前端应刷新会话列表；若删除的是当前会话，应清空或切换当前会话。

### API 调用约束

- 注册：`POST /register`
  - 请求体：`{ "username": string, "password": string }`
  - 成功后提示用户可登录，不要求自动登录。
- 登录：`POST /login`
  - 请求体同注册。
  - 成功返回 `access_token`、`token_type`、`username`。
- 当前用户：`GET /me`
  - 用于校验 token 是否仍有效。
- 创建会话：`POST /create_session`
  - 成功后把 `session_id` 设为当前会话，并刷新历史会话。
- 会话列表：`GET /get_sessions`
  - 以返回顺序展示，通常按创建时间倒序。
- 历史消息：`GET /get_messages?session_id=...`
  - `documents`、`recommended_questions` 可能是数组，也可能是 JSON 字符串；前端必须兼容解析。
- 删除会话：`DELETE /sessions/{session_id}`
  - 删除前给用户确认。
- 快速解析：`POST /quick_parse?session_id=...`
  - `FormData` 字段名为 `file`。
  - 上传成功后展示文件名、类型、长度或后端返回的提示。
- 长期上传：`POST /upload_files?session_id=...`
  - `FormData` 字段名为 `files`，支持多文件。
  - 必须展示 `success`、`partial_success`、`failed` 三类结果。
  - 遇到 `duplicate_files` 时，明确提示用户改名后再传。
- 聊天：`POST /chat_on_docs?session_id=...`
  - 请求体：`{ "message": string }`。
  - 通过 `ReadableStream.getReader()` 读取 SSE。
  - `content` 且 `thinking !== true` 追加到回答正文。
  - `content` 且 `thinking === true` 追加到思考内容。
  - `documents` 更新引用文档展示。
  - `recommended_questions` 更新推荐追问。
  - 收到 `[DONE]` 后结束 loading 状态。

### UI/交互要求

- 聊天输入区必须阻止空消息发送。
- 当前没有会话时，发送、快速解析、长期上传都应禁用或引导先创建会话。
- 上传按钮必须在请求中显示 loading，避免重复提交。
- SSE 过程中用户能看到增量输出；异常中断时保留用户问题并显示错误。
- 推荐问题点击后可直接填入输入框或触发发送，二选一即可，但行为要明确。
- 中文文案保持面向普通使用者，不暴露内部变量名、ES、Redis 等实现细节，除非是在开发调试区域。

### 前端验收

- `npm run build` 必须通过。
- 手动联调至少覆盖：
  - 注册新用户；
  - 登录并刷新页面后仍保持登录；
  - 创建会话；
  - 发送一次普通聊天；
  - 上传一个快速解析文件后继续聊天；
  - 上传一个长期知识库文件，重复文件名会被提示；
  - 退出并重新登录后能恢复会话与历史消息；
  - 删除会话后列表与当前视图同步。

## backend_cyl 规范

### 技术栈与运行

- 使用 FastAPI + SQLAlchemy。
- 当前数据库目标是 MySQL；Redis 用于快速解析缓存；Elasticsearch 用于长期知识库检索。
- `main.py` 是后端入口，启动时初始化数据库表并注册 `chat_rt`、`user_rt`、`history_rt`。
- 关键配置只记录变量名：
  - `MYSQL_HOST`
  - `MYSQL_PORT`
  - `MYSQL_USER`
  - `MYSQL_PASSWORD`
  - `MYSQL_DATABASE`
  - `JWT_SECRET_KEY`
  - `ACCESS_TOKEN_EXPIRE_HOURS`
  - `REDIS_HOST`
  - `REDIS_PORT`
  - `REDIS_DB`
  - `QUICK_PARSE_EXPIRE_SECONDS`
  - `ES_HOST`
  - `DASHSCOPE_API_KEY`
  - `DASHSCOPE_BASE_URL`

### 路由规范

- `POST /register`
  - 校验用户名 3 到 50 字符，密码 6 到 128 字符。
  - 密码必须哈希存储，不保存明文。
  - 用户名重复返回 400。
- `POST /login`
  - 校验成功返回 Bearer token。
  - JWT payload 至少包含用户 id 或 `sub`、用户名、过期时间。
- `GET /me`
  - 从 Bearer token 解析当前用户。
- `POST /create_session`
  - 必须登录。
  - 创建 16 位左右的 `session_id`。
  - 薄副本中应立即写入 `sessions` 表，默认会话名为 `新对话`。
- `GET /get_sessions`
  - 只返回当前用户自己的会话。
- `GET /get_messages?session_id=...`
  - 必须校验会话归属。
  - 返回用户问题、模型回答、思考内容、引用文档、推荐问题和创建时间。
- `DELETE /sessions/{session_id}`
  - 必须校验会话归属。
  - 删除该会话数据库消息与会话记录。
  - 不递归删除本地上传文件目录。
- `POST /quick_parse?session_id=...`
  - 必须校验会话归属。
  - 支持 `txt`、`docx`、`pdf`。
  - 解析结果写 Redis，key 应绑定 `session_id`，value 应带 `user_id`，TTL 默认 7200 秒。
  - 快速解析不写 ES，不写 `knowledgebases`。
- `GET /get_parsed_content?session_id=...`
  - 只允许读取当前用户当前会话的 Redis 内容。
- `POST /upload_files?session_id=...`
  - 必须登录并校验会话归属。
  - `FormData` 字段名为 `files`。
  - 文件名必须用 basename 规整，禁止路径穿越。
  - 同一请求内重复文件名、用户目录已有同名文件，都必须拒绝，避免覆盖。
  - 空文件应失败，不写入 ES。
  - 成功文件应落盘、解析切片、生成 embedding、写入 ES，并写入 `knowledgebases`。
- `POST /chat_on_docs?session_id=...`
  - 必须登录并校验会话归属。
  - 先尝试从 ES 检索当前用户索引；检索失败时可继续无引用回答，但要记录日志。
  - 生成时应合并 ES 引用与 Redis 快速解析内容。
  - SSE 先发送引用文档，再发送思考/回答片段，最后发送推荐问题和 `[DONE]`。
  - 完成后写入 `messages`，并可用用户首问摘要更新会话名。

### 数据模型规范

- `users`：用户名、密码哈希、创建时间。
- `sessions`：`session_id`、`user_id`、会话名、创建时间/更新时间。
- `messages`：`session_id`、用户问题、模型回答、思考内容、引用文档 JSON、推荐问题 JSON、创建时间。
- `knowledgebases`：用户、会话、文件路径或文件名、创建时间。
- `document_uploads`：用于当前会话文档上传记录；如果暂未接完整接口，应在 README 或后续任务中明确标记为未完成能力。

### RAG 与文件处理规范

- 长期上传走 `app/features/file_parse/file_parse.py` 到 `app/rag/app/naive.py` 的解析切片链路。
- embedding 默认沿用 DashScope/OpenAI-compatible 调用，模型与维度要与 ES mapping 匹配。
- ES 索引建议按用户隔离，避免跨用户召回。
- 检索结果返回给聊天服务时，至少保留文档名与 chunk 内容，便于前端展示引用。
- PDF 解析可以包含 OCR、版面和表格文本提取，但不要把当前能力描述成真正的统一多模态向量检索。

### 后端验收

- Python 语法检查应至少覆盖入口和改动文件，例如：
  - `python -m py_compile main.py`
  - `python -m py_compile app/router/chat_rt.py app/router/history_rt.py app/router/user_rt.py`
- 服务启动后 `GET /health` 返回 `{ "status": "ok" }`。
- 手动或脚本联调至少覆盖：
  - 注册、登录、`/me`；
  - 创建会话、查询会话；
  - 查询空历史消息；
  - 快速解析 txt/docx/pdf 中至少一种；
  - 上传长期知识库文件；
  - 重复文件名拒绝；
  - 聊天 SSE 能返回 `[DONE]`；
  - 聊天结束后 `GET /get_messages` 能查到记录；
  - 删除会话后不能再查到该会话消息。

## 前后端接口契约速查

| 能力 | 前端请求 | 后端响应重点 | 备注 |
| --- | --- | --- | --- |
| 注册 | `POST /register` JSON | `message` | 无 token |
| 登录 | `POST /login` JSON | `access_token`, `token_type`, `username` | 保存 token |
| 当前用户 | `GET /me` | `id`, `username` | Bearer token |
| 创建会话 | `POST /create_session` | `session_id`, `status`, `message` | Bearer token |
| 会话列表 | `GET /get_sessions` | `sessions[]` | Bearer token |
| 历史消息 | `GET /get_messages?session_id=...` | `messages[]` | 兼容 JSON 字符串字段 |
| 删除会话 | `DELETE /sessions/{session_id}` | `status`, `message` | 不递归删文件 |
| 快速解析 | `POST /quick_parse?session_id=...` form `file` | `filename`, `file_type`, `content_length`, `status` | Redis，短期 |
| 读取解析内容 | `GET /get_parsed_content?session_id=...` | 解析内容或 `{}` | 当前用户隔离 |
| 长期上传 | `POST /upload_files?session_id=...` form `files` | `successful_files`, `failed_files`, `duplicate_files` | ES + knowledgebases |
| 聊天 | `POST /chat_on_docs?session_id=...` JSON | SSE `data:` | 结束标记 `[DONE]` |

## 开发顺序建议

1. 后端先稳定认证、会话、历史消息接口；前端完成登录和工作台壳。
2. 后端完成 SSE 聊天和消息落库；前端完成流式渲染和历史恢复。
3. 后端完成 Redis 快速解析；前端接入当前会话上传。
4. 后端完成长期上传、ES 入库和召回；前端接入知识库上传结果展示。
5. 再补文档列表、知识库删除、会话文档摘要等非首要能力。

每完成一个阶段，都应以前端真实页面能操作验证为准，而不是只看单个函数或单个接口能运行。
