import { useEffect, useState } from 'react'
import { deleteOrder, fetchOrderDetail, fetchOrders } from '../api'
import { Empty, Loading } from '../components/Status'

export default function Orders() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState(null) // 详情模态框

  async function load() {
    setOrders(await fetchOrders())
    setLoading(false)
  }

  useEffect(() => {
    load()
  }, [])

  async function showDetail(id) {
    setDetail(await fetchOrderDetail(id))
  }

  async function handleDelete(id) {
    if (!confirm('确定删除该订单吗？此操作不可恢复。')) return
    await deleteOrder(id)
    if (detail && detail.id === id) setDetail(null)
    load()
  }

  if (loading) return <Loading />

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>我的订单</h2>

      {orders.length === 0 ? (
        <Empty text="还没有订单，去商城逛逛吧" />
      ) : (
        orders.map((o) => (
          <div key={o.id} className="card" style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{ flex: 1, cursor: 'pointer' }} onClick={() => showDetail(o.id)}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <b>{o.product_name}</b>
                <span className="tag">{o.status}</span>
              </div>
              <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>
                订单号：{o.order_no} ｜ ¥{o.amount} ｜ {o.created_at}
              </div>
            </div>
            <button className="btn red" style={{ marginLeft: 12 }} onClick={() => handleDelete(o.id)}>
              删除
            </button>
          </div>
        ))
      )}

      {/* 订单详情模态框 */}
      {detail && (
        <div className="modal-mask" onClick={() => setDetail(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginBottom: 12 }}>订单详情</h3>
            <div style={{ fontSize: 14, lineHeight: 1.9 }}>
              <div>商品：{detail.product_name}</div>
              <div>配置：{detail.cpu} ｜ {detail.memory} ｜ {detail.storage} ｜ {detail.gpu}</div>
              <div>屏幕：{detail.screen}</div>
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
              {/* 状态流转记录（迭代5：订单状态机，可追溯） */}
              {detail.events && detail.events.length > 0 && (
                <>
                  <div style={{ marginTop: 8 }}>状态流转：</div>
                  {detail.events.map((e, i) => (
                    <div key={i} style={{ paddingLeft: 12 }}>
                      • {(e.from_status || '创建')} → {e.to_status}（{e.reason}）
                    </div>
                  ))}
                </>
              )}
            </div>
            <button className="btn" style={{ marginTop: 16 }} onClick={() => setDetail(null)}>
              关闭
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
