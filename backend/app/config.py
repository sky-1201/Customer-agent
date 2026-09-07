"""配置管理：从 .env 读取环境变量"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录（code/），.env 文件在这里
# config.py 位于 backend/app/，向上三级是项目根目录
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")

# --- 阿里云百炼（LLM + Embedding 共用） ---
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# --- LLM 分层（分流小模型 + 回答强模型） ---
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "qwen-flash")
AGENT_MODEL = os.getenv("AGENT_MODEL", "qwen-max")

# --- Embedding ---
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")

# --- 数据库 ---
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/customer_agent",
)
