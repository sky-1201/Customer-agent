// API 封装：所有后端调用统一在这里

export async function fetchProducts() {
  const res = await fetch('/api/products')
  return res.json()
}

export async function createOrder(productId) {
  const res = await fetch('/api/orders', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: productId }),
  })
  return res.json()
}

export async function fetchOrders() {
  const res = await fetch('/api/orders')
  return res.json()
}

export async function fetchOrderDetail(id) {
  const res = await fetch(`/api/orders/${id}`)
  return res.json()
}

export async function fetchApprovalStatus(threadId) {
  const res = await fetch(`/api/approvals/status?thread_id=${threadId}`)
  return res.json()
}

export async function fetchApprovals() {
  const res = await fetch('/api/approvals')
  return res.json()
}

export async function submitApproval(id, action, reason = '') {
  const res = await fetch(`/api/approvals/${id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, reason }),
  })
  return res.json()
}

// 对话接口（SSE 流式），onEvent 处理每个事件
export async function chat(message, threadId, onEvent) {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, thread_id: threadId }),
  })
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
