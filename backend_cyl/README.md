# backend_cyl 后端逻辑维护说明

`backend_cyl` 是后端的 FastAPI 版本。当前代码已经覆盖用户认证、会话管理、历史消息、当前会话文档快速解析、长期文档上传入库、Elasticsearch 检索和 SSE 流式聊天。它不是完整主后端的等量拷贝，部分文档上传记录接口仍处于未接完状态。

## 运行入口

- `main.py` 创建 `FastAPI(title="swxy cyl minimal auth")`。
- 启动时执行 `app.core.database.init_db()`：
  - 先按 `.env` 中的 MySQL 配置创建数据库。
  - 再通过 SQLAlchemy `Base.metadata.create_all()` 创建 ORM 表。
  - 最后 `_ensure_messages_schema()` 补齐 `messages` 表的历史字段。
- 注册路由：
  - `app.router.chat_rt.router`
  - `app.router.user_rt.router`
  - `app.router.history_rt.router`
- CORS 当前允许 `http://localhost:5173` 和 `http://127.0.0.1:5173`。

## 目录结构

```text
backend_cyl/
  main.py                         # FastAPI 应用入口
  docker-compose.yaml             # Redis、Elasticsearch、Kibana
  requirements.txt                # Python 依赖
  app/
    core/
      config.py                   # JWT、MySQL、Redis 配置
      database.py                 # SQLAlchemy、建库建表、knowledgebases 写入
      es_conn.py                  # Elasticsearch bulk、search、delete 封装
      logger.py                   # 日志初始化
    db_models/
      user.py                     # users
      session.py                  # sessions
      message.py                  # messages
      knowledgebase.py            # knowledgebases
      document_upload.py          # document_uploads，当前未完整接入主流程
    router/
      user_rt.py                  # /register、/login、/me
      chat_rt.py                  # 会话创建、quick_parse、chat_on_docs、upload_files
      history_rt.py               # 历史会话、历史消息、删除会话
    features/
      auth/                       # 认证 schema、安全函数、注册登录服务
      sessions/                   # 会话服务、SSE 聊天、Redis 快速解析
      file_parse/                 # 文件解析入 ES 的薄切片封装
      retrieval/                  # 从 ES 召回文档片段
      doc_upload/                 # 文档上传记录 service，当前未完整接入
    rag/
      app/naive.py                # 文档解析与 chunk
      nlp/model.py                # DashScope/OpenAI-compatible embedding、rerank
      nlp/query.py                # 问题转全文检索表达式
      nlp/search_v2.py            # 混合检索、rerank
      conf/mapping.json           # ES 字段和 dense_vector mapping
      storage/file/               # 上传文件落盘目录
```

## 已实现功能总览

1. 用户注册、登录和当前用户查询。
2. Bearer JWT 鉴权。
3. 创建会话，立即写入 `sessions` 表。
4. 查询历史会话和历史消息。
5. 删除会话，并级联/同步删除该会话消息。
6. 当前会话文档快速解析，结果写 Redis，供后续聊天参考。
7. 长期文档上传，保存到本地 `app/rag/storage/file/{session_id}/`。
8. 上传文档解析、切片、生成 embedding，并写入 Elasticsearch。
9. 聊天前从用户 ES 索引召回文档片段。
10. SSE 流式聊天，支持思考内容、回答正文、引用文档和推荐问题。
11. 聊天完成后写入 `messages` 表，并把默认会话名改为问题摘要。

## 认证流程

### `POST /register`

执行路径：

```text
app/router/user_rt.py::register
  -> app/features/auth/service.py::register_user
    -> app/features/auth/security.py::hash_password
    -> app/db_models/user.py::User
    -> app/core/database.py::SessionLocal
    -> users 表
```

逻辑说明：

- 请求体使用 `AuthRequest`，要求 `username` 3 到 50 字符，`password` 6 到 128 字符。
- `hash_password()` 使用随机 salt 和 `hashlib.pbkdf2_hmac("sha256", ..., 100000)` 生成 `salt$hash`。
- 用户名重复时捕获 `IntegrityError`，返回 400 `用户名已存在`。

### `POST /login`

执行路径：

```text
app/router/user_rt.py::login
  -> app/features/auth/service.py::login_user
    -> 查询 users
    -> app/features/auth/security.py::verify_password
    -> app/features/auth/security.py::create_access_token
```

逻辑说明：

- 登录成功返回 `access_token`、`token_type=bearer`、`username`。
- JWT payload 包含 `sub`、`username`、`exp`。
- 过期时间由 `ACCESS_TOKEN_EXPIRE_HOURS` 控制，默认 24 小时。

### `GET /me`

执行路径：

```text
app/router/user_rt.py::me
  -> Depends(get_current_user)
    -> 读取 Authorization: Bearer <token>
    -> jose.jwt.decode
    -> UserInfo(id, username)
```

所有需要登录的接口都复用 `get_current_user()`。

## 会话和历史流程

### `POST /create_session`

执行路径：

```text
app/router/chat_rt.py::create_chat_session
  -> app/features/sessions/service.py::create_session
    -> uuid.uuid4().hex[:16]
    -> app/db_models/session.py::Session
    -> sessions 表
```

逻辑说明：

- 当前薄切片会立即写入 `sessions` 表。
- 初始会话名是 `新对话`。
- 返回 `SessionResponse(session_id, status, message)`。

### `GET /get_sessions`

执行路径：

```text
app/router/history_rt.py::list_sessions
  -> app/features/sessions/service.py::get_sessions
    -> sessions 表按 user_id 查询
    -> created_at desc 排序
```

返回当前用户自己的会话列表。

### `GET /get_messages?session_id=...`

执行路径：

```text
app/router/history_rt.py::list_messages
  -> app/features/sessions/service.py::get_messages
    -> 校验 sessions.user_id + session_id
    -> 查询 messages
    -> documents/recommended_questions 尝试 json.loads
```

逻辑说明：

- 如果会话不属于当前用户，返回 404。
- `messages.documents` 和 `messages.recommended_questions` 在库中是 JSON 字符串，返回前会尽量还原成列表。

### `DELETE /sessions/{session_id}`

执行路径：

```text
app/router/history_rt.py::remove_session
  -> app/features/sessions/service.py::delete_session
    -> 校验会话归属
    -> 删除 messages 中该 session_id 的记录
    -> 删除 sessions 记录
```

注意：这里删除的是数据库会话和消息记录，不会递归删除本地文件目录。

## 快速解析流程

### `POST /quick_parse?session_id=...`

执行路径：

```text
app/router/chat_rt.py::quick_parse_current_session_document
  -> UploadFile.read()
  -> app/features/sessions/quick_parse_service.py::quick_parse_document
    -> _ensure_session_owner
    -> _get_file_type
    -> _parse_txt / _parse_docx / _parse_pdf
    -> _limit_text_len
    -> app/features/sessions/redis_store.py::store_quick_parsed_document_to_redis
      -> Redis key: quick_parse:{session_id}
```

功能边界：

- 支持 `txt`、`docx`、`pdf`。
- `txt` 会依次尝试 `utf-8-sig`、`utf-8`、`gbk`、`gb2312`。
- `docx` 使用 `python-docx` 读取段落文本。
- `pdf` 使用 `pdfplumber` 提取文本。
- PDF 最多 4 页。
- TXT/DOCX/PDF 解析出的文本最多 34000 字符。
- Redis TTL 由 `QUICK_PARSE_EXPIRE_SECONDS` 控制，默认 7200 秒。
- 快速解析内容不写 Elasticsearch，也不写 `knowledgebases`。

### `GET /get_parsed_content?session_id=...`

执行路径：

```text
app/router/chat_rt.py::read_parsed_content
  -> app/features/sessions/quick_parse_service.py::get_quick_parsed_document
    -> app/features/sessions/redis_store.py::load_quick_parsed_document_from_redis
```

逻辑说明：

- 只返回当前用户自己的 Redis 快速解析内容。
- 如果 Redis 中没有内容或用户不匹配，当前实现返回空字典 `{}`。

## 长期文档上传和 ES 入库流程

### `POST /upload_files?session_id=...`

执行路径：

```text
app/router/chat_rt.py::upload_files
  -> Depends(get_current_user)
  -> user_owns_session
  -> app.rag.utils.file_utils.get_project_base_dir("storage", "file")
  -> 保存到 app/rag/storage/file/{session_id}/{file_name}
  -> app/features/file_parse/file_parse.py::execute_insert_file_to_es
    -> app/rag/app/naive.py::chunk
    -> process_items
      -> app/rag/nlp/model.py::generate_embedding
      -> FileParsedMetadataES
    -> app/core/es_conn.py::ESConnection.insert
  -> app/core/database.py::insert_knowledgebase
    -> knowledgebases 表
```

已实现保护：

- 必须登录。
- 必须拥有 `session_id`。
- 文件名会通过 `Path(file.filename).name` 取 basename，降低路径注入风险。
- 同一次请求内文件名重复会拒绝。
- 与当前 `session_id` 目录中已有文件同名会拒绝，避免覆盖。
- 空文件会记录为失败。
- 保存后会检查文件大小是否与上传内容一致。
- 解析或入库失败时，会删除这一次刚保存的明确文件路径。

返回结构：

- 全部成功：`status=success`，包含 `successful_files`。
- 部分成功：`status=partial_success`，包含 `successful_files` 和 `failed_files`。
- 全部失败：抛出 400，detail 中包含失败列表。

注意事项：

- `insert_knowledgebase()` 当前写入的是 `file_url`，字段名叫 `file_name`，实际值是本地文件路径。
- `execute_insert_file_to_es()` 捕获 ES 插入异常后只记录日志，没有继续向上抛出；因此上层可能把部分 ES 写入失败视为上传成功，需要后续修正。
- `except Exception as exc` 分支里有一处 `str(e)` 变量名错误，应改为 `str(exc)`，否则该异常分支会再次报错。

## 文档解析和 chunk 生成

主入口：

```text
app/features/file_parse/file_parse.py::execute_insert_file_to_es
```

解析入口：

```text
app/rag/app/naive.py::chunk
```

当前 `backend_cyl` 的 `naive.py` 是轻量实现：

- PDF：使用 `pdfplumber` 按页提取文本。
- DOCX：使用 `python-docx` 提取段落和表格文本。
- Markdown：移除代码块并按标题/段落拆分。
- 普通文本：按编码读取后拆分。
- chunk 字段包括：
  - `content_with_weight`
  - `content_ltks`
  - `content_sm_ltks`
  - `docnm_kwd`
  - `title_tks`

与主项目完整 DeepDoc 路径相比，这里更偏轻量文本抽取；虽然目录中保留 `deepdoc/` 和模型资源，但当前入库主入口调用的是 `app/rag/app/naive.py::chunk`。

## Embedding 和 ES 字段

执行路径：

```text
process_items
  -> batch_generate_embeddings
    -> app/rag/nlp/model.py::generate_embedding
      -> OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)
      -> embeddings.create(model="text-embedding-v3", dimensions=1024)
```

写入 ES 的模型是 `FileParsedMetadataES`：

- `id`：`content_with_weight + index_name` 的 xxhash。
- `knowledgebase_id`：当前传入的 ES 索引名，实际使用当前 `user_id`。
- `doc_id`：文件名的 xxhash。
- `doc_name`：原始文件名。
- `doc_name_kwd`：文档名关键词。
- `content_ltks` / `content_sm_ltks`：粗粒度和细粒度 token。
- `content_with_weight`：chunk 正文。
- `q_1024_vec`：1024 维 embedding。

`app/core/es_conn.py::ESConnection` 会读取 `app/rag/conf/mapping.json`，但当前 `insert()` 只是 bulk index，没有在该方法里显式创建索引或套用 mapping；新索引首次写入时是否正确套用 mapping 需要实际验证。

## 检索流程

聊天接口中长期知识库召回执行路径：

```text
app/router/chat_rt.py::chat_on_docs
  -> app/features/retrieval/retrieval.py::retrieve_content
    -> app/rag/nlp/search_v2.py::Dealer.retrieval
      -> FulltextQueryer.question
      -> Dealer.get_vector
      -> ESConnection.search
      -> rerank_by_model / rerank
```

逻辑说明：

- ES 索引名使用当前用户 ID 字符串。
- `retrieve_content()` 默认返回 5 条 chunk。
- `Dealer.search()` 同时构造全文 query_string 和 dense vector kNN。
- `FusionExpr("weighted_sum", {"weights": "0.05, 0.95"})` 表示 ES 召回阶段更偏向向量相似度。
- `retrieve_content()` 调用 `Dealer.retrieval(..., vector_similarity_weight=0.6)`，重排阶段按该权重融合。
- 返回给聊天层的字段包括：
  - `id`
  - `document_id`
  - `document_name`
  - `content_with_weight`

## SSE 聊天流程

### `POST /chat_on_docs?session_id=...`

执行路径：

```text
app/router/chat_rt.py::chat_on_docs
  -> user_owns_session
  -> retrieve_content(user_id, question)
  -> StreamingResponse(get_chat_completion(...), media_type="text/event-stream")
```

生成器执行路径：

```text
app/features/sessions/service.py::get_chat_completion
  -> 合并 ES 检索内容
  -> quick_parse_service.get_quick_parsed_document
  -> 构造 prompt
  -> 先 yield documents 事件
  -> OpenAI(...).chat.completions.create(stream=True)
  -> reasoning_content 作为 thinking=true 流式返回
  -> content 作为回答正文流式返回
  -> finish_reason == "stop"
    -> generate_recommended_questions
    -> yield recommended_questions
    -> yield event:end data:[DONE]
    -> write_chat_to_db
    -> update_session_name
```

SSE 数据形态：

```text
event: message
data: {"documents": [...]}

event: message
data: {"content": "...", "thinking": true}

event: message
data: {"content": "..."}

event: message
data: {"recommended_questions": [...]}

event: end
data: [DONE]
```

模型配置：

- 回答模型由 `LLM_MODEL` 环境变量控制，默认 `qwen3.6-plus`。
- OpenAI-compatible 客户端读取：
  - `DASHSCOPE_API_KEY`
  - `DASHSCOPE_BASE_URL`

聊天上下文边界：

- 当前实现会把 ES 召回内容和 Redis 快速解析内容放入 prompt。
- 历史 `messages` 只用于页面恢复展示，不会自动拼入下一轮 prompt。
- 如果既没有 ES 召回也没有快速解析内容，prompt 中会写入 `暂无参考内容。`，并要求模型拒绝回答。

## 聊天落库流程

执行路径：

```text
get_chat_completion
  -> write_chat_to_db
    -> app/db_models/message.py::Message
    -> messages 表
  -> update_session_name
    -> sessions 表
```

`messages` 写入字段：

- `session_id`
- `user_question`
- `model_answer`
- `documents`
- `recommended_questions`
- `think`
- `created_at`
- `updated_at`

`documents` 和 `recommended_questions` 使用 `json.dumps(..., ensure_ascii=False)` 存储。

`update_session_name()` 只在会话名仍为 `新对话` 时更新，名称取用户问题前 20 个字符，超长追加 `...`。

## 数据存储职责

- MySQL：
  - `users`：用户账号和密码 hash。
  - `sessions`：会话 ID、用户 ID、会话名、创建时间。
  - `messages`：每轮问答、引用文档、推荐问题、思考内容。
  - `knowledgebases`：用户、会话和上传文件路径记录。
- Redis：
  - `quick_parse:{session_id}`：当前会话快速解析文档内容，有 TTL。
- Elasticsearch：
  - 每个用户一个索引，索引名是用户 ID 字符串。
  - 存储长期上传文件的 chunk、token 字段和 `q_1024_vec`。
- 本地磁盘：
  - `app/rag/storage/file/{session_id}/{file_name}` 保存 `/upload_files` 上传的原文件。

## 当前未完成或需注意的点

- `app/router/chat_rt.py` 中 `@router.get("sessions/{session_id}/documents", ...)` 少了开头 `/`，函数体也没有真正查询并返回文档列表。
- `app/features/doc_upload/document_upload_service.py` 和 `app/db_models/document_upload.py` 已存在，但 `DocumentUpload` 没有在 `app/db_models/__init__.py` 导出，且该模型里使用了 `from db_models.base import Base`，按当前包路径可能导入失败。
- `/quick_parse` 当前只写 Redis，没有调用 `DocumentUploadRecordService.create_upload_record()`。
- `/upload_files` 会写 `knowledgebases`，但还没有提供知识库文件列表和删除接口。
- `ESConnection` 中 ES 账号密码当前写在代码里，应改为环境变量读取，文档和提交中不要记录真实密钥。
- `retrieve_content()` 从 ES chunk 中取 `doc_name_kwd`，而入库 schema 写的是 `doc_name_kwd`；如果 mapping 或旧数据使用其他字段名，需要迁移或兼容。
- `chat_on_docs` 对检索失败是降级处理：记录 warning 后继续无引用聊天。
- `get_chat_completion()` 中快速解析文档分块逻辑在循环内追加 `current_chunk`，长文档时可能产生重复 chunk，后续可单独修正。

## 配置和运行

关键环境变量名：

- `JWT_SECRET_KEY`
- `MYSQL_DATABASE_NAME`
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_CHARSET`
- `MYSQL_COLLATION`
- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_DB`
- `QUICK_PARSE_EXPIRE_SECONDS`
- `DASHSCOPE_API_KEY`
- `DASHSCOPE_BASE_URL`
- `LLM_MODEL`
- `ES_HOST`

本地依赖服务：

```powershell
docker compose up -d
```

后端启动：

```powershell
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

接口文档：

```text
http://127.0.0.1:8001/docs
```

健康检查：

```text
GET http://127.0.0.1:8001/health
```

## 维护原则

- 删除文件时只能删除单个明确路径文件，禁止递归批量删除。
- 不要把 `.env` 中的真实密钥、密码、Token 写入文档、提交信息或记忆。
- 修改聊天接口时保持 SSE 的 `data: JSON` 行协议兼容。
- 修改 `/upload_files` 时不要引入覆盖已有文件的行为。
- 修改快速解析时保持 Redis 临时上下文边界，不要误写入 ES。
- 修改历史消息时注意 `documents` 和 `recommended_questions` 在数据库中是 JSON 字符串。
