"""Embedding 调用（通义 text-embedding-v3，1024 维）"""
from openai import OpenAI

from app.config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, EMBEDDING_MODEL

_client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)


def embed(text: str) -> list[float]:
    """把文本向量化为 1024 维向量"""
    resp = _client.embeddings.create(model=EMBEDDING_MODEL, input=[text])
    return resp.data[0].embedding
