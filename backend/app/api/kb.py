"""知识库管理接口（CRUD）"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import get_current_user
from pydantic import BaseModel

from app.db import catalog, kb_crud
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ========== 请求模型 ==========

class FaqCreate(BaseModel):
    question: str
    answer: str


class TroubleshootingCreate(BaseModel):
    product_model: Optional[str] = None
    fault: str
    cause: str = ""
    solution: str = ""


class PolicyUpdate(BaseModel):
    warranty_period: Optional[str] = None
    major_parts_period: Optional[str] = None
    major_parts: Optional[str] = None
    replace_condition: Optional[str] = None
    return_condition: Optional[str] = None
    source: Optional[str] = None


# ========== 产品（只读，复用 catalog） ==========

@router.get("/kb/products")
def list_products(user_id: int = Depends(get_current_user)):
    return catalog.list_products()


# ========== FAQ ==========

@router.get("/kb/faqs")
def list_faqs(user_id: int = Depends(get_current_user)):
    return kb_crud.list_faqs()


@router.post("/kb/faqs")
def create_faq(req: FaqCreate, user_id: int = Depends(get_current_user)):
    try:
        faq_id = kb_crud.add_faq(req.question, req.answer)
        return {"id": faq_id}
    except Exception as e:
        logger.error("FAQ 新增失败", extra={"error": type(e).__name__}, exc_info=True)
        raise HTTPException(status_code=500, detail="新增失败（可能是 embedding 服务不可用）")


@router.delete("/kb/faqs/{faq_id}")
def delete_faq(faq_id: int, user_id: int = Depends(get_current_user)):
    if not kb_crud.delete_faq(faq_id):
        raise HTTPException(status_code=404, detail="FAQ 不存在")
    return {"status": "deleted"}


# ========== 故障说明 ==========

@router.get("/kb/troubleshooting")
def list_troubleshooting(user_id: int = Depends(get_current_user)):
    return kb_crud.list_troubleshooting()


@router.post("/kb/troubleshooting")
def create_troubleshooting(req: TroubleshootingCreate, user_id: int = Depends(get_current_user)):
    try:
        t_id = kb_crud.add_troubleshooting(req.product_model, req.fault, req.cause, req.solution)
        return {"id": t_id}
    except Exception as e:
        logger.error("故障说明新增失败", extra={"error": type(e).__name__}, exc_info=True)
        raise HTTPException(status_code=500, detail="新增失败（可能是 embedding 服务不可用）")


@router.delete("/kb/troubleshooting/{t_id}")
def delete_troubleshooting(t_id: int, user_id: int = Depends(get_current_user)):
    if not kb_crud.delete_troubleshooting(t_id):
        raise HTTPException(status_code=404, detail="故障说明不存在")
    return {"status": "deleted"}


# ========== 政策 ==========

@router.get("/kb/policies")
def list_policies(user_id: int = Depends(get_current_user)):
    return kb_crud.list_policies()


@router.put("/kb/policies/{policy_id}")
def update_policy(policy_id: int, req: PolicyUpdate, user_id: int = Depends(get_current_user)):
    fields = req.model_dump(exclude_none=True)
    if not kb_crud.update_policy(policy_id, fields):
        raise HTTPException(status_code=404, detail="政策不存在或没有可更新字段")
    return {"status": "updated"}
