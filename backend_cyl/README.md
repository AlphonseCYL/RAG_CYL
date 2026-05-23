# backend_cyl

最小可用后端，目前只实现用户注册、密码登录、当前用户校验。

## 目录结构

```text
backend_cyl/
  main.py                    # FastAPI 应用入口，只负责创建 app、注册中间件和挂载路由
  app/
    core/
      config.py              # 数据库路径、JWT 配置等公共配置
      database.py            # SQLite 连接和 users 表初始化
    features/
      auth/
        router.py            # 注册、登录、当前用户接口
        schemas.py           # 请求体和响应体模型
        security.py          # 密码哈希、密码校验、JWT 生成和解析
        service.py           # 注册和登录的业务逻辑
```

## 运行

```powershell
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

接口：

- `GET /`
- `GET /health`
- `POST /register`
- `POST /login`
- `GET /me`

接口文档：

```text
http://127.0.0.1:8001/docs
```
