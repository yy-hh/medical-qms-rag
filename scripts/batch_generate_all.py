"""批量生成全部可生成文档并归档到文件管理。

复用 /api/generate/stream（整篇模式）+ /api/docs/save，与路线图点击生成一致。
同一 doc_id 只生成一次；无 doc_id 的按 seq 生成。失败跳过继续。
"""
import sys, os, json, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.registration_checklist import CHECKLIST, is_genable

BASE = "http://127.0.0.1:8003"


def post(path, payload, timeout=600):
    req = urllib.request.Request(BASE + path,
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


def gen_one(item):
    """整篇流式生成，返回全文（命中 [DONE] 或断流为止）。"""
    body = {"doc_id": item["doc_id"]} if item.get("doc_id") else {"seq": item["seq"]}
    full = ""
    try:
        with post("/api/generate/stream", body, timeout=600) as r:
            for raw in r:
                l = raw.decode("utf-8", "replace").rstrip("\n")
                if not l.startswith("data: "):
                    continue
                p = l[6:]
                if p == "[DONE]":
                    break
                ev = json.loads(p)
                if ev.get("type") == "delta":
                    full += ev["content"]
                elif ev.get("type") == "error":
                    break
    except Exception as e:
        print(f"     [流异常] {e}", flush=True)
    return full


def main():
    items = [i for i in CHECKLIST if is_genable(i)]
    # 同一 doc_id 去重（保留首个）
    # 已归档的 doc_name（可重入：续跑时跳过已生成的）
    done_names = set()
    try:
        with urllib.request.urlopen(BASE + "/api/docs", timeout=20) as r:
            for d in json.loads(r.read())["docs"]:
                done_names.add(d["doc_name"])
    except Exception:
        pass

    seen_doc = set()
    queue = []
    for it in items:
        did = it.get("doc_id")
        if did:
            if did in seen_doc:
                continue
            seen_doc.add(did)
        name = it["output"].split("；")[0].split("&")[0].strip()
        if name in done_names:
            continue  # 已归档，跳过
        queue.append(it)
    print(f"待生成 {len(queue)} 份（已归档 {len(done_names)} 份跳过）", flush=True)

    ok = fail = 0
    for n, it in enumerate(queue, 1):
        name = it["output"].split("；")[0].split("&")[0].strip()
        tag = it.get("doc_id") or f"#{it['seq']}"
        t0 = time.time()
        print(f"[{n}/{len(queue)}] {tag} {name} ...", flush=True)
        full = gen_one(it)
        if not full.strip():
            print(f"     ✗ 空内容，跳过 ({time.time()-t0:.0f}s)", flush=True)
            fail += 1
            continue
        # 存档
        try:
            post("/api/docs/save", {"doc_id": it.get("doc_id"), "doc_name": name, "content": full}, timeout=30).read()
            ok += 1
            print(f"     ✓ {len(full)}字 已归档 ({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            fail += 1
            print(f"     ✗ 归档失败 {e}", flush=True)

    print(f"\n=== 批量完成：成功 {ok}，失败 {fail}，共 {len(queue)} ===", flush=True)


if __name__ == "__main__":
    main()