import { useEffect, useState } from 'react'
import { fetchApprovals, submitApproval } from '../api'
import { Empty, Loading } from '../components/Status'

// JSONB 字段可能是字符串（需解析）或对象（直接用），防御性处理
function parseJson(value) {
  if (value == null) return null
  if (typeof value === 'string') {
    try { return JSON.parse(value) } catch { return value }
  }
  return value
}

// 布尔值友好展示
function bool(v) {
  return v ? '✅ 是' : '❌ 否'
}

// 置信度格式化
function pct(v) {
  return v == null ? '-' : `${(v * 100).toFixed(0)}%`
}

export default function Approval() {
  const [approvals, setApprovals] = useState([])
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState(null) // 详情模态框

  async function load() {
    setApprovals(await fetchApprovals())
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  async function submit(id, action) {
    const reason = action === 'reject' ? prompt('请输入拒绝理由：') : ''
    const result = await submitApproval(id, action, reason)
    alert(`审批完成：${result.status}\n回复用户：${result.reply}`)
    setDetail(null)
    load()
  }

  if (loading) return <Loading />

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>管理端 · 待审批队列</h2>
      <button className="btn" onClick={load} style={{ marginBottom: 12 }}>
        刷新列表
      </button>

      {approvals.length === 0 && <Empty text="暂无待审批工单" />}

      {approvals.map((a) => (
        <div
          key={a.id}
          className="card"
          style={{ cursor: 'pointer' }}
          onClick={() => setDetail(a)}
        >
          <div>
            <b>#{a.id} · 结论：{a.decision}</b>
            <span className="tag" style={{ marginLeft: 8 }}>置信度 {pct(a.confidence)}</span>
          </div>
          <div style={{ fontSize: 14, color: '#666', marginTop: 6 }}>用户诉求：{a.user_request}</div>
          <div style={{ fontSize: 12, color: '#999', marginTop: 6 }}>点击查看完整判断依据 →</div>
        </div>
      ))}

      {/* 审批详情模态框：展示完整判断依据链 */}
      {detail && (
        <div className="modal-mask" onClick={() => setDetail(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: 12 }}>审批详情 #{detail.id}</h3>

            <Section title="用户诉求">
              <p>{detail.user_request}</p>
            </Section>

            <Section title="技术诊断">
              <TechDetail data={parseJson(detail.tech_result)} />
            </Section>

            <Section title="售后核实">
              <AftersaleDetail data={parseJson(detail.aftersale_result)} />
            </Section>

            <Section title="政策依据">
              <p style={{ background: '#fff8e1', padding: '8px 12px', borderRadius: 6 }}>
                {detail.policy_ref || '无'}
              </p>
            </Section>

            <Section title="草拟回复">
              <p style={{ color: '#555' }}>{detail.comfort_msg || '无'}</p>
            </Section>

            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              <button className="btn green" onClick={() => submit(detail.id, 'approve')}>
                批准
              </button>
              <button className="btn red" onClick={() => submit(detail.id, 'reject')}>
                拒绝
              </button>
              <button className="btn" style={{ background: '#999' }} onClick={() => setDetail(null)}>
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// 区块标题（导出给接管台复用）
export function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontWeight: 'bold', fontSize: 14, marginBottom: 6, color: '#1976d2' }}>
        {title}
      </div>
      <div style={{ fontSize: 14, lineHeight: 1.8 }}>{children}</div>
    </div>
  )
}

// 技术诊断明细（导出给接管台复用）
export function TechDetail({ data }) {
  if (!data) return <p style={{ color: '#999' }}>无技术诊断数据</p>
  return (
    <div>
      <div>故障现象：{data.fault || '-'}</div>
      <div>是否同一故障：{bool(data.same_fault)}</div>
      <div>可能原因：{data.cause || '-'}</div>
      <div>置信度：{pct(data.confidence)}</div>
    </div>
  )
}

// 售后核实明细（导出给接管台复用）
export function AftersaleDetail({ data }) {
  if (!data) return <p style={{ color: '#999' }}>无售后核实数据</p>
  return (
    <div>
      <div>订单号：{data.order_no || '-'}</div>
      <div>购买时间：{data.purchase_date || '-'}</div>
      <div>订单有效：{bool(data.order_valid)}</div>
      <div>三包期内：{bool(data.in_warranty)}</div>
      <div>维修次数：{data.repair_count ?? '-'} 次</div>
      <div>政策适用：{bool(data.policy_applicable)}</div>
      <div>置信度：{pct(data.confidence)}</div>
    </div>
  )
}
