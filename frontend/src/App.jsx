import { useState } from 'react'
import Admin from './pages/Admin'
import Chat from './pages/Chat'
import Orders from './pages/Orders'
import Shop from './pages/Shop'

const PAGES = [
  { key: 'shop', label: '商品', component: Shop },
  { key: 'orders', label: '我的订单', component: Orders },
  { key: 'chat', label: '智能客服', component: Chat },
  { key: 'admin', label: '管理端', component: Admin },
]

export default function App() {
  const [page, setPage] = useState('shop')
  const Current = PAGES.find((p) => p.key === page).component

  return (
    <div className="app">
      <nav className="nav">
        <span className="brand">🖥️ 笔记本售后客服</span>
        {PAGES.map((p) => (
          <button
            key={p.key}
            className={`nav-btn ${page === p.key ? 'active' : ''}`}
            onClick={() => setPage(p.key)}
          >
            {p.label}
          </button>
        ))}
      </nav>
      <main className="main">
        <Current />
      </main>
    </div>
  )
}
