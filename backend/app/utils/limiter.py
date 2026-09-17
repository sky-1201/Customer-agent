"""限流器（迭代5：API 限流，防刷/防暴力破解）

按客户端 IP 限流（slowapi）。挂在认证接口（防密码爆破）和对话接口（防刷 LLM 调用）。
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
