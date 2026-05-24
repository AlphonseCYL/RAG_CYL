import React, { useEffect, useMemo, useState } from 'react'
import ReactDOM from 'react-dom/client'
import {
  Button,
  Card,
  ConfigProvider,
  Form,
  Input,
  Layout,
  List,
  Menu,
  Popconfirm,
  Space,
  Tabs,
  Tag,
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

type CreateSessionResponse = {
  session_id: string
  status: string
  message: string
}

type SessionItem = {
  session_id: string
  name: string
  created_at: string
}

type SessionListResponse = {
  sessions: SessionItem[]
  status: string
  message: string
}

type ChatSession = {
  id: string
  title: string
  createdAt: string
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

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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
    return <AuthedApp token={token} username={username} onLogout={logout} />
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

function AuthedApp(props: { token: string; username: string; onLogout: () => void }) {
  const [activeKey, setActiveKey] = useState('chat')
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState('')
  const [creating, setCreating] = useState(false)
  const [loadingSessions, setLoadingSessions] = useState(false)
  const [deletingSessionId, setDeletingSessionId] = useState('')

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId),
    [activeSessionId, sessions],
  )

  async function loadSessions() {
    setLoadingSessions(true)
    try {
      const data = await request<SessionListResponse>('/get_sessions', {}, props.token)
      const mappedSessions = data.sessions.map((item) => ({
        id: item.session_id,
        title: item.name || '新对话',
        createdAt: item.created_at,
      }))
      setSessions(mappedSessions)
      setActiveSessionId((current) => current || mappedSessions[0]?.id || '')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载历史会话失败')
    } finally {
      setLoadingSessions(false)
    }
  }

  useEffect(() => {
    loadSessions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.token])

  async function createNewSession() {
    message.destroy()
    setCreating(true)
    try {
      const data = await request<CreateSessionResponse>(
        '/create_session',
        {
          method: 'POST',
          body: JSON.stringify({}),
        },
        props.token,
      )
      const nextSession: ChatSession = {
        id: data.session_id,
        title: `新对话 ${sessions.length + 1}`,
        createdAt: new Date().toLocaleString('zh-CN', { hour12: false }),
      }
      setSessions((current) => [nextSession, ...current])
      setActiveSessionId(nextSession.id)
      setActiveKey('chat')
      message.success('已创建新对话')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '创建会话失败')
    } finally {
      setCreating(false)
    }
  }

  async function deleteHistorySession(sessionId: string) {
    message.destroy()
    setDeletingSessionId(sessionId)
    try {
      await request(`/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' }, props.token)
      setSessions((current) => current.filter((session) => session.id !== sessionId))
      setActiveSessionId((current) => (current === sessionId ? '' : current))
      message.success('已删除会话')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '删除会话失败')
    } finally {
      setDeletingSessionId('')
    }
  }

  function selectHistorySession(sessionId: string) {
    setActiveSessionId(sessionId)
    setActiveKey('chat')
  }

  return (
    <Layout className="app-shell">
      <Layout.Sider width={232} className="app-sidebar" breakpoint="lg" collapsedWidth={0}>
        <div className="brand">
          <div className="brand-mark">文</div>
          <div>
            <div className="brand-title">智能文档问答</div>
            <div className="brand-subtitle">frontend_cyl</div>
          </div>
        </div>

        <Button
          block
          type="primary"
          className="new-chat-button"
          loading={creating}
          onClick={createNewSession}
        >
          新建对话
        </Button>

        <Menu
          mode="inline"
          selectedKeys={[activeKey]}
          onClick={(item) => setActiveKey(item.key)}
          items={[
            { key: 'chat', label: '对话工作台' },
            { key: 'repository', label: '知识库文件' },
            { key: 'history', label: '历史会话' },
          ]}
        />
      </Layout.Sider>

      <Layout className="app-main">
        <header className="topbar">
          <div>
            <Typography.Title level={3}>欢迎回来，{props.username}</Typography.Title>
            <Typography.Text type="secondary">
              登录后会自动从后端读取当前用户的历史会话。
            </Typography.Text>
          </div>
          <Button onClick={props.onLogout}>退出登录</Button>
        </header>

        <main className="workspace">
          {activeKey === 'chat' && <ChatHome session={activeSession} />}
          {activeKey === 'repository' && <RepositoryHome />}
          {activeKey === 'history' && (
            <HistoryHome
              sessions={sessions}
              loading={loadingSessions}
              deletingSessionId={deletingSessionId}
              onDeleteSession={deleteHistorySession}
              onSelectSession={selectHistorySession}
            />
          )}
        </main>
      </Layout>
    </Layout>
  )
}

function ChatHome(props: { session?: ChatSession }) {
  if (!props.session) {
    return (
      <section className="empty-chat">
        <Tag color="blue">会话入口</Tag>
        <Typography.Title level={2}>点击左侧“新建对话”开始</Typography.Title>
        <Typography.Paragraph type="secondary">
          新建成功后会生成 session_id，并进入对应聊天窗口。
        </Typography.Paragraph>
      </section>
    )
  }

  return (
    <section className="chat-home">
      <div className="session-header">
        <div>
          <Tag color="green">当前会话</Tag>
          <Typography.Title level={2}>{props.session.title}</Typography.Title>
          <Typography.Text type="secondary">session_id: {props.session.id}</Typography.Text>
        </div>
        <Typography.Text type="secondary">{props.session.createdAt}</Typography.Text>
      </div>

      <div className="chat-board">
        <div className="message assistant-message">
          新会话窗口已创建。后续接入 <Typography.Text code>/chat_on_docs</Typography.Text> 后，
          这里会显示当前 session 的流式问答、引用文档和推荐追问。
        </div>
        <div className="composer">
          <Input.TextArea
            autoSize={{ minRows: 3, maxRows: 6 }}
            placeholder="当前切片先完成会话创建；发送问题将进入下一步接入 SSE 聊天接口。"
          />
          <Button type="primary">发送</Button>
        </div>
      </div>
    </section>
  )
}

function RepositoryHome() {
  return (
    <section className="simple-panel">
      <Typography.Title level={3}>知识库文件</Typography.Title>
      <Typography.Paragraph type="secondary">
        这里后续接入文件列表、上传和删除。建议下一步先实现文件列表接口。
      </Typography.Paragraph>
      <Button type="primary">上传文件</Button>
    </section>
  )
}

function HistoryHome(props: {
  sessions: ChatSession[]
  loading: boolean
  deletingSessionId: string
  onDeleteSession: (sessionId: string) => void
  onSelectSession: (sessionId: string) => void
}) {
  return (
    <section className="simple-panel">
      <Typography.Title level={3}>历史会话</Typography.Title>
      <List
        loading={props.loading}
        locale={{ emptyText: '还没有会话，先点“新建对话”。' }}
        dataSource={props.sessions}
        renderItem={(item) => (
          <List.Item
            className="session-list-item"
            actions={[
              <Button key="open" type="link" onClick={() => props.onSelectSession(item.id)}>
                打开
              </Button>,
              <Popconfirm
                key="delete"
                title="删除会话"
                description="确定从数据库中删除这个对话窗口吗？"
                okText="删除"
                cancelText="取消"
                okButtonProps={{ danger: true }}
                onConfirm={() => props.onDeleteSession(item.id)}
              >
                <Button danger type="link" loading={props.deletingSessionId === item.id}>
                  删除
                </Button>
              </Popconfirm>,
            ]}
          >
            <List.Item.Meta
              title={item.title}
              description={
                <Space direction="vertical" size={0}>
                  <Typography.Text type="secondary">session_id: {item.id}</Typography.Text>
                  <Typography.Text type="secondary">{item.createdAt}</Typography.Text>
                </Space>
              }
            />
          </List.Item>
        )}
      />
    </section>
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
