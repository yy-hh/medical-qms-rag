"""FastAPI 依赖：从请求头解析当前账号（飞书 open_id）。

受保护端点加参数 `account_id: str = Depends(get_current_account)`。
支持 `Authorization: Bearer <token>` 或 `X-Session: <token>` 两种传法。
"""
from fastapi import Header, HTTPException

from app.core import account_store


def get_current_account(
    authorization: str | None = Header(default=None),
    x_session: str | None = Header(default=None),
) -> str:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_session:
        token = x_session.strip()
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    open_id = account_store.resolve_session(token)
    if not open_id:
        raise HTTPException(status_code=401, detail="会话已失效，请重新登录")
    return open_id
