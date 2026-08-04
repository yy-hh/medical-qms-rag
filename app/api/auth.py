"""账号认证：飞书验证码登录。

流程：输入姓名/邮箱 → 核对为属主飞书联系人 → 给其飞书发 6 位验证码 →
回填验证码 → 建立会话。账号身份即飞书 open_id。
"""
import secrets

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel

from app.core import account_store, feishu_cli
from app.api.deps import get_current_account

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RequestCodeReq(BaseModel):
    name: str
    open_id: str | None = None   # 多同名时前端选定后回传，精确定位


class VerifyReq(BaseModel):
    open_id: str | None = None
    name: str | None = None
    code: str


@router.post("/request-code")
async def request_code(req: RequestCodeReq):
    """核对联系人并发验证码。多个同名候选且未指定 open_id 时返回列表让前端选，不发码。"""
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="请输入飞书姓名或邮箱")

    res = feishu_cli.search_user(name)
    if not res["ok"]:
        raise HTTPException(status_code=503, detail=f"无法核对飞书身份：{res['error']}")

    cands = res["candidates"]
    if not cands:
        raise HTTPException(status_code=404, detail="未找到该飞书联系人（须为本人的飞书联系人）")

    # 前端已选定 open_id：必须在候选内（防绕过联系人校验）
    if req.open_id:
        c = next((x for x in cands if x["open_id"] == req.open_id), None)
        if not c:
            raise HTTPException(status_code=404, detail="所选联系人无效")
    elif len(cands) > 1:
        return {"ok": True, "multiple": True,
                "candidates": [{"open_id": x["open_id"], "name": x["name"]} for x in cands]}
    else:
        c = cands[0]

    code = f"{secrets.randbelow(1000000):06d}"
    account_store.set_code(c["open_id"], code)
    sent = feishu_cli.send_code_message(c["open_id"], code, email=c.get("email", ""))
    if not sent["ok"]:
        raise HTTPException(status_code=502, detail=f"验证码发送失败：{sent.get('error', '')}")
    account_store.upsert_account(c["open_id"], c["name"], c.get("email", ""))
    return {"ok": True, "open_id": c["open_id"], "name": c["name"], "sent": True}


@router.post("/verify")
async def verify(req: VerifyReq):
    """校验验证码，成功则建立会话返回 token。"""
    open_id = (req.open_id or "").strip()
    if not open_id and req.name:
        res = feishu_cli.search_user(req.name.strip())
        if res["ok"] and len(res["candidates"]) == 1:
            open_id = res["candidates"][0]["open_id"]
    if not open_id:
        raise HTTPException(status_code=400, detail="缺少身份标识（open_id）")

    if not account_store.verify_code(open_id, (req.code or "").strip()):
        raise HTTPException(status_code=401, detail="验证码错误或已过期")

    token = account_store.create_session(open_id)
    account_store.touch_login(open_id)
    acct = account_store.get_account(open_id)
    display = acct["display_name"] if acct else open_id
    return {"ok": True, "token": token,
            "account": {"open_id": open_id, "display_name": display}}


@router.post("/logout")
async def logout(
    authorization: str | None = Header(default=None),
    x_session: str | None = Header(default=None),
):
    """登出：删除当前 token 对应会话。未登录也安全（幂等）。"""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_session:
        token = x_session.strip()
    if token:
        account_store.delete_session(token)
    return {"ok": True}


@router.get("/me")
async def me(account_id: str = Depends(get_current_account)):
    acct = account_store.get_account(account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="账号不存在")
    return {"open_id": acct["open_id"], "display_name": acct["display_name"],
            "email": acct.get("email", "")}
