import { useEffect, useRef, useState } from 'react'
import {
  closeHandover, connectWs, fetchHandoverDetail, fetchHandovers,
  getToken, returnHandover, sendHandoverMessage, takeHandover,
} from '../api'
import { Empty, Loading } from '../components/Status'
import { AftersaleDetail, Section, TechDetail } from './Approval'

// 转人工原因中文映射
const REASON_LABELS = {
  complaint: '⚠️ 投诉',
  user_request: '主动转人工',
  clarify_overflow: '澄清失败',
  ai_escalate: 'AI 无法处理',
}

// JSONB 字段可能是字符串（需解析）或对象（直接用），防御性处理
function parseJson(value) {
  if (value == null) return null
  if (typeof value === 'string') {
    try { return JSON.parse(value) } catch { return value }
  }
  return value
}

// 等待时长友好显示
function waitTime(createdAt) {
  if (!createdAt) return ''
  const mins = Math.max(0, Math.floor((Date.now() - new Date(createdAt.replace(' ', 'T'))) / 60000))
  return mins < 60 ? `等待 ${mins} 分钟` : `等待 ${Math.floor(mins / 60)} 小时`
}

// 坐席视角的消息气泡：我（真人客服）在右，用户/AI 在左
function ConsoleMsg({ m }) {
  if (m.type === 'system') return <div className="msg system">{m.content}</div>
  const cls = m.type === 'human_agent' ? 'msg user' : 'msg assistant'
  const label = m.type === 'user' ? '用户' : m.type === 'human_agent' ? '我（客服）' : 'AI'
  return (
    <div className={cls}>
      <span className="role-label">{label}</span>
      {m.content}
    </div>
  )
}

export default function Handover() {
  const [pendings, setPendings] = useState([])
  const [actives, setActives] = useState([])
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState(null) // {handover, history}
  const [liveMsgs, setLiveMsgs] = useState([]) // 接管后的实时消息
  const [input, setInput] = useState('')
  const detailRef = useRef(null) // 让 WS 回调读到最新 detail（避免闭包旧值）
  detailRef.current = detail

  async function load() {
    const all = await fetchHandovers()
    setPendings(all.filter((h) => h.status === 'pending'))
    setActives(all.filter((h) => h.status === 'active'))
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  // 坐席端 WS：新接管单 → 刷新队列；用户留言 → 若正打开该会话则实时追加
  useEffect(() => {
    const ws = connectWs(`/ws/agent?token=${encodeURIComponent(getToken() || '')}`)
    ws.onmessage = (e) => {
      let data
      try { data = JSON.parse(e.data) } catch { return }
      if (data.type === 'queue_update') {
        load()
      } else if (data.type === 'user_message') {
        const cur = detailRef.current
        if (cur && cur.handover.id === data.handover_id && cur.handover.status === 'active') {
          setLiveMsgs((m) => [...m, { type: 'user', content: data.content }])
        }
      }
    }
    return () => ws.close()
  }, [])

  async function openDetail(id) {
    const data = await fetchHandoverDetail(id)
    setDetail(data)
    setLiveMsgs([])
  }

  async function take() {
    await takeHandover(detail.handover.id)
    await openDetail(detail.handover.id) // 刷新为接管中（历史里也会多出系统提示）
    load()
  }

  async function send() {
    const msg = input.trim()
    if (!msg) return
    setInput('')
    await sendHandoverMessage(detail.handover.id, msg)
    setLiveMsgs((m) => [...m, { type: 'human_agent', content: msg }])
  }

  async function finish(returnToAi) {
    await (returnToAi ? returnHandover(detail.handover.id) : closeHandover(detail.handover.id))
    setDetail(null)
    load()
  }

  if (loading) return <Loading />

  const ctx = detail ? parseJson(detail.handover.agent_context) || {} : {}

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>待接管队列</h3>
        <button className="btn" onClick={load}>刷新</button>
      </div>

      {pendings.length === 0 && actives.length === 0 && <Empty text="暂无待接管会话" />}

      {pendings.map((h) => (
        <div key={h.id} className="card" style={{ cursor: 'pointer' }} onClick={() => openDetail(h.id)}>
          <div>
            <b>#{h.id} · {h.username || '未知用户'}</b>
            <span className="tag" style={{ marginLeft: 8 }}>{REASON_LABELS[h.reason] || h.reason}</span>
            <span className="tag">{waitTime(h.created_at)}</span>
          </div>
          <div style={{ fontSize: 14, color: '#666', marginTop: 6 }}>诉求：{(h.user_request || '').slice(0, 60)}</div>
        </div>
      ))}

      {actives.length > 0 && <h3 style={{ margin: '16px 0 12px' }}>接管中</h3>}
      {actives.map((h) => (
        <div key={h.id} className="card" style={{ cursor: 'pointer', borderLeft: '3px solid #4caf50' }} onClick={() => openDetail(h.id)}>
          <b>#{h.id} · {h.username || '未知用户'}</b>
          <span className="tag" style={{ marginLeft: 8 }}>接管中</span>
          <div style={{ fontSize: 14, color: '#666', marginTop: 6 }}>诉求：{(h.user_request || '').slice(0, 60)}</div>
        </div>
      ))}

      {/* 接管详情/对话台 */}
      {detail && (
        <div className="modal-mask" onClick={() => setDetail(null)}>
          <div className="modal" style={{ maxWidth: 640 }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: 4 }}>
              接管单 #{detail.handover.id} · {detail.handover.username}
            </h3>
            <div style={{ fontSize: 13, color: '#888', marginBottom: 12 }}>
              原因：{REASON_LABELS[detail.handover.reason] || detail.handover.reason}
              {detail.handover.taken_at && ` ｜ 接管于 ${detail.handover.taken_at}`}
            </div>

            {/* AI 已核实信息置顶（交接上下文，用户无需重复描述） */}
            {(ctx.tech_result || ctx.aftersale_result || ctx.final_decision) && (
              <div style={{ background: '#f5f8ff', borderRadius: 8, padding: 12, marginBottom: 12 }}>
                <div style={{ fontWeight: 'bold', fontSize: 13, color: '#1976d2', marginBottom: 8 }}>
                  AI 已核实信息（交接上下文）
                </div>
                {ctx.tech_result && <Section title="技术诊断"><TechDetail data={ctx.tech_result} /></Section>}
                {ctx.aftersale_result && <Section title="售后核实"><AftersaleDetail data={ctx.aftersale_result} /></Section>}
                {ctx.final_decision && (
                  <Section title="AI 决策建议">
                    <div>结论：{ctx.final_decision.conclusion}（置信度 {Math.round((ctx.final_decision.confidence || 0) * 100)}%）</div>
                    <div style={{ color: '#666' }}>{ctx.final_decision.reasoning}</div>
                  </Section>
                )}
              </div>
            )}

            {/* 完整对话历史 + 实时消息 */}
            <div className="messages" style={{ maxHeight: 320, border: '1px solid #eee', borderRadius: 8, padding: 8, marginBottom: 12 }}>
              {[...detail.history, ...liveMsgs].map((m, i) => <ConsoleMsg key={i} m={m} />)}
            </div>

            {detail.handover.status === 'pending' && (
              <button className="btn green" onClick={take}>接管该会话</button>
            )}

            {detail.handover.status === 'active' && (
              <>
                <div className="input-row" style={{ marginBottom: 10 }}>
                  <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && send()}
                    placeholder="以真人客服身份回复用户..."
                  />
                  <button className="btn" onClick={send}>发送</button>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn" onClick={() => finish(true)}>转回 AI</button>
                  <button className="btn red" onClick={() => finish(false)}>结束会话</button>
                  <button className="btn" style={{ background: '#999' }} onClick={() => setDetail(null)}>最小化</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
