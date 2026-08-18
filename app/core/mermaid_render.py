"""把 mermaid 代码渲染成 PNG（调 node 侧 @mermaid-js/mermaid-cli）。

用途：文档里的流程图/组织架构图用 ```mermaid 表达，导出 Word 时渲染成 PNG 嵌入。
按 mermaid 源码 sha1 做磁盘缓存，同一段图第二次渲染直接命中、瞬时返回。
渲染失败（语法错/环境缺）返回 None，由调用方降级（保留源码文本），不中断导出。
"""
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "mermaid_cache"

# fnm 的会话级 shim 路径（带 PID）不稳定，优先用固定安装目录里的 npx。
_NPX_CANDIDATES = [
    os.path.expanduser("~/.local/share/fnm/node-versions/v22.20.0/installation/bin/npx"),
]


def _find_npx() -> str | None:
    for p in _NPX_CANDIDATES:
        if os.path.exists(p):
            return p
    return shutil.which("npx")


def _npx_env(npx_path: str) -> dict:
    """确保 subprocess 的 PATH 含 npx 所在目录（服务进程 PATH 可能没有）。"""
    env = os.environ.copy()
    npx_dir = os.path.dirname(npx_path)
    if npx_dir and npx_dir not in env.get("PATH", ""):
        env["PATH"] = npx_dir + os.pathsep + env.get("PATH", "")
    return env


def render_mermaid_to_png(code: str) -> bytes | None:
    """渲染一段 mermaid 源码为 PNG bytes；失败返回 None。带 sha1 磁盘缓存。"""
    code = (code or "").strip()
    if not code:
        return None

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(code.encode("utf-8")).hexdigest()
    cached = _CACHE_DIR / f"{h}.png"
    if cached.exists() and cached.stat().st_size > 0:
        return cached.read_bytes()

    npx = _find_npx()
    if not npx:
        return None

    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.mmd"
        out = Path(td) / "out.png"
        src.write_text(code, encoding="utf-8")
        try:
            subprocess.run(
                [npx, "-y", "@mermaid-js/mermaid-cli",
                 "-i", str(src), "-o", str(out), "-b", "white", "-s", "2"],
                capture_output=True, timeout=120, env=_npx_env(npx),
            )
        except Exception:
            return None
        if not out.exists() or out.stat().st_size == 0:
            return None
        data = out.read_bytes()

    try:
        cached.write_bytes(data)
    except Exception:
        pass
    return data
