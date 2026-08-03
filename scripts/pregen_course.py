"""通用「按章长视频课」预生成脚本（board 方式，非 seedance）。

把 13485 专用链泛化为可对任意标准生成：每章 = 一节课 = 一个较长黑板讲解视频，
逐句讲解、分屏黑板（按小节切换）、仅中文单行字幕、Gemini TTS 播音、长音频分块合成。

一个脚本跑完三阶段（均可重入，已就绪的段/已补的 secmap 会跳过）：
  1) outline   : 逐章调 LLM 生成中文逐句讲解 + 小节名，落库 segments
  2) annotate  : 逐段补 secmap（句→小节映射 + 每小节板书要点）
  3) render    : 分块 TTS 合成整章音频 → build_zh_srt_timed 单中文折行字幕
                 → compose_board_sections 分屏黑板渲染

用法：
  python scripts/pregen_course.py 14971            # 生成 ISO 14971 全流程
  python scripts/pregen_course.py 62304 62366      # 依次生成两门
  python scripts/pregen_course.py all              # 三门都做
  python scripts/pregen_course.py 14971 --outline  # 只生大纲不渲染
  python scripts/pregen_course.py 14971 --force-outline  # 重生大纲（覆盖已有）

数据落地（复用现有表结构，与 13485 一致）：
  narration     : 本章中文讲解全文（TTS 朗读）
  visual_prompt : JSON {"points":[小节名], "zh":[中文句], "en":[], "secmap":[...]}
"""
import sys
import os
import re
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import training_store, audio_gen
from app.core.rag_engine import get_engine
from app.core.config import settings
from app.api.training import _board_sentences

# 每门课的 topic（须与 tutorials 表已有 topic 完全一致，以便复用/覆盖同一条教程）与章节表。
COURSES = {
    "13485": {
        "topic": "ISO 13485 质量管理体系概览",
        "standard": "ISO 13485:2016",
        "chapters": [
            "第1章 范围", "第2章 规范性引用文件", "第3章 术语和定义",
            "第4章 质量管理体系", "第5章 管理职责", "第6章 资源管理",
            "第7章 产品实现", "第8章 测量、分析和改进",
        ],
    },
    "14971": {
        "topic": "ISO 14971 风险管理流程",
        "standard": "ISO 14971:2019",
        "chapters": [
            "第1章 范围",
            "第2章 规范性引用文件",
            "第3章 术语和定义",
            "第4章 风险管理体系通用要求",
            "第5章 风险分析",
            "第6章 风险评价",
            "第7章 风险控制",
            "第8章 综合剩余风险的评价",
            "第9章 风险管理评审",
            "第10章 生产和生产后活动",
        ],
    },
    "62304": {
        "topic": "IEC 62304 医疗器械软件生命周期",
        "standard": "IEC 62304:2006+A1:2015",
        "chapters": [
            "第1章 范围",
            "第2章 规范性引用文件",
            "第3章 术语和定义",
            "第4章 通用要求（含软件安全性分类）",
            "第5章 软件开发过程",
            "第6章 软件维护过程",
            "第7章 软件风险管理过程",
            "第8章 软件配置管理过程",
            "第9章 软件问题解决过程",
        ],
    },
    "62366": {
        "topic": "IEC 62366 可用性工程与人因",
        "standard": "IEC 62366-1:2015",
        # 正文仅 5 章且第 5 章过大，拆成均衡的 9 节
        "chapters": [
            "第1节 范围与目的",
            "第2节 规范性引用文件",
            "第3节 术语和定义",
            "第4节 通用要求（可用性工程过程概览）",
            "第5节 使用规范（Use specification）",
            "第6节 用户接口规范与识别已知问题",
            "第7节 使用场景与用户接口评估计划",
            "第8节 形成性评估（Formative evaluation）",
            "第9节 总结性评估与可用性工程文档",
        ],
    },
    # ===== NMPA 中国医疗器械法规（4 门） =====
    "tiaoli": {
        "topic": "医疗器械监督管理条例",
        "standard": "《医疗器械监督管理条例》（国务院令第739号，2021修订）",
        "chapters": [
            "第一章 总则",
            "第二章 医疗器械产品注册与备案",
            "第三章 医疗器械生产",
            "第四章 医疗器械经营与使用",
            "第五章 不良事件的处理与医疗器械的召回",
            "第六章 监督管理",
            "第七章 法律责任",
            "第八章 附则",
        ],
    },
    "zhuce": {
        "topic": "医疗器械注册与备案管理办法",
        "standard": "《医疗器械注册与备案管理办法》（国家市场监管总局令第47号，2021）",
        "chapters": [
            "第一章 总则",
            "第二章 基本要求",
            "第三章 医疗器械注册",
            "第四章 医疗器械备案",
            "第五章 特殊注册程序",
            "第六章 变更注册与延续注册",
            "第七章 工作时限",
            "第八章 监督管理与法律责任",
            "第九章 附则",
        ],
    },
    "gmp": {
        "topic": "医疗器械生产质量管理规范",
        "standard": "《医疗器械生产质量管理规范》（国家食品药品监管总局2014年第64号）",
        "chapters": [
            "第一章 总则",
            "第二章 机构与人员",
            "第三章 厂房与设施",
            "第四章 设备",
            "第五章 文件管理",
            "第六章 设计开发",
            "第七章 采购",
            "第八章 生产管理",
            "第九章 质量控制",
            "第十章 销售和售后服务",
            "第十一章 不合格品控制",
            "第十二章 不良事件监测、分析和改进",
            "第十三章 附则",
        ],
    },
    "gsp": {
        "topic": "医疗器械经营质量管理规范",
        "standard": "《医疗器械经营质量管理规范》（国家食品药品监管总局2014年第58号）",
        "chapters": [
            "第一章 总则",
            "第二章 职责与制度",
            "第三章 人员与培训",
            "第四章 设施与设备",
            "第五章 采购、收货与验收",
            "第六章 入库、贮存与检查",
            "第七章 销售、出库与运输",
            "第八章 售后服务与追溯",
            "第九章 附则",
        ],
    },
    # ===== 国际法规 / 临床（3 门） =====
    "part820": {
        "topic": "FDA 21 CFR Part 820 医疗器械质量体系",
        "standard": "21 CFR Part 820 QSR（2026 过渡为 QMSR，向 ISO 13485 靠拢）",
        "chapters": [
            "第1节 概述与法规背景（QSR 到 QMSR 过渡）",
            "第2节 Subpart A 通用要求与定义",
            "第3节 Subpart B 质量体系要求（管理职责）",
            "第4节 Subpart C 设计控制（Design Controls）",
            "第5节 Subpart D-E 文件控制与采购控制",
            "第6节 Subpart F-G 标识可追溯性与生产过程控制",
            "第7节 Subpart H-I 验收活动与不合格品",
            "第8节 Subpart J CAPA 纠正与预防措施",
            "第9节 Subpart K-O 标签包装、处理贮存、记录与服务",
        ],
    },
    "mdr": {
        "topic": "欧盟医疗器械法规 MDR 2017/745",
        "standard": "Regulation (EU) 2017/745 (MDR)",
        "chapters": [
            "第1章 范围与定义",
            "第2章 器械上市与经济运营商义务",
            "第3章 器械识别与追溯（UDI）及注册",
            "第4章 公告机构（Notified Bodies）",
            "第5章 分类与符合性评估",
            "第6章 临床评价与临床研究",
            "第7章 上市后监督、警戒与市场监管",
            "第8章 技术文档与通用安全性能要求（GSPR）",
            "第9章 治理、过渡期与实施",
        ],
    },
    "gcp": {
        "topic": "医疗器械临床试验质量管理规范",
        "standard": "《医疗器械临床试验质量管理规范》（2022年第28号）",
        "chapters": [
            "第一章 总则",
            "第二章 临床试验的前提条件",
            "第三章 受试者权益保障（知情同意与伦理审查）",
            "第四章 临床试验方案",
            "第五章 伦理委员会职责",
            "第六章 申办者职责",
            "第七章 临床试验机构与研究者职责",
            "第八章 记录、监查与稽查",
            "第九章 试验用器械管理与安全性报告",
            "第十章 附则",
        ],
    },
}

CHAPTER_SYSTEM = """你是资深的医疗器械 QMS 培训讲师，正在为一部国际标准录制逐章精讲课程。
本节课只讲解指定的一个章节，要求「逐句讲解」——把该章的核心要求讲透，条理清晰、口语自然、可直接朗读。

请严格按以下纯文本格式输出（不要 JSON、不要 markdown、不要多余说明）：

第一行固定以「小节：」开头，后面跟本章 3-6 个小节名，用「｜」分隔（每个小节名 4-12 字，作为黑板板书大纲）。
从第二行起，每行是一句讲解（仅中文，不要英文、不要拼音）。

要求：
- 中文句口语化、完整、可朗读，每句 15-40 字。
- 句子按讲课逻辑连贯推进：先点出本章主旨，再逐条讲解主要条款要求，最后小结。
- 句子数量按内容多少而定：短章（范围/引用/术语）12-18 句，长章（核心过程章）24-36 句。
- 讲解具体、有信息量，避免空话；涉及条款编号用中文表述（如「第5.1条」）。
- 不要给句子编号，不要使用竖线等特殊分隔符。

输出示例：
小节：标准适用范围｜适用对象｜法规衔接
本标准规定了医疗器械风险管理的要求。
它适用于医疗器械的整个生命周期。"""

ANNOTATE_SYSTEM = """你是课程编辑。下面给你一节课的逐句讲解（每句前有编号）和该章的小节名列表。
请把这些句子按讲课进程划分给各个小节（每句只属于一个小节，按顺序连续切分，不跳跃、不重叠、全覆盖），
并为每个小节提炼 2-4 个「黑板板书要点」（每个 4-14 字的极短中文短语，概括该小节要讲的关键点）。

严格只输出一个 JSON 数组，每个元素形如：
{"title":"小节名","points":["要点1","要点2"],"start":起始句号,"end":结束句号}
其中 start/end 是该小节覆盖的句子编号范围（含两端，从 1 开始，与输入编号一致）。
第一个小节的 start 必须是 1，最后一个小节的 end 必须是最后一句的编号，各小节首尾相接。
不要输出任何额外文字，不要 markdown。"""


def _find_tutorial(topic):
    for t in training_store.list_tutorials():
        if t["kind"] == "video" and t["topic"] == topic:
            return t
    return None


def gen_chapter(standard, zh_title):
    """调 LLM 生成单章内容，返回 segment dict（仅中文）。"""
    engine = get_engine()
    resp = engine.llm.chat.completions.create(
        model=settings.claude_model, max_tokens=8192,
        messages=[
            {"role": "system", "content": CHAPTER_SYSTEM},
            {"role": "user", "content":
                f"请讲解 {standard} 标准的「{zh_title}」。结合医疗器械行业实际，把本章要求讲清楚。"},
        ],
    )
    raw = resp.choices[0].message.content or ""
    sections, zh_list = [], []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("小节：") or line.startswith("小节:"):
            body = line.split("：", 1)[-1] if "：" in line else line.split(":", 1)[-1]
            sections = [s.strip() for s in re.split(r"[｜|]", body) if s.strip()][:6]
            continue
        # 去掉可能的行首编号，剔除竖线
        cand = re.sub(r"^\d+[\.、\)]\s*", "", line).replace("|||", "").replace("｜", "").strip()
        if cand and not cand.startswith("小节"):
            zh_list.append(cand)
    if not zh_list:
        raise RuntimeError("章节内容解析失败：无有效句子")
    narration = "".join(z if z.endswith(("。", "！", "？", ".", "!", "?")) else z + "。" for z in zh_list)
    visual = {"points": sections, "zh": zh_list, "en": []}
    return {
        "title": zh_title,
        "seg_kind": "board",
        "narration": narration,
        "narration_en": "",
        "visual_prompt": json.dumps(visual, ensure_ascii=False),
    }


def build_outline(course, force=False):
    topic = course["topic"]
    existing = _find_tutorial(topic)
    if existing and training_store.list_segments(existing["id"]) and not force:
        print(f"  复用已有大纲（{len(training_store.list_segments(existing['id']))} 章），不重生", flush=True)
        return existing["id"]
    tid = existing["id"] if existing else training_store.save_tutorial(
        topic=topic, kind="video", status="draft")
    segs = []
    for i, zh in enumerate(course["chapters"], 1):
        print(f"  大纲 [{i}/{len(course['chapters'])}] {zh} …", flush=True)
        segs.append(gen_chapter(course["standard"], zh))
        print(f"      ✓ {len(json.loads(segs[-1]['visual_prompt'])['zh'])} 句", flush=True)
    training_store.replace_segments(tid, segs)
    training_store.update_tutorial(tid, status="draft")
    print(f"  大纲 {len(segs)} 章 → tutorial={tid}", flush=True)
    return tid


def annotate_seg(seg):
    v = json.loads(seg["visual_prompt"])
    if v.get("secmap"):
        return len(v["secmap"])  # 已补，跳过
    zh = v.get("zh") or []
    sections = v.get("points") or []
    if not zh or not sections:
        raise RuntimeError("缺 zh 或 points")
    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(zh))
    user = f"小节名列表：{'、'.join(sections)}\n\n逐句讲解（共 {len(zh)} 句）：\n{numbered}"
    engine = get_engine()
    resp = engine.llm.chat.completions.create(
        model=settings.claude_model, max_tokens=4096,
        messages=[{"role": "system", "content": ANNOTATE_SYSTEM},
                  {"role": "user", "content": user}],
    )
    raw = resp.choices[0].message.content or ""
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        raise RuntimeError("secmap 解析失败：无 JSON")
    arr = json.loads(m.group(0))
    secmap = []
    for x in arr:
        if not isinstance(x, dict):
            continue
        start, end = int(x.get("start", 0)), int(x.get("end", 0))
        pts = [str(p).strip() for p in (x.get("points") or []) if str(p).strip()][:4]
        title = str(x.get("title", "")).strip()
        if start >= 1 and end >= start and title:
            secmap.append({"title": title, "points": pts,
                           "start_idx": start - 1, "end_idx": end - 1})
    if not secmap:
        raise RuntimeError("secmap 为空")
    secmap[0]["start_idx"] = 0
    secmap[-1]["end_idx"] = len(zh) - 1
    v["secmap"] = secmap
    training_store.update_segment(seg["id"], visual_prompt=json.dumps(v, ensure_ascii=False))
    return len(secmap)


def render_seg(seg):
    sid = seg["id"]
    v = json.loads(seg["visual_prompt"])
    zh = v.get("zh") or []
    secmap = v.get("secmap") or []
    zh_s, _ = _board_sentences(seg)  # 若无 en 配对返回 (None,None)
    zh_s = zh_s or zh
    # 分块合成整章语音（避免长文本 TTS 超时），拿到每句实测时长
    apath, per = audio_gen.generate_speech_sentences(zh_s, base_name=f"seg_{sid}")
    dur = audio_gen._probe_duration(apath) or 0.0
    if dur <= 0:
        raise RuntimeError("音频时长为 0")
    starts = [0.0]
    for d in per:
        starts.append(starts[-1] + d)
    srt = audio_gen.AUDIO_DIR / f"{sid}.srt"
    audio_gen.build_zh_srt_timed(zh_s, per, srt)
    sections = []
    for sm in secmap:
        si = max(0, min(sm["start_idx"], len(zh_s) - 1))
        ei = max(si, min(sm["end_idx"], len(zh_s) - 1))
        sections.append({
            "title": sm["title"], "points": sm.get("points") or [],
            "start": starts[si], "end": starts[ei + 1] if ei + 1 < len(starts) else dur,
        })
    if sections:
        sections[0]["start"] = 0.0
        sections[-1]["end"] = dur
    final = audio_gen.compose_board_sections(
        seg["title"], sections, apath, srt, out_name=f"seg_{sid}.mp4")
    training_store.update_segment(sid, final_path=final, status="ready")
    return dur, len(sections)


def do_course(key, only_outline=False, force_outline=False):
    course = COURSES[key]
    topic = course["topic"]
    print(f"\n########## {topic}（{course['standard']}） ##########", flush=True)
    tid = build_outline(course, force=force_outline)
    if only_outline:
        return
    # 补 secmap
    print("  --- 补 secmap ---", flush=True)
    for seg in training_store.list_segments(tid):
        try:
            n = annotate_seg(seg)
            print(f"    ✓ {seg['title']} → {n} 小节", flush=True)
        except Exception as e:
            print(f"    ✗ {seg['title']}：{e}", flush=True)
    # 渲染
    print("  --- 分屏渲染 ---", flush=True)
    for i, seg in enumerate(training_store.list_segments(tid), 1):
        seg = training_store.get_segment(seg["id"])
        if seg["status"] == "ready" and seg["final_path"] and os.path.exists(
                os.path.join("static", seg["final_path"])):
            print(f"    [{i}] {seg['title']} 已就绪，跳过", flush=True)
            continue
        t0 = time.time()
        print(f"    [{i}] {seg['title']} 渲染中…", flush=True)
        try:
            training_store.update_segment(seg["id"], status="generating")
            dur, ns = render_seg(seg)
            print(f"        ✓ {time.time()-t0:.0f}s, {dur:.0f}s, {ns} 分屏", flush=True)
        except Exception as e:
            training_store.update_segment(seg["id"], status="failed")
            print(f"        ✗ 失败 ({time.time()-t0:.0f}s)：{e}", flush=True)
    segs = training_store.list_segments(tid)
    if segs and all(s["status"] == "ready" for s in segs):
        training_store.update_tutorial(tid, status="ready")
        print(f"  ✓ 「{topic}」全部就绪", flush=True)
    else:
        done = sum(1 for s in segs if s["status"] == "ready")
        print(f"  ⚠ {done}/{len(segs)} 章就绪", flush=True)


def main():
    argv = sys.argv[1:]
    only_outline = "--outline" in argv
    force_outline = "--force-outline" in argv
    keys = [a for a in argv if not a.startswith("--")]
    if not keys or keys == ["all"]:
        keys = list(COURSES.keys())
    bad = [k for k in keys if k not in COURSES]
    if bad:
        print(f"未知课程：{bad}，可选：{list(COURSES.keys())} 或 all", flush=True)
        return
    get_engine()
    for k in keys:
        do_course(k, only_outline=only_outline, force_outline=force_outline)
    print("\n=== 全部结束 ===", flush=True)


if __name__ == "__main__":
    main()
