"""图文教程预生成脚本（kind=article，代码绘制 SVG 配图，非 AI 生图）。

与视频课（pregen_course.py）覆盖同样的 11 个主题，但产出一篇「图文讲义」：
按标准章节结构组织的 markdown 正文 + 内联 SVG 结构图（flow/cycle/hierarchy/cards）。
管理员预生成好落库（status=ready），前端纯观看，与同名视频课并存。

流程（每个主题一次 LLM 调用产结构化 JSON → 组装 markdown → 落库）：
  1) LLM 按主题+章节表产出 {"intro","chapters":[{"heading","paragraphs","diagram"}],"summary"}
     每章由 LLM 自选最合适的图表类型并给出图表数据（不适合配图则 diagram=null）。
  2) 脚本用 diagram_svg 把 diagram 渲染成内联 <figure>，拼成完整 markdown。
  3) training_store.save_tutorial(kind='article', lecture=md, status='ready')。

用法：
  python scripts/pregen_article.py 13485                 # 只做一门（先验证）
  python scripts/pregen_article.py 14971 62304           # 依次做多门
  python scripts/pregen_article.py all                   # 全 11 门
  python scripts/pregen_article.py all --force           # 重生已有图文课
可重入：已 ready 的图文课默认跳过，--force 才重生。
"""
import sys
import os
import re
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import training_store, diagram_svg
from app.core.rag_engine import get_engine
from app.core.config import settings
from scripts.pregen_course import COURSES

ARTICLE_SYSTEM = """你是资深的医疗器械 QMS 培训讲师，正在为团队新成员编写一份**图文培训讲义**。
面向质量、研发、注册团队新成员，深入浅出、内容具体实用，结合医疗器械（含 SaMD 软件）行业实际。

请严格只输出一个 JSON 对象（不要 markdown、不要代码围栏、不要多余说明），结构如下：
{
  "intro": "1-2 句开场，点出本讲义要解决什么、学完能掌握什么",
  "chapters": [
    {
      "heading": "章节小标题（简洁，不必照抄标准章号，可用更易懂的表述）",
      "paragraphs": ["该章讲解，每个字符串是一个自然段，2-4 段，每段 2-4 句、具体有信息量"],
      "diagram": null 或 {
        "type": "flow|cycle|hierarchy|cards",
        "data": <见下>,
        "caption": "图注（一句话说明这张图）",
        "vertical": true/false   // 仅 flow 可选，步骤多或为纵向流程时置 true
      }
    }
  ],
  "summary": "1-2 句小结或实操提醒"
}

图表类型与 data 格式（**只在该章确实适合可视化时才配图**，否则 diagram 置 null）：
- "flow"：顺序流程/步骤。data = ["步骤1","步骤2",...]，每个 ≤10 字，建议 3-6 步。
- "cycle"：循环/迭代（如 PDCA、生命周期闭环）。data = ["阶段1",...] 3-6 个，每个 ≤8 字；可另给同级 "title" 字段作圆心标题（≤6 字）。
- "hierarchy"：分层/金字塔（如文档层级、体系结构）。data = [["顶层"],["中层A","中层B"],["底层1","底层2","底层3"]]，从上到下，每格 ≤10 字。
- "cards"：并列要点（如若干关键概念/角色/文件）。data = [["要点名","一句说明"],...]，4-6 张，说明 ≤22 字。

要求：
- 章节数量与主题复杂度匹配（一般 4-7 章），逻辑连贯：概述→核心要求→关键流程→实操要点。
- 图表文字精炼、能被上面各类型的字数上限容纳；不确定是否适合配图就置 null，宁缺勿滥。
- 全中文，专业术语首次出现可括注英文/缩写。

**极其重要（JSON 合法性）**：字符串值内部**严禁**出现英文半角双引号 " 或单引号 '（会破坏 JSON）。
需要强调、引用或标注术语时，一律改用中文引号「」『』或书名号《》。段落里的括注一律用中文全角括号（）。"""


def _strip_fence(s):
    s = (s or "").strip()
    # 去掉 ```json ... ``` 围栏
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s


_JSON_OPEN = set("{[,:")
_JSON_CLOSE = set(",}]:")


def _is_cjk(ch):
    return "一" <= ch <= "鿿" or ch in "：，。！？（）、；「」『』《》“”‘’—…·"


def _prev_nonws(txt, i):
    j = i - 1
    while j >= 0 and txt[j] in " \t\r\n":
        j -= 1
    return txt[j] if j >= 0 else ""


def _next_nonws(txt, i):
    j = i + 1
    while j < len(txt) and txt[j] in " \t\r\n":
        j += 1
    return txt[j] if j < len(txt) else ""


def _repair_cjk_quotes(txt):
    """把落在字符串内容里的半角双引号（LLM 常见错误）改成中文引号，避免破坏 JSON。
    结构引号：跳过空白后紧邻 { [ , : 之后，或 , } ] : 之前；其余判为内容引号并替换。"""
    out = []
    for i, ch in enumerate(txt):
        if ch == '"':
            p = _prev_nonws(txt, i)
            n = _next_nonws(txt, i)
            if not ((p in _JSON_OPEN) or (n in _JSON_CLOSE)):
                out.append("”" if _is_cjk(p) else "“")
                continue
        out.append(ch)
    return "".join(out)


def _extract_json(raw):
    """从 LLM 输出里稳妥抽取顶层 JSON 对象。"""
    txt = _strip_fence(raw)
    m = re.search(r"\{.*\}", txt, re.S)
    if m:
        txt = m.group(0)
    try:
        return json.loads(txt)
    except Exception:
        pass
    # 兜底：修复中文内容里的半角引号后再解析
    return json.loads(_repair_cjk_quotes(txt))


def gen_article_md(course):
    """调 LLM 产结构化大纲，组装成含内联 SVG 的 markdown。返回 (markdown, 章数, 图数)。"""
    topic = course["topic"]
    standard = course.get("standard", "")
    chapters = course.get("chapters", [])
    ch_hint = "、".join(chapters) if chapters else ""
    user = (f"请为培训主题「{topic}」（相关标准/法规：{standard}）编写图文讲义。\n"
            f"可参考的章节脉络（不必逐章照搬，可合并归纳为更易懂的讲解章节）：{ch_hint}")
    engine = get_engine()
    last_err = None
    for attempt in range(3):
        resp = engine.llm.with_options(timeout=240.0).chat.completions.create(
            model=settings.claude_model, max_tokens=8192,
            messages=[{"role": "system", "content": ARTICLE_SYSTEM},
                      {"role": "user", "content": user}],
        )
        raw = resp.choices[0].message.content or ""
        try:
            data = _extract_json(raw)
            break
        except Exception as e:
            last_err = e
            print(f"    JSON 解析失败（第 {attempt+1} 次），重试…", flush=True)
    else:
        raise RuntimeError(f"三次解析均失败：{last_err}")

    parts = [f"# {topic}"]
    intro = (data.get("intro") or "").strip()
    if intro:
        parts.append(intro)
    n_fig = 0
    for ch in data.get("chapters", []):
        if not isinstance(ch, dict):
            continue
        heading = (ch.get("heading") or "").strip()
        if heading:
            parts.append(f"## {heading}")
        for para in ch.get("paragraphs", []) or []:
            p = str(para).strip()
            if p:
                parts.append(p)
        fig = diagram_svg.render(ch.get("diagram"))
        if fig:
            parts.append(fig)
            n_fig += 1
    summary = (data.get("summary") or "").strip()
    if summary:
        parts.append("## 小结")
        parts.append(summary)
    md = "\n\n".join(parts)
    return md, len(data.get("chapters", [])), n_fig


def _find_article(topic):
    for t in training_store.list_tutorials():
        if t.get("kind") == "article" and t.get("topic") == topic:
            return t
    return None


def do_course(key, force=False):
    course = COURSES.get(key)
    if not course:
        print(f"[跳过] 未知课程 key：{key}", flush=True)
        return
    topic = course["topic"]
    print(f"\n=== 图文：{topic} ({key}) ===", flush=True)
    existing = _find_article(topic)
    if existing and existing.get("status") == "ready" and not force:
        print("  已有 ready 图文课，跳过（--force 可重生）", flush=True)
        return
    md, n_ch, n_fig = gen_article_md(course)
    tid = training_store.save_tutorial(
        tutorial_id=existing["id"] if existing else None,
        topic=topic, kind="article", lecture=md, status="ready")
    print(f"  ✓ {n_ch} 章 · {n_fig} 图 · {len(md)} 字 → tutorial={tid}", flush=True)


def main():
    argv = sys.argv[1:]
    force = "--force" in argv
    keys = [a for a in argv if not a.startswith("--")]
    if not keys:
        print(__doc__)
        return
    if keys == ["all"]:
        keys = list(COURSES.keys())
    for k in keys:
        try:
            do_course(k, force=force)
        except Exception as e:
            print(f"  ✗ {k} 生成失败：{e}", flush=True)


if __name__ == "__main__":
    main()
