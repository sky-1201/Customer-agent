// API 封装：所有后端调用统一在这里
// 迭代1（多用户隔离）：token 管理 + 请求自动带 Authorization 头 + 401 全局处理

// ========== 登录态管理 ==========

const TOKEN_KEY = 'auth_token'
const USERNAME_KEY = 'auth_username'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function getUsername() {
  return localStorage.getItem(USERNAME_KEY) || ''
}

export function saveAuth(token, username) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USERNAME_KEY, username)
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USERNAME_KEY)
}

// ========== 认证接口 ==========

async function authRequest(path, username, password) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.detail || '请求失败')
  return data
}

export function login(username, password) {
  return authRequest('/api/auth/login', username, password)
}

export function register(username, password) {
  return authRequest('/api/auth/register', username, password)
}

// ========== 统一请求封装 ==========
// 自动带 token；401 时清登录态并刷新回登录页（App 根据 token 有无渲染登录页）

async function request(url, options = {}) {
  const token = getToken()
  const headers = { ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(url, { ...options, headers })
  if (res.status === 401) {
    clearAuth()
    location.reload()
    throw new Error('登录已过期，请重新登录')
  }
  return res
}

function post(url, body) {
  return request(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

// ========== 商品与订单 ==========

export async function fetchProducts() {
  const res = await request('/api/products')
  return res.json()
}

export async function createOrder(productId) {
  const res = await post('/api/orders', { product_id: productId })
  return res.json()
}

export async function fetchOrders() {
  const res = await request('/api/orders')
  return res.json()
}

export async function fetchOrderDetail(id) {
  const res = await request(`/api/orders/${id}`)
  return res.json()
}

export async function deleteOrder(id) {
  const res = await request(`/api/orders/${id}`, { method: 'DELETE' })
  return res.json()
}

// ========== 知识库管理 ==========

export async function fetchFaqs() {
  const res = await request('/api/kb/faqs')
  return res.json()
}

export async function createFaq(question, answer) {
  const res = await post('/api/kb/faqs', { question, answer })
  return res.json()
}

export async function deleteFaq(id) {
  const res = await request(`/api/kb/faqs/${id}`, { method: 'DELETE' })
  return res.json()
}

export async function fetchTroubleshooting() {
  const res = await request('/api/kb/troubleshooting')
  return res.json()
}

export async function createTroubleshooting(data) {
  const res = await post('/api/kb/troubleshooting', data)
  return res.json()
}

export async function deleteTroubleshooting(id) {
  const res = await request(`/api/kb/troubleshooting/${id}`, { method: 'DELETE' })
  return res.json()
}

export async function fetchPolicies() {
  const res = await request('/api/kb/policies')
  return res.json()
}

export async function updatePolicy(id, fields) {
  const res = await request(`/api/kb/policies/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fields),
  })
  return res.json()
}

// ========== 审批（管理端）==========

export async function fetchApprovals() {
  const res = await request('/api/approvals')
  return res.json()
}

export async function submitApproval(id, action, reason = '') {
  const res = await post(`/api/approvals/${id}`, { action, reason })
  return res.json()
}

export async function fetchApprovalStatus(sessionId) {
  // 只传 session_id，thread_id 由服务端用 token 里的 user_id 拼接（防越权轮询）
  const res = await request(`/api/approvals/status?session_id=${encodeURIComponent(sessionId)}`)
  return res.json()
}

// ========== 接管（管理端，迭代4）==========

export async function fetchHandovers(status) {
  const res = await request('/api/handovers' + (status ? `?status=${status}` : ''))
  return res.json()
}

export async function fetchHandoverDetail(id) {
  const res = await request(`/api/handovers/${id}`)
  return res.json()
}

export async function takeHandover(id) {
  const res = await post(`/api/handovers/${id}/take`, {})
  return res.json()
}

export async function sendHandoverMessage(id, content) {
  const res = await post(`/api/handovers/${id}/messages`, { content })
  return res.json()
}

export async function closeHandover(id) {
  const res = await post(`/api/handovers/${id}/close`, {})
  return res.json()
}

export async function returnHandover(id) {
  const res = await post(`/api/handovers/${id}/return`, {})
  return res.json()
}

// ========== 会话管理（迭代5）==========

export async function fetchSessions() {
  const res = await request('/api/sessions')
  return res.json()
}

export async function archiveSession(sessionId) {
  const res = await request(`/api/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' })
  return res.json()
}

// ========== 指标（迭代5，管理端）==========

export async function fetchMetrics() {
  const res = await request('/api/metrics')
  return res.json()
}

// ========== WebSocket（迭代4）==========

// 建立 WS 连接（经 vite 代理 ws:true 转发到后端），返回 WebSocket 实例
export function connectWs(path) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return new WebSocket(`${proto}://${location.host}${path}`)
}

// ========== 对话（SSE 流式）==========

// 会话历史（服务端 checkpoint 是唯一事实源）
export async function fetchChatHistory(sessionId) {
  const res = await request(`/api/chat/history?session_id=${encodeURIComponent(sessionId)}`)
  return res.json()
}

// sessionId 只是会话标识，不含身份；服务端拼 user_id 成 thread_id（防越权）
export async function chat(message, sessionId, onEvent) {
  const token = getToken()
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
  if (res.status === 401) {
    clearAuth()
    location.reload()
    return
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // SSE 事件块格式："event: xxx\ndata: {...}\n\n"
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop()
    for (const block of blocks) {
      const dataLine = block.split('\n').find((l) => l.startsWith('data: '))
      if (!dataLine) continue
      try {
        const data = JSON.parse(dataLine.slice(6))
        if (data && Object.keys(data).length > 0) {
          onEvent(data)
        }
      } catch {
        /* 忽略解析失败 */
      }
    }
  }
}
