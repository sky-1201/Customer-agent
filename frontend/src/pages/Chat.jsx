import { useEffect, useRef, useState } from 'react'
import { chat, fetchApprovalStatus, getUsername } from '../api'

// Agent 名称展示（前端展示层，对应 PRD 客服页设计点①）
const AGENT_NAMES = {
  analyzing: '分流分析中',
  customer_agent: '客服 Agent',
  tech: '技术诊断 Agent',
  aftersale: '售后核实 Agent',
  decision: '决策 Agent',
  pending_approval: '等待人工审批',
}

// localStorage 缓存按用户名隔离（迭代1）：
// 同一浏览器先后登录 A/B 时，B 不会看到 A 缓存的聊天记录
function msgKey() { return `chat_messages_${getUsername()}` }
function sessionKey() { return `chat_session_id_${getUsername()}` }

function getOrCreateSessionId() {
  let id = localStorage.getItem(sessionKey())
  if (!id) {
    id = 'session-' + Date.now()
    localStorage.setItem(sessionKey(), id)
  }
  return id
}

export default function Chat() {
  // 历史消息从 localStorage 恢复（刷新/换页面不丢）
  const [messages, setMessages] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(msgKey())) || []
    } catch {
      return []
    }
  })
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [sessionId, setSessionId] = useState(getOrCreateSessionId)
  const pollTimer = useRef(null)

  // 消息变化时持久化
  useEffect(() => {
    localStorage.setItem(msgKey(), JSON.stringify(messages))
  }, [messages])

  // 组件卸载时清理轮询定时器
  useEffect(() => {
    return () => {
      if (pollTimer.current) clearInterval(pollTimer.current)
    }
  }, [])

  // 组件挂载时：若上次对话停在"等待审核"（切换页面/刷新后回来），重启轮询
  useEffect(() => {
    const last = messages[messages.length - 1]
    if (last && last.type === 'assistant' && last.content.includes('等待人工审核')) {
      startPolling()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 审批轮询：收到"等待审核"后，每 2 秒查一次审批状态，审批完成显示结果
  function startPolling() {
    if (pollTimer.current) return
    pollTimer.current = setInterval(async () => {
      try {
        const result = await fetchApprovalStatus(sessionId)
        if (result.status === 'approved' || result.status === 'rejected') {
          clearInterval(pollTimer.current)
          pollTimer.current = null
          setMessages((m) => [
            ...m,
            { type: 'agent', content: result.status === 'approved' ? '✅ 审批通过' : '❌ 审批被拒绝' },
          ])
          if (result.reply) {
            setMessages((m) => [...m, { type: 'assistant', content: result.reply }])
          }
        }
      } catch {
        /* 轮询失败忽略，下轮再试 */
      }
    }, 2000)
  }

  function clearChat() {
    if (pollTimer.current) {
      clearInterval(pollTimer.current)
      pollTimer.current = null
    }
    setMessages([])
    localStorage.removeItem(msgKey())
    localStorage.removeItem(sessionKey())
    setSessionId(getOrCreateSessionId()) // 开新会话
  }

  async function send() {
    const msg = input.trim()
    if (!msg || sending) return
    setInput('')
    setMessages((m) => [...m, { type: 'user', content: msg }])
    setSending(true)

    try {
      await chat(msg, sessionId, (event) => {
        // event.agent → Agent 工作状态；event.content → 助手回复
        if (event.agent) {
          setMessages((m) => [
            ...m,
            {
              type: 'agent',
              content: `[${AGENT_NAMES[event.agent] || event.agent}] ${event.msg || '处理中...'}`,
            },
          ])
        } else if (event.content) {
          setMessages((m) => [...m, { type: 'assistant', content: event.content }])
          // 收到"等待审核" → 开始轮询审批结果
          if (event.content.includes('等待人工审核')) {
            startPolling()
          }
        }
      })
    } catch (e) {
      setMessages((m) => [...m, { type: 'assistant', content: '请求失败：' + e.message }])
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="chat-box">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ marginBottom: 12 }}>智能客服</h2>
        <button className="btn red" onClick={clearChat} style={{ marginBottom: 12 }}>
          清空对话
        </button>
      </div>
      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.type}`}>
            {m.type === 'agent' ? '⚙️ ' + m.content : m.content}
          </div>
        ))}
        {sending && <div className="msg status">正在处理...</div>}
      </div>
      <div className="input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="输入问题，如：蓝屏修两次要换货"
        />
        <button className="btn" onClick={send} disabled={sending}>发送</button>
      </div>
    </div>
  )
}
