"""批量补齐某产品缺失的 QMS 框架文件——独立进程内直接用 curl_chat_stream 生成并落库。

为什么不走服务 HTTP 接口：服务（uvicorn+asyncio+executor 线程池）里用 subprocess 调 curl
会偶发退出码 92（HTTP2 stream error），而独立 Python 进程里 curl_chat_stream 100% 稳定。
所以批量补文件绕开服务，在本脚本进程内生成 + doc_store.save_doc 落库。

用法：
    python scripts/batch_generate.py                  # 跑全部缺失（按 doc_id 严格判断）
    python scripts/batch_generate.py L2-001 L3-002    # 只跑指定 doc_id

每篇：
- 复用 generate.py 的 _build_prompt / _retrieve_refs（检索法规依据）。
- 长文档（LONG_DOC_IDS）先拉大纲分章节，每章一次 curl_chat_stream，未见结束标记则续写。
- 短文档整篇生成。
- 每章/整篇带重试（RETRY 次）：curl 失败或空内容则退避重试。
- 全文 doc_store.save_doc 落库（product_name 取当前 profile）。
"""
import sys
import time

from app.core.qms_framework import get_all_documents, get_document_by_id
from app.api.company import load_profile
from app.core.rag_engine import get_engine, curl_chat_stream
from app.core.config import settings
from app.core import doc_store
from app.core.account_store import DEFAULT_ACCOUNT
from app.api.generate import (
    _build_prompt, _retrieve_refs, _parse_outline, _build_dep_context,
    GENERATE_SYSTEM, OUTLINE_SYSTEM, DOC_END_MARKER,
)

ACCOUNT_ID = DEFAULT_ACCOUNT   # 归属账号，main() 可用 --account=<open_id> 覆盖

MAX_TOKENS_PER_ROUND = 16384
MAX_ROUNDS = 8
MAX_TOTAL_CHARS = 80000
RETRY = 8                       # 单次 curl 调用失败/空内容的重试次数（链路会偶发 HTTP2
                                # stream error 退出码 92，是网络抖动非稳定故障，多重试可扛过）
LONG_DOC_IDS = {"L1-001", "L4-001", "L4-003", "L4-004", "AI-001", "AI-002"}


def _api_key():
    return settings.api_key or settings.anthropic_api_key


def _stream_once(messages, max_tokens, max_time=300):
    """一次 curl 流式调用，累计返回文本。失败抛异常。"""
    txt = []
    for ch in curl_chat_stream(_api_key(), settings.api_base_url, settings.claude_model,
                               messages, max_tokens, connect_timeout=15, max_time=max_time):
        c = ch.choices[0].delta.content
        if c:
            txt.append(c)
    return "".join(txt)


def _stream_retry(messages, max_tokens, label=""):
    """带重试的单次流式。返回文本；全部重试失败抛异常。"""
    last = None
    for attempt in range(1, RETRY + 1):
        try:
            t = _stream_once(messages, max_tokens)
            if t.strip():
                return t
            last = "空内容"
        except Exception as e:
            last = str(e)[:80]
        if attempt < RETRY:
            wait = min(3 * attempt, 15)
            print(f"        重试 {attempt}/{RETRY}（{label}）：{last}，{wait}s 后重试")
            time.sleep(wait)
    raise RuntimeError(f"重试 {RETRY} 次仍失败：{last}")


def _generate_full(user_prompt):
    """整篇/单章生成：结束标记判定 + 未完续写。返回 full_text。"""
    messages = [
        {"role": "system", "content": GENERATE_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]
    full = ""
    for round_idx in range(MAX_ROUNDS):
        chunk_txt = _stream_retry(messages, MAX_TOKENS_PER_ROUND, label=f"round{round_idx+1}")
        if DOC_END_MARKER in chunk_txt:
            full += chunk_txt.split(DOC_END_MARKER, 1)[0]
            break
        full += chunk_txt
        if len(full) >= MAX_TOTAL_CHARS:
            break
        if round_idx < MAX_ROUNDS - 1:
            messages = [
                {"role": "system", "content": GENERATE_SYSTEM},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": full},
                {"role": "user", "content": f"请从上次中断处继续，无缝接着写，不要重复已写内容、不要重述已写标题、不要加任何过渡说明，直接续写剩余章节直至全文完成。全文写完后在最后单独一行输出结束标记：{DOC_END_MARKER}"},
            ]
    return full.strip()


def _gen_outline(doc, profile):
    standards = "、".join(doc.get("standards") or [])
    desc = doc.get("desc") or doc.get("description") or ""
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
    try:
        content = _stream_once(
            [{"role": "system", "content": OUTLINE_SYSTEM}, {"role": "user", "content": prompt}],
            2048, max_time=120)
    except Exception as e:
        print(f"      大纲失败：{str(e)[:60]}，降级整篇")
        return None
    return _parse_outline(content) or None


TEMPLATE_NS = "__template__"

def generate_one(engine, profile, doc, as_template=False):
    ref_context, _ = _retrieve_refs(engine, doc)
    dep_context = "" if as_template else _build_dep_context(ACCOUNT_ID, profile.get("product_name") or "", doc)
    if dep_context:
        print(f"      依赖上下文：{len(doc.get('depends_docs') or [])} 份关联文件")
    failed_sections = []

    if doc["id"] in LONG_DOC_IDS:
        sections = _gen_outline(doc, profile)
        if sections:
            print(f"      大纲 {len(sections)} 章")
            parts = []
            for i, sec in enumerate(sections, 1):
                print(f"      [{i}/{len(sections)}] {sec}")
                prompt = _build_prompt(doc, profile, "", ref_context, section=sec, outline=sections, dep_context=dep_context)
                try:
                    parts.append(_generate_full(prompt).strip())
                except Exception as e:
                    print(f"         ! 章节失败：{str(e)[:60]}")
                    failed_sections.append(sec)
            content = "\n\n".join(p for p in parts if p)
        else:
            content = _generate_full(_build_prompt(doc, profile, "", ref_context, dep_context=dep_context))
    else:
        content = _generate_full(_build_prompt(doc, profile, "", ref_context, dep_context=dep_context))

    content = content.strip()
    if not content:
        raise RuntimeError("生成内容为空")
    doc_store.save_doc(
        account_id=ACCOUNT_ID,
        doc_id=doc["id"], doc_name=doc["name"], content=content,
        product_name=(TEMPLATE_NS if as_template else profile.get("product_name", "")),
        company_name=profile.get("company_name", ""),
    )
    return len(content), failed_sections


def main():
    global ACCOUNT_ID
    from app.core.account_store import DEFAULT_ACCOUNT
    argv = sys.argv[1:]
    ACCOUNT_ID = DEFAULT_ACCOUNT
    as_template = False
    want_ids = []
    for a in argv:
        if a.startswith("--account="):
            ACCOUNT_ID = a.split("=", 1)[1]
        elif a == "--template":
            as_template = True
        else:
            want_ids.append(a)

    full_profile = load_profile(ACCOUNT_ID)
    if as_template:
        # 生成质量体系模板：带公司信息(名称/地址/经营范围/体系范围)、不带具体产品(走占位符)，存 __template__
        from app.api.company import COMPANY_FIELDS
        profile = {f: full_profile.get(f, "") for f in COMPANY_FIELDS}
        product = TEMPLATE_NS
        print(f"账号：{ACCOUNT_ID}　模式：质量体系模板(__template__) / {profile.get('company_name')}")
    else:
        profile = full_profile
        product = profile.get("product_name", "")
        print(f"账号：{ACCOUNT_ID}　当前产品：{product} / {profile.get('company_name')}")
        if not product:
            print("!! profile 未选中产品，已中止。")
            sys.exit(1)

    engine = get_engine()
    alldocs = get_all_documents()
    by_id = {d["id"]: d for d in alldocs}
    if want_ids:
        targets = [by_id[d] for d in want_ids if d in by_id]
    else:
        done = {r["doc_id"] for r in doc_store.list_docs(ACCOUNT_ID, product_name=product) if r.get("doc_id")}
        targets = [d for d in alldocs if d["id"] not in done]

    print(f"待生成 {len(targets)} 篇：{[d['id'] for d in targets]}\n")
    results = []
    for idx, doc in enumerate(targets, 1):
        t0 = time.time()
        mode = "分章节" if doc["id"] in LONG_DOC_IDS else "整篇"
        print(f"[{idx}/{len(targets)}] {doc['id']} {doc['name']}（{mode}）…")
        try:
            n, failed = generate_one(engine, profile, doc, as_template=as_template)
            tag = "ok" if not failed else f"ok(缺章:{failed})"
            print(f"    OK {n} 字，{time.time()-t0:.0f}s {('缺章节:'+str(failed)) if failed else ''}\n")
            results.append((doc["id"], doc["name"], n, tag))
        except Exception as e:
            print(f"    FAIL：{str(e)[:100]}\n")
            results.append((doc["id"], doc["name"], 0, f"FAIL:{str(e)[:60]}"))

    print("=" * 60)
    for did, nm, n, st in results:
        print(f"  {'OK' if st.startswith('ok') else 'XX'} {did:<10} {n:>7} 字  {nm}  {st if st!='ok' else ''}")
    ok = sum(1 for *_, st in results if st.startswith("ok"))
    print(f"\n成功 {ok}/{len(results)}")


if __name__ == "__main__":
    main()
