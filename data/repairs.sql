-- ============================================================
-- 维修记录数据（构造，支撑"修两次换货"核心场景）
-- O-001 有 2 次蓝屏维修记录 → 演示"同一故障修两次可换货"
-- ============================================================

INSERT INTO repairs (order_id, repair_date, fault, status)
SELECT id, '2026-05-20'::date, '蓝屏死机', '已修复' FROM orders WHERE order_no = 'O-001'
UNION ALL
SELECT id, '2026-07-10'::date, '蓝屏死机', '已修复' FROM orders WHERE order_no = 'O-001'
UNION ALL
SELECT id, '2026-08-05'::date, '屏幕花屏', '已修复' FROM orders WHERE order_no = 'O-003';
