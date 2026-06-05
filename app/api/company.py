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
    # 注册产品信息（SaMD 文件生成时注入，让内容贴合具体产品）
    "core_functions": "",        # 核心功能（如：病灶检测、测量、分割、辅助诊断）
    "ai_type": "",               # AI 类型：辅助决策 / 非辅助决策（检测/测量/分割）/ 不含AI
    "algorithm": "",             # 算法/模型（如：CNN/U-Net/Transformer；是否用预训练大模型）
    "input_data": "",            # 输入数据（如：CT影像/超声图像/病理切片/结构化EHR）
    "output_result": "",         # 输出结果（如：阳性概率、标注框、测量值、分级建议）
    "clinical_indication": "",   # 适应症 / 临床应用场景
    "operating_env": "",         # 运行环境（云端SaaS/院内服务器/嵌入式；硬件/OS依赖）
    "data_source": "",           # 训练/测试数据来源（多中心、医院数、样本量、标注方式）
    "key_metrics": "",           # 关键性能指标（灵敏度/特异度/AUC 目标值）
    "soup_list": "",             # 主要第三方组件/SOUP（PyTorch、OpenCV、DICOM库等）
}


class CompanyProfile(BaseModel):
    company_name: str = ""
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
