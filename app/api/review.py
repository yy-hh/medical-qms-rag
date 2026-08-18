"""AI 模拟审查员（红队）· 体系整体审查。

让 LLM 扮演 NMPA/FDA 核查员，对【已生成的整套 QMS 文档】做整体体系审查，
输出结构化问题清单（对抗性问题/缺陷，带严重度+涉及条款+整改建议）。

两类检查：
- 结构化确定性检查（纯代码，秒出、零成本、零幻觉）：缺失文档 / depends_docs 断点 / 档案不完整。
- LLM 对抗检查（按 6 个注册阶段分批）：内容矛盾/含糊/不满足条款/缺关键要素。

审查对象是共享数据（DEFAULT_ACCOUNT 下的共享生成文档），端点用 get_shared_account。
"""
import asyncio
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.core import doc_store
from app.core.rag_engine import get_engine
from app.core.config import settings
from app.core.registration_checklist import CHECKLIST, STAGES, is_genable
from app.core.compliance_graph import by_stage
from app.core.qms_framework import DOSSIERS, get_document_by_id, get_all_documents, TAILORING
from app.api.company import current_product_name
from app.api.docs import TEMPLATE_NS
from app.api.generate import _extract_outline_and_gist, _GEN_POOL
from app.api.deps import get_shared_account

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/review", tags=["review"])

GIST_MAX = 1500          # 单份文档摘要压缩上限
MAX_DOCS_PER_STAGE = 12  # 单阶段喂 LLM 的文档数上限，超出仅列标题


class ReviewRequest(BaseModel):
    product_name: Optional[str] = None   # 传 "__template__" 审模板；空=当前选中产品


REVIEW_SYS = """你是一位极其严格、经验丰富的医疗器械（NMPA/FDA）注册质量管理体系核查员，
正在对一家医疗器械软件（SaMD）企业做飞行检查（体系核查）。你的职责是找出体系文件中的
真实缺陷，站在审查员视角提对抗性质询。

审查原则：
- 只基于我提供的文档摘要判断。摘要是"标题结构+关键段"的压缩版，若某要求在摘要中确实未见
  体现，可谨慎质疑（表述为"摘要中未见…，请核实原文是否覆盖"），但不要凭空编造文档没有的内容。
- 参考给出的"剪裁声明"：对 SaMD 明确不适用的条款（如洁净厂房、物料平衡）不要挑刺。
- 聚焦这几类问题：文件内容与法规要求不符 / 文件之间相互矛盾 / 表述含糊无法执行 /
  缺少该要求下的关键要素 / 应满足的审查要点在文档中无体现。
- 严重度定义：高=直接导致核查不通过或注册被拒的硬缺陷；中=需整改但不致命；低=完善性建议。

输出格式（严格遵守）：只输出一个 JSON 数组，数组元素为对象，字段：
- severity: "高" | "中" | "低"
- category: "矛盾" | "依据不足" | "缺失" | "其它"
- title: 一句话问题标题
- detail: 具体质询内容（像核查员发问）
- related_clause: 涉及的法规/标准条款（用我提供的 basis｜clause，无则空串）
- related_docs: 涉及的文档名数组
- suggestion: 整改建议
不要输出任何 JSON 数组以外的文字，不要用 markdown 代码块围栏。若本阶段无问题，输出 []。"""


# ── 审查对象解析 ──────────────────────────────────────────────────────────────

def _resolve_product(account_id: str, req_product: Optional[str]) -> str:
    if req_product:
        return req_product
    return current_product_name(account_id) or ""


def _generated_docid_set(account_id: str, product_name: str) -> set:
    """该产品（或模板）下已生成、且挂了 doc_id 的文档集合。"""
    rows = doc_store.list_docs(account_id, product_name=product_name)
    return {r["doc_id"] for r in rows if r.get("doc_id")}


# ── 结构化确定性检查（纯代码）─────────────────────────────────────────────────

def _structural_findings(account_id: str, product_name: str) -> list[dict]:
    generated = _generated_docid_set(account_id, product_name)
    findings: list[dict] = []
    n = 0

    # ① 缺失文档：CHECKLIST 中可由企业自产、且挂了 doc_id 的应产出，尚未生成
    for item in CHECKLIST:
        did = item.get("doc_id")
        if not did or not is_genable(item):
            continue
        if did not in generated:
            n += 1
            findings.append({
                "id": f"S-{n:03d}", "severity": "高", "category": "缺失",
                "title": f"应产出文档缺失：{item.get('output') or did}",
                "detail": f"注册流程「{item.get('activity','')}」要求产出「{item.get('output','')}」，"
                          f"但体系中尚未生成对应文档（{did}）。",
                "related_clause": f"{item.get('basis','')}｜{item.get('clause','')}".strip("｜"),
                "related_docs": [item.get("output") or did],
                "suggestion": "生成/补充该文档并纳入体系。",
                "source": "结构检查", "stage": item.get("stage", ""),
            })

    # ② depends_docs 断点：已生成文档所依赖的文件尚未生成
    for did in list(generated):
        doc = get_document_by_id(did)
        for dep in (doc or {}).get("depends_docs") or []:
            if dep not in generated:
                n += 1
                dep_doc = get_document_by_id(dep)
                dep_name = (dep_doc or {}).get("name") or dep
                findings.append({
                    "id": f"S-{n:03d}", "severity": "高", "category": "断点",
                    "title": f"依赖断点：{doc.get('name', did)} 依赖的《{dep_name}》未生成",
                    "detail": f"{doc.get('name', did)}（{did}）声明依赖 {dep}，但后者尚未生成，"
                              f"引用/一致性无法建立。",
                    "related_clause": "",
                    "related_docs": [doc.get("name", did), dep_name],
                    "suggestion": f"先生成依赖文档 {dep}，再确保引用一致。",
                    "source": "结构检查", "stage": "",
                })

    # ③ 档案不完整：DOSSIERS.compiles 里应汇编的文档尚未生成
    for ds in DOSSIERS:
        missing = [c for c in (ds.get("compiles") or []) if c not in generated]
        if missing:
            n += 1
            names = []
            for c in missing:
                cd = get_document_by_id(c)
                names.append((cd or {}).get("name") or c)
            findings.append({
                "id": f"S-{n:03d}", "severity": "中", "category": "缺失",
                "title": f"档案不完整：{ds.get('name', ds['id'])} 缺 {len(missing)} 份汇编文档",
                "detail": f"归档档案「{ds.get('name','')}」应汇编 {len(ds.get('compiles') or [])} 份文档，"
                          f"其中 {len(missing)} 份尚未生成：{', '.join(names)}。",
                "related_clause": "、".join(ds.get("standards") or []),
                "related_docs": [ds.get("name", ds["id"])],
                "suggestion": "补齐缺失文档后再汇编该档案。",
                "source": "结构检查", "stage": "",
            })

    return findings


# ── LLM 对抗检查（按阶段分批）─────────────────────────────────────────────────

def _stage_user_prompt(stage: dict, account_id: str, product_name: str) -> tuple[int, str]:
    """组装某阶段的审查 prompt。返回 (该阶段已生成文档数, prompt)。"""
    sg = by_stage(stage["key"])
    stage_docs = sg.get("documents", [])
    reqs = sg.get("requirements", [])

    # 该阶段应满足的审查要点
    req_lines = [f"- {r.get('basis','')}｜{r.get('clause','')}" for r in reqs] or ["（本阶段无登记的审查要点）"]

    # 该阶段应产出文档 → 已生成的取摘要，未生成的标缺失
    generated_ids = _generated_docid_set(account_id, product_name)
    doc_blocks, present = [], 0
    for d in stage_docs:
        did = d.get("doc_id")
        name = d.get("name") or did or "?"
        if did and did in generated_ids:
            row = doc_store.get_doc_by_doc_id(account_id, product_name, did)
            content = (row or {}).get("content") or ""
            if present >= MAX_DOCS_PER_STAGE:
                doc_blocks.append(f"### {name}（{did}）\n（已生成，因数量限制此处仅列标题）")
            else:
                gist = _extract_outline_and_gist(content, max_chars=GIST_MAX)
                doc_blocks.append(f"### {name}（{did}）\n{gist}")
            present += 1
        else:
            doc_blocks.append(f"### {name}（{did or '无编号'}）\n【该文档尚未生成——如属本阶段必需，属缺失】")

    tailoring = "\n".join(f"- {t['clause']}：{t['reason']}" for t in TAILORING[:8])

    prompt = f"""## 审查阶段
{stage['no']} {stage['name']}（{stage.get('goal','')}）

## 本阶段应满足的审查要点（法规/标准）
{chr(10).join(req_lines)}

## SaMD 剪裁声明（以下条款对纯软件不适用，勿据此挑刺）
{tailoring}

## 本阶段体系文档（摘要）
{chr(10).join(doc_blocks) if doc_blocks else '（本阶段无登记的应产出文档）'}

请以核查员视角，对照上述审查要点逐条审查这些文档，输出 JSON 数组问题清单（无问题输出 []）。"""
    return present, prompt


def _parse_json_array(text: str) -> list:
    """从 LLM 输出里稳健地抽出 JSON 数组。失败返回 []（不抛异常）。"""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if t.count("```") >= 2 else t.strip("`")
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
    i, j = t.find("["), t.rfind("]")
    if i == -1 or j == -1 or j < i:
        return []
    try:
        arr = json.loads(t[i:j + 1])
        return arr if isinstance(arr, list) else []
    except Exception:
        return []


def _normalize(arr: list, stage_key: str, start_no: int) -> list[dict]:
    out = []
    n = start_no
    for x in arr:
        if not isinstance(x, dict):
            continue
        n += 1
        rd = x.get("related_docs") or []
        if isinstance(rd, str):
            rd = [rd]
        out.append({
            "id": f"A-{stage_key}-{n:03d}",
            "severity": x.get("severity") if x.get("severity") in ("高", "中", "低") else "中",
            "category": x.get("category") or "其它",
            "title": (x.get("title") or "").strip() or "（未命名问题）",
            "detail": (x.get("detail") or "").strip(),
            "related_clause": (x.get("related_clause") or "").strip(),
            "related_docs": [str(d) for d in rd],
            "suggestion": (x.get("suggestion") or "").strip(),
            "source": "AI审查", "stage": stage_key,
        })
    return out


def _call_llm_json(prompt: str) -> list:
    engine = get_engine()
    resp = engine.llm.chat.completions.create(
        model=settings.claude_model,
        messages=[{"role": "system", "content": REVIEW_SYS},
                  {"role": "user", "content": prompt}],
        max_tokens=4096,
        temperature=0.2,
        stream=False,
        extra_body=engine._extra_body(),
    )
    return _parse_json_array(resp.choices[0].message.content or "")


# ── 端点 ──────────────────────────────────────────────────────────────────────

@router.post("/system/stream")
async def review_system_stream(req: ReviewRequest,
                               account_id: str = Depends(get_shared_account)):
    """SSE：meta → findings(结构检查秒发) → 每阶段 progress/findings → done → [DONE]"""
    product_name = _resolve_product(account_id, req.product_name)

    async def event_gen():
        label = "文件模板" if product_name == TEMPLATE_NS else (product_name or "（未选产品）")
        yield f"data: {json.dumps({'type':'meta','product':label}, ensure_ascii=False)}\n\n"

        total = 0
        # 1) 结构化确定性检查，秒发
        struct = _structural_findings(account_id, product_name)
        total += len(struct)
        yield f"data: {json.dumps({'type':'findings','stage':'结构检查','findings':struct}, ensure_ascii=False)}\n\n"

        # 2) 6 个阶段 LLM 对抗检查——并发提交（阶段间独立），谁先完成先下发，
        #    把总墙钟从 6×单批 压到 ≈1×单批（Poe opus 单批 ~60-70s）。
        loop = asyncio.get_event_loop()

        async def _run_stage(stage):
            present, prompt = _stage_user_prompt(stage, account_id, product_name)
            arr = await loop.run_in_executor(_GEN_POOL, _call_llm_json, prompt)
            return stage, _normalize(arr, stage["key"], 0)

        yield f"data: {json.dumps({'type':'progress','name':'并发审查 6 个注册阶段…'}, ensure_ascii=False)}\n\n"
        tasks = [asyncio.ensure_future(_run_stage(s)) for s in STAGES]
        for fut in asyncio.as_completed(tasks):
            try:
                stage, fs = await fut
                total += len(fs)
                yield f"data: {json.dumps({'type':'findings','stage':stage['name'],'findings':fs}, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.warning("阶段审查失败: %s", e)
                yield f"data: {json.dumps({'type':'error','message':str(e)[:200]}, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'type':'done','total':total}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/system")
async def review_system(product_name: Optional[str] = None,
                        account_id: str = Depends(get_shared_account)):
    """非流式一次性返回全量 findings（冒烟/将来 CAPA 抓全量）。"""
    pname = _resolve_product(account_id, product_name)
    findings = _structural_findings(account_id, pname)
    engine_ok = True
    for stage in STAGES:
        try:
            _present, prompt = _stage_user_prompt(stage, account_id, pname)
            findings += _normalize(_call_llm_json(prompt), stage["key"], 0)
        except Exception as e:
            engine_ok = False
            logger.warning("阶段 %s 审查失败: %s", stage["key"], e)
    label = "文件模板" if pname == TEMPLATE_NS else (pname or "")
    return {"product": label, "total": len(findings), "llm_ok": engine_ok, "findings": findings}
