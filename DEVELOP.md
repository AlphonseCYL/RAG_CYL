# swxy 重构开发记录

本文档记录本轮从原项目 `backend` / `frontend` 向教学版 `backend_cyl` / `frontend_cyl` 重构时已经完成的内容，方便后续回顾。

## 1. 新建最小可用版目录

新增两个重构目录：

- `backend_cyl/`：新的后端最小可用版。
- `frontend_cyl/`：新的前端最小可用版。

本轮没有改造原来的 `backend/` 和 `frontend/` 主业务代码，新的登录注册功能先独立放在 `*_cyl` 目录中。

## 2. backend_cyl 完成内容

### 2.1 后端最小登录注册闭环

实现了以下接口：

- `GET /`：后端运行状态提示。
- `GET /health`：健康检查。
- `POST /register`：用户注册。
- `POST /login`：用户名和密码登录。
- `GET /me`：根据 token 获取当前登录用户。

实现了以下能力：

- 使用 FastAPI 搭建后端服务。
- 使用 SQLite 保存用户数据。
- 启动时自动创建 `users` 表。
- 注册时对密码做哈希存储，不保存明文密码。
- 登录成功后生成 JWT token。
- `/me` 接口通过 `Depends(get_current_user)` 校验 token。
- 配置 CORS，允许 `http://localhost:5173` 和 `http://127.0.0.1:5173` 的前端访问后端。

### 2.2 后端目录结构整理

为了让项目更整洁，将原来集中在 `backend_cyl/main.py` 里的注册、登录、密码、JWT、数据库逻辑拆分到功能目录中。

当前结构：

```text
backend_cyl/
  main.py
  requirements.txt
  README.md
  .gitignore
  app/
    __init__.py
    core/
      __init__.py
      config.py
      database.py
    features/
      __init__.py
      auth/
        __init__.py
        router.py
        schemas.py
        security.py
        service.py
```

文件职责：

- `backend_cyl/main.py`：FastAPI 应用入口，配置 CORS，注册启动事件，挂载 auth 路由。
- `backend_cyl/app/core/config.py`：公共配置，例如数据库路径、JWT 密钥、JWT 算法、token 有效期。
- `backend_cyl/app/core/database.py`：SQLite 连接和 `users` 表初始化。
- `backend_cyl/app/features/auth/router.py`：注册、登录、当前用户接口。
- `backend_cyl/app/features/auth/schemas.py`：接口请求体和响应体模型。
- `backend_cyl/app/features/auth/security.py`：密码哈希、密码校验、JWT 创建、JWT 解析、当前用户校验。
- `backend_cyl/app/features/auth/service.py`：注册和登录的业务逻辑。
- `backend_cyl/requirements.txt`：后端最小依赖。
- `backend_cyl/README.md`：后端运行方式和目录说明。
- `backend_cyl/.gitignore`：忽略 `.venv/`、`__pycache__/`、`app.db` 等本地生成文件。

## 3. frontend_cyl 完成内容

### 3.1 前端最小登录注册页面

实现了一个最小可用前端页面：

- 使用 Vite + React + TypeScript + Ant Design。
- 页面包含“登录”和“注册”两个 Tab。
- 注册时调用后端 `POST /register`。
- 登录时调用后端 `POST /login`。
- 登录成功后把 `access_token` 和 `username` 保存到 `localStorage`。
- 登录成功后显示一个最小首页。
- 支持退出登录，清理本地 token 和用户名。

### 3.2 前端交互问题修复

修复了两个前端体验问题：

- 登录和注册最初共用同一个 Ant Design `Form` 实例，导致注册失败后的提示可能影响登录。现在已拆成 `loginForm` 和 `registerForm` 两个独立表单。
- 密码少于 6 位时，后端返回的校验错误原本会被前端显示成 `[object Object]`。现在前端会先做表单校验，并把后端复杂错误转换成中文提示。

当前交互效果：

- 用户名少于 3 个字符时，在输入框下提示“用户名至少 3 个字符”。
- 密码少于 6 个字符时，在输入框下提示“密码至少 6 个字符”。
- 用户名已存在时，显示“用户名已存在”。
- 登录失败时，显示“用户名或密码错误”。

### 3.3 前端目录结构

当前结构：

```text
frontend_cyl/
  index.html
  package.json
  tsconfig.json
  tsconfig.app.json
  vite.config.ts
  .gitignore
  src/
    main.tsx
    styles.css
    vite-env.d.ts
```

文件职责：

- `frontend_cyl/src/main.tsx`：当前前端主页面，包含登录、注册、请求封装、token 保存、退出登录等逻辑。
- `frontend_cyl/src/styles.css`：页面基础样式。
- `frontend_cyl/src/vite-env.d.ts`：Vite 类型声明。
- `frontend_cyl/package.json`：前端依赖和运行脚本。
- `frontend_cyl/vite.config.ts`：Vite 配置。
- `frontend_cyl/.gitignore`：忽略 `node_modules/`、`dist/`、`.npm-cache/`。

## 4. 当前运行方式

后端：

```powershell
cd D:\Users\ALPHONSE\VSCodeProjects\swxy\backend_cyl
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8001
```

前端：

```powershell
cd D:\Users\ALPHONSE\VSCodeProjects\swxy\frontend_cyl
npm run dev
```

访问地址：

- 前端页面：`http://localhost:5173/`
- 后端首页：`http://127.0.0.1:8001/`
- 后端接口文档：`http://127.0.0.1:8001/docs`

## 5. 已验证内容

已验证：

- 后端 `/register`、`/login`、`/me` 接口可用。
- 后端拆分目录后，模块导入和路由挂载正常。
- 前端 `npm run build` 通过。
- 前端短密码提示已从 `[object Object]` 改为中文表单提示。
- 登录和注册表单状态已隔离。
