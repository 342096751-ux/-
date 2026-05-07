"""
兼容从 `backend` 目录执行 `uvicorn main:app`。

业务路由（含 knowledge_batch）均在 ``app.main`` 中注册，此处仅转发 ``app`` 实例。
等价命令：``uvicorn app.main:app``（推荐）。
"""

from app.main import app

__all__ = ["app"]
