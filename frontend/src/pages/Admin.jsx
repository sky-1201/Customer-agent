import { useEffect, useState } from 'react'
import { fetchMetrics } from '../api'
import Approval from './Approval'
import Handover from './Handover'
import Knowledge from './Knowledge'

const TABS = [
  { key: 'approval', label: '待审批队列' },
  { key: 'handover', label: '待接管队列' },  // 迭代4：转人工坐席接管
  { key: 'knowledge', label: '知识库管理' },
]

export default function Admin() {
  const [tab, setTab] = useState('approval')
  const [metrics, setMetrics] = useState(null)

  // 核心运营指标（迭代5：可观测性）
  useEffect(() => {
    fetchMetrics().then(setMetrics).catch(() => {})
  }, [tab]) // 切 tab 时刷新，审批/接管操作后回来能看到最新值

  return (
    <div>
      {metrics && (
        <div className="stats-strip">
          <span>待审批 <b>{metrics.approvals.pending}</b></span>
          <span>待接管 <b>{metrics.handovers.pending}</b></span>
          <span>接管中 <b>{metrics.handovers.active}</b></span>
          <span>平均审批时长 <b>{metrics.approvals.avg_decision_minutes ?? '-'} 分钟</b></span>
          <span>用户 <b>{metrics.users}</b></span>
          <span>订单 <b>{metrics.orders}</b></span>
          <span>会话 <b>{metrics.sessions}</b></span>
        </div>
      )}
      <div className="tabs" style={{ marginBottom: 16 }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`tab ${tab === t.key ? 'active' : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'approval' && <Approval />}
      {tab === 'handover' && <Handover />}
      {tab === 'knowledge' && <Knowledge />}
    </div>
  )
}
