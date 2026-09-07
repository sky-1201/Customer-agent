import { useEffect, useState } from 'react'
import { fetchOrderDetail, fetchOrders } from '../api'

export default function Orders() {
  const [orders, setOrders] = useState([])
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    fetchOrders().then(setOrders)
  }, [])

  async function showDetail(id) {
    setDetail(await fetchOrderDetail(id))
  }

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>我的订单</h2>
      {orders.map((o) => (
        <div
          key={o.id}
          className="card"
          onClick={() => showDetail(o.id)}
          style={{ cursor: 'pointer' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <b>{o.product_name}</b>
            <span className="tag">{o.status}</span>
          </div>
          <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>
            订单号：{o.order_no} ｜ ¥{o.amount} ｜ {o.created_at}
          </div>
        </div>
      ))}

      {detail && (
        <div className="card" style={{ background: '#fafafa' }}>
          <h3 style={{ marginBottom: 8 }}>订单详情</h3>
          <div style={{ fontSize: 14, lineHeight: 1.8 }}>
            <div>商品：{detail.product_name}</div>
            <div>配置：{detail.cpu} ｜ {detail.memory} ｜ {detail.storage} ｜ {detail.gpu}</div>
            <div>金额：¥{detail.amount} ｜ 状态：{detail.status}</div>
            <div>下单时间：{detail.created_at}</div>
            <div style={{ marginTop: 8 }}>维修记录：</div>
            {detail.repairs && detail.repairs.length > 0 ? (
              detail.repairs.map((r, i) => (
                <div key={i} style={{ paddingLeft: 12 }}>
                  • {r.repair_date} {r.fault}（{r.status}）
                </div>
              ))
            ) : (
              <div style={{ paddingLeft: 12 }}>无</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
