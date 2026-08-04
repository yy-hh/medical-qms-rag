"""离线批量生成 QMS 文档：复刻 generate.py 的多轮回灌到 DOC_END 逻辑，
在进程内一次写完整篇并落盘，避免 SSE 管道/后台任务被回收的问题。

用法：
  python scripts/gen_doc.py --seq 3   --out /tmp/cx_FLJ.md   --name "产品分类界定结论及分类界定申请"
  python scripts/gen_doc.py --doc_id L1-001 --out /tmp/cx_L1-001.md
"""
import sys, argparse, time
sys.path.insert(0, ".")

from app.api.generate import (
    _build_prompt, GENERATE_SYSTEM, DOC_END_MARKER,
    _doc_from_checklist_seq, _retrieve_refs,
)
from app.core.qms_framework import get_document_by_id
from app.core.rag_engine import get_engine
from app.core.config import settings
from app.api.company import load_profile

MAX_TOKENS_PER_ROUND = 16384
MAX_ROUNDS = 8
MAX_TOTAL_CHARS = 80000


def gen(doc, out_path, extra="", account_id=None):
    from app.core.account_store import DEFAULT_ACCOUNT
    eng = get_engine()
    profile = load_profile(account_id or DEFAULT_ACCOUNT)
    ref_context, _ = _retrieve_refs(eng, doc)
    user_prompt = _build_prompt(doc, profile, extra, ref_context)
    messages = [
        {"role": "system", "content": GENERATE_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]
    full = ""
    completed = False
    t0 = time.time()
    for rnd in range(MAX_ROUNDS):
        stream = eng.llm.chat.completions.create(
            model=settings.claude_model,
            max_tokens=MAX_TOKENS_PER_ROUND,
            messages=messages,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            piece = getattr(chunk.choices[0].delta, "content", None)
            if not piece:
                continue
            full += piece
            if DOC_END_MARKER in full:
                full = full.replace(DOC_END_MARKER, "")
                completed = True
                break
        print(f"  round {rnd+1}: {len(full)} chars, {time.time()-t0:.0f}s, done={completed}", flush=True)
        if completed or len(full) >= MAX_TOTAL_CHARS:
            break
        # 回灌续写：把已生成内容接回去，要求继续
        messages = [
            {"role": "system", "content": GENERATE_SYSTEM},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": full},
            {"role": "user", "content": "请从你上次中断处继续写完剩余内容，不要重复已写部分，写完后单独一行输出 " + DOC_END_MARKER},
        ]
    open(out_path, "w").write(full)
    print(f"DONE {out_path}: {len(full)} chars, completed={completed}", flush=True)
    return full, completed


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", type=int)
    ap.add_argument("--doc_id")
    ap.add_argument("--out", required=True)
    ap.add_argument("--extra", default="")
    ap.add_argument("--account", default=None, help="账号 open_id（默认属主账号）")
    a = ap.parse_args()
    doc = get_document_by_id(a.doc_id) if a.doc_id else _doc_from_checklist_seq(a.seq)
    if not doc:
        print("doc not found"); sys.exit(1)
    print(f"生成: {doc['name']}", flush=True)
    gen(doc, a.out, a.extra, account_id=a.account)
