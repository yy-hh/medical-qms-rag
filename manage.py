#!/usr/bin/env python
"""medical-qms-rag 运维 CLI —— 封装常用操作，省得手敲长命令。

用法：
  # 服务管理（端口 8003）
  python manage.py serve          # 前台启动（调试用，Ctrl+C 停）
  python manage.py restart        # 重启（fuser 杀旧 + 后台起 + 健康确认）
  python manage.py stop           # 停服务
  python manage.py status         # 看进程/端口/健康
  python manage.py logs [-n 50]   # 看服务日志尾部

  # 知识库管理（qms.db）
  python manage.py kb list [--collection X]   # 列库内文档(份数/chunk/中文占比)
  python manage.py kb health                  # 体检：乱码(中文<15%)/网页噪声/重复/开头残留
  python manage.py kb clean                   # 深度清洗全库(scripts/deep_clean_all)
  python manage.py kb ingest <文件/目录> [--collection X]   # 导入文档入库

  # 文档生成（generated_docs）
  python manage.py gen <doc_id...>   # 生成指定文档
  python manage.py gen --all         # 生成全部缺失
  python manage.py gen --template    # 生成质量体系模板(__template__)

约定：本 CLI 用当前 python 解释器；重活(生成/清洗)会自动带 PYTHONPATH/PYTHONNOUSERSITE。
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = 8003
PY = sys.executable
LOG = "/tmp/qms_8003.log"
QMS_DB = ROOT / "qms.db"
GEN_DB = ROOT / "data" / "generated_docs.db"


def _env():
    e = os.environ.copy()
    e["PYTHONPATH"] = str(ROOT)
    e["PYTHONNOUSERSITE"] = "1"
    return e


def _health():
    import urllib.request, json
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=3) as r:
            return json.loads(r.read())
    except Exception:
        return None


# ── 服务管理 ──────────────────────────────────────────────────────
def cmd_stop(args):
    subprocess.run(["fuser", "-k", f"{PORT}/tcp"], capture_output=True)
    time.sleep(2)
    print(f"✓ 已停止 {PORT} 端口服务")


def cmd_serve(args):
    print(f"前台启动 uvicorn :{PORT}（Ctrl+C 停）...")
    os.execvpe(PY, [PY, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0",
                    "--port", str(PORT)], _env())


def cmd_restart(args):
    subprocess.run(["fuser", "-k", f"{PORT}/tcp"], capture_output=True)
    time.sleep(2)
    with open(LOG, "wb") as logf:
        subprocess.Popen(
            ["setsid", PY, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(PORT)],
            stdout=logf, stderr=logf, stdin=subprocess.DEVNULL, env=_env(), cwd=str(ROOT),
            start_new_session=True)
    for _ in range(15):
        time.sleep(1)
        h = _health()
        if h:
            print(f"✓ 服务已重启 :{PORT} — {h.get('total_documents')} 文档 / {h.get('total_chunks')} chunk")
            return
    print(f"⚠️ 重启后 15s 未就绪，看日志：python manage.py logs")


def cmd_status(args):
    r = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True)
    listening = f":{PORT} " in r.stdout or f":{PORT}\n" in r.stdout
    print(f"端口 {PORT} 监听：{'✓ 是' if listening else '✗ 否'}")
    h = _health()
    if h:
        print(f"健康检查：✓ ok — {h.get('total_documents')} 文档 / {h.get('total_chunks')} chunk")
    else:
        print("健康检查：✗ 无响应")


def cmd_logs(args):
    if not os.path.exists(LOG):
        print("无日志文件"); return
    subprocess.run(["tail", "-n", str(args.n), LOG])


# ── 知识库管理 ────────────────────────────────────────────────────
def _kb_docs():
    import sqlite3, re
    con = sqlite3.connect(QMS_DB); con.row_factory = sqlite3.Row
    docs = {}
    for r in con.execute("SELECT doc_name,collection,text FROM chunks ORDER BY collection,doc_name,chunk_index"):
        d = docs.setdefault(r["doc_name"], {"col": r["collection"], "t": [], "n": 0})
        d["t"].append(r["text"] or ""); d["n"] += 1
    con.close()
    for d in docs.values():
        d["full"] = "\n".join(d["t"]); d["cjk"] = len(re.findall(r"[一-鿿]", d["full"]))
    return docs


def cmd_kb_list(args):
    docs = _kb_docs()
    items = sorted(docs.items(), key=lambda x: x[1]["col"])
    if args.collection:
        items = [(k, v) for k, v in items if v["col"] == args.collection]
    print(f"{'中文%':>5} {'字数':>7} {'块':>4}  文档")
    for name, d in items:
        c = len(d["full"]); r = 100 * d["cjk"] // max(c, 1)
        print(f"{r:>4}% {c:>7} {d['n']:>4}  [{d['col']}] {name[:44]}")
    print(f"\n共 {len(items)} 份")


def cmd_kb_health(args):
    import re
    docs = _kb_docs()
    HEAD = ["标题：", "来源URL", "下载时间：", "原始附件", "当前位置", "_其他工作文件_", "首页\n", "保护视力色"]
    NOISE = ["全国政协", "网站声明", "保护视力色", "科技动态"]
    bad_cjk = bad_head = bad_noise = 0
    fp = {}
    dup = 0
    for name, d in docs.items():
        t = d["full"]; c = 100 * d["cjk"] // max(len(t), 1)
        if c < 15 and d["col"] != "classification" and "standards" not in d["col"]:
            bad_cjk += 1; print(f"  ⚠️乱码{c}%: {name[:40]}")
        if any(k in t[:120] for k in HEAD):
            bad_head += 1; print(f"  ⚠️开头残留: {name[:40]}")
        if any(k in t for k in NOISE):
            bad_noise += 1; print(f"  ⚠️网页噪声: {name[:40]}")
        tt = re.sub(r"\s", "", t)
        if len(tt) > 600:
            import hashlib
            s = hashlib.md5(tt[300:800].encode()).hexdigest()
            if s in fp:
                dup += 1; print(f"  ⚠️内容重复: {name[:30]} == {fp[s][:30]}")
            else:
                fp[s] = name
    print(f"\n体检 {len(docs)} 份：乱码 {bad_cjk} · 开头残留 {bad_head} · 网页噪声 {bad_noise} · 重复 {dup}")
    if bad_cjk + bad_head + bad_noise + dup == 0:
        print("✅ 全部干净")


def cmd_kb_clean(args):
    subprocess.run([PY, str(ROOT / "scripts" / "deep_clean_all.py")], env=_env(), cwd=str(ROOT))


def cmd_kb_ingest(args):
    subprocess.run([PY, str(ROOT / "scripts" / "ingest.py"), args.path]
                   + (["--collection", args.collection] if args.collection else []),
                   env=_env(), cwd=str(ROOT))


# ── 文档生成 ──────────────────────────────────────────────────────
def cmd_gen(args):
    cmd = [PY, "-u", str(ROOT / "scripts" / "batch_generate.py")]
    if args.template:
        cmd.append("--template")
    cmd += args.doc_ids
    print(f"生成中（后台，日志 /tmp/gen.log）... {'模板模式' if args.template else ''} {args.doc_ids or '全部缺失'}")
    with open("/tmp/gen.log", "wb") as logf:
        subprocess.Popen(cmd, stdout=logf, stderr=logf, stdin=subprocess.DEVNULL,
                         env=_env(), cwd=str(ROOT), start_new_session=True)
    print("已在后台启动。查看进度：python manage.py logs -n 30 或 tail -f /tmp/gen.log")


def main():
    ap = argparse.ArgumentParser(description="medical-qms-rag 运维 CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("serve").set_defaults(fn=cmd_serve)
    sub.add_parser("restart").set_defaults(fn=cmd_restart)
    sub.add_parser("stop").set_defaults(fn=cmd_stop)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    p = sub.add_parser("logs"); p.add_argument("-n", type=int, default=40); p.set_defaults(fn=cmd_logs)

    kb = sub.add_parser("kb").add_subparsers(dest="kbcmd", required=True)
    p = kb.add_parser("list"); p.add_argument("--collection"); p.set_defaults(fn=cmd_kb_list)
    kb.add_parser("health").set_defaults(fn=cmd_kb_health)
    kb.add_parser("clean").set_defaults(fn=cmd_kb_clean)
    p = kb.add_parser("ingest"); p.add_argument("path"); p.add_argument("--collection"); p.set_defaults(fn=cmd_kb_ingest)

    p = sub.add_parser("gen")
    p.add_argument("doc_ids", nargs="*")
    p.add_argument("--all", action="store_true")
    p.add_argument("--template", action="store_true")
    p.set_defaults(fn=cmd_gen)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
