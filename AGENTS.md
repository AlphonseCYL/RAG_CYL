# swxy 项目维护指南

## 操作边界

- 禁止批量删除文件或目录。
- 禁止使用 `del /s`、`rd /s`、`rmdir /s`、`Remove-Item -Recurse`、`rm -rf`。
- 需要删除文件时，只能一次删除一个明确路径的文件，例如 `Remove-Item "C:\path\to\file.txt"`。
- 如果需要批量删除文件，应停止操作并请求用户手动删除。
- 不要把 `.env` 中的真实密钥、密码、Token 写入文档、提交信息或记忆；只记录变量名和用途。
- Windows PowerShell 可能把中文文件显示成乱码，判断文件是否损坏前应使用 UTF-8 方式或 `git diff` 复核。

## 总体架构

本项目是前后端分离的智能文档问答系统：

- `frontend/`：Vite + React 18 + TypeScript + Ant Design 前端，负责登录注册、会话创建、聊天流式展示、知识库文件管理、语音 STS token 请求等交互。
- `backend/`：FastAPI 后端，负责 JWT 认证、文件上传与解析、RAG 检索、SSE 流式回答、会话/消息/知识库记录持久化。
- 基础设施由 `backend/docker-compose.yml` 编排：`swxy_api`、PostgreSQL、Elasticsearch、Redis。
- 文档问答主链路是“上传文件 -> DeepDoc/RAG 解析切片 -> DashScope embedding -> 写入 Elasticsearch -> 用户提问 -> 混合召回/重排 -> 大模型流式回答 -> PostgreSQL 记录会话与消息”。

## 已实现的完整功能

当前 `backend/` + `frontend/` 主项目大约形成 8 个前后端闭环能力：
后续需要根据这些完整功能在frontend_cyl和backend_cyl中进行一一复现。

1. 用户注册与登录：
   - 前端 `/login` 页面提供注册、登录表单。
   - 后端 `POST /register` 写入用户，`POST /login` 校验密码并返回 JWT。
   - 前端保存 token，后续请求自动携带 `Authorization: Bearer ...`。

2. 创建聊天会话：
   - 前端访问 `/` 时调用 `POST /create_session`，拿到 `session_id` 后跳转 `/chat/:id`。
   - 该 `session_id` 后续用于聊天、快速解析上传、历史消息查询和会话文档记录。

3. 聊天窗口流式对话：
   - 前端 `frontend/src/pages/chat/index.tsx` 调用 `POST /chat_on_docs?session_id=...`。
   - 后端通过 SSE 流式返回内容，前端边接收边渲染回答。
   - 支持回答正文、思考内容、引用文档、推荐追问的展示。

4. 知识库文档上传、解析与入库：
   - 前端 `/repository` 页面调用 `POST /upload_files`。
   - 后端保存文件，调用 DeepDoc/RAG 解析切片，生成 embedding，写入 Elasticsearch。
   - 同时在 PostgreSQL 的 `knowledgebases` 表记录当前用户上传的文件名。
   - 后续聊天会从当前用户对应的 ES 索引中召回相关 chunk。

5. 当前会话文档快速解析并参与聊天：
   - 前端聊天输入区可上传当前会话文档，接口为 `POST /quick_parse?session_id=...`。
   - 后端支持 `pdf`、`docx`、`txt`，解析结果写入 Redis，默认 2 小时过期。
   - 聊天生成时 `get_chat_completion()` 会把 Redis 中的当前会话文档内容和知识库召回内容一起放入 prompt。

6. 知识库文件列表与删除：
   - 前端 `/repository` 调用 `GET /get_files` 展示当前用户已上传文件。
   - 删除按钮调用 `DELETE /delete_file/{file_name}`。
   - 后端会删除 PostgreSQL 记录、ES 中对应文档，并尝试删除一个明确路径的本地文件；禁止改成递归批量删除。

7. 历史会话与历史消息查看：
   - 后端 `GET /get_sessions` 按用户查询历史会话。
   - 后端 `GET /get_messages?session_id=...` 查询某个会话的历史问答。
   - 前端聊天页进入时会加载历史消息，并还原回答、引用文档和推荐问题。

8. 语音 STS Token 支撑：
   - 前端 `frontend/src/api/other.ts` 提供 `getVolcToken()`。
   - 后端 `POST /sts-token` 转发到火山语音 STS token API。
   - 这是语音能力的支撑接口，不是文档问答主链路。

## 前端结构

- 入口：`frontend/src/main.tsx` 挂载 `App`，`frontend/src/App.tsx` 配置 Ant Design 中文 locale、主题色和全局 loading API。
- 路由：`frontend/src/router/routes.tsx` 定义主页面：
  - `/`：进入后创建新会话并跳转到 `/chat/:id`。
  - `/chat/:id`：聊天页。
  - `/repository`：知识库文件列表、上传、删除。
  - `/login`：登录/注册页。
- 鉴权：`frontend/src/router/guard/*` 与 `frontend/src/api/request/plugins/auth.ts` 配合，本地持久化 token 后自动加 `Authorization: Bearer ...`；401 会清空 token 并跳转登录页。
- 状态：`frontend/src/store/user.ts` 持久化 token/username，`frontend/src/store/session.ts` 保存会话列表与刷新标记，状态管理使用 Valtio。
- 请求封装：`frontend/src/api/request/index.ts` 使用 `VITE_API_BASE` 作为后端地址，默认启用 loading、错误 toast、重复请求取消和响应解包。
- API 分组：
  - `frontend/src/api/user.ts`：`POST /login`、`POST /register`。
  - `frontend/src/api/session.ts`：`/create_session`、`/get_sessions`、`/get_messages`、`/chat_on_docs`、`/quick_parse`、`/sessions/{session_id}/documents`。
  - `frontend/src/api/repository.ts`：`/get_files`、`/upload_files`、`/delete_file/{file_name}`。
  - `frontend/src/api/other.ts`：`/sts-token`。

## 前端主要页面

- `frontend/src/pages/index/index.tsx`：页面挂载时调用 `api.session.create()` 创建会话，再跳转聊天页。
- `frontend/src/pages/login/index.tsx`：Ant Design 表单实现登录与注册；登录成功后保存 token 并跳回首页。
- `frontend/src/pages/repository/index.tsx`：调用 `api.repository.list()` 展示当前用户知识库文件；上传弹窗走 `upload_files`；删除按钮走 `delete_file/{file_name}`。
- `frontend/src/pages/chat/index.tsx`：
  - 进入页面后优先处理页面传参中的首条消息，否则调用 `/get_messages` 加载历史。
  - 发送消息时调用 `api.session.chat()`，实际请求 `POST /chat_on_docs?session_id=...`。
  - 使用 fetch adapter + `ReadableStream.getReader()` 读取 SSE 行，只解析 `data: ...`。
  - 后端返回 `content` 时追加到回答；`thinking=true` 时追加到思考内容；`documents` 用于右侧引用/文档抽屉；`recommended_questions` 用于推荐追问。
- `frontend/src/components/sender/*`：聊天输入、文件上传、录音相关控件；快速解析上传会带 `session_id`。

## 后端入口与路由

- `backend/app/app_main.py`：FastAPI 应用入口，读取 `ROOT_PATH`，开启 CORS，注册 `chat_rt`、`user_rt`、`history_rt`。
- `backend/app/router/user_rt.py`：
  - `POST /login`：调用 `service.auth.authenticate()`，返回 JWT access token。
  - `POST /register`：调用 `service.auth.register_user()`，写入 `users`。
  - `POST /sts-token`：转发请求到火山语音 STS token API。
- `backend/app/router/chat_rt.py`：
  - `POST /create_session`：生成 16 位 session_id，但真正的 session 表记录主要在首次回答结束后由 `update_session_name()` 插入。
  - `POST /quick_parse`：解析当前会话临时文档，内容写 Redis，上传记录写 `document_uploads`。
  - `GET /get_parsed_content`：从 Redis 取快速解析内容。
  - `POST /chat_on_docs`：从用户 ES 索引召回内容，再调用 `get_chat_completion()` 以 SSE 返回回答。
  - `POST /upload_files`：保存文件到 `storage/file/{session_id}/`，解析并写 ES，再把文件名写入 PostgreSQL 的 `knowledgebases`。
  - `GET /sessions/{session_id}/documents` 与 `/summary`：查询当前会话快速上传记录。
- `backend/app/router/history_rt.py`：
  - `GET /get_files`：按当前用户查询 `knowledgebases`。
  - `DELETE /delete_file/{file_name}`：删除 PostgreSQL 记录、ES 文档，并尝试删除本地明确路径文件。
  - `GET /get_messages`：按 `session_id` 查询历史消息。
  - `GET /get_sessions`：按 `user_id` 查询历史会话。

## 认证与数据库

- JWT 实现在 `backend/app/service/auth.py`，使用 `fastapi_jwt.JwtAccessBearerCookie`，前端主要通过请求头传 Bearer token。
- 密码哈希与校验在 `backend/app/utils/password.py`。
- SQLAlchemy 连接在 `backend/app/utils/database.py`，`DATABASE_URL` 来自环境变量。
- 数据模型位于 `backend/app/models/`：
  - `User` -> `users`
  - `Session` -> `sessions`
  - `Message` -> `messages`
  - `KnowledgeBase` -> `knowledgebases`
  - `DocumentUpload` -> `document_uploads`
- 初始化 SQL 在 `backend/init.sql`；Alembic 配置在 `backend/app/alembic.ini` 和 `backend/app/alembic/`。

## RAG 入库链路

主入口是 `backend/app/service/core/file_parse.py`：

1. `execute_insert_process(file_path, file_name, index_name)` 调用 `parse()`。
2. `parse()` 使用 `service.core.rag.app.naive.chunk()` 解析文件并切片。
3. `chunk()` 根据扩展名分流到 PDF、DOCX、Excel、TXT、Markdown、HTML、JSON、DOC 等解析器。
4. PDF 默认走 DeepDoc 版面/OCR/表格相关解析；DOCX 会处理段落、表格和图片关联；随后进入 naive merge 和 tokenize。
5. `process_items()` 为每个 chunk 构造 ES 文档字段：`content_ltks`、`content_sm_ltks`、`content_with_weight`、`docnm_kwd`、`title_tks`、`doc_id`、`kb_id` 等。
6. `generate_embedding()` 默认调用 DashScope/OpenAI-compatible embedding，模型名为 `text-embedding-v3`，维度默认 1024。
7. 向量字段按维度写成 `q_1024_vec` 等，最后通过 `ESConnection.insert()` bulk 写入用户对应的 ES 索引。

注意：当前实现会解析 PDF 版面、OCR、表格等内容并转为文本 chunk，但检索主路径仍是文本字段 + dense vector 的混合召回；不要描述成真正的统一多模态向量检索系统。

## 检索与生成链路

- `backend/app/service/core/retrieval.py` 创建全局 `ESConnection` 和 `Dealer`，`retrieve_content(user_id, question)` 检索当前用户索引，默认返回 5 条 chunk。
- `backend/app/service/core/rag/nlp/query.py` 负责把自然语言问题转成 query_string 检索表达式，包含中文分词、细粒度 token、同义词扩展和 `minimum_should_match`。
- `backend/app/service/core/rag/nlp/search_v2.py` 是核心检索器：
  - `Dealer.get_vector()` 为问题生成 embedding，并选择 `q_{dim}_vec` 字段。
  - `Dealer.search()` 同时构造全文 query_string 和 ES kNN dense vector 查询。
  - `FusionExpr("weighted_sum", {"weights": "0.05, 0.95"})` 表示召回阶段更偏向向量相似度。
  - `Dealer.retrieval()` 前 3 页会对候选做 rerank；实现上调用 DashScope rerank 相关逻辑。
- `backend/app/service/core/conf/mapping.json` 通过 dynamic templates 定义 `*_512_vec`、`*_768_vec`、`*_1024_vec`、`*_1536_vec` 为 `dense_vector`，`similarity` 为 `cosine`。
- `backend/app/service/core/chat.py`：
  - `get_quick_parse_content()` 从 Redis 读取当前会话临时文档。
  - `get_chat_completion()` 将知识库召回内容和快速解析内容合并成引用上下文。
  - 使用 OpenAI-compatible client 调用 `deepseek-r1` 流式输出。
  - SSE 先发送 `documents`，再持续发送回答/思考片段，结束时发送推荐问题和 `[DONE]`。
  - 完成后调用 `write_chat_to_db()` 写 `messages`，调用 `update_session_name()` 生成并写入 `sessions`。

## 快速解析与正式知识库的区别

- `/quick_parse`：仅支持 `docx`、`pdf`、`txt`；PDF 页数限制较小，TXT/DOCX 有字符数限制；内容写 Redis，默认 2 小时过期；适合当前会话临时问答。
- `/upload_files`：面向长期知识库；文件保存到本地 storage，经过 DeepDoc/RAG 切片、embedding、ES 入库，并在 `knowledgebases` 记录文件名。
- 聊天时两者会合并进入提示词：ES 召回内容作为知识库引用，Redis 内容作为当前会话文档引用。

## 配置与运行

- 后端依赖：`backend/app/requirements.txt`。
- 后端 Dockerfile：`backend/app/Dockerfile`。
- Compose：`backend/docker-compose.yml`。
- 关键环境变量名：
  - `DATABASE_URL`
  - `ES_HOST`
  - `ROOT_PATH`
  - `REDIS_HOST`
  - `REDIS_PORT`
  - `REDIS_DB`
  - `DASHSCOPE_API_KEY`
  - `DASHSCOPE_BASE_URL`
  - `JWT_SECRET_KEY`
  - Elasticsearch 相关账号密码变量
- 前端后端地址由 `frontend/.env` 的 `VITE_API_BASE` 控制。
- 本地开发常用命令：
  - 前端：在 `frontend/` 下运行 `npm run dev`、`npm run build`、`npm run lint`。
  - 后端：在 `backend/` 下按 README 使用 `docker compose up -d --build`，API 文档通常在 `http://localhost:8000/docs`。

## 维护注意事项

- 前端请求默认会解包带 `status` 字段的响应；后端若新增接口，需留意 `status: "success"` 与错误结构，否则可能被 `servicePlugin` 判为异常。
- 聊天接口返回的是 SSE，前端只处理 `data: ...` 行；新增流式事件时要保持 JSON 行协议兼容。
- `create_session` 只返回 session_id，不立即写 `sessions` 表；历史会话列表依赖首次聊天完成后的 `update_session_name()`。
- 删除知识库文件时，后端会删除 ES、PG 和一个明确本地文件路径；不要改成批量递归删除。
- `ESConnection` 当前会读取 `backend/app/service/core/conf/mapping.json`，并连接 `ES_HOST`；如果索引不存在或 mapping 未创建，ES 动态模板和 bulk 行为需要实际验证。
- `backend_cyl/`、`frontend_cyl/` 看起来是旁路副本或实验目录；本指南以 `backend/`、`frontend/` 为主项目路径。
- 项目包含真实示例 PDF、测试文件和 storage 样例，修改解析/入库逻辑后应至少用一个小文件验证上传、ES 入库、聊天召回和历史记录。
