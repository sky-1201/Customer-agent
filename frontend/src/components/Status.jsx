// 统一状态组件：加载 / 空 / 错误（全站复用）

export function Loading({ text = '加载中...' }) {
  return <div className="status-hint">{text}</div>
}

export function Empty({ text = '暂无数据' }) {
  return <div className="status-hint">{text}</div>
}

export function Error({ text = '加载失败，请重试' }) {
  return <div className="status-hint error">{text}</div>
}
