import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from typing import Optional

from app.core.qms_framework import get_document_by_id, get_framework as build_framework
from app.api.company import load_profile
from app.api.deps import get_shared_account
from app.core.rag_engine import get_engine
from app.core.config import settings
from app.core.docx_export import markdown_to_docx


def _retrieve_refs(engine, doc: dict, top_k: int = 4) -> tuple[str, list[dict]]:
    """根据文件节点的 refs，从知识库检索真实法规条款，返回 (上下文文本, 来源列表)。"""
    refs = doc.get("refs") or []
    if not refs:
        return "", []
    query = doc["name"] + " " + doc.get("desc", "") + " " + "、".join(doc.get("standards", []))
    parts, sources, seen = [], [], set()
    for ref in refs:
        collection = ref.get("collection")
        try:
            hits = engine.retrieve(query, top_k, collection)
        except Exception:
            hits = []
        match = ref.get("match", "")
        for s in hits:
            if match and match not in s.doc_name:
                continue
            key = (s.doc_name, s.chunk_index)
            if key in seen:
                continue
            seen.add(key)
            parts.append(f"【{s.doc_name}】\n{s.content}")
            sources.append({"doc_name": s.doc_name, "page": s.page, "score": s.score})
            if len(parts) >= 6:
                break
    return "\n\n---\n\n".join(parts), sources


def _extract_outline_and_gist(content: str, max_chars: int = 1800) -> str:
    """从已生成文件的 markdown 抽"标题结构 + 关键段"，控制长度，供作依赖上下文（不塞全文）。"""
    if not content:
        return ""
    lines = content.split("\n")
    out = []
    total = 0
    para_buf = []
    def flush_para():
        nonlocal total
        if para_buf:
            txt = " ".join(para_buf).strip()
            if txt and total < max_chars:
                seg = txt[:200]
                out.append(seg)
                total += len(seg)
            para_buf.clear()
    for ln in lines:
        s = ln.strip()
        if s.startswith("#"):          # 标题：保留层级
            flush_para()
            if total < max_chars:
                out.append(s)
                total += len(s)
        elif s.startswith("|") or s.startswith("---"):
            continue                   # 跳过表格/分隔线
        elif s:
            para_buf.append(s)
        else:
            flush_para()
        if total >= max_chars:
            break
    flush_para()
    return "\n".join(out)


def _build_dep_context(account_id, product_name, doc: dict) -> str:
    """遍历 doc 的 depends_docs，取已保存依赖文件的"标题结构+关键段"拼成上下文；未生成的跳过。"""
    from app.core import doc_store
    deps = doc.get("depends_docs") or []
    if not deps or not product_name:
        return ""
    parts = []
    for dep_id in deps:
        rec = doc_store.get_doc_by_doc_id(account_id, product_name, dep_id)
        if not rec or not rec.get("content"):
            continue
        gist = _extract_outline_and_gist(rec["content"])
        if gist:
            parts.append(f"【{rec['doc_name']}】\n{gist}")
    return "\n\n---\n\n".join(parts)


router = APIRouter(prefix="/api/generate", tags=["generate"])

# 全文完成信号：模型写完整篇后输出此标记。HTML 注释形式，marked 渲染后浏览器不显示，
# 后端据此判断是否还需续写（不能只靠 Poe 的 finish_reason —— 实测它常返回 "stop" 却内容未完）。
DOC_END_MARKER = "<!--DOC_END-->"

# 生成专用线程池：流式生成把同步迭代器的 next() 放到这里跑。独立且较大，
# 即使个别请求卡在 Poe 读取上，也不会耗尽默认线程池而拖垮整个服务。
_GEN_POOL = ThreadPoolExecutor(max_workers=64, thread_name_prefix="gen")


class GenerateRequest(BaseModel):
    doc_id: Optional[str] = None
    # 按全流程对照表序号生成（无预置 doc_id 的"企业自产文档"走这条）
    seq: Optional[int] = None
    extra_context: Optional[str] = None
    # 分章节生成：指定则只生成该章节（长文档如质量手册逐章生成，避免单次过慢/超时）
    section: Optional[str] = None
    # 该章在整篇大纲中的上下文（章节列表），让单章生成时风格、编号连贯
    outline: Optional[list[str]] = None
    # True=生成"质量体系模板"(带公司、不带具体产品，走占位符)；False=生成"某产品注册申报实例"(带当前产品信息)
    as_template: bool = False


def _doc_from_checklist_seq(seq: int) -> dict | None:
    """把 checklist 项构造成生成所需的 doc 结构（用于没有预置 doc_id 的企业自产文档）。"""
    from app.core.registration_checklist import get_checklist_item, is_genable
    it = get_checklist_item(seq)
    if not it or not is_genable(it):
        return None
    if it.get("doc_id"):
        d = get_document_by_id(it["doc_id"])
        if d:
            return d
    # 合成 doc：用对照表项自身信息
    return {
        "id": f"SEQ-{seq}",
        "name": (it["output"].split("；")[0].split("&")[0]).strip(),
        "type": "注册文档",
        "desc": f"{it['activity']}（{it['sub']}）。法规依据：{it['basis']} {it['clause']}。{it.get('note','')}",
        "standards": [it["basis"]],
        "refs": [],
    }


class OutlineRequest(BaseModel):
    doc_id: Optional[str] = None
    seq: Optional[int] = None


def _build_prompt(doc: dict, profile: dict, extra_context: str = "", ref_context: str = "",
                  section: str = "", outline: Optional[list[str]] = None, dep_context: str = "") -> str:
    company = profile.get("company_name") or "[公司名称]"
    product = profile.get("product_name") or "[产品名称]"
    classes = "、".join(profile.get("device_class") or ["二类", "三类"])
    markets = "、".join(profile.get("markets") or ["NMPA", "CE", "FDA"])
    intended_use = profile.get("intended_use") or "（待填写）"
    target_users = profile.get("target_users") or "（待填写）"
    standards = "、".join(doc.get("standards") or [])
    description = doc.get("desc") or doc.get("description") or ""

    # 注册产品信息：只把填了的字段拼进去，让生成内容贴合具体产品
    prod_fields = [
        ("产品描述", profile.get("product_description")),
        ("核心功能", profile.get("core_functions")),
        ("AI类型", profile.get("ai_type")),
        ("算法/模型", profile.get("algorithm")),
        ("输入数据", profile.get("input_data")),
        ("输出结果", profile.get("output_result")),
        ("适应症/临床场景", profile.get("clinical_indication")),
        ("运行环境", profile.get("operating_env")),
        ("数据来源", profile.get("data_source")),
        ("关键性能指标", profile.get("key_metrics")),
        ("主要第三方组件(SOUP)", profile.get("soup_list")),
    ]
    prod_lines = "\n".join(f"- {label}：{val}" for label, val in prod_fields if (val or "").strip())
    product_block = f"\n## 注册产品信息（请据此生成贴合本产品的内容，不要泛泛而谈）\n{prod_lines}\n" if prod_lines else ""

    # 公司级信息：地址/联系方式/经营范围/质量体系范围（填了才拼，供质量手册等公司级文件用真实信息）
    company_extra = [
        ("注册地址", profile.get("company_address")),
        ("联系方式", profile.get("contact")),
        ("经营范围", profile.get("business_scope")),
        ("质量管理体系范围", profile.get("qms_scope")),
    ]
    company_extra_lines = "".join(
        f"- {label}：{val}\n" for label, val in company_extra if (val or "").strip())

    base_info = f"""## 企业信息
- 企业名称：{company}
{company_extra_lines}- 产品名称：{product}
- 产品类型：医疗器械软件（SaMD）
- 注册类别：{classes}
- 目标市场：{markets}
- 预期用途：{intended_use}
- 目标用户：{target_users}
{product_block}
## 文件要求
- 文件名称：{doc['name']}
- 文件类型：{doc.get('type', '档案汇编')}
- 适用标准：{standards}
- 文件说明：{description}

{f"## 检索到的法规/标准依据（请据此生成，并在文中引用对应文件名）{chr(10)}{ref_context}{chr(10)}" if ref_context else ""}{f"## 已生成的关联文件内容（本文件需与之保持一致、正确引用其内容/编号，勿照抄）{chr(10)}{dep_context}{chr(10)}" if dep_context else ""}{f"## 补充说明{chr(10)}{extra_context}" if extra_context else ""}"""

    common_rules = f"""1. 内容必须符合上述标准的具体条款要求
2. 结合 SaMD 软件产品特点，内容具体实用，避免泛泛而谈
3. 在需要企业填写的位置使用【{company}】、【产品名称】、【版本号】、【日期】等占位符
4. 格式：标题使用 Markdown # ## ###，表格使用 Markdown 表格语法
5. 凡涉及图形化表达——流程图、组织架构图、**文件体系层次结构图/分级结构图**、框图、时序/状态图、树状结构等，一律用 ```mermaid 代码块表达（flowchart/graph TD、sequenceDiagram、stateDiagram 等）。
   - **严禁用以下任何方式模拟图形**：ASCII 字符、竖线 |、方框字符 ┌└│─├、空格/居中排版拼框、或用 Markdown 表格来画"框图/层次图/结构图"。这些都极丑且无法排版。
   - 例：文件体系"第一层质量手册→第二层程序文件→第三层作业指导书→第四层记录"这种分级结构，必须写成 `flowchart TD; A["第一层 质量手册（体系纲领）"] --> B["第二层 程序文件"] --> C["第三层 作业指导书/技术文件"] --> D["第四层 记录与表单"]`，绝不能用表格或方框字符拼。
   - mermaid 节点文字用简洁中文短语，含括号/冒号等特殊字符时须用双引号包裹如 A["文字（说明）"]，避免语法错误。
   - 仅**纯数据/条目**（如指标值、清单、对照）才用 Markdown 表格；凡是"有层级、有流向、有框和连线"的，一律 mermaid。
6. 不得中途省略、不得用"（略）""以下章节类似"等占位省略
7. 内容真正写完后，在最后单独一行输出结束标记：{DOC_END_MARKER}（完成信号，务必输出）"""

    # 分章节模式：只生成指定章节，并告知全篇大纲以保持连贯
    if section:
        outline_block = ""
        if outline:
            outline_block = "## 全篇大纲（供参考，保持编号与风格一致，本次只写下面指定章节）\n" + \
                "\n".join(f"- {s}" for s in outline) + "\n\n"
        return f"""请为以下企业生成「{doc['name']}」中的【{section}】这一章节的完整内容。

{base_info}

{outline_block}## 本次任务
只生成章节「{section}」的完整内容，不要生成其他章节、不要写文档封面/页眉表格（除非本章就是封面章）。
直接从该章节标题开始写，内容要详尽、可直接使用。

## 生成要求
{common_rules}

请直接输出该章节内容，不要添加额外说明。"""

    # 整篇模式（短文档，如程序文件/记录表单）
    return f"""请为以下企业生成「{doc['name']}」的完整文件模板。

{base_info}

## 生成要求
{common_rules}
7. 程序文件需包含：目的、范围、职责、定义、程序内容、相关文件、记录
8. 记录表单需包含完整的字段设计和填写说明

请直接生成文件内容，不要添加额外说明。"""


GENERATE_SYSTEM = """你是一位拥有 15 年经验的医疗器械 QMS 咨询师，专精于 SaMD（医疗器械软件）的质量管理体系建设。
你熟悉 ISO 13485、IEC 62304、ISO 14971、IEC 62366、YY/T 0664、YY/T 1833 等核心标准，
以及中国 NMPA、欧盟 CE/MDR、美国 FDA 的注册合规要求。

生成的文件应当：
- 专业、完整、可直接使用（填入公司具体信息后即可执行）
- 覆盖标准要求的所有关键要素
- 语言准确、条款清晰、职责明确
- 中文撰写，专业术语准确"""


@router.post("/stream")
async def generate_document_stream(request: GenerateRequest,
                                   account_id: str = Depends(get_shared_account)):
    doc = None
    if request.doc_id:
        doc = get_document_by_id(request.doc_id)
    if not doc and request.seq is not None:
        doc = _doc_from_checklist_seq(request.seq)
    if not doc:
        raise HTTPException(status_code=404, detail="未找到可生成的文档")

    full_profile = load_profile(account_id)
    engine = get_engine()
    ref_context, ref_sources = _retrieve_refs(engine, doc)
    if request.as_template:
        # 质量体系模板：带公司信息（名称/地址/经营范围/体系范围）、不带具体产品（产品字段走占位符），不注入产品依赖
        from app.api.company import COMPANY_FIELDS
        profile = {f: full_profile.get(f, "") for f in COMPANY_FIELDS}
        dep_context = ""
    else:
        # 产品实例：带当前产品信息 + 依赖上下文
        profile = full_profile
        dep_context = _build_dep_context(account_id, profile.get("product_name") or "", doc)
    user_prompt = _build_prompt(
        doc, profile, request.extra_context or "", ref_context,
        section=request.section or "", outline=request.outline, dep_context=dep_context,
    )

    # 不传 thinking：Poe 兼容端点带 thinking 会导致流式 ~30s 后 Connection error（见 rag_engine._extra_body）
    extra_body = {}

    async def event_gen():
        yield f"data: {json.dumps({'type': 'meta', 'doc_id': doc['id'], 'doc_name': doc['name'], 'sources': ref_sources}, ensure_ascii=False)}\n\n"

        loop = asyncio.get_event_loop()
        _END = object()

        # 长文档单轮装不下，且 Poe 的 finish_reason 常返回 "stop" 却内容未完，不可靠。
        # 改用「结束标记 DOC_END_MARKER」判断是否真正写完：未见标记就回灌续写。
        # 单轮 token 取舍：opus-4-6 名义最大输出 ~32K，但实测 max_tokens=32000 时单条流要 ~285s，
        # 会被上游 Poe 代理掐断（incomplete chunked read）。16384 约 ~200s，留余量避开断连点，
        # 且本轮已加断连容错（中途断开会把已生成内容回灌续写接上），即使偶发断连也能恢复。
        MAX_TOKENS_PER_ROUND = 16384
        MAX_ROUNDS = 8
        # 总字数硬上限：防止 SDD 等可无限展开的文档续写失控（曾出现 22 万字）。
        # 超过即停止续写，保证单份文档体量合理、耗时可控。
        MAX_TOTAL_CHARS = 80000

        messages = [
            {"role": "system", "content": GENERATE_SYSTEM},
            {"role": "user", "content": user_prompt},
        ]

        def _open_stream(msgs):
            # 建立 Poe 流式连接会阻塞直到首响应，必须放到 executor，
            # 否则会卡住整个 asyncio 事件循环（导致 /api/health 等全部挂起）。
            # 用 curl 子进程流式（curl_chat_stream）而非 openai/httpx：本机 httpx 连 Poe
            # 前置 Cloudflare 时 HTTP/2 握手时好时坏，curl --http2 却 100% 稳定。
            # --max-time 300：单轮最长 5 分钟，超时 curl 退出、上层按断流续写接力。
            from app.core.rag_engine import curl_chat_stream
            return curl_chat_stream(
                api_key=settings.api_key or settings.anthropic_api_key,
                base_url=settings.api_base_url,
                model=settings.claude_model,
                messages=msgs,
                max_tokens=MAX_TOKENS_PER_ROUND,
                connect_timeout=15,
                max_time=300,
            )

        full_text = ""          # 累计已发给前端的正文（不含结束标记）
        errored = False
        completed = False
        # 尾部缓冲：结束标记可能跨多个 chunk，先扣住可能是标记前缀的尾巴再决定是否下发
        tail = ""

        for round_idx in range(MAX_ROUNDS):
            try:
                # wait_for 兜底：建连 + 首响应最多等 100s，超时即放弃本轮，避免无限挂
                gen = await asyncio.wait_for(
                    loop.run_in_executor(_GEN_POOL, _open_stream, messages), timeout=100)
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': '生成超时或失败：' + str(e)}, ensure_ascii=False)}\n\n"
                errored = True
                break

            it = iter(gen)
            round_chars = 0
            stream_broke = False
            while True:
                try:
                    # 用 sentinel 避免 StopIteration 跨 run_in_executor 边界——
                    # asyncio 无法把 StopIteration 设入 Future，否则 await 会永久挂起。
                    # wait_for 兜底：单个 chunk 最多等 100s，超时按断流处理（已有内容则续写接力）。
                    chunk = await asyncio.wait_for(
                        loop.run_in_executor(_GEN_POOL, next, it, _END), timeout=100)
                    if chunk is _END:
                        break
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    piece = getattr(delta, "content", None)
                    if not piece:
                        continue
                    round_chars += len(piece)
                    tail += piece

                    # 命中结束标记：发出标记前的内容后收尾
                    if DOC_END_MARKER in tail:
                        before = tail.split(DOC_END_MARKER, 1)[0]
                        if before:
                            full_text += before
                            yield f"data: {json.dumps({'type': 'delta', 'content': before}, ensure_ascii=False)}\n\n"
                        tail = ""
                        completed = True
                        break

                    # 安全下发：保留可能是标记前缀的尾巴（最长 len(marker)-1 字符），其余发出
                    keep = len(DOC_END_MARKER) - 1
                    if len(tail) > keep:
                        emit = tail[:-keep]
                        tail = tail[-keep:]
                        full_text += emit
                        yield f"data: {json.dumps({'type': 'delta', 'content': emit}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    # 上游中途断连：若本轮已产出内容，不报错终止，转入续写接力（容错）；
                    # 若一个字都没拿到才算真失败。
                    if round_chars == 0 and not full_text:
                        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
                        errored = True
                    else:
                        stream_broke = True
                    break

            if errored or completed:
                break

            # 本轮一个字都没出且未中断 —— 视为异常，停止避免空转
            if round_chars == 0 and not stream_broke:
                break

            # 总字数达到硬上限 —— 停止续写，防止失控
            if len(full_text) >= MAX_TOTAL_CHARS:
                break

            # 还没写完 → 回灌已生成内容，要求无缝续写
            if round_idx < MAX_ROUNDS - 1:
                # 续写前先把扣住的尾巴并入上下文（但不下发，避免它其实是半截标记）
                carry = full_text + tail
                yield f"data: {json.dumps({'type': 'meta', 'continuing': True, 'round': round_idx + 1}, ensure_ascii=False)}\n\n"
                messages = [
                    {"role": "system", "content": GENERATE_SYSTEM},
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": carry},
                    {"role": "user", "content": f"请从上次中断处继续，无缝接着写，不要重复已写内容、不要重述已写标题、不要加任何过渡说明，直接续写剩余章节直至全文完成。全文写完后在最后单独一行输出结束标记：{DOC_END_MARKER}"},
                ]

        # 收尾：把残留尾巴（非标记部分）补发出去
        if not errored:
            leftover = tail.replace(DOC_END_MARKER, "")
            if leftover:
                yield f"data: {json.dumps({'type': 'delta', 'content': leftover}, ensure_ascii=False)}\n\n"
            if not completed:
                yield f"data: {json.dumps({'type': 'meta', 'truncated': True, 'message': '已达续写上限，文档可能仍不完整，可点击重新生成或缩小范围'}, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


OUTLINE_SYSTEM = """你是医疗器械 QMS 文档架构师。只输出该文件应包含的章节标题列表，不要输出正文。"""


@router.post("/outline")
async def generate_outline(request: OutlineRequest,
                           account_id: str = Depends(get_shared_account)):
    """为某个文件生成章节大纲（章节标题列表），供前端分章节逐章生成。单轮小输出，快。"""
    doc = None
    if request.doc_id:
        doc = get_document_by_id(request.doc_id)
    if not doc and request.seq is not None:
        doc = _doc_from_checklist_seq(request.seq)
    if not doc:
        raise HTTPException(status_code=404, detail="未找到可生成的文档")

    standards = "、".join(doc.get("standards") or [])
    desc = doc.get("desc") or doc.get("description") or ""
    profile = load_profile(account_id)
    pctx_fields = [
        ("产品名称", profile.get("product_name")),
        ("核心功能", profile.get("core_functions")),
        ("AI类型", profile.get("ai_type")),
        ("适应症/临床场景", profile.get("clinical_indication")),
    ]
    pctx = "；".join(f"{k}：{v}" for k, v in pctx_fields if (v or "").strip())
    pctx_line = f"\n产品背景：{pctx}" if pctx else ""
    prompt = f"""请为医疗器械软件（SaMD）企业的「{doc['name']}」设计章节大纲。
文件说明：{desc}
适用标准：{standards}{pctx_line}

要求：
- 输出该文件应包含的一级章节标题（如"第一章 ××"或"1. ××"），覆盖标准要求的关键要素
- 章节数量控制在 8-12 章，每章可包含多个小节，不要拆得过细（不要超过 12 章）
- 严格只输出一个 JSON 数组，元素是字符串章节标题，不要任何额外文字、不要 markdown 代码块
示例：["第一章 目的与范围", "第二章 ……"]"""

    engine = get_engine()
    loop = asyncio.get_event_loop()

    def _call():
        return engine.llm.chat.completions.create(
            model=settings.claude_model,
            max_tokens=2048,
            messages=[
                {"role": "system", "content": OUTLINE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
        )

    try:
        resp = await loop.run_in_executor(_GEN_POOL, _call)
        content = resp.choices[0].message.content or ""
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"大纲生成失败：{e}")

    # 解析 JSON 数组（容错：可能被包在 ```json 代码块或有多余文字里）
    sections = _parse_outline(content)
    if not sections:
        raise HTTPException(status_code=502, detail="大纲解析失败，请重试")

    return {"doc_id": doc["id"], "doc_name": doc["name"], "sections": sections}


def _parse_outline(text: str) -> list[str]:
    text = text.strip()
    # 1) 正常情况：完整 JSON 数组（可能被 ```json 包裹）
    m = re.search(r"\[.*\]", text, re.S)
    if m:
        try:
            arr = json.loads(m.group(0))
            out = [str(x).strip() for x in arr if str(x).strip()]
            if out:
                return out
        except Exception:
            pass
    # 2) JSON 被 max_tokens 截断（缺尾部 ]）：直接抽取所有双引号字符串元素，丢弃最后可能不完整的一个
    quoted = re.findall(r'"((?:[^"\\]|\\.)*)"', text)
    if quoted:
        items = [q.strip() for q in quoted if q.strip()]
        # 若原文末尾不是引号闭合（被截断），最后一个元素可能不完整，但 findall 只匹配成对引号，安全
        if items:
            return items
    # 3) 兜底：按行提取看起来像标题的行
    lines = [l.strip().lstrip("-*0123456789.、 ").strip() for l in text.splitlines()]
    return [l for l in lines if l][:15]


class ExportRequest(BaseModel):
    doc_id: Optional[str] = None
    doc_name: Optional[str] = None
    content: str          # 前端已渲染的完整 Markdown 全文


@router.post("/export")
async def export_document(request: ExportRequest):
    """把生成的 Markdown 全文导出为 .docx 下载。"""
    if not (request.content or "").strip():
        raise HTTPException(status_code=400, detail="内容为空，无法导出")

    name = request.doc_name or "生成文档"
    if not request.doc_name and request.doc_id:
        doc = get_document_by_id(request.doc_id)
        if doc:
            name = doc["name"]

    try:
        data = markdown_to_docx(request.content, title=name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败：{e}")

    filename = f"{name}.docx"
    # RFC 5987：中文文件名用 filename* 编码，避免 latin-1 报错
    disposition = f"attachment; filename=\"document.docx\"; filename*=UTF-8''{quote(filename)}"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": disposition},
    )


@router.get("/framework")
async def get_framework():
    return build_framework()
