import { useState } from 'react'
import { clearAuth, getToken, getUsername } from './api'
import Admin from './pages/Admin'
import Chat from './pages/Chat'
import Login from './pages/Login'
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
  // 登录态：无 token 时只渲染登录页（路由守卫）
  const [authed, setAuthed] = useState(!!getToken())

  if (!authed) {
    return <Login onLogin={() => setAuthed(true)} />
  }

  function logout() {
    clearAuth()
    setAuthed(false)
    setPage('shop')
  }

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
        <span className="nav-user">{getUsername()}</span>
        <button className="nav-btn" onClick={logout}>退出</button>
      </nav>
      <main className="main">
        <Current />
      </main>
    </div>
  )
}
