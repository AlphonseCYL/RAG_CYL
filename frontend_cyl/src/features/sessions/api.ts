const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8001'

export type QuickParseResponse = {
  filename?: string
  file_type?: string
  content_length?: number
  message?: string
  status: string
}

function getApiErrorMessage(data: unknown): string {
  if (!data || typeof data !== 'object') {
    return '请求失败'
  }

  const detail = (data as { detail?: unknown }).detail
  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail)) {
    const firstError = detail[0] as { msg?: string } | undefined
    return firstError?.msg || '输入内容不符合要求'
  }

  return '请求失败'
}

export async function quickParseCurrentDocument(params: {
  token: string
  sessionId: string
  file: File
}): Promise<QuickParseResponse> {
  const formData = new FormData()
  formData.append('file', params.file)

  const response = await fetch(
    `${API_BASE}/quick_parse?session_id=${encodeURIComponent(params.sessionId)}`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${params.token}`,
      },
      body: formData,
    },
  )

  const data = (await response.json().catch(() => ({}))) as QuickParseResponse
  if (!response.ok) {
    throw new Error(getApiErrorMessage(data))
  }

  return data
}
