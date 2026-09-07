import { useEffect, useState } from 'react'
import { fetchApprovals, submitApproval } from '../api'

export default function Approval() {
  const [approvals, setApprovals] = useState([])

  async function load() {
    setApprovals(await fetchApprovals())
  }

  useEffect(() => {
    load()
  }, [])

  async function submit(id, action) {
    const reason = action === 'reject' ? prompt('请输入拒绝理由：') : ''
    const result = await submitApproval(id, action, reason)
    alert(`审批完成：${result.status}\n回复用户：${result.reply}`)
    load()
  }

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>管理端 · 待审批队列</h2>
      <button className="btn" onClick={load} style={{ marginBottom: 12 }}>
        刷新列表
      </button>

      {approvals.length === 0 && (
        <div style={{ color: '#999', textAlign: 'center', marginTop: 40 }}>
          暂无待审批工单
        </div>
      )}

      {approvals.map((a) => (
        <div key={a.id} className="card">
          <div>
            <b>#{a.id} · 结论：{a.decision}</b>
            <span className="tag" style={{ marginLeft: 8 }}>
              置信度 {a.confidence}
            </span>
          </div>
          <div style={{ fontSize: 14, color: '#666', margin: '8px 0' }}>
            用户诉求：{a.user_request}
          </div>
          <button className="btn green" onClick={() => submit(a.id, 'approve')}>
            批准
          </button>
          <button
            className="btn red"
            style={{ marginLeft: 8 }}
            onClick={() => submit(a.id, 'reject')}
          >
            拒绝
          </button>
        </div>
      ))}
    </div>
  )
}
