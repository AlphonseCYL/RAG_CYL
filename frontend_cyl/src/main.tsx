import React, { useEffect, useState } from 'react'
import ReactDOM from 'react-dom/client'
import {
  Button,
  Card,
  ConfigProvider,
  Form,
  Input,
  Space,
  Tabs,
  Typography,
  message,
} from 'antd'
import zhCN from 'antd/locale/zh_CN'
import './styles.css'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8001'

type AuthForm = {
  username: string
  password: string
}

type LoginResponse = {
  access_token: string
  token_type: string
  username: string
}

function getErrorMessage(data: unknown): string {
  if (!data || typeof data !== 'object') {
    return '请求失败'
  }

  const detail = (data as { detail?: unknown }).detail
  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail)) {
    const firstError = detail[0] as { loc?: string[]; msg?: string } | undefined
    const fieldName = firstError?.loc?.at(-1)
    if (fieldName === 'password') {
      return '密码至少需要 6 个字符'
    }
    if (fieldName === 'username') {
      return '用户名长度需要在 3 到 50 个字符之间'
    }
    return firstError?.msg || '输入内容不符合要求'
  }

  return '请求失败'
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(getErrorMessage(data))
  }
  return data
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('access_token') ?? '')
  const [username, setUsername] = useState(() => localStorage.getItem('username') ?? '')
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('login')
  const [loginForm] = Form.useForm<AuthForm>()
  const [registerForm] = Form.useForm<AuthForm>()

  useEffect(() => {
    if (username) {
      loginForm.setFieldValue('username', username)
    }
  }, [loginForm, username])

  function changeTab(key: string) {
    message.destroy()
    setActiveTab(key)
  }

  async function login(values: AuthForm) {
    message.destroy()
    setLoading(true)
    try {
      const data = await request<LoginResponse>('/login', {
        method: 'POST',
        body: JSON.stringify(values),
      })
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('username', data.username)
      setToken(data.access_token)
      setUsername(data.username)
      message.success('登录成功')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }

  async function register(values: AuthForm) {
    message.destroy()
    setLoading(true)
    try {
      await request('/register', {
        method: 'POST',
        body: JSON.stringify(values),
      })
      message.success('注册成功，请登录')
      loginForm.setFieldValue('username', values.username)
      registerForm.resetFields(['password'])
      setActiveTab('login')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '注册失败')
    } finally {
      setLoading(false)
    }
  }

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('username')
    setToken('')
    setUsername('')
  }

  if (token) {
    return (
      <main className="page">
        <Card className="panel">
          <Space direction="vertical" size={16}>
            <Typography.Title level={2}>登录成功</Typography.Title>
            <Typography.Text>当前用户：{username}</Typography.Text>
            <Typography.Text type="secondary">
              这里是最小可用版首页。下一步可以继续接入会话列表或聊天页面。
            </Typography.Text>
            <Button type="primary" onClick={logout}>
              退出登录
            </Button>
          </Space>
        </Card>
      </main>
    )
  }

  return (
    <main className="page">
      <Card className="panel">
        <Typography.Title level={2}>智能文档问答系统</Typography.Title>
        <Tabs
          activeKey={activeTab}
          onChange={changeTab}
          destroyInactiveTabPane
          items={[
            {
              key: 'login',
              label: '登录',
              children: (
                <AuthPanel
                  buttonText="登录"
                  loading={loading}
                  form={loginForm}
                  onFinish={login}
                />
              ),
            },
            {
              key: 'register',
              label: '注册',
              children: (
                <AuthPanel
                  buttonText="注册"
                  loading={loading}
                  form={registerForm}
                  onFinish={register}
                />
              ),
            },
          ]}
        />
      </Card>
    </main>
  )
}

function AuthPanel(props: {
  buttonText: string
  loading: boolean
  form: ReturnType<typeof Form.useForm<AuthForm>>[0]
  onFinish: (values: AuthForm) => void
}) {
  return (
    <Form layout="vertical" form={props.form} onFinish={props.onFinish}>
      <Form.Item
        label="用户名"
        name="username"
        rules={[
          { required: true, message: '请输入用户名' },
          { min: 3, message: '用户名至少 3 个字符' },
          { max: 50, message: '用户名最多 50 个字符' },
        ]}
      >
        <Input size="large" placeholder="至少 3 个字符" autoComplete="username" />
      </Form.Item>
      <Form.Item
        label="密码"
        name="password"
        rules={[
          { required: true, message: '请输入密码' },
          { min: 6, message: '密码至少 6 个字符' },
          { max: 128, message: '密码最多 128 个字符' },
        ]}
      >
        <Input.Password
          size="large"
          placeholder="至少 6 个字符"
          autoComplete="current-password"
        />
      </Form.Item>
      <Button block type="primary" size="large" htmlType="submit" loading={props.loading}>
        {props.buttonText}
      </Button>
    </Form>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN}>
      <App />
    </ConfigProvider>
  </React.StrictMode>,
)
