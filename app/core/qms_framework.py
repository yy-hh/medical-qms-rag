"""
医疗 AI 器械 QMS 体系框架（基于用户整理的三层框架）

第一层：核心工作框架（9 大模块）
第二层：三国法规标准对照（NMPA / FDA / EU）
第三层：四级文件体系（质量手册 / 程序文件 / 作业指导书 / 记录表单 + AI 特有文件）

每个文件节点关联知识库中真实入库的法规/标准文档（refs），用于检索溯源与生成。
"""

# ── 第二层：三国法规标准对照 ────────────────────────────────────────────────
REGULATORY_MATRIX = [
    {
        "category": "基础法规（法律/法规层）",
        "nmpa": {"name": "医疗器械监督管理条例", "note": "国务院令第739号（2021）"},
        "fda": {"name": "FD&C Act + 21 CFR Part 820", "note": "Quality System Regulation / QMSR"},
        "eu": {"name": "MDR 2017/745", "note": "+ AI Act 2024/1689"},
    },
    {
        "category": "质量管理体系标准",
        "nmpa": {"name": "YY/T 0287 / GB/T 42061", "note": "等同采用 ISO 13485:2016"},
        "fda": {"name": "ISO 13485:2016", "note": "FDA QMSR 已纳入该标准"},
        "eu": {"name": "EN ISO 13485:2016", "note": "CE 认证必须满足"},
    },
    {
        "category": "软件生命周期标准",
        "nmpa": {"name": "YY/T 0664 / YY/T 1406", "note": "参考 / 对应 IEC 62304"},
        "fda": {"name": "IEC 62304:2006+AMD1", "note": "第2版预计 2026 年发布"},
        "eu": {"name": "EN IEC 62304", "note": "协调标准（2028年前）"},
    },
    {
        "category": "风险管理标准",
        "nmpa": {"name": "YY/T 0316 / GB/T 42062", "note": "等同采用 ISO 14971:2019"},
        "fda": {"name": "ISO 14971:2019", "note": "2025年3月确认无更新"},
        "eu": {"name": "EN ISO 14971:2019", "note": "+ ISO TR 34971（AI专项）"},
    },
    {
        "category": "AI/ML 专项法规与指引",
        "nmpa": {"name": "NMPA AI 指导原则", "note": "注册审查指导原则（2022）/ 北京AI GMP检查指南（2024）"},
        "fda": {"name": "FDA AI 综合指导草案", "note": "2025年1月发布 / PCCP 预定变更控制计划"},
        "eu": {"name": "EU AI Act（高风险）", "note": "2026/8 完全适用 / MDCG 2025-6 FAQ"},
    },
    {
        "category": "补充技术标准（各市场共用）",
        "nmpa": {"name": "可用性工程 IEC 62366-1", "note": "网络安全 IEC 81001-5-1 / AI数据质量 ISO/IEC 5259"},
        "fda": {"name": "同左", "note": "通用技术标准"},
        "eu": {"name": "同左", "note": "通用技术标准"},
    },
    {
        "category": "临床评价 / 性能评价",
        "nmpa": {"name": "NMPA AI辅助检测临床评价指导原则（2023）", "note": "卫健委AI应用场景参考指引（2024）"},
        "fda": {"name": "IMDRF SaMD 框架", "note": "临床评价 / 性能评价"},
        "eu": {"name": "MDR Annex XIV", "note": "临床评价"},
    },
]

# ── 第三层：四级文件体系（文件清单，每个文件挂知识库 refs）────────────────────
# refs 格式: {"collection": 集合名, "match": 文档名关键词}
DOC_LEVELS = [
    {
        "level": 1,
        "name": "第一级 · 质量手册",
        "en": "Quality Manual",
        "desc": "约 1 本，20-50 页，全公司唯一，顶层政策",
        "color": "#805ad5",
        "documents": [
            {
                "id": "L1-001", "name": "质量手册", "type": "manual",
                "desc": "描述 QMS 范围、质量方针、过程及其相互关系，是体系纲领性文件",
                "standards": ["ISO 13485 §4.2.2", "GB/T 42061 §4.2.2", "21 CFR 820", "EU MDR Annex IX"],
                "refs": [
                    {"collection": "standards", "match": "质量管理体系用于法规"},
                    {"collection": "regulations", "match": "医疗器械生产质量管理规范"},
                ],
            },
        ],
    },
    {
        "level": 2,
        "name": "第二级 · 程序文件（SOP）",
        "en": "Standard Operating Procedure",
        "desc": "20-60 份，跨部门流程，回答\"谁做、何时做\"",
        "color": "#38a169",
        "documents": [
            {
                "id": "L2-001", "name": "文件与记录控制程序", "type": "procedure",
                "desc": "文件起草、评审、批准、发布、变更、作废；记录标识、存储、保留",
                "standards": ["ISO 13485 §4.2.4", "§4.2.5"],
                "refs": [{"collection": "standards", "match": "质量管理体系用于法规"}],
            },
            {
                "id": "L2-002", "name": "管理评审程序", "type": "procedure",
                "desc": "管理评审的输入、输出、频率与记录要求",
                "standards": ["ISO 13485 §5.6"],
                "refs": [{"collection": "standards", "match": "质量管理体系用于法规"}],
            },
            {
                "id": "L2-003", "name": "软件开发生命周期程序", "type": "procedure",
                "desc": "按 IEC 62304 定义软件开发各阶段活动、输入输出与验收准则",
                "standards": ["IEC 62304 §5", "YY/T 0664"],
                "refs": [
                    {"collection": "standards", "match": "YY_T0664"},
                    {"collection": "guidance-software", "match": "医疗器械软件注册审查"},
                ],
            },
            {
                "id": "L2-004", "name": "软件配置管理与版本控制程序", "type": "procedure",
                "desc": "软件版本管理、变更控制、基线管理、配置审计",
                "standards": ["IEC 62304 §8", "YY/T 0664"],
                "refs": [{"collection": "standards", "match": "YY_T0664"}],
            },
            {
                "id": "L2-005", "name": "软件问题与缺陷管理程序", "type": "procedure",
                "desc": "软件缺陷的发现、记录、分类、修复与关闭",
                "standards": ["IEC 62304 §9", "YY/T 0664"],
                "refs": [{"collection": "standards", "match": "YY_T0664"}],
            },
            {
                "id": "L2-006", "name": "风险管理程序", "type": "procedure",
                "desc": "风险分析、评价、控制、剩余风险评价、风险管理报告全流程",
                "standards": ["ISO 14971:2019", "GB/T 42062", "YY/T 0316"],
                "refs": [
                    {"collection": "standards", "match": "风险管理对医疗器械"},
                    {"collection": "standards", "match": "0316"},
                ],
            },
            {
                "id": "L2-007", "name": "可用性工程程序", "type": "procedure",
                "desc": "用户研究、使用规范、UI 设计、形成性与总结性评价",
                "standards": ["IEC 62366-1", "可用性工程注册审查指导原则"],
                "refs": [{"collection": "guidance-usability", "match": "可用性工程注册审查"}],
            },
            {
                "id": "L2-008", "name": "网络安全管理程序", "type": "procedure",
                "desc": "软件全生命周期网络安全活动：威胁建模、安全测试、漏洞管理",
                "standards": ["YY/T 1833", "医疗器械网络安全注册审查指导原则", "IEC 81001-5-1"],
                "refs": [
                    {"collection": "guidance-cybersecurity", "match": "网络安全注册审查"},
                    {"collection": "cybersecurity", "match": "网络安全法"},
                ],
            },
            {
                "id": "L2-009", "name": "纠正和预防措施（CAPA）程序", "type": "procedure",
                "desc": "不合格、投诉、审核发现的根因分析、纠正措施、有效性验证",
                "standards": ["ISO 13485 §8.5.2", "§8.5.3", "21 CFR 820.100"],
                "refs": [{"collection": "standards", "match": "质量管理体系用于法规"}],
            },
            {
                "id": "L2-010", "name": "内部审核程序", "type": "procedure",
                "desc": "内审计划、审核员资质、执行、发现记录与跟踪关闭",
                "standards": ["ISO 13485 §8.2.2"],
                "refs": [{"collection": "standards", "match": "质量管理体系用于法规"}],
            },
            {
                "id": "L2-011", "name": "采购与供应商管理程序", "type": "procedure",
                "desc": "外包开发商、云服务商、组件供应商的评估、合同与绩效监控",
                "standards": ["ISO 13485 §7.4"],
                "refs": [{"collection": "standards", "match": "质量管理体系用于法规"}],
            },
            {
                "id": "L2-012", "name": "注册申报管理程序", "type": "procedure",
                "desc": "产品注册/备案的准备、提交、沟通、维护与变更申报",
                "standards": ["医疗器械注册与备案管理办法", "产品技术要求编写指导原则"],
                "refs": [
                    {"collection": "regulations", "match": "注册与备案管理办法"},
                    {"collection": "guidance-registration", "match": "产品技术要求编写"},
                ],
            },
            {
                "id": "L2-013", "name": "上市后监督与不良事件程序", "type": "procedure",
                "desc": "上市后数据收集、趋势分析、不良事件上报、再评价",
                "standards": ["医疗器械不良事件监测和再评价管理办法", "ISO 13485 §8.2.1"],
                "refs": [{"collection": "regulations", "match": "不良事件监测"}],
            },
        ],
    },
    {
        "level": 3,
        "name": "第三级 · 作业指导书（WI）",
        "en": "Work Instruction / 技术规范",
        "desc": "按需制定，回答\"如何做\"",
        "color": "#dd6b20",
        "documents": [
            {
                "id": "L3-001", "name": "数据标注作业指导书", "type": "wi",
                "desc": "训练/验证/测试数据的标注规范、质控规则与一致性要求",
                "standards": ["YY/T 1833.3 数据标注通用要求"],
                "refs": [{"collection": "standards", "match": "数据标注通用要求"}],
            },
            {
                "id": "L3-002", "name": "数据集构建与管理作业指导书", "type": "wi",
                "desc": "数据采集、清洗、划分、数据集说明（datasheet）",
                "standards": ["YY/T 1833.2 数据集通用要求"],
                "refs": [{"collection": "standards", "match": "数据集通用要求"}],
            },
            {
                "id": "L3-003", "name": "算法验证与性能评估作业指导书", "type": "wi",
                "desc": "模型性能指标、泛化与鲁棒性测试、影响因素分析方法",
                "standards": ["人工智能医疗器械注册审查指导原则", "YY/T 1858/1843"],
                "refs": [{"collection": "guidance-ai", "match": "人工智能医疗器械注册审查"}],
            },
            {
                "id": "L3-004", "name": "软件测试作业指导书", "type": "wi",
                "desc": "单元/集成/系统测试用例设计、执行与缺陷记录方法",
                "standards": ["IEC 62304 §5.6", "GB/T 25000.51"],
                "refs": [{"collection": "standards", "match": "YY_T0664"}],
            },
        ],
    },
    {
        "level": 4,
        "name": "第四级 · 记录与表单",
        "en": "Records / Forms — 客观证据",
        "desc": "数量最多，是审核/注册申报的直接证据，不可修改，须可追溯",
        "color": "#e53e3e",
        "documents": [
            {
                "id": "L4-001", "name": "风险管理档案（RMF）", "type": "record",
                "desc": "危害识别、风险分析、控制措施、剩余风险评价完整档案",
                "standards": ["ISO 14971 §3.5", "GB/T 42062"],
                "refs": [{"collection": "standards", "match": "风险管理对医疗器械"}],
            },
            {
                "id": "L4-002", "name": "软件需求规格说明（SRS）", "type": "record",
                "desc": "功能、性能、安全、接口需求记录",
                "standards": ["IEC 62304 §5.2", "YY/T 0664"],
                "refs": [{"collection": "standards", "match": "YY_T0664"}],
            },
            {
                "id": "L4-003", "name": "测试报告", "type": "record",
                "desc": "测试范围、用例、结果与通过判定记录",
                "standards": ["IEC 62304 §5.6"],
                "refs": [{"collection": "standards", "match": "YY_T0664"}],
            },
            {
                "id": "L4-004", "name": "临床评价报告", "type": "record",
                "desc": "临床数据收集、文献评价、等同性论证、临床评价结论",
                "standards": ["医疗器械临床评价技术指导原则", "AI辅助检测临床评价指导原则"],
                "refs": [
                    {"collection": "guidance-clinical", "match": "临床评价技术指导原则"},
                    {"collection": "guidance-ai-clinical", "match": "临床评价注册审查"},
                ],
            },
            {
                "id": "L4-005", "name": "CAPA 表单", "type": "record",
                "desc": "问题描述、根因分析、纠正措施、责任人、有效性验证",
                "standards": ["ISO 13485 §8.5.2"],
                "refs": [{"collection": "standards", "match": "质量管理体系用于法规"}],
            },
        ],
    },
    {
        "level": 0,
        "name": "医疗 AI 特有文件（贯穿各级）",
        "en": "AI-Specific Documents",
        "desc": "算法文档包 / 数据治理文件 / 变更控制文件",
        "color": "#3182ce",
        "documents": [
            {
                "id": "AI-001", "name": "算法文档包（模型卡 + 算法验证报告）", "type": "ai",
                "desc": "模型卡、数据集说明、算法验证报告，描述算法设计与性能",
                "standards": ["YY/T 1833.1 术语", "YY/T 1833.5 预训练模型", "人工智能医疗器械注册审查指导原则"],
                "refs": [
                    {"collection": "standards", "match": "术语"},
                    {"collection": "standards", "match": "预训练模型"},
                    {"collection": "guidance-ai", "match": "人工智能医疗器械注册审查"},
                ],
            },
            {
                "id": "AI-002", "name": "数据治理文件（数据管理计划 + 溯源记录）", "type": "ai",
                "desc": "数据管理计划、标注规范、数据溯源记录",
                "standards": ["YY/T 1833.2 数据集", "YY/T 1833.3 标注", "YY/T 1833.4 可追溯性"],
                "refs": [
                    {"collection": "standards", "match": "数据集通用要求"},
                    {"collection": "standards", "match": "数据标注通用要求"},
                    {"collection": "standards", "match": "可追溯性"},
                ],
            },
            {
                "id": "AI-003", "name": "变更控制文件（PCCP / 重大变更评审）", "type": "ai",
                "desc": "版本变更申请、PCCP 预定变更控制计划、重大变更评审",
                "standards": ["IEC 62304 §8", "人工智能医疗器械注册审查指导原则", "FDA PCCP"],
                "refs": [{"collection": "guidance-ai", "match": "人工智能医疗器械注册审查"}],
            },
        ],
    },
]

# ── 第一层：核心工作框架（9 大模块，用于地图顶部展示）─────────────────────────
CORE_MODULES = [
    {"id": "M1", "name": "文件体系", "sub": "四级文件架构", "group": "base"},
    {"id": "M2", "name": "风险管理", "sub": "ISO 14971 全周期", "group": "base"},
    {"id": "M3", "name": "软件开发", "sub": "IEC 62304 生命周期", "group": "base"},
    {"id": "M4", "name": "临床与性能", "sub": "验证确认评价", "group": "base"},
    {"id": "M5", "name": "上市后监督", "sub": "持续监测反馈", "group": "base"},
    {"id": "M6", "name": "数据管理", "sub": "训练/验证/测试集 · 数据标注质量", "group": "ai"},
    {"id": "M7", "name": "算法验证", "sub": "模型性能评估 · 泛化与鲁棒性", "group": "ai"},
    {"id": "M8", "name": "模型变更控制", "sub": "版本管理 · 持续学习评审", "group": "ai"},
    {"id": "M9", "name": "可解释性", "sub": "算法透明度 · 偏差监测", "group": "ai"},
    {"id": "M10", "name": "人员培训", "sub": "能力矩阵 · 上岗资质", "group": "support"},
    {"id": "M11", "name": "内外部审核", "sub": "内审 · 管理评审 · CAPA", "group": "support"},
    {"id": "M12", "name": "供应商与基础设施", "sub": "算力 · 云平台 · 外包管理", "group": "support"},
    {"id": "M13", "name": "注册申报与持续合规", "sub": "技术文档 · 临床评价报告 · 注册证维护 · 不良事件报告", "group": "registration"},
]

DOC_TYPE_LABELS = {
    "manual": "质量手册", "procedure": "程序文件", "wi": "作业指导书",
    "record": "记录表单", "ai": "AI 特有文件",
}


def get_all_documents() -> list[dict]:
    docs = []
    for lvl in DOC_LEVELS:
        for doc in lvl["documents"]:
            docs.append({**doc, "level": lvl["level"], "level_name": lvl["name"]})
    return docs


def get_document_by_id(doc_id: str) -> dict | None:
    for doc in get_all_documents():
        if doc["id"] == doc_id:
            return doc
    return None


def get_stats() -> dict:
    all_docs = get_all_documents()
    return {
        "total": len(all_docs),
        "levels": len([l for l in DOC_LEVELS if l["level"] > 0]),
        "core_modules": len(CORE_MODULES),
        "markets": ["NMPA", "FDA", "EU"],
        "by_type": {t: sum(1 for d in all_docs if d["type"] == t) for t in DOC_TYPE_LABELS},
    }


def get_framework() -> dict:
    return {
        "core_modules": CORE_MODULES,
        "regulatory_matrix": REGULATORY_MATRIX,
        "doc_levels": DOC_LEVELS,
        "stats": get_stats(),
    }
