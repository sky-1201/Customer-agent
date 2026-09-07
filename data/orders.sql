-- ============================================================
-- 订单数据（构造，单一用户演示）
-- 目的：给"订单核实"Agent 提供真实可查的数据
-- 说明：O-001 是"修两次换货"核心场景的订单
-- ============================================================

INSERT INTO orders (order_no, product_id, amount, created_at, status)
SELECT 'O-001', id, 4599, '2026-03-15 10:00:00'::timestamp, '已完成'   FROM products WHERE name = '小新 Pro 16'
UNION ALL
SELECT 'O-002', id, 9999, '2026-04-20 14:30:00'::timestamp, '已完成'   FROM products WHERE name = '拯救者 Y9000P'
UNION ALL
SELECT 'O-003', id, 8999, '2026-07-01 09:15:00'::timestamp, '退换货中' FROM products WHERE name = 'MacBook Air 13英寸 M3';
