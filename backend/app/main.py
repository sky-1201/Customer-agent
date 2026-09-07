"""FastAPI 入口

完整启动流程（从零到跑起来，在项目根目录 code/ 下执行）：

1. 起数据库（PostgreSQL + pgvector，schema 自动建表）
   docker compose up -d

2. 建 conda 环境（仅首次）
   conda env create -f environment.yml
   conda activate customer-agent

3. 配密钥（仅首次）
   cp .env.example .env      # 然后编辑 .env 填 DASHSCOPE_API_KEY

4. 初始化数据（仅首次：SQL 种子数据 + FAQ/故障向量化入库）
   cd backend
   python -m app.db.seed

5. 启动后端（开发模式，--reload 自动重载代码改动）
   uvicorn app.main:app --reload

启动后浏览器访问 http://localhost:8000 打开前端对话页。
测试接口：curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"message":"怎么激活系统"}'
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.approval import router as approval_router
from app.api.catalog import router as catalog_router
from app.api.chat import router as chat_router
from app.config import ROOT_DIR
from app.graph.main import checkpoint_pool
from app.utils.logger import setup_logging

# 日志配置（结构化 JSON + trace_id，见 docs/日志规范.md）
setup_logging()


@asynccontextmanager
async def lifespan(app):
    """启动时打开 checkpoint 异步连接池，关闭时释放"""
    await checkpoint_pool.open()
    yield
    await checkpoint_pool.close()


app = FastAPI(title="智能笔记本售后客服", lifespan=lifespan)

# 开发期放开 CORS，方便前端联调
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(chat_router, prefix="/api")
app.include_router(approval_router, prefix="/api")
app.include_router(catalog_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}


# 挂载前端静态文件（放最后，避免覆盖 /api 路由）
# 访问 http://localhost:8000 即可打开前端对话页
app.mount(
    "/",
    StaticFiles(directory=str(ROOT_DIR / "frontend"), html=True),
    name="frontend",
)
