"""数据库连接（SQLAlchemy）"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL

# pool_pre_ping 防止连接池里的失效连接
# connect_timeout 防止数据库挂起时连接无限等待（5 秒超时）
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
