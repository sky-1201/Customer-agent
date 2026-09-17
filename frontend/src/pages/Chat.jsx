import { useEffect, useRef, useState } from 'react'
import {
  archiveSession, chat, connectWs, fetchApprovalStatus, fetchChatHistory,
  fetchSessions, getToken, getUsername,
} from '../api'

// Agent 名称展示（前端展示层，对应 PRD 客服页设计点①）
const AGENT_NAMES = {
  analyzing: '分流分析中',
  customer_agent: '客服 Agent',
  tech: '技术诊断 Agent',
  aftersale: '售后核实 Agent',
  decision: '决策 Agent',
  clarify: '订单确认',
  pending_approval: '等待人工审批',
}

// session_id 指针按用户名隔离存 localStorage；对话内容本身以服务端
// checkpoint 为唯一事实源（企业标准做法），刷新/换页面/换浏览器都能恢复
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
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [sessionId, setSessionId] = useState(getOrCreateSessionId)
  // 人工接管状态：null=AI 服务中；pending=等待坐席接管；active=人工服务中（迭代4）
  const [handoverStatus, setHandoverStatus] = useState(null)
  // 会话列表（迭代5：会话管理——历史会话/多会话/归档）
  const [sessions, setSessions] = useState([])
  const pollTimer = useRef(null)
  const sendingRef = useRef(false) // 同步发送守卫（state 生效有延迟，双击/双击回车会穿过）
  const messagesEndRef = useRef(null)
  const wsRef = useRef(null)

  // 自动滚动到底部（新事件追加在列表末尾，不滚动会渲染到视野外，看起来像"没输出"）
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 组件卸载时清理轮询定时器和 WS
  useEffect(() => {
    return () => {
      if (pollTimer.current) clearInterval(pollTimer.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [])

  // 会话列表：挂载时拉取
  useEffect(() => {
    fetchSessions().then(setSessions).catch(() => {})
  }, [])

  // 组件挂载/切会话时：从服务端 checkpoint 拉取完整对话历史；
  // 有未完成的审批 → 直接启动轮询；有未完结接管 → 进入人工模式（不依赖消息是否送达）
  useEffect(() => {
    setMessages([])
    setHandoverStatus(null)
    fetchChatHistory(sessionId)
      .then((data) => {
        if (data.messages && data.messages.length > 0) setMessages(data.messages)
        if (data.pending_approval) startPolling()
        if (data.handover_status) setHandoverStatus(data.handover_status)
      })
      .catch(() => {
        /* 拉取失败按空会话处理，不影响发消息 */
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  // 用户端 WebSocket（迭代4）：接收坐席消息 + 接管状态变化，断线自动重连
  useEffect(() => {
    let closed = false
    let retryTimer = null

    function connect() {
      const ws = connectWs(`/ws/chat?session_id=${encodeURIComponent(sessionId)}&token=${encodeURIComponent(getToken() || '')}`)
      wsRef.current = ws
      ws.onmessage = (e) => {
        let data
        try { data = JSON.parse(e.data) } catch { return }
        if (data.type === 'human_message') {
          // 真人坐席消息（带真人标识，与 AI 消息明确区分）
          setMessages((m) => [...m, { type: 'human_agent', content: data.content, agent_name: data.agent_name }])
        } else if (data.type === 'handover_status') {
          if (data.status === 'active' || data.status === 'pending') {
            setHandoverStatus(data.status)
          } else {
            // returned / closed → 回到 AI 模式 + 系统提示（身份切换明确告知）
            setHandoverStatus(null)
            if (data.msg) setMessages((m) => [...m, { type: 'system', content: data.msg }])
          }
        }
      }
      ws.onclose = () => {
        if (!closed) retryTimer = setTimeout(connect, 3000) // 断线重连
      }
    }
    connect()
    return () => {
      closed = true
      if (retryTimer) clearTimeout(retryTimer)
      if (wsRef.current) wsRef.current.close()
    }
  }, [sessionId])

  // 审批轮询：每 2 秒查一次审批状态，审批完成显示结果
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

  // 开新会话（服务端 checkpoint 按 session_id 隔离，旧会话历史保留可查）
  function newSession() {
    if (pollTimer.current) {
      clearInterval(pollTimer.current)
      pollTimer.current = null
    }
    localStorage.removeItem(sessionKey())
    setSessionId(getOrCreateSessionId()) // sessionId 变化 → 历史/WS effect 自动重载
  }

  // 切换历史会话
  function switchSession(id) {
    if (id === sessionId || sendingRef.current) return
    localStorage.setItem(sessionKey(), id)
    setSessionId(id)
  }

  // 归档会话（列表里移除；服务端 checkpoint 保留）
  async function handleArchive(e, id) {
    e.stopPropagation()
    await archiveSession(id)
    setSessions((s) => s.filter((x) => x.session_id !== id))
    if (id === sessionId) newSession()
  }

  async function send() {
    const msg = input.trim()
    if (!msg || sendingRef.current) return
    sendingRef.current = true
    setInput('')
    setMessages((m) => [...m, { type: 'user', content: msg }])
    setSending(true)

    let gotMessage = false // 流是否正常带回了最终消息
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
          gotMessage = true
          setMessages((m) => [...m, { type: 'assistant', content: event.content }])
          // 收到"等待审核" → 开始轮询审批结果
          if (event.content.includes('等待人工审核')) {
            startPolling()
          }
        } else if (event.handover) {
          // 人工模式回执：消息已留言给坐席，AI 不回复（不是中断，不显示兜底提示）
          gotMessage = true
          setHandoverStatus(event.handover)
        }
      })
      // 兜底：流结束了但没带回任何消息（中途断开）→ 明确提示，不让用户干等
      if (!gotMessage) {
        setMessages((m) => [
          ...m,
          { type: 'assistant', content: '处理可能中断了，请重新发送；如已提交审批，可稍后在管理端查看。' },
        ])
      }
    } catch (e) {
      setMessages((m) => [...m, { type: 'assistant', content: '请求失败：' + e.message }])
    } finally {
      sendingRef.current = false
      setSending(false)
      fetchSessions().then(setSessions).catch(() => {}) // 首条消息已建档，刷新会话列表
    }
  }

  return (
    <div className="chat-box">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ marginBottom: 12 }}>智能客服</h2>
        <button className="btn" onClick={newSession} style={{ marginBottom: 12 }}>
          ＋ 新会话
        </button>
      </div>

      {/* 会话列表（迭代5：历史会话切换 / 归档） */}
      {sessions.length > 0 && (
        <div className="session-chips">
          {sessions.map((s) => (
            <span
              key={s.session_id}
              className={`session-chip ${s.session_id === sessionId ? 'active' : ''}`}
              onClick={() => switchSession(s.session_id)}
            >
              {s.title || '未命名会话'}
              <span className="session-chip-x" onClick={(e) => handleArchive(e, s.session_id)}>×</span>
            </span>
          ))}
        </div>
      )}

      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.type}`}>
            {m.type === 'agent' && '⚙️ ' + m.content}
            {m.type === 'human_agent' && (
              <>
                <span className="agent-badge">🧑‍💼 {m.agent_name || '人工客服'}</span>
                {m.content}
              </>
            )}
            {m.type === 'system' && m.content}
            {m.type !== 'agent' && m.type !== 'human_agent' && m.type !== 'system' && m.content}
          </div>
        ))}
        {sending && <div className="msg status">正在处理...</div>}
        <div ref={messagesEndRef} />
      </div>

      {/* 人工模式横幅（PRD：身份切换必须明确告知，绝不互相伪装） */}
      {handoverStatus === 'pending' && (
        <div className="handover-banner">⏳ 已转人工，等待坐席接管，您可以直接留言补充情况</div>
      )}
      {handoverStatus === 'active' && (
        <div className="handover-banner active">🧑‍💼 人工客服服务中</div>
      )}

      <div className="input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder={handoverStatus ? '给人工客服留言...' : '输入问题，如：蓝屏修两次要换货'}
        />
        <button className="btn" onClick={send} disabled={sending}>发送</button>
      </div>
    </div>
  )
}
