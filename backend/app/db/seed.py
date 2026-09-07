"""数据初始化脚本：执行 SQL 种子数据 + 向量化 FAQ/故障说明入库

用法（在 backend 目录下运行）：
    python -m app.db.seed
"""
import json

from app.config import ROOT_DIR
from app.db.database import engine
from app.kb.embedding import embed

DATA_DIR = ROOT_DIR / "data"


def run_sql_file(filename: str):
    """执行 SQL 文件（含多条 INSERT）"""
    sql = (DATA_DIR / filename).read_text(encoding="utf-8")
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print(f"✅ {filename} 执行完成")


def seed_structured():
    """结构化数据（商品/政策/订单/维修记录）"""
    for f in ["policies.sql", "products.sql", "orders.sql", "repairs.sql"]:
        run_sql_file(f)


def _vec_str(vec: list[float]) -> str:
    """把向量转成 pgvector 的字符串格式 [a,b,c,...]"""
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


def seed_vectors():
    """向量化 FAQ 和故障说明入库（非结构化知识，RAG 召回）"""
    with engine.raw_connection() as conn:
        with conn.cursor() as cur:
            # FAQ
            faqs = json.loads((DATA_DIR / "faqs.json").read_text(encoding="utf-8"))
            for item in faqs:
                vec = embed(item["question"])
                cur.execute(
                    "INSERT INTO faqs (question, answer, question_embedding) "
                    "VALUES (%s, %s, %s::vector)",
                    (item["question"], item["answer"], _vec_str(vec)),
                )
            print(f"✅ FAQ 向量化入库 {len(faqs)} 条")

            # 故障说明
            troubles = json.loads(
                (DATA_DIR / "troubleshooting.json").read_text(encoding="utf-8")
            )
            for item in troubles:
                vec = embed(item["fault"])
                cur.execute(
                    "INSERT INTO troubleshooting "
                    "(product_model, fault, cause, solution, fault_embedding) "
                    "VALUES (%s, %s, %s, %s, %s::vector)",
                    (
                        item.get("product_model"),
                        item["fault"],
                        item["cause"],
                        item["solution"],
                        _vec_str(vec),
                    ),
                )
            print(f"✅ 故障说明向量化入库 {len(troubles)} 条")
        conn.commit()


def main():
    print("开始初始化数据...")
    seed_structured()
    seed_vectors()
    print("✅ 数据初始化完成")


if __name__ == "__main__":
    main()
