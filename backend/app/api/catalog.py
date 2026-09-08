"""商品与订单接口（客户端数据底座）"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import catalog
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/products")
def get_products():
    """商品列表"""
    return catalog.list_products()


class CreateOrderRequest(BaseModel):
    product_id: int


@router.post("/orders")
def create_order(req: CreateOrderRequest):
    """下单"""
    try:
        return catalog.create_order(req.product_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/orders")
def get_orders():
    """订单列表"""
    return catalog.list_orders()


@router.get("/orders/{order_id}")
def get_order_detail(order_id: int):
    """订单详情（含维修记录）"""
    order = catalog.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


@router.delete("/orders/{order_id}")
def delete_order(order_id: int):
    """删除订单"""
    if not catalog.delete_order(order_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    return {"status": "deleted"}
