"""用飞书实体文件(PDF/doc/docx)重抽替换库中对应文档，并删除多余9份、严格对齐飞书清单。
严格用 (feishu_doc_id → 库doc_name关键词) 精确映射，不模糊匹配(吸取内容窜教训)。
"""
import re, sqlite3, subprocess, os, glob, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ROOT = Path(__file__).resolve().parent.parent

# 飞书有实体文件的22份: (feishu_wiki_doc_id, 库doc_name唯一关键词, 显示标题)
# 只列 gov.cn 网页版之外、飞书有实体、值得用实体替换的。标准另处理。
ENTITY = [
    ('XtVTwLiMri3LeRkzhDDc90PMnXg', '分类规则_CFDA', '医疗器械分类规则'),
    ('Ty5bwDYyPiS5V2k3ka1c5qT1nMe', '创新医疗器械特别审查', '创新医疗器械特别审查程序'),
    ('RNYVwNzECinc3dkx80HcbtjunAd', '生产监督管理办法', '医疗器械生产监督管理办法（2022年第53号）'),
    ('HgawwRbhWiPO3OknAuzcUgcQnsc', '临床评价技术指导原则', '医疗器械临床评价技术指导原则'),
    ('AUWmwMrsMikGIFkdPEacsx0Zn9g', '分类界定', '人工智能医用软件产品分类界定指导原则'),
    ('FfZ5wDgiei3bNQkdEdDcOqDXnbh', '软件注册审查指导原则_2022', '医疗器械软件注册审查指导原则（2022年修订版）'),
    ('TbETw9hKFiOiRikBkQXcszbmnjg', '现场检查', '医疗器械生产质量管理规范独立软件现场检查指导原则'),
    ('VxKNwIIHqiUFHgkwjX5cINWjnOf', '附录独立软件', '医疗器械生产质量管理规范附录独立软件'),
    ('MzdbwsEOJiB0hfkVHmScZ1TNnqg', '移动医疗器械', '移动医疗器械注册审查指导原则（2025年修订版）'),
    ('BWNbwgCn5iH8ppkRnK8co50LnIc', '人工智能医疗器械注册审查', '人工智能医疗器械注册审查指导原则'),
    ('JSeqwT38diCxC6kcfFncto5Enfc', '网络安全注册审查', '医疗器械网络安全注册审查指导原则（2022年修订版）'),
    ('L8owwyw8biPhDDkoiNmcDIZznQf', '可用性工程注册审查指导原则_2024', '医疗器械可用性工程注册审查指导原则'),
    ('Cwo5wI9FwiBGWFkeBthcMsEenzi', '应用说明', '关于医疗器械可用性工程注册审查指导原则的应用说明'),
    ('N5PbwC8tViSi93k22pYcpg2Fn5d', '真实世界数据', '真实世界数据用于医疗器械临床评价技术指导原则（试行）'),
    ('PU7KwooTciSDOOkVhDscyRGKnge', '人工智能辅助检测', '人工智能辅助检测医疗器械（软件）临床评价注册审查指导原则'),
    ('SMlRwgpCTiCY4ZkP8TLctBJ2nEd', '产品技术要求编写', '医疗器械产品技术要求编写指导原则'),
    ('JTlMwseJJidoktkiLBBcNB2UnR0', '深度学习', '深度学习辅助决策医疗器械软件审评要点'),
    ('REL9wHapLi9QLmkVuYVcGhQWn2f', '通用名称命名', '医用软件通用名称命名指导原则'),
    ('EErOwtqnviQIlok5oRDcZSMZn5e', '乳腺X射线', '乳腺X射线图像辅助检测软件注册审查指导原则'),
    ('RzM8wUPA9iluCrkA3yhcQKjZnPB', '糖尿病视网膜', '糖尿病视网膜病变眼底图像辅助诊断软件注册审查指导原则'),
    ('HQKxwCUNVidaGykEUN5cEAkWnNg', '肺结节CT', '肺结节CT图像辅助检测软件注册审查指导原则'),
]
# 多余9份(不在飞书清单)——删除
EXTRA = [
    '深度合成管理规定', '关于调整《医疗器械分类目录》部分内容', '关于医疗器械分类调整有关工作',
    '关于发布医疗器械分类目录动态调整工作程序', '人工智能生成合成内容标识办法',
    '2025年第132号公告附件', '算法推荐管理规定', '2026年第53号公告附件', '网络数据安全管理条例',
]
DL = ROOT / '../tt/法规/替换下载'


def resolve_and_download(feishu_id, title):
    r = subprocess.run(['lark-cli', 'wiki', '+node-get', '--node-token',
                        f'https://my.feishu.cn/wiki/{feishu_id}', '--as', 'user'],
                       capture_output=True, text=True)
    m = re.search(r'"obj_token":\s*"([^"]+)"', r.stdout)
    tm = re.search(r'"title":\s*"([^"]+)"', r.stdout)
    if not m: return None
    obj = m.group(1); ftitle = tm.group(1) if tm else title
    ext = ftitle.rsplit('.', 1)[-1] if '.' in ftitle else 'bin'
    DL.mkdir(parents=True, exist_ok=True)
    out = DL / f'{re.sub(chr(92)+"W", "_", title)[:40]}.{ext}'
    subprocess.run(['lark-cli', 'drive', '+download', '--file-token', obj,
                    '--output', str(out.relative_to(Path.cwd())) if str(out).startswith(str(Path.cwd())) else str(out),
                    '--overwrite', '--as', 'user'], capture_output=True, text=True, cwd=str(DL.parent))
    # download 需相对路径,直接在DL目录内下
    return out if out.exists() else None
