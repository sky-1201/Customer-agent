import { useEffect, useMemo, useState } from 'react'
import { createOrder, fetchProducts } from '../api'
import { Empty, Loading } from '../components/Status'

const CATEGORIES = ['全部', '轻薄', '游戏', '全能', '苹果', '入门']

export default function Shop() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [category, setCategory] = useState('全部')
  const [keyword, setKeyword] = useState('')

  useEffect(() => {
    fetchProducts().then((data) => {
      setProducts(data)
      setLoading(false)
    })
  }, [])

  const filtered = useMemo(() => {
    return products.filter((p) => {
      const matchCat = category === '全部' || p.category === category
      const kw = keyword.trim().toLowerCase()
      const matchKw = !kw || p.name.toLowerCase().includes(kw) || p.brand.toLowerCase().includes(kw)
      return matchCat && matchKw
    })
  }, [products, category, keyword])

  async function handleOrder(p) {
    const result = await createOrder(p.id)
    alert(`下单成功！订单号：${result.order_no}`)
  }

  if (loading) return <Loading />

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>笔记本商城</h2>

      <div className="toolbar">
        <div className="tabs">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              className={`tab ${category === c ? 'active' : ''}`}
              onClick={() => setCategory(c)}
            >
              {c}
            </button>
          ))}
        </div>
        <input
          className="search"
          placeholder="搜索型号或品牌"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
      </div>

      {filtered.length === 0 ? (
        <Empty text="没有匹配的商品" />
      ) : (
        <div className="grid">
          {filtered.map((p) => (
            <div key={p.id} className="card product-card">
              <div>
                <span className="tag">{p.category}</span>
                <span className="tag">{p.brand}</span>
              </div>
              <h3 style={{ margin: '8px 0' }}>{p.name}</h3>
              <div style={{ fontSize: 13, color: '#666', lineHeight: 1.7 }}>
                <div>CPU：{p.cpu}</div>
                <div>内存：{p.memory} ｜ 硬盘：{p.storage}</div>
                <div>显卡：{p.gpu}</div>
                <div>屏幕：{p.screen}</div>
                <div>重量：{p.weight}</div>
              </div>
              <div style={{ margin: '10px 0' }}>
                <span className="price">¥{p.price}</span>
              </div>
              <button className="btn" onClick={() => handleOrder(p)}>立即下单</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
