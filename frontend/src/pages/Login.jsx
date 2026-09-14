import { useState } from 'react'
import { login, register, saveAuth } from '../api'

// 登录/注册一体页（迭代1：多用户隔离）
export default function Login({ onLogin }) {
  const [mode, setMode] = useState('login') // login / register
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit() {
    const name = username.trim()
    if (!name || !password) {
      setError('请输入用户名和密码')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const data = await (mode === 'login' ? login(name, password) : register(name, password))
      saveAuth(data.token, data.username)
      onLogin()
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h2 style={{ textAlign: 'center', marginBottom: 16 }}>🖥️ 笔记本售后客服</h2>

        <div className="tabs" style={{ justifyContent: 'center', marginBottom: 16 }}>
          <button
            className={`tab ${mode === 'login' ? 'active' : ''}`}
            onClick={() => { setMode('login'); setError('') }}
          >
            登录
          </button>
          <button
            className={`tab ${mode === 'register' ? 'active' : ''}`}
            onClick={() => { setMode('register'); setError('') }}
          >
            注册
          </button>
        </div>

        <input
          className="login-input"
          placeholder="用户名"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          className="login-input"
          type="password"
          placeholder="密码（至少 6 位）"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
        />

        {error && <div className="login-error">{error}</div>}

        <button className="btn login-btn" onClick={submit} disabled={submitting}>
          {submitting ? '请稍候...' : mode === 'login' ? '登录' : '注册并登录'}
        </button>

        <div className="login-demo">
          演示账号：user_a / 123456（有 3 个订单）
          <br />
          user_b / 123456（无订单，验证数据隔离）
        </div>
      </div>
    </div>
  )
}
