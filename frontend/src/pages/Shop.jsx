import { useEffect, useState } from 'react'
import { createOrder, fetchProducts } from '../api'

export default function Shop() {
  const [products, setProducts] = useState([])

  useEffect(() => {
    fetchProducts().then(setProducts)
  }, [])

  async function handleOrder(p) {
    const result = await createOrder(p.id)
    alert(`下单成功！订单号：${result.order_no}`)
  }

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>笔记本商城（{products.length} 款）</h2>
      <div className="grid">
        {products.map((p) => (
          <div key={p.id} className="card">
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
    </div>
  )
}
