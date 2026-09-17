"""指标接口（迭代5：可观测性——运营指标聚合）"""
from fastapi import APIRouter, Depends
from psycopg.rows import dict_row

from app.api.auth import get_current_user
from app.db.database import engine

router = APIRouter()


@router.get("/metrics")
def metrics(user_id: int = Depends(get_current_user)):
    """核心运营指标：审批/接管/业务量统计（管理端数据条）"""
    with engine.raw_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # 审批：按状态计数 + 平均审批时长（分钟）
            cur.execute("SELECT status, COUNT(*) AS n FROM approvals GROUP BY status")
            approvals = {r["status"]: r["n"] for r in cur.fetchall()}
            cur.execute(
                "SELECT AVG(EXTRACT(EPOCH FROM (decided_at - created_at))/60) AS m "
                "FROM approvals WHERE decided_at IS NOT NULL"
            )
            avg_minutes = cur.fetchone()["m"]

            # 接管：按状态计数
            cur.execute("SELECT status, COUNT(*) AS n FROM handovers GROUP BY status")
            handovers = {r["status"]: r["n"] for r in cur.fetchall()}

            # 业务量
            cur.execute("SELECT COUNT(*) AS n FROM users")
            users = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM orders")
            orders = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM sessions")
            sessions = cur.fetchone()["n"]

    return {
        "approvals": {
            "pending": approvals.get("pending", 0),
            "approved": approvals.get("approved", 0),
            "rejected": approvals.get("rejected", 0),
            "avg_decision_minutes": round(avg_minutes, 1) if avg_minutes is not None else None,
        },
        "handovers": {
            "pending": handovers.get("pending", 0),
            "active": handovers.get("active", 0),
            "closed": handovers.get("closed", 0),
            "returned": handovers.get("returned", 0),
        },
        "users": users,
        "orders": orders,
        "sessions": sessions,
    }
