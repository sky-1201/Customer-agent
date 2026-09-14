-- ============================================================
-- 智能笔记本售后客服系统 · 数据库建表脚本
-- 技术栈：PostgreSQL + pgvector
-- 对应《技术设计文档》第 8 节 + 《迭代01》迭代1（多用户隔离）
-- ============================================================

-- 1. 启用 pgvector 扩展（向量检索）
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. 商品表（21 个笔记本，规格字段化）
CREATE TABLE IF NOT EXISTS products (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,      -- 型号名，如"小新 Pro 16"
    brand       VARCHAR(50)  NOT NULL,      -- 品牌
    category    VARCHAR(50)  NOT NULL,      -- 定位：轻薄/游戏/全能/苹果/入门
    cpu         VARCHAR(100),               -- CPU 型号
    memory      VARCHAR(50),                -- 内存
    storage     VARCHAR(50),                -- 硬盘
    gpu         VARCHAR(100),               -- 显卡
    screen      VARCHAR(50),                -- 屏幕
    weight      VARCHAR(20),                -- 重量
    price       DECIMAL(10,2)               -- 参考价（元）
);

-- 3. 用户表（迭代1：多用户隔离的地基）
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(200) NOT NULL,    -- bcrypt 哈希，绝不存明文
    created_at    TIMESTAMP DEFAULT now()
);

-- 4. 订单表（user_id 归属用户，查询必须按 user_id 过滤——安全红线）
CREATE TABLE IF NOT EXISTS orders (
    id          SERIAL PRIMARY KEY,
    order_no    VARCHAR(50) UNIQUE NOT NULL,
    product_id  INT REFERENCES products(id),
    user_id     INT REFERENCES users(id),   -- 订单归属（迭代1 新增，暂允许 NULL，迭代内收敛）
    amount      DECIMAL(10,2),
    created_at  TIMESTAMP DEFAULT now(),
    status      VARCHAR(20) DEFAULT '已完成'  -- 已完成 / 退换货中 / 已退换
);

-- 5. 维修记录表（构造数据，支撑"修两次换货"核心场景）
CREATE TABLE IF NOT EXISTS repairs (
    id          SERIAL PRIMARY KEY,
    order_id    INT REFERENCES orders(id),
    repair_date DATE,
    fault       VARCHAR(200),
    status      VARCHAR(20)
);

-- 6. 政策表（字段化，精确查询，禁止用向量检索）
CREATE TABLE IF NOT EXISTS policies (
    id                  SERIAL PRIMARY KEY,
    category            VARCHAR(50),         -- 品类：微型计算机
    warranty_period     VARCHAR(50),         -- 整机保修期
    major_parts_period  VARCHAR(50),         -- 主要部件保修期
    major_parts         TEXT,                -- 主要部件清单
    replace_condition   TEXT,                -- 换货条件
    return_condition    TEXT,                -- 退货条件
    source              VARCHAR(200)         -- 政策出处
);

-- 7. FAQ 表（文本 + 向量双存，RAG 召回）
CREATE TABLE IF NOT EXISTS faqs (
    id                  SERIAL PRIMARY KEY,
    question            TEXT NOT NULL,
    answer              TEXT NOT NULL,
    -- 向量维度取决于 embedding 模型，1024（通义 text-embedding-v3）
    question_embedding  vector(1024)
);

-- 8. 故障说明表（文本 + 向量双存，RAG 召回）
CREATE TABLE IF NOT EXISTS troubleshooting (
    id               SERIAL PRIMARY KEY,
    product_model    VARCHAR(100),           -- 关联型号（NULL = 通用故障）
    fault            TEXT NOT NULL,
    cause            TEXT,
    solution         TEXT,
    fault_embedding  vector(1024)
);

-- 9. 审批单表（HITL 数据枢纽，管理端"待审批详情页"读这张表）
CREATE TABLE IF NOT EXISTS approvals (
    id               SERIAL PRIMARY KEY,
    thread_id        VARCHAR(100),           -- 关联对话会话（resume 用）
    user_id          INT REFERENCES users(id),  -- 诉求归属用户（迭代1 新增）
    user_request     TEXT,                   -- 用户诉求
    tech_result      JSONB,                  -- 技术诊断结果（TechResult）
    aftersale_result JSONB,                  -- 售后核实结果（AftersaleResult）
    decision         VARCHAR(50),            -- 结论：换货/退货/维修/不满足
    policy_ref       TEXT,                   -- 政策依据（可溯源）
    comfort_msg      TEXT,                   -- 草拟回复
    confidence       FLOAT,                  -- 置信度
    status           VARCHAR(20) DEFAULT 'pending'  -- pending/approved/rejected/edited
);

-- ============================================================
-- 注：checkpoint 表由 LangGraph 的 PostgresSaver 自动创建，无需手动建。
--     embedding 维度 1024（通义 text-embedding-v3 默认维度），
--     若换用其他维度模型，需 ALTER TABLE 调整 vector 维度。
-- ============================================================
