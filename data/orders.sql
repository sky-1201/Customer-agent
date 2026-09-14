-- ============================================================
-- 订单数据（构造，归属内置演示用户 user_a）
-- 目的：给"订单核实"Agent 提供真实可查的数据
-- 说明：O-001 是"修两次换货"核心场景的订单
--      user_b 无订单，用于验收多用户隔离（A 见订单、B 不见）
-- ============================================================

INSERT INTO orders (order_no, product_id, user_id, amount, created_at, status)
SELECT 'O-001', p.id, u.id, 4599, '2026-03-15 10:00:00'::timestamp, '已完成'
FROM products p CROSS JOIN users u WHERE p.name = '小新 Pro 16' AND u.username = 'user_a'
UNION ALL
SELECT 'O-002', p.id, u.id, 9999, '2026-04-20 14:30:00'::timestamp, '已完成'
FROM products p CROSS JOIN users u WHERE p.name = '拯救者 Y9000P' AND u.username = 'user_a'
UNION ALL
SELECT 'O-003', p.id, u.id, 8999, '2026-07-01 09:15:00'::timestamp, '退换货中'
FROM products p CROSS JOIN users u WHERE p.name = 'MacBook Air 13英寸 M3' AND u.username = 'user_a';
