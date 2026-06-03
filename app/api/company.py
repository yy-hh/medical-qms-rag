import json
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/company", tags=["company"])

PROFILE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "company_profile.json"

DEFAULT_PROFILE = {
    "company_name": "",
    "product_name": "",
    "device_class": ["II", "III"],
    "markets": ["NMPA", "CE", "FDA"],
    "product_description": "",
    "intended_use": "",
    "target_users": "",
}


class CompanyProfile(BaseModel):
    company_name: str = ""
    product_name: str = ""
    device_class: list[str] = ["II", "III"]
    markets: list[str] = ["NMPA", "CE", "FDA"]
    product_description: str = ""
    intended_use: str = ""
    target_users: str = ""


def load_profile() -> dict:
    if PROFILE_PATH.exists():
        try:
            return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return DEFAULT_PROFILE.copy()


def save_profile(profile: dict):
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("", response_model=CompanyProfile)
async def get_profile():
    return load_profile()


@router.post("", response_model=CompanyProfile)
async def update_profile(profile: CompanyProfile):
    data = profile.model_dump()
    save_profile(data)
    return data
