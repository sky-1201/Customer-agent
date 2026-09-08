import { useEffect, useState } from 'react'
import {
  createFaq, createTroubleshooting, deleteFaq, deleteTroubleshooting,
  fetchFaqs, fetchPolicies, fetchProducts, fetchTroubleshooting, updatePolicy,
} from '../api'
import { Empty, Loading } from '../components/Status'

const TABS = [
  { key: 'faqs', label: 'FAQ' },
  { key: 'troubleshooting', label: '故障说明' },
  { key: 'policies', label: '三包政策' },
  { key: 'products', label: '产品文档' },
]

export default function Knowledge() {
  const [tab, setTab] = useState('faqs')
  return (
    <div>
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
      {tab === 'faqs' && <FaqTab />}
      {tab === 'troubleshooting' && <TroubleshootingTab />}
      {tab === 'policies' && <PolicyTab />}
      {tab === 'products' && <ProductTab />}
    </div>
  )
}

// ========== FAQ ==========

function FaqTab() {
  const [faqs, setFaqs] = useState([])
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [a, setA] = useState('')

  async function load() {
    setFaqs(await fetchFaqs())
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  async function add() {
    if (!q.trim() || !a.trim()) return
    await createFaq(q.trim(), a.trim())
    setQ(''); setA('')
    load()
  }

  async function del(id) {
    if (!confirm('确定删除该 FAQ？')) return
    await deleteFaq(id)
    load()
  }

  if (loading) return <Loading />

  return (
    <div>
      <div className="card" style={{ background: '#fafafa' }}>
        <input className="kb-input" placeholder="问题" value={q} onChange={(e) => setQ(e.target.value)} />
        <input className="kb-input" placeholder="答案" value={a} onChange={(e) => setA(e.target.value)} />
        <button className="btn" onClick={add}>新增 FAQ</button>
      </div>
      {faqs.length === 0 ? <Empty /> : faqs.map((f) => (
        <div key={f.id} className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ flex: 1, marginRight: 12 }}>
              <b>Q：{f.question}</b>
              <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>A：{f.answer}</div>
            </div>
            <button className="btn red" onClick={() => del(f.id)}>删除</button>
          </div>
        </div>
      ))}
    </div>
  )
}

// ========== 故障说明 ==========

function TroubleshootingTab() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ fault: '', cause: '', solution: '', product_model: '' })

  async function load() {
    setItems(await fetchTroubleshooting())
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  async function add() {
    if (!form.fault.trim()) return
    await createTroubleshooting({
      fault: form.fault.trim(),
      cause: form.cause.trim(),
      solution: form.solution.trim(),
      product_model: form.product_model.trim() || null,
    })
    setForm({ fault: '', cause: '', solution: '', product_model: '' })
    load()
  }

  async function del(id) {
    if (!confirm('确定删除该故障说明？')) return
    await deleteTroubleshooting(id)
    load()
  }

  if (loading) return <Loading />

  return (
    <div>
      <div className="card" style={{ background: '#fafafa' }}>
        <input className="kb-input" placeholder="故障现象（如：蓝屏死机）" value={form.fault}
          onChange={(e) => setForm({ ...form, fault: e.target.value })} />
        <input className="kb-input" placeholder="原因" value={form.cause}
          onChange={(e) => setForm({ ...form, cause: e.target.value })} />
        <input className="kb-input" placeholder="排查方法" value={form.solution}
          onChange={(e) => setForm({ ...form, solution: e.target.value })} />
        <button className="btn" onClick={add}>新增故障说明</button>
      </div>
      {items.length === 0 ? <Empty /> : items.map((t) => (
        <div key={t.id} className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ flex: 1, marginRight: 12 }}>
              <b>【{t.fault}】</b>
              <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>原因：{t.cause}</div>
              <div style={{ fontSize: 13, color: '#666', marginTop: 2 }}>解决：{t.solution}</div>
            </div>
            <button className="btn red" onClick={() => del(t.id)}>删除</button>
          </div>
        </div>
      ))}
    </div>
  )
}

// ========== 三包政策 ==========

const POLICY_FIELDS = [
  { key: 'warranty_period', label: '整机保修期' },
  { key: 'major_parts_period', label: '主要部件保修期' },
  { key: 'major_parts', label: '主要部件清单' },
  { key: 'replace_condition', label: '换货条件' },
  { key: 'return_condition', label: '退货条件' },
  { key: 'source', label: '政策出处' },
]

function PolicyTab() {
  const [policies, setPolicies] = useState([])
  const [loading, setLoading] = useState(true)

  async function load() {
    setPolicies(await fetchPolicies())
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  async function editField(p, field) {
    const meta = POLICY_FIELDS.find((f) => f.key === field)
    const val = prompt(`修改「${meta.label}」：`, p[field] || '')
    if (val === null) return
    await updatePolicy(p.id, { [field]: val })
    load()
  }

  if (loading) return <Loading />

  return (
    <div>
      {policies.length === 0 ? <Empty /> : policies.map((p) => (
        <div key={p.id} className="card">
          <h3 style={{ marginBottom: 8 }}>{p.category} 三包政策</h3>
          {POLICY_FIELDS.map((f) => (
            <div key={f.key} style={{ display: 'flex', alignItems: 'center', marginBottom: 6 }}>
              <span style={{ width: 130, fontSize: 13, color: '#666' }}>{f.label}：</span>
              <span style={{ flex: 1, fontSize: 14 }}>{p[f.key] || '-'}</span>
              <button className="btn" style={{ padding: '4px 10px', fontSize: 12 }} onClick={() => editField(p, f.key)}>
                编辑
              </button>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

// ========== 产品文档（只读） ==========

function ProductTab() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchProducts().then((data) => {
      setProducts(data)
      setLoading(false)
    })
  }, [])

  if (loading) return <Loading />

  return (
    <div>
      <p style={{ fontSize: 13, color: '#888', marginBottom: 12 }}>
        商品由 seed 脚本预置，如需修改请编辑 data/products.sql 后重新初始化。
      </p>
      {products.map((p) => (
        <div key={p.id} className="card">
          <b>{p.name}</b>
          <span className="tag" style={{ marginLeft: 8 }}>{p.brand}</span>
          <span className="tag">{p.category}</span>
          <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>
            {p.cpu} ｜ {p.memory} ｜ {p.storage} ｜ {p.gpu} ｜ ¥{p.price}
          </div>
        </div>
      ))}
    </div>
  )
}
