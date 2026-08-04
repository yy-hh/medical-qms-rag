"""lark-cli 子进程封装：联系人搜索（登录核对）+ 发消息（送验证码）。

设计原则：**永不抛异常**——所有失败都归一化为 {"ok": False, "error": ...}，
由调用方（auth.py）决定给前端什么 HTTP 状态。lark-cli 在 PATH 上，可用环境变量
LARK_CLI_BIN 覆盖二进制路径。
"""
import os
import json
import time
import subprocess
import logging
import urllib.request

from app.core.config import settings

logger = logging.getLogger(__name__)

LARK_CLI = os.environ.get("LARK_CLI_BIN", "lark-cli")

# tenant_access_token 缓存（官方通知机器人）
_tat = {"token": "", "expires_at": 0.0}


def _http_json(url: str, payload: dict, headers: dict, timeout: int = 15) -> dict:
    """POST JSON，返回解析后的 dict；失败返回 {"code": -1, "msg": ...}。"""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"code": -1, "msg": str(e)}


def _notify_token() -> str | None:
    """取官方通知机器人的 tenant_access_token（带缓存）。未配置则返回 None。"""
    if not (settings.notify_app_id and settings.notify_app_secret):
        return None
    if _tat["token"] and time.time() < _tat["expires_at"]:
        return _tat["token"]
    url = f"{settings.lark_domain}/open-apis/auth/v3/tenant_access_token/internal"
    r = _http_json(url, {"app_id": settings.notify_app_id,
                         "app_secret": settings.notify_app_secret}, {})
    if r.get("code") == 0 and r.get("tenant_access_token"):
        _tat["token"] = r["tenant_access_token"]
        _tat["expires_at"] = time.time() + max(60, r.get("expire", 7200) - 120)
        return _tat["token"]
    logger.warning("通知机器人取 token 失败: %s", r)
    return None


def _send_via_notify_bot(email: str, text: str) -> dict:
    """用官方通知机器人（tenant token）按【邮箱】发文本私信。
    按邮箱而非 open_id：open_id 是分 app 的，通知机器人与主 app 不是同一个，
    open_id 会报 99992361 'open_id cross app'；邮箱是租户内跨 app 通用标识。"""
    token = _notify_token()
    if not token:
        return {"ok": False, "error": "notify bot 未配置或取 token 失败", "code": None}
    if not email:
        return {"ok": False, "error": "该用户无企业邮箱，通知机器人无法按邮箱投递", "code": None}
    url = f"{settings.lark_domain}/open-apis/im/v1/messages?receive_id_type=email"
    payload = {"receive_id": email, "msg_type": "text",
               "content": json.dumps({"text": text}, ensure_ascii=False)}
    r = _http_json(url, payload, {"Authorization": f"Bearer {token}"})
    if r.get("code") == 0:
        return {"ok": True}
    return {"ok": False, "error": r.get("msg") or "发送失败", "code": r.get("code")}


def _run(args: list[str], timeout: int = 30) -> dict:
    """跑 lark-cli 并解析 stdout JSON。失败一律返回 {"ok": False, "error": ...}。"""
    try:
        p = subprocess.run(
            [LARK_CLI, *args],
            capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError:
        return {"ok": False, "error": f"lark-cli 未安装或不在 PATH（{LARK_CLI}）"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "lark-cli 调用超时"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if not (p.stdout or "").strip():
        return {"ok": False, "error": (p.stderr or "无输出").strip()[:500]}
    try:
        data = json.loads(p.stdout)
    except Exception:
        return {"ok": False, "error": "lark-cli 输出非 JSON", "raw": p.stdout[:500]}
    return data if isinstance(data, dict) else {"ok": True, "data": data}


def search_user(query: str) -> dict:
    """按姓名/邮箱搜「聊过天」的联系人（user 身份）。

    返回 {"ok": True, "candidates": [{open_id, name, email}, ...]}，
    或 {"ok": False, "error": ...}（含 user token 缺失的情况）。
    """
    res = _run([
        "contact", "+search-user",
        "--query", query,
        "--has-chatted",
        "--as", "user",
    ])
    if not res.get("ok"):
        err = res.get("error")
        if isinstance(err, dict):
            subtype = err.get("subtype") or ""
            if subtype == "token_missing" or "need_user_authorization" in str(err.get("message", "")):
                return {"ok": False, "error": "联系人搜索未授权：请管理员先运行 lark-cli auth login"}
            err = err.get("message") or subtype or "联系人搜索失败"
        return {"ok": False, "error": err or "联系人搜索失败"}
    users = (res.get("data") or {}).get("users") or []
    candidates = []
    for u in users:
        oid = u.get("open_id")
        if not oid:
            continue
        candidates.append({
            "open_id": oid,
            "name": u.get("localized_name") or u.get("name") or oid,
            "email": u.get("enterprise_email") or u.get("email") or "",
        })
    return {"ok": True, "candidates": candidates}


def _send_once(open_id: str, text: str, identity: str) -> dict:
    res = _run([
        "im", "+messages-send",
        "--user-id", open_id,
        "--text", text,
        "--as", identity,
    ])
    if res.get("ok"):
        return {"ok": True}
    err = res.get("error")
    code = None
    if isinstance(err, dict):
        code = err.get("code")
        err = err.get("message") or str(err)
    return {"ok": False, "error": err or "发送失败", "code": code}


def send_code_message(open_id: str, code: str, email: str = "") -> dict:
    """发验证码私信。优先用企业官方通知机器人按邮箱投递（对全员可用）；未配置/无邮箱/
    失败时，回退到 lark-cli 的 bot→user 双重发送（按 open_id）。"""
    text = f"【医械注册助手】您的登录验证码：{code}，5 分钟内有效。请勿泄露。"

    # 1. 首选：企业官方通知机器人按邮箱发（对全员可用，绕开 bot-availability 与 cross-app open_id）
    if settings.notify_app_id and settings.notify_app_secret and email:
        r = _send_via_notify_bot(email, text)
        if r["ok"]:
            return {"ok": True}
        logger.warning("通知机器人发送失败，回退 lark-cli: %s", r.get("error"))

    # 2. 回退：lark-cli bot 身份（对方已加机器人时成立）
    bot_res = _send_once(open_id, text, "bot")
    if bot_res["ok"]:
        return {"ok": True}

    # 3. 回退：属主 user 身份代发（属主与对方聊过时成立）
    user_res = _send_once(open_id, text, "user")
    if user_res["ok"]:
        return {"ok": True}

    codes = {bot_res.get("code"), user_res.get("code")}
    if 230013 in codes:
        return {"ok": False, "error": (
            "无法向该用户发送验证码：机器人对其不可用，且你与其在飞书上尚无会话。"
            "请先在飞书里给该用户发一条消息（建立会话）后重试，或让其先添加本机器人。"
        )}
    return {"ok": False, "error": user_res.get("error") or bot_res.get("error") or "验证码发送失败"}
