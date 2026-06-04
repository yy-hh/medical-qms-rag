"""
QMS 实施路线图（Roadmap）

把"四级文件体系 + 档案汇编"重新组织成一条可执行的落地时间线：
从产品定义到上市后监督，分 8 个阶段，每个阶段下若干任务卡片。

每个任务卡片回答 7 件事：
  what       要做什么
  why        为什么做（法规/业务动机）
  input      输入（依赖的前置产物）
  output     输出（本任务交付物）
  standards  法规依据
  doc_ids    对应文件（引用 qms_framework 的文件 id，点击即可走 /api/generate/stream 生成模板）
  dossier    交付物最终归入哪些档案（DHF / DMR / DHR / TF / NMPA）

doc_ids 指向 qms_framework.DOC_LEVELS / DOSSIERS 中真实存在的 id，
因此生成模板时复用现有 get_document_by_id + RAG 检索逻辑，无需新增生成路径。
"""

ROADMAP = [
    {
        "phase": 1,
        "name": "启动与策划",
        "en": "Initiation & Planning",
        "goal": "明确产品定位、预期用途与法规路径，组建团队并立项",
        "duration": "约 2-4 周",
        "color": "#1a365d",
        "tasks": [
            {
                "id": "R1-1",
                "title": "产品定义与预期用途",
                "what": "确定产品的预期用途、适应症、目标人群、使用环境与核心功能边界，形成产品描述。",
                "why": "预期用途是后续风险分级、法规分类、临床评价与注册路径的根本依据，必须最先锁定。",
                "input": "市场需求、临床调研、竞品分析",
                "output": "产品定义文档 / 预期用途声明",
                "standards": ["IMDRF SaMD 框架", "NMPA 人工智能医疗器械注册审查指导原则"],
                "doc_ids": [],
                "dossier": ["DHF", "TF", "NMPA"],
            },
            {
                "id": "R1-2",
                "title": "法规分类与注册路径规划",
                "what": "确定产品在 NMPA/FDA/EU 各市场的管理类别（二/三类）、审批通道与适用法规清单。",
                "why": "类别决定了体系深度、临床要求与申报资料范围，路径错误会导致返工与上市延期。",
                "input": "产品定义、三国法规对照矩阵",
                "output": "法规策略报告 / 适用标准清单",
                "standards": ["医疗器械监督管理条例", "21 CFR Part 820", "EU MDR 2017/745"],
                "doc_ids": ["L2-012"],
                "dossier": ["NMPA", "TF"],
            },
            {
                "id": "R1-3",
                "title": "项目立项与团队组建",
                "what": "确定项目范围、里程碑、资源与组织职责（含管理者代表、质量、研发、临床、注册）。",
                "why": "ISO 13485 要求最高管理者承诺并明确职责权限，团队与资源是体系运行的前提。",
                "input": "法规策略、公司资源",
                "output": "项目计划 / 组织架构与职责矩阵",
                "standards": ["ISO 13485 §5.1", "§5.5"],
                "doc_ids": [],
                "dossier": ["DHF"],
            },
        ],
    },
    {
        "phase": 2,
        "name": "质量管理体系建立",
        "en": "QMS Establishment",
        "goal": "搭建 ISO 13485 文件体系骨架，发布质量手册与核心程序文件",
        "duration": "约 6-10 周",
        "color": "#2b6cb0",
        "tasks": [
            {
                "id": "R2-1",
                "title": "编写质量手册与质量方针",
                "what": "定义 QMS 范围、质量方针与目标、过程及其相互关系，形成顶层纲领文件。",
                "why": "质量手册是体系的纲领，注册与审核时第一份被审阅的文件。",
                "input": "组织架构、法规策略",
                "output": "质量手册",
                "standards": ["ISO 13485 §4.2.2", "GB/T 42061 §4.2.2"],
                "doc_ids": ["L1-001"],
                "dossier": ["TF", "NMPA"],
            },
            {
                "id": "R2-2",
                "title": "建立文件与记录控制程序",
                "what": "规定文件起草、评审、批准、发布、变更、作废及记录的标识、存储与保留规则。",
                "why": "文件/记录控制是 QMS 的地基，没有受控文件，其余所有程序都无法形成有效证据。",
                "input": "质量手册",
                "output": "文件与记录控制程序",
                "standards": ["ISO 13485 §4.2.4", "§4.2.5"],
                "doc_ids": ["L2-001"],
                "dossier": ["DHF"],
            },
            {
                "id": "R2-3",
                "title": "建立管理评审与内审机制",
                "what": "制定管理评审程序与内部审核程序，明确输入输出、频率与跟踪闭环。",
                "why": "管理评审与内审是体系自我检查与持续改进的机制，也是认证审核的必查项。",
                "input": "质量手册、文件控制程序",
                "output": "管理评审程序 / 内部审核程序",
                "standards": ["ISO 13485 §5.6", "§8.2.2"],
                "doc_ids": ["L2-002", "L2-010"],
                "dossier": ["DHF"],
            },
            {
                "id": "R2-4",
                "title": "建立采购与供应商管理程序",
                "what": "规定外包开发商、云服务商、组件供应商的评估、合同与绩效监控流程。",
                "why": "SaMD 大量依赖云平台与外包，供应商失控会直接传导为产品质量与合规风险。",
                "input": "质量手册",
                "output": "采购与供应商管理程序",
                "standards": ["ISO 13485 §7.4"],
                "doc_ids": ["L2-011"],
                "dossier": ["DHF"],
            },
        ],
    },
    {
        "phase": 3,
        "name": "风险管理启动",
        "en": "Risk Management",
        "goal": "建立贯穿全生命周期的风险管理流程并完成初始风险分析",
        "duration": "约 3-5 周（持续更新）",
        "color": "#c53030",
        "tasks": [
            {
                "id": "R3-1",
                "title": "建立风险管理程序",
                "what": "按 ISO 14971 定义风险分析、评价、控制、剩余风险评价与风险管理报告的全流程。",
                "why": "风险管理是医疗器械的核心，贯穿设计、验证、临床到上市后，须在开发前先建立。",
                "input": "产品定义、预期用途",
                "output": "风险管理程序",
                "standards": ["ISO 14971:2019", "GB/T 42062", "YY/T 0316"],
                "doc_ids": ["L2-006"],
                "dossier": ["DHF", "TF", "NMPA"],
            },
            {
                "id": "R3-2",
                "title": "初始风险分析与风险管理档案",
                "what": "识别危害、估计风险、制定控制措施，建立并持续维护风险管理档案（RMF）。",
                "why": "风险分析输出会驱动软件需求与设计，是设计输入的重要来源，需尽早启动并持续更新。",
                "input": "风险管理程序、产品定义",
                "output": "风险管理档案（RMF）",
                "standards": ["ISO 14971 §3.5", "GB/T 42062"],
                "doc_ids": ["L4-001"],
                "dossier": ["DHF", "TF", "NMPA"],
            },
        ],
    },
    {
        "phase": 4,
        "name": "软件设计与开发",
        "en": "Software Design & Development",
        "goal": "按 IEC 62304 建立软件生命周期，产出需求、设计与配置管理证据",
        "duration": "约 8-16 周",
        "color": "#dd6b20",
        "tasks": [
            {
                "id": "R4-1",
                "title": "建立软件开发生命周期程序",
                "what": "按 IEC 62304 定义软件安全分级及各开发阶段的活动、输入输出与验收准则。",
                "why": "IEC 62304 是 SaMD 的强制软件过程标准，决定了开发各阶段需留存哪些客观证据。",
                "input": "风险管理档案、产品定义",
                "output": "软件开发生命周期程序",
                "standards": ["IEC 62304 §5", "YY/T 0664"],
                "doc_ids": ["L2-003"],
                "dossier": ["DHF", "DMR"],
            },
            {
                "id": "R4-2",
                "title": "编写软件需求规格说明（SRS）",
                "what": "形成功能、性能、安全、接口需求，并与风险控制措施、预期用途双向追溯。",
                "why": "SRS 是设计与测试的基线，也是注册软件研究资料的核心；需求缺陷成本最高。",
                "input": "风险管理档案、产品定义",
                "output": "软件需求规格说明（SRS）",
                "standards": ["IEC 62304 §5.2", "YY/T 0664"],
                "doc_ids": ["L4-002"],
                "dossier": ["DHF", "DMR", "NMPA"],
            },
            {
                "id": "R4-3",
                "title": "建立配置管理与缺陷管理程序",
                "what": "规定版本管理、变更控制、基线与配置审计，以及缺陷的发现、分类、修复与关闭。",
                "why": "可追溯的版本与缺陷记录是 DHR 与放行的基础，缺失会导致版本无法证明可控。",
                "input": "软件开发生命周期程序",
                "output": "配置管理程序 / 缺陷管理程序",
                "standards": ["IEC 62304 §8", "§9", "YY/T 0664"],
                "doc_ids": ["L2-004", "L2-005"],
                "dossier": ["DMR", "DHR"],
            },
        ],
    },
    {
        "phase": 5,
        "name": "数据与算法治理（AI 专项）",
        "en": "Data & Algorithm Governance",
        "goal": "建立数据全流程治理与算法验证证据，形成算法文档包",
        "duration": "约 8-14 周",
        "color": "#3182ce",
        "tasks": [
            {
                "id": "R5-1",
                "title": "建立数据治理与数据集管理",
                "what": "制定数据管理计划、数据集构建与标注作业指导书，留存数据溯源记录。",
                "why": "AI 器械性能取决于数据质量，监管要求数据来源、标注与划分全程可追溯。",
                "input": "产品定义、预期用途",
                "output": "数据治理文件 / 数据集与标注 WI",
                "standards": ["YY/T 1833.2 数据集", "YY/T 1833.3 标注", "YY/T 1833.4 可追溯性"],
                "doc_ids": ["AI-002", "L3-002", "L3-001"],
                "dossier": ["DHF", "TF", "NMPA"],
            },
            {
                "id": "R5-2",
                "title": "算法验证与性能评估",
                "what": "制定算法验证 WI，开展性能指标、泛化与鲁棒性、影响因素分析。",
                "why": "算法性能证据是临床评价与注册审评的核心，决定产品能否证明安全有效。",
                "input": "数据集、SRS",
                "output": "算法验证与性能评估报告",
                "standards": ["NMPA 人工智能医疗器械注册审查指导原则", "YY/T 1858/1843"],
                "doc_ids": ["L3-003"],
                "dossier": ["DHF", "TF", "NMPA"],
            },
            {
                "id": "R5-3",
                "title": "编制算法文档包（模型卡）",
                "what": "汇编模型卡、数据集说明与算法验证报告，描述算法设计、训练与性能。",
                "why": "算法文档包是 AI 器械区别于普通软件的关键申报材料，需结构化呈现算法可解释性。",
                "input": "数据治理文件、算法验证报告",
                "output": "算法文档包",
                "standards": ["YY/T 1833.1 术语", "YY/T 1833.5 预训练模型"],
                "doc_ids": ["AI-001"],
                "dossier": ["DHF", "TF", "NMPA"],
            },
        ],
    },
    {
        "phase": 6,
        "name": "验证与确认（V&V）",
        "en": "Verification & Validation",
        "goal": "完成软件测试、可用性与网络安全验证，形成测试报告",
        "duration": "约 6-10 周",
        "color": "#38a169",
        "tasks": [
            {
                "id": "R6-1",
                "title": "软件测试与测试报告",
                "what": "制定软件测试 WI，开展单元/集成/系统测试并形成测试报告。",
                "why": "测试报告证明软件满足 SRS，是 DHF/DHR 与软件研究资料的直接证据。",
                "input": "SRS、软件设计",
                "output": "软件测试 WI / 测试报告",
                "standards": ["IEC 62304 §5.6", "GB/T 25000.51"],
                "doc_ids": ["L3-004", "L4-003"],
                "dossier": ["DHF", "DHR", "NMPA"],
            },
            {
                "id": "R6-2",
                "title": "可用性工程验证",
                "what": "建立可用性工程程序，开展形成性与总结性评价，识别使用相关风险。",
                "why": "IEC 62366-1 要求证明界面在预期使用环境下安全，使用错误是医疗器械重要风险源。",
                "input": "SRS、风险管理档案",
                "output": "可用性工程程序 / 可用性评价报告",
                "standards": ["IEC 62366-1", "可用性工程注册审查指导原则"],
                "doc_ids": ["L2-007"],
                "dossier": ["DHF", "TF", "NMPA"],
            },
            {
                "id": "R6-3",
                "title": "网络安全验证",
                "what": "建立网络安全管理程序，开展威胁建模、安全测试与漏洞管理。",
                "why": "联网 SaMD 须证明网络安全可控，是 NMPA/FDA 注册的强制审查项。",
                "input": "软件架构、SRS",
                "output": "网络安全管理程序 / 安全测试报告",
                "standards": ["YY/T 1833", "医疗器械网络安全注册审查指导原则", "IEC 81001-5-1"],
                "doc_ids": ["L2-008"],
                "dossier": ["DHF", "TF", "NMPA"],
            },
        ],
    },
    {
        "phase": 7,
        "name": "临床评价与注册申报",
        "en": "Clinical Evaluation & Registration",
        "goal": "完成临床评价并汇编技术文档与注册申报资料",
        "duration": "约 10-20 周",
        "color": "#805ad5",
        "tasks": [
            {
                "id": "R7-1",
                "title": "临床评价",
                "what": "收集临床数据、开展文献评价或临床试验，形成临床评价报告。",
                "why": "临床评价证明产品临床有效与安全，是注册申报与 CE 技术文档的必备要件。",
                "input": "算法验证报告、风险管理档案",
                "output": "临床评价报告",
                "standards": ["医疗器械临床评价技术指导原则", "AI辅助检测临床评价指导原则"],
                "doc_ids": ["L4-004"],
                "dossier": ["TF", "NMPA"],
            },
            {
                "id": "R7-2",
                "title": "汇编技术文档与注册申报资料",
                "what": "按各市场要求汇编 DHF/DMR/技术文档(TF)/注册申报资料(NMPA)。",
                "why": "汇编不是新写文件，而是把已有体系产物按法规结构归档，直接决定能否通过受理与审评。",
                "input": "前述全部交付物",
                "output": "DHF / DMR / 技术文档 / 注册申报资料",
                "standards": ["EU MDR Annex II/III", "医疗器械注册与备案管理办法"],
                "doc_ids": ["DOSSIER-DHF", "DOSSIER-DMR", "DOSSIER-TF", "DOSSIER-NMPA"],
                "dossier": ["DHF", "DMR", "TF", "NMPA"],
            },
        ],
    },
    {
        "phase": 8,
        "name": "上市后与持续合规",
        "en": "Post-Market & Continuous Compliance",
        "goal": "建立上市后监督、CAPA 与变更控制，维持体系持续运行",
        "duration": "持续（产品全生命周期）",
        "color": "#4a5568",
        "tasks": [
            {
                "id": "R8-1",
                "title": "建立上市后监督与不良事件程序",
                "what": "建立上市后数据收集、趋势分析、不良事件上报与再评价机制。",
                "why": "上市后监督是法规强制义务，也是 AI 器械监测真实世界性能漂移的关键。",
                "input": "已上市产品、临床数据",
                "output": "上市后监督与不良事件程序",
                "standards": ["医疗器械不良事件监测和再评价管理办法", "ISO 13485 §8.2.1"],
                "doc_ids": ["L2-013"],
                "dossier": ["TF", "NMPA"],
            },
            {
                "id": "R8-2",
                "title": "建立 CAPA 闭环",
                "what": "建立纠正和预防措施程序与 CAPA 表单，对不合格、投诉、审核发现做根因闭环。",
                "why": "CAPA 是体系持续改进的引擎，审核中 CAPA 失效是最常见的不符合项。",
                "input": "上市后数据、内审/投诉",
                "output": "CAPA 程序 / CAPA 表单",
                "standards": ["ISO 13485 §8.5.2", "§8.5.3", "21 CFR 820.100"],
                "doc_ids": ["L2-009", "L4-005"],
                "dossier": ["DHR"],
            },
            {
                "id": "R8-3",
                "title": "建立模型变更控制（PCCP）",
                "what": "建立变更控制文件与 PCCP 预定变更控制计划，规范模型迭代与重大变更评审。",
                "why": "AI 模型会持续迭代，PCCP 让预期内的更新无需每次重新注册，是 AI 器械合规关键。",
                "input": "上市后性能监测、变更需求",
                "output": "变更控制文件 / PCCP",
                "standards": ["IEC 62304 §8", "FDA PCCP", "NMPA 人工智能医疗器械注册审查指导原则"],
                "doc_ids": ["AI-003"],
                "dossier": ["DHR", "DMR"],
            },
        ],
    },
]

# 档案缩写 → 中文标签（用于卡片归档徽章展示）
DOSSIER_LABELS = {
    "DHF": "DHF 设计历史文档",
    "DMR": "DMR 器械主记录",
    "DHR": "DHR 器械历史记录",
    "TF": "技术文档（EU）",
    "NMPA": "注册申报资料",
}


def _doc_ref(doc_id: str) -> dict:
    """把 doc_id 解析成 {id, name, type}，供前端展示"对应文件"并触发生成。"""
    from app.core.qms_framework import get_document_by_id

    doc = get_document_by_id(doc_id)
    if not doc:
        return {"id": doc_id, "name": doc_id, "type": "unknown", "exists": False}
    return {
        "id": doc_id,
        "name": doc.get("name", doc_id),
        "type": doc.get("type", "dossier"),
        "exists": True,
    }


def _enrich_task(task: dict) -> dict:
    """把任务的 doc_ids 解析为带名称的对应文件列表。"""
    return {
        **task,
        "docs": [_doc_ref(d) for d in task.get("doc_ids", [])],
        "dossier_labels": [
            {"key": k, "label": DOSSIER_LABELS.get(k, k)} for k in task.get("dossier", [])
        ],
    }


def get_roadmap() -> dict:
    phases = []
    total_tasks = 0
    for phase in ROADMAP:
        tasks = [_enrich_task(t) for t in phase["tasks"]]
        total_tasks += len(tasks)
        phases.append({**phase, "tasks": tasks})
    return {
        "phases": phases,
        "stats": {
            "total_phases": len(ROADMAP),
            "total_tasks": total_tasks,
            "dossier_labels": DOSSIER_LABELS,
        },
    }


def get_task_by_id(task_id: str) -> dict | None:
    for phase in ROADMAP:
        for task in phase["tasks"]:
            if task["id"] == task_id:
                return {
                    **_enrich_task(task),
                    "phase": phase["phase"],
                    "phase_name": phase["name"],
                }
    return None
