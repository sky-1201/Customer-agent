"""商品与订单接口（客户端数据底座）

鉴权（迭代1）：
- 商品列表公开（游客可浏览，符合真实电商逻辑）
- 订单相关接口全部需登录，且只能操作自己的订单（数据隔离是安全红线）
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.db import catalog
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/products")
def get_products():
    """商品列表（公开）"""
    return catalog.list_products()


class CreateOrderRequest(BaseModel):
    product_id: int


@router.post("/orders")
def create_order(req: CreateOrderRequest, user_id: int = Depends(get_current_user)):
    """下单（订单归属当前登录用户）"""
    try:
        return catalog.create_order(req.product_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/orders")
def get_orders(user_id: int = Depends(get_current_user)):
    """订单列表（只能看到自己的）"""
    return catalog.list_orders(user_id)


@router.get("/orders/{order_id}")
def get_order_detail(order_id: int, user_id: int = Depends(get_current_user)):
    """订单详情（含维修记录）。越权与不存在统一 404，不暴露订单是否存在"""
    order = catalog.get_order(order_id, user_id)
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


@router.delete("/orders/{order_id}")
def delete_order(order_id: int, user_id: int = Depends(get_current_user)):
    """删除订单（只能删自己的）"""
    if not catalog.delete_order(order_id, user_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    return {"status": "deleted"}
