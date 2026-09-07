# 智能笔记本售后客服系统

聚焦笔记本电脑售后的多 Agent 智能客服系统，能对"复杂售后"做多维度协同核实，并通过人工审批实现人机协作闭环。

## 技术栈

React + FastAPI + LangGraph + PostgreSQL(pgvector)

## 文档

- [PRD](docs/PRD.md) — 产品需求（做什么）
- [技术设计文档](docs/技术设计文档.md) — 技术方案（怎么做）
- [开发计划](docs/开发计划.md) — 开发顺序

## 环境搭建（换电脑从零恢复）

> 前置：已安装 Docker、Anaconda（或 Miniconda）

### 1. 起服务（PostgreSQL + pgvector）

```bash
docker compose up -d
# schema.sql 会随容器首次启动自动建表
```

### 2. 建 conda 环境

```bash
conda env create -f environment.yml
conda activate customer-agent
```

### 3. 配密钥

```bash
cp .env.example .env
# 然后编辑 .env，填入自己的 LLM / Embedding API key
```

### 4. 初始化数据

```bash
# schema 已自动建表，只需插入数据（用 psql 或后续的 seed 脚本）
psql postgresql://postgres:postgres@localhost:5432/customer_agent \
  -f data/products.sql -f data/policies.sql -f data/orders.sql -f data/repairs.sql
```

### 5. 启动

```bash
uvicorn backend.app.main:app --reload
```

## 项目结构

```
code/
├── docker-compose.yml     # 服务层（PG + pgvector）
├── environment.yml        # conda 环境（锁 Python 3.12）
├── requirements.txt       # pip 依赖
├── .env.example           # 密钥模板
├── backend/               # FastAPI + LangGraph
│   └── app/
│       ├── api/           # 接口层
│       ├── graph/         # LangGraph 图 + Agent + 工具
│       ├── models/        # Pydantic schema
│       ├── db/            # 数据库
│       └── kb/            # 知识库（结构化 + 向量）
├── frontend/              # React
├── data/                  # 数据文件（建表 + 种子数据）
└── docs/                  # 文档
```

## 协作开发约定

- **密钥**：真实 key 只放 `.env`（git 忽略），`.env.example` 才是提交的模板
- **版本**：开发期 requirements 用范围约束，稳定后 `pip freeze > requirements.txt` 锁定
- **提交**：一个阶段一个 commit（如"阶段0：数据地基"）
