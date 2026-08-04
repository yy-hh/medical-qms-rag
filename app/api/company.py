import json
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_current_account

router = APIRouter(prefix="/api/company", tags=["company"])

ACCOUNTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "accounts"


def _profile_path(account_id: str) -> Path:
    """某账号的公司档案文件路径。"""
    return ACCOUNTS_DIR / account_id / "company_profile.json"

# 产品级字段（每个产品独立一份）
PRODUCT_FIELDS = [
    "product_name", "device_class", "markets", "product_description",
    "intended_use", "target_users", "core_functions", "ai_type", "algorithm",
    "input_data", "output_result", "clinical_indication", "operating_env",
    "data_source", "key_metrics", "soup_list",
]


def _empty_product(pid: str = None) -> dict:
    return {
        "id": pid or uuid.uuid4().hex[:8],
        "product_name": "",
        "device_class": ["II", "III"],
        "markets": ["NMPA", "CE", "FDA"],
        "product_description": "", "intended_use": "", "target_users": "",
        "core_functions": "", "ai_type": "", "algorithm": "", "input_data": "",
        "output_result": "", "clinical_indication": "", "operating_env": "",
        "data_source": "", "key_metrics": "", "soup_list": "",
    }


def _default_store() -> dict:
    p = _empty_product()
    return {"company_name": "", "products": [p], "current_product_id": p["id"]}


def _load_store(account_id: str) -> dict:
    """读取某账号的原始存储结构（{company_name, products[], current_product_id}）。
    自动把旧的单产品平铺结构迁移成多产品结构。"""
    path = _profile_path(account_id)
    if not path.exists():
        return _default_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _default_store()
    # 已是新结构
    if isinstance(data, dict) and "products" in data:
        if not data.get("products"):
            data = _default_store() | {"company_name": data.get("company_name", "")}
        if not data.get("current_product_id"):
            data["current_product_id"] = data["products"][0]["id"]
        return data
    # 旧单产品结构 → 迁移
    prod = _empty_product()
    for f in PRODUCT_FIELDS:
        if f in data:
            prod[f] = data[f]
    if not prod["product_name"]:
        prod["product_name"] = data.get("product_name", "") or "默认产品"
    return {"company_name": data.get("company_name", ""),
            "products": [prod], "current_product_id": prod["id"]}


def _save_store(account_id: str, store: dict):
    path = _profile_path(account_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def _current_product(store: dict) -> dict:
    pid = store.get("current_product_id")
    for p in store["products"]:
        if p["id"] == pid:
            return p
    return store["products"][0]


def load_profile(account_id: str) -> dict:
    """供生成/问答使用：把某账号的公司信息 + 当前选中产品字段合并到一层。"""
    store = _load_store(account_id)
    cur = _current_product(store)
    return {"company_name": store.get("company_name", ""), **cur,
            "current_product_id": store.get("current_product_id")}


def current_product_name(account_id: str) -> str:
    return _current_product(_load_store(account_id)).get("product_name", "")


# ── 数据模型 ────────────────────────────────────────────────────────────────

class Product(BaseModel):
    id: str = ""
    product_name: str = ""
    device_class: list[str] = ["II", "III"]
    markets: list[str] = ["NMPA", "CE", "FDA"]
    product_description: str = ""
    intended_use: str = ""
    target_users: str = ""
    core_functions: str = ""
    ai_type: str = ""
    algorithm: str = ""
    input_data: str = ""
    output_result: str = ""
    clinical_indication: str = ""
    operating_env: str = ""
    data_source: str = ""
    key_metrics: str = ""
    soup_list: str = ""


class CompanyStore(BaseModel):
    company_name: str = ""
    products: list[Product] = []
    current_product_id: str = ""


# ── 接口 ────────────────────────────────────────────────────────────────────

@router.get("")
async def get_company(account_id: str = Depends(get_current_account)):
    """完整公司+多产品结构（前端用）。"""
    return _load_store(account_id)


@router.get("/current")
async def get_current(account_id: str = Depends(get_current_account)):
    """当前选中产品的合并视图（公司信息+当前产品字段）。"""
    return load_profile(account_id)


@router.post("/company-name")
async def set_company_name(payload: dict, account_id: str = Depends(get_current_account)):
    store = _load_store(account_id)
    store["company_name"] = (payload.get("company_name") or "").strip()
    _save_store(account_id, store)
    return store


@router.post("/product")
async def upsert_product(product: Product, account_id: str = Depends(get_current_account)):
    """新增或更新产品（id 为空=新增）。"""
    store = _load_store(account_id)
    data = product.model_dump()
    if not data.get("id"):
        data["id"] = uuid.uuid4().hex[:8]
        store["products"].append(data)
        store["current_product_id"] = data["id"]   # 新增后自动设为当前
    else:
        for i, p in enumerate(store["products"]):
            if p["id"] == data["id"]:
                store["products"][i] = data
                break
        else:
            store["products"].append(data)
    _save_store(account_id, store)
    return store


@router.post("/current/{product_id}")
async def switch_current(product_id: str, account_id: str = Depends(get_current_account)):
    """切换当前选中产品。"""
    store = _load_store(account_id)
    if not any(p["id"] == product_id for p in store["products"]):
        raise HTTPException(status_code=404, detail="产品不存在")
    store["current_product_id"] = product_id
    _save_store(account_id, store)
    return store


@router.delete("/product/{product_id}")
async def delete_product(product_id: str, account_id: str = Depends(get_current_account)):
    store = _load_store(account_id)
    if len(store["products"]) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个产品")
    store["products"] = [p for p in store["products"] if p["id"] != product_id]
    if store["current_product_id"] == product_id:
        store["current_product_id"] = store["products"][0]["id"]
    _save_store(account_id, store)
    return store


# 兼容旧前端：POST / 仍可整体保存当前产品（把传入字段写回当前产品）
@router.post("")
async def update_profile_legacy(payload: dict, account_id: str = Depends(get_current_account)):
    store = _load_store(account_id)
    if "company_name" in payload:
        store["company_name"] = payload.get("company_name", "")
    cur = _current_product(store)
    for f in PRODUCT_FIELDS:
        if f in payload:
            cur[f] = payload[f]
    _save_store(account_id, store)
    return load_profile(account_id)
