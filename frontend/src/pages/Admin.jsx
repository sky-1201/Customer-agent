import { useState } from 'react'
import Approval from './Approval'
import Knowledge from './Knowledge'

export default function Admin() {
  const [tab, setTab] = useState('approval')

  return (
    <div>
      <div className="tabs" style={{ marginBottom: 16 }}>
        <button
          className={`tab ${tab === 'approval' ? 'active' : ''}`}
          onClick={() => setTab('approval')}
        >
          待审批队列
        </button>
        <button
          className={`tab ${tab === 'knowledge' ? 'active' : ''}`}
          onClick={() => setTab('knowledge')}
        >
          知识库管理
        </button>
      </div>
      {tab === 'approval' ? <Approval /> : <Knowledge />}
    </div>
  )
}
