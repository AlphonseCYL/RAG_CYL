import React, { useEffect, useMemo, useState } from 'react'
import ReactDOM from 'react-dom/client'
import {
  Alert,
  Button,
  Card,
  ConfigProvider,
  Divider,
  Empty,
  Form,
  Input,
  Layout,
  List,
  Menu,
  Popconfirm,
  Progress,
  Space,
  Tabs,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd'
import type { UploadFile } from 'antd/es/upload/interface'
import zhCN from 'antd/locale/zh_CN'
import './styles.css'
import { quickParseCurrentDocument } from './features/sessions/api'

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

type HistoryMessageItem = {
  id: number
  session_id: string
  user_question: string
  model_answer: string
  documents: ChatDocument[] | string
  recommended_questions: string[] | string
  think: string
  created_at: string
}

type MessageListResponse = {
  messages: HistoryMessageItem[]
  status: string
  message: string
}

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  think?: string
  loading?: boolean
  error?: string
  documentNames?: string[]
  recommendedQuestions?: string[]
}

type ChatDocument = {
  document_id?: string
  document_name?: string
  content_with_weight?: string
}

type ChatStreamPayload = {
  content?: string
  thinking?: boolean
  documents?: ChatDocument[]
  recommended_questions?: string[]
  role?: string
  error?: string
}

type UploadFilesResponse = {
  status: string
  message: string
  successful_files?: string[]
  failed_files?: string[]
  duplicate_files?: string[]
  total_files?: number
}

function createLocalId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function parseStringArray(value: string[] | string): string[] {
  if (Array.isArray(value)) {
    return value
  }

  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : []
  } catch {
    return []
  }
}

function parseHistoryDocuments(value: ChatDocument[] | string): ChatDocument[] {
  if (Array.isArray(value)) {
    return value
  }

  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function historyItemToChatMessages(item: HistoryMessageItem): ChatMessage[] {
  const documents = parseHistoryDocuments(item.documents)

  return [
    {
      id: `history-${item.id}-user`,
      role: 'user',
      content: item.user_question,
    },
    {
      id: `history-${item.id}-assistant`,
      role: 'assistant',
      content: item.model_answer,
      think: item.think || undefined,
      documentNames: documents
        .map((document) => document.document_name)
        .filter((name): name is string => Boolean(name)),
      recommendedQuestions: parseStringArray(item.recommended_questions),
    },
  ]
}

function getErrorMessage(data: unknown): string {
  if (!data || typeof data !== 'object') {
    return '请求失败'
  }

  const detail = (data as { detail?: unknown }).detail
  if (typeof detail === 'string') {
    return detail
  }

  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const payload = detail as {
      message?: string
      duplicate_files?: string[]
      failed_files?: string[]
    }
    const files = payload.duplicate_files?.length
      ? `：${payload.duplicate_files.join('、')}`
      : payload.failed_files?.length
        ? `：${payload.failed_files.join('、')}`
        : ''
    return `${payload.message || '请求失败'}${files}`
  }

  if (Array.isArray(detail)) {
    const firstError = detail[0] as { loc?: string[]; msg?: string } | undefined
    const fieldName = firstError?.loc?.[firstError.loc.length - 1]
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

async function uploadKnowledgeFiles(params: {
  token: string
  sessionId: string
  files: File[]
}): Promise<UploadFilesResponse> {
  const formData = new FormData()
  params.files.forEach((file) => {
    formData.append('files', file)
  })

  const response = await fetch(
    `${API_BASE}/upload_files?session_id=${encodeURIComponent(params.sessionId)}`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${params.token}`,
      },
      body: formData,
    },
  )

  const data = (await response.json().catch(() => ({}))) as UploadFilesResponse
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
        <div className="login-brand">
          <div className="brand-mark">文</div>
          <div>
            <Typography.Title level={2}>智能文档问答系统</Typography.Title>
            <Typography.Text type="secondary">复现主项目的登录、会话与文档问答流程</Typography.Text>
          </div>
        </div>
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
            { key: 'repository', label: '文档上传' },
            { key: 'history', label: '历史会话' },
          ]}
        />
      </Layout.Sider>

      <Layout className="app-main">
        <header className="topbar">
          <div>
            <Typography.Title level={3}>欢迎回来，{props.username}</Typography.Title>
            <Typography.Text type="secondary">
              当前前端只调用 backend_cyl 已有路由，适合逐步验证复现进度。
            </Typography.Text>
          </div>
          <Space>
            {activeSessionId && <Tag color="blue">session: {activeSessionId}</Tag>}
            <Button onClick={props.onLogout}>退出登录</Button>
          </Space>
        </header>

        <main className="workspace">
          {activeKey === 'chat' && (
            <ChatHome
              session={activeSession}
              token={props.token}
              onSessionUpdated={loadSessions}
            />
          )}
          {activeKey === 'repository' && (
            <RepositoryHome
              session={activeSession}
              token={props.token}
              onCreateSession={createNewSession}
            />
          )}
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

function ChatHome(props: {
  session?: ChatSession
  token: string
  onSessionUpdated: () => Promise<void>
}) {
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [parsing, setParsing] = useState(false)
  const [parsedDocumentName, setParsedDocumentName] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const latestAssistant = [...messages].reverse().find((item) => item.role === 'assistant')

  useEffect(() => {
    setMessages([])
    setInput('')
    setSending(false)
    setSelectedFile(null)
    setParsing(false)
    setParsedDocumentName('')

    if (!props.session) {
      return
    }

    let cancelled = false
    async function loadHistoryMessages() {
      setLoadingHistory(true)
      try {
        const data = await request<MessageListResponse>(
          `/get_messages?session_id=${encodeURIComponent(props.session!.id)}`,
          {},
          props.token,
        )
        if (!cancelled) {
          setMessages(data.messages.flatMap(historyItemToChatMessages))
        }
      } catch (error) {
        if (!cancelled) {
          message.error(error instanceof Error ? error.message : '加载会话记录失败')
        }
      } finally {
        if (!cancelled) {
          setLoadingHistory(false)
        }
      }
    }

    loadHistoryMessages()

    return () => {
      cancelled = true
    }
  }, [props.session, props.token])

  function updateAssistantMessage(
    assistantId: string,
    update: (message: ChatMessage) => ChatMessage,
  ) {
    setMessages((current) =>
      current.map((item) => (item.id === assistantId ? update(item) : item)),
    )
  }

  function parseSseBlock(block: string, assistantId: string) {
    const data = block
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.replace(/^data:\s?/, ''))
      .join('\n')
      .trim()

    if (!data || data === '[DONE]') {
      return
    }

    const json = JSON.parse(data) as ChatStreamPayload
    if (json.role === 'error' || json.error) {
      updateAssistantMessage(assistantId, (messageItem) => ({
        ...messageItem,
        error: json.content || json.error || '后端生成回答失败',
      }))
      return
    }

    if (json.documents?.length) {
      updateAssistantMessage(assistantId, (messageItem) => ({
        ...messageItem,
        documentNames: json.documents
          ?.map((item) => item.document_name)
          .filter((name): name is string => Boolean(name)),
      }))
      return
    }

    if (json.content && json.thinking) {
      updateAssistantMessage(assistantId, (messageItem) => ({
        ...messageItem,
        think: `${messageItem.think || ''}${json.content}`,
      }))
      return
    }

    if (json.content) {
      updateAssistantMessage(assistantId, (messageItem) => ({
        ...messageItem,
        content: `${messageItem.content}${json.content}`,
      }))
    }

    if (json.recommended_questions?.length) {
      updateAssistantMessage(assistantId, (messageItem) => ({
        ...messageItem,
        recommendedQuestions: json.recommended_questions,
      }))
    }
  }

  async function readChatStream(reader: ReadableStreamDefaultReader<Uint8Array>, assistantId: string) {
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })

      let blockEnd = buffer.indexOf('\n\n')
      while (blockEnd !== -1) {
        const block = buffer.slice(0, blockEnd)
        buffer = buffer.slice(blockEnd + 2)
        parseSseBlock(block, assistantId)
        blockEnd = buffer.indexOf('\n\n')
      }

      if (done) {
        if (buffer.trim()) {
          parseSseBlock(buffer, assistantId)
        }
        break
      }
    }
  }

  async function parseCurrentDocument() {
    if (!props.session || !selectedFile || parsing) {
      return
    }

    setParsing(true)
    message.destroy()

    try {
      const data = await quickParseCurrentDocument({
        token: props.token,
        sessionId: props.session.id,
        file: selectedFile,
      })

      setParsedDocumentName(data.filename || selectedFile.name)
      setSelectedFile(null)
      message.success(data.message || '文档解析完成')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '文档解析失败')
    } finally {
      setParsing(false)
    }
  }

  async function sendMessage() {
    if (!props.session || sending) {
      return
    }

    const question = input.trim()
    if (!question) {
      message.warning('请输入问题')
      return
    }

    const assistantId = createLocalId()
    setInput('')
    setSending(true)
    setMessages((current) => [
      ...current,
      { id: createLocalId(), role: 'user', content: question },
      { id: assistantId, role: 'assistant', content: '', loading: true },
    ])

    let completed = false
    try {
      const response = await fetch(
        `${API_BASE}/chat_on_docs?session_id=${encodeURIComponent(props.session.id)}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${props.token}`,
          },
          body: JSON.stringify({ message: question }),
        },
      )

      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(getErrorMessage(data))
      }

      if (!response.body) {
        throw new Error('浏览器没有收到流式响应体')
      }

      await readChatStream(response.body.getReader(), assistantId)
      completed = true
    } catch (error) {
      updateAssistantMessage(assistantId, (messageItem) => ({
        ...messageItem,
        error: error instanceof Error ? error.message : '发送失败',
      }))
    } finally {
      updateAssistantMessage(assistantId, (messageItem) => ({
        ...messageItem,
        loading: false,
      }))
      setSending(false)
      if (completed) {
        await props.onSessionUpdated()
      }
    }
  }

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
          {parsedDocumentName && (
            <div className="session-document">
              <Tag color="cyan">已解析</Tag>
              <Typography.Text>{parsedDocumentName}</Typography.Text>
            </div>
          )}
        </div>
        <Typography.Text type="secondary">{props.session.createdAt}</Typography.Text>
      </div>

      <div className="chat-layout">
        <div className="chat-board">
        <div className="message-list">
          {messages.length === 0 && (
            <div className="message assistant-message">
              {loadingHistory
                ? '正在加载该会话的历史对话...'
                : '新会话窗口已创建。现在可以发送问题，前端会读取 '}
              {!loadingHistory && <Typography.Text code>/chat_on_docs</Typography.Text>}
              {!loadingHistory && ' 的 SSE 流式响应。'}
            </div>
          )}

          {messages.map((item) => (
            <div key={item.id} className={`message ${item.role}-message`}>
              <div className="message-role">{item.role === 'user' ? '我' : '助手'}</div>
              {item.think && <div className="message-think">{item.think}</div>}
              {item.documentNames?.length ? (
                <Space className="document-list" size={[8, 8]} wrap>
                  {item.documentNames.map((name) => (
                    <Tag key={name} color="cyan">
                      引用：{name}
                    </Tag>
                  ))}
                </Space>
              ) : null}
              <div className="message-content">
                {item.content || (item.loading ? '正在生成回答...' : '')}
                {item.error && <Typography.Text type="danger">{item.error}</Typography.Text>}
              </div>
              {item.recommendedQuestions?.length ? (
                <Space className="recommend-list" size={[8, 8]} wrap>
                  {item.recommendedQuestions.map((question) => (
                    <Tag key={question} color="blue" onClick={() => setInput(question)}>
                      {question}
                    </Tag>
                  ))}
                </Space>
              ) : null}
            </div>
          ))}
        </div>
        <div className="composer">
          <div className="quick-parse-bar">
            <Input
              type="file"
              accept=".txt,.docx,.pdf"
              disabled={parsing || sending}
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            />
            <Button
              loading={parsing}
              disabled={!selectedFile || parsing || sending}
              onClick={parseCurrentDocument}
            >
              快速解析
            </Button>
          </div>
          <Input.TextArea
            autoSize={{ minRows: 3, maxRows: 6 }}
            value={input}
            placeholder="输入问题，按发送后会通过 SSE 流式显示回答。"
            onChange={(event) => setInput(event.target.value)}
            onPressEnter={(event) => {
              if (!event.shiftKey) {
                event.preventDefault()
                sendMessage()
              }
            }}
          />
          <Button type="primary" loading={sending} onClick={sendMessage}>
            发送
          </Button>
        </div>
      </div>
        <aside className="reference-panel">
          <Typography.Title level={4}>回答依据</Typography.Title>
          <Typography.Text type="secondary">
            SSE 返回的引用文档和推荐追问会在这里同步展示。
          </Typography.Text>
          <Divider />
          {latestAssistant?.documentNames?.length ? (
            <Space size={[8, 8]} wrap>
              {latestAssistant.documentNames.map((name) => (
                <Tag key={name} color="cyan">
                  {name}
                </Tag>
              ))}
            </Space>
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无引用文档" />
          )}
          {latestAssistant?.recommendedQuestions?.length ? (
            <>
              <Divider />
              <Typography.Title level={5}>推荐追问</Typography.Title>
              <Space size={[8, 8]} wrap>
                {latestAssistant.recommendedQuestions.map((question) => (
                  <Tag key={question} color="blue" onClick={() => setInput(question)}>
                    {question}
                  </Tag>
                ))}
              </Space>
            </>
          ) : null}
        </aside>
      </div>
    </section>
  )
}

function RepositoryHome(props: {
  session?: ChatSession
  token: string
  onCreateSession: () => Promise<void>
}) {
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [uploading, setUploading] = useState(false)
  const [lastResult, setLastResult] = useState<UploadFilesResponse | null>(null)

  async function submitUpload() {
    if (!props.session) {
      message.warning('请先新建或打开一个会话')
      return
    }

    const files = fileList.flatMap((item) =>
      item.originFileObj ? [item.originFileObj as File] : [],
    )

    if (!files.length) {
      message.warning('请选择要上传的文件')
      return
    }

    setUploading(true)
    message.destroy()
    try {
      const result = await uploadKnowledgeFiles({
        token: props.token,
        sessionId: props.session.id,
        files,
      })
      setLastResult(result)
      setFileList([])
      message.success(result.message || '上传完成')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '上传失败')
    } finally {
      setUploading(false)
    }
  }

  return (
    <section className="repository-page">
      <div className="repository-hero">
        <div>
          <Typography.Title level={2}>文档上传</Typography.Title>
          <Typography.Text type="secondary">
            对齐主项目知识库入口，当前接入 backend_cyl 的 POST /upload_files。
          </Typography.Text>
        </div>
        {props.session ? (
          <Tag color="green">上传到 {props.session.title}</Tag>
        ) : (
          <Button type="primary" onClick={props.onCreateSession}>
            新建会话
          </Button>
        )}
      </div>

      <div className="upload-grid">
        <div className="upload-panel">
          <Typography.Title level={4}>添加文档</Typography.Title>
          <Upload.Dragger
            multiple
            fileList={fileList}
            beforeUpload={() => false}
            onChange={({ fileList: nextList }) => setFileList(nextList)}
            disabled={uploading || !props.session}
          >
            <div className="upload-icon">+</div>
            <Typography.Text>拖拽文件到这里，或点击选择</Typography.Text>
            <Typography.Paragraph type="secondary">
              文件会携带当前 session_id 上传，后端负责保存、解析并写入 ES。
            </Typography.Paragraph>
          </Upload.Dragger>
          <Button
            type="primary"
            block
            className="upload-submit"
            loading={uploading}
            disabled={!props.session || fileList.length === 0}
            onClick={submitUpload}
          >
            开始上传解析
          </Button>
        </div>

        <div className="upload-panel">
          <Typography.Title level={4}>上传状态</Typography.Title>
          {!props.session && (
            <Alert
              type="info"
              showIcon
              message="需要先创建会话"
              description="backend_cyl 的 /upload_files 目前要求 session_id，并校验会话归属。"
            />
          )}
          {uploading && <Progress percent={60} status="active" showInfo={false} />}
          {lastResult ? (
            <div className="upload-result">
              <Tag color={lastResult.status === 'success' ? 'green' : 'orange'}>
                {lastResult.status}
              </Tag>
              <Typography.Paragraph>{lastResult.message}</Typography.Paragraph>
              {lastResult.successful_files?.length ? (
                <List
                  size="small"
                  header="成功文件"
                  dataSource={lastResult.successful_files}
                  renderItem={(item) => <List.Item>{item}</List.Item>}
                />
              ) : null}
              {lastResult.failed_files?.length ? (
                <List
                  size="small"
                  header="失败文件"
                  dataSource={lastResult.failed_files}
                  renderItem={(item) => <List.Item>{item}</List.Item>}
                />
              ) : null}
            </div>
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无上传结果" />
          )}
        </div>
      </div>
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
