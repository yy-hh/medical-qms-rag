import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.core.qms_framework import get_document_by_id, QMS_PHASES, get_stats
from app.api.company import load_profile
from app.core.rag_engine import get_engine
from app.core.config import settings

router = APIRouter(prefix="/api/generate", tags=["generate"])


class GenerateRequest(BaseModel):
    doc_id: str
    extra_context: Optional[str] = None


def _build_prompt(doc: dict, profile: dict, extra_context: str = "") -> str:
    company = profile.get("company_name") or "[公司名称]"
    product = profile.get("product_name") or "[产品名称]"
    classes = "、".join(profile.get("device_class") or ["二类", "三类"])
    markets = "、".join(profile.get("markets") or ["NMPA", "CE", "FDA"])
    intended_use = profile.get("intended_use") or "（待填写）"
    target_users = profile.get("target_users") or "（待填写）"
    standards = "、".join(doc.get("standards") or [])

    prompt = f"""请为以下企业生成「{doc['name']}」的完整文件模板。

## 企业信息
- 企业名称：{company}
- 产品名称：{product}
- 产品类型：医疗器械软件（SaMD）
- 注册类别：{classes}
- 目标市场：{markets}
- 预期用途：{intended_use}
- 目标用户：{target_users}

## 文件要求
- 文件名称：{doc['name']}
- 文件类型：{doc['type']}
- 适用标准：{standards}
- 文件说明：{doc['description']}

{f"## 补充说明{chr(10)}{extra_context}" if extra_context else ""}

## 生成要求
1. 文件内容必须符合上述标准的具体条款要求
2. 结合 SaMD 软件产品特点，内容具体实用，避免泛泛而谈
3. 在需要企业填写的位置使用【{company}】、【产品名称】、【版本号】、【日期】等占位符
4. 文件格式：标题使用 Markdown # ## ###，表格使用 Markdown 表格语法
5. 程序文件需包含：目的、范围、职责、定义、程序内容、相关文件、记录
6. 记录表单需包含完整的字段设计和填写说明

请直接生成文件内容，不要添加额外说明。"""

    return prompt


GENERATE_SYSTEM = """你是一位拥有 15 年经验的医疗器械 QMS 咨询师，专精于 SaMD（医疗器械软件）的质量管理体系建设。
你熟悉 ISO 13485、IEC 62304、ISO 14971、IEC 62366、YY/T 0664、YY/T 1833 等核心标准，
以及中国 NMPA、欧盟 CE/MDR、美国 FDA 的注册合规要求。

生成的文件应当：
- 专业、完整、可直接使用（填入公司具体信息后即可执行）
- 覆盖标准要求的所有关键要素
- 语言准确、条款清晰、职责明确
- 中文撰写，专业术语准确"""


@router.post("/stream")
async def generate_document_stream(request: GenerateRequest):
    doc = get_document_by_id(request.doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"文档 {request.doc_id} 不在框架中")

    profile = load_profile()
    user_prompt = _build_prompt(doc, profile, request.extra_context or "")

    engine = get_engine()
    extra_body = {}
    if "opus-4" in settings.claude_model:
        extra_body["thinking"] = {"type": "enabled", "budget_tokens": 1024}

    async def event_gen():
        yield f"data: {json.dumps({'type': 'meta', 'doc_id': doc['id'], 'doc_name': doc['name']}, ensure_ascii=False)}\n\n"

        gen = engine.llm.chat.completions.create(
            model=settings.claude_model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": GENERATE_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
            extra_body=extra_body or None,
        )

        loop = asyncio.get_event_loop()
        it = iter(gen)
        while True:
            try:
                chunk = await loop.run_in_executor(None, next, it)
                delta = chunk.choices[0].delta
                if getattr(delta, "content", None):
                    yield f"data: {json.dumps({'type': 'delta', 'content': delta.content}, ensure_ascii=False)}\n\n"
            except StopIteration:
                break
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
                break

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/framework")
async def get_framework():
    return {"phases": QMS_PHASES, "stats": get_stats()}
