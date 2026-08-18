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
        "name": "质量手册",
        "en": "Quality Manual",
        "desc": "约 1 本，20-50 页，全公司唯一，顶层政策",
        "color": "#805ad5",
        "documents": [
            {
                "id": "QMS-QM-001",
                "category": "质量保证",
                "name": "质量手册",
                "type": "manual",
                "desc": "描述 QMS 范围、质量方针、组织机构与职责、过程及其相互关系，是体系纲领性文件",
                "standards": [
                    "ISO 13485 §4.2.2",
                    "GB/T 42061 §4.2.2",
                    "21 CFR 820",
                    "EU MDR Annex IX",
                    "独立软件现场检查指导原则 §4.1.2"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    },
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            },
            {
                "id": "QMS-QM-002",
                "category": "质量保证",
                "name": "质量方针与目标文件",
                "type": "manual",
                "parent": "QMS-QP-036",
                "desc": "经批准发布的质量方针，以及分解到各层级、可测量的质量目标",
                "standards": [
                    "ISO 13485 §5.3",
                    "§5.4.1",
                    "GB/T 42061 §5.3/§5.4"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            }
        ]
    },
    {
        "level": 2,
        "name": "程序文件（SOP）",
        "en": "Standard Operating Procedure",
        "desc": "20-60 份，跨部门流程，回答\"谁做、何时做\"",
        "color": "#38a169",
        "documents": [
            {
                "id": "QMS-QP-001",
                "category": "文件和数据管理",
                "name": "文件与记录控制程序",
                "type": "procedure",
                "desc": "文件起草、评审、批准、发布、变更、作废；记录标识、存储、保留",
                "standards": [
                    "ISO 13485 §4.2.4",
                    "§4.2.5",
                    "独立软件现场检查指导原则 §4.2/§4.4"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-002",
                "category": "质量保证",
                "name": "管理评审程序",
                "type": "procedure",
                "desc": "管理评审的输入、输出、频率与记录要求",
                "standards": [
                    "ISO 13485 §5.6",
                    "独立软件现场检查指导原则 §11.9.1"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-003",
                "scope": "sw",
                "category": "设计开发",
                "name": "软件开发生命周期程序",
                "type": "procedure",
                "desc": "按 IEC 62304 定义软件开发各阶段活动、输入输出与验收准则",
                "standards": [
                    "IEC 62304 §5",
                    "YY/T 0664"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    },
                    {
                        "collection": "guidance-software",
                        "match": "医疗器械软件注册审查"
                    }
                ]
            },
            {
                "id": "QMS-QP-004",
                "scope": "sw",
                "category": "设计开发",
                "name": "软件配置管理与版本控制程序",
                "type": "procedure",
                "desc": "软件版本管理、变更控制、基线管理、配置审计",
                "standards": [
                    "IEC 62304 §8",
                    "YY/T 0664",
                    "独立软件现场检查指导原则 §5.4"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    }
                ]
            },
            {
                "id": "QMS-QP-005",
                "scope": "sw",
                "category": "设计开发",
                "name": "软件问题与缺陷管理程序",
                "type": "procedure",
                "desc": "软件缺陷的发现、记录、分类、修复与关闭",
                "standards": [
                    "IEC 62304 §9",
                    "YY/T 0664",
                    "独立软件现场检查指导原则 §5.17"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    }
                ]
            },
            {
                "id": "QMS-QP-006",
                "category": "质量保证",
                "name": "风险管理程序",
                "type": "procedure",
                "desc": "风险分析、评价、控制、剩余风险评价、风险管理报告全流程",
                "standards": [
                    "ISO 14971:2019",
                    "GB/T 42062",
                    "YY/T 0316"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "风险管理对医疗器械"
                    },
                    {
                        "collection": "standards",
                        "match": "0316"
                    }
                ]
            },
            {
                "id": "QMS-QP-007",
                "category": "设计开发",
                "name": "可用性工程程序",
                "type": "procedure",
                "desc": "用户研究、使用规范、UI 设计、形成性与总结性评价",
                "standards": [
                    "IEC 62366-1",
                    "可用性工程注册审查指导原则"
                ],
                "refs": [
                    {
                        "collection": "guidance-usability",
                        "match": "可用性工程注册审查"
                    }
                ]
            },
            {
                "id": "QMS-QP-008",
                "scope": "sw",
                "category": "网络安全",
                "name": "网络安全管理程序",
                "type": "procedure",
                "desc": "软件全生命周期网络安全活动：威胁建模、安全测试、漏洞管理",
                "standards": [
                    "YY/T 1833",
                    "医疗器械网络安全注册审查指导原则",
                    "IEC 81001-5-1"
                ],
                "refs": [
                    {
                        "collection": "guidance-cybersecurity",
                        "match": "网络安全注册审查"
                    },
                    {
                        "collection": "cybersecurity",
                        "match": "网络安全法"
                    }
                ]
            },
            {
                "id": "QMS-QP-009",
                "category": "分析与改进",
                "name": "纠正和预防措施（CAPA）程序",
                "type": "procedure",
                "desc": "不合格、投诉、审核发现的根因分析、纠正措施、有效性验证",
                "standards": [
                    "ISO 13485 §8.5.2",
                    "§8.5.3",
                    "21 CFR 820.100",
                    "独立软件现场检查指导原则 §11.4.1"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-010",
                "category": "质量保证",
                "name": "内部审核程序",
                "type": "procedure",
                "desc": "内审计划、审核员资质、执行、发现记录与跟踪关闭",
                "standards": [
                    "ISO 13485 §8.2.2",
                    "独立软件现场检查指导原则 §11.8.1"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-011",
                "category": "采购与物料管理",
                "name": "采购与供应商管理程序",
                "type": "procedure",
                "desc": "外包开发商、云服务商、组件供应商的评估、合同与绩效监控",
                "standards": [
                    "ISO 13485 §7.4",
                    "独立软件现场检查指导原则 §6"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-012",
                "category": "质量保证",
                "name": "注册申报管理程序",
                "type": "procedure",
                "desc": "产品注册/备案的准备、提交、沟通、维护与变更申报",
                "standards": [
                    "医疗器械注册与备案管理办法",
                    "产品技术要求编写指导原则"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "注册与备案管理办法"
                    },
                    {
                        "collection": "guidance-registration",
                        "match": "产品技术要求编写"
                    }
                ]
            },
            {
                "id": "QMS-QP-013",
                "category": "分析与改进",
                "name": "上市后监督与不良事件程序",
                "type": "procedure",
                "desc": "上市后数据收集、趋势分析、不良事件上报、再评价",
                "standards": [
                    "医疗器械不良事件监测和再评价管理办法",
                    "ISO 13485 §8.2.1"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "不良事件监测"
                    }
                ]
            },
            {
                "id": "QMS-QP-014",
                "category": "机构与人员",
                "name": "人力资源控制程序",
                "type": "procedure",
                "desc": "岗位能力要求、培训、考核与资质管理，含开发/测试黑盒不兼任要求",
                "standards": [
                    "ISO 13485 §6.2",
                    "独立软件现场检查指导原则 §1.6/§1.7/§1.8"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-015",
                "category": "厂房设施与设备",
                "name": "设施和设备管理控制程序",
                "type": "procedure",
                "desc": "软件开发/测试所用软硬件设备与工具的验收、运行、维护、台账与报废",
                "standards": [
                    "ISO 13485 §6.3",
                    "独立软件现场检查指导原则 §3.1/§3.3"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-016",
                "category": "厂房设施与设备",
                "name": "工作环境控制程序",
                "type": "procedure",
                "desc": "开发测试环境的定期验证、更新升级、病毒防护、数据备份与恢复要求",
                "standards": [
                    "ISO 13485 §6.4",
                    "独立软件·附录 §2.2",
                    "独立软件现场检查指导原则 §3.2"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-QP-017",
                "category": "销售与售后服务",
                "name": "与顾客有关的过程控制程序",
                "type": "procedure",
                "desc": "顾客需求识别、合同/订单评审、与顾客的沟通",
                "standards": [
                    "ISO 13485 §7.2"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-018",
                "scope": "sw",
                "category": "设计开发",
                "name": "设计开发控制程序",
                "type": "procedure",
                "desc": "设计策划、输入、输出、评审、验证、确认、转换、变更的总体控制流程",
                "standards": [
                    "ISO 13485 §7.3",
                    "IEC 62304 §5",
                    "独立软件现场检查指导原则 §5.8~5.16"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "医疗器械软件注册审查"
                    },
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    }
                ]
            },
            {
                "id": "QMS-QP-019",
                "category": "生产管理与追溯",
                "name": "生产过程控制程序",
                "type": "procedure",
                "desc": "软件产品的构建、复制、许可授权等生产过程受控要求",
                "standards": [
                    "ISO 13485 §7.5.1",
                    "独立软件·附录 §2.5"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-QP-020",
                "category": "生产管理与追溯",
                "name": "标识和可追溯性控制程序",
                "type": "procedure",
                "desc": "产品/软件版本的标识与可追溯性范围、程度、必要记录",
                "standards": [
                    "ISO 13485 §7.5.8/§7.5.9",
                    "独立软件现场检查指导原则 §7.6/§7.8"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-021",
                "category": "生产管理与追溯",
                "name": "产品防护控制程序",
                "type": "procedure",
                "desc": "软件产品及存储媒介的标识、搬运、包装、贮存与保护要求",
                "standards": [
                    "ISO 13485 §7.5.11",
                    "独立软件现场检查指导原则 §7.10"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-022",
                "category": "厂房设施与设备",
                "name": "监视和测量装置控制程序",
                "type": "procedure",
                "desc": "用于检验的计算机软件/测量装置的确认、校准与状态标识",
                "standards": [
                    "ISO 13485 §7.6",
                    "独立软件现场检查指导原则 §8.2"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-023",
                "category": "销售与售后服务",
                "name": "信息反馈控制程序",
                "type": "procedure",
                "desc": "从生产和生产后阶段收集顾客反馈信息并跟踪分析",
                "standards": [
                    "ISO 13485 §8.2.1",
                    "独立软件现场检查指导原则 §9.5"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-024",
                "category": "分析与改进",
                "name": "客户投诉处理控制程序",
                "type": "procedure",
                "desc": "投诉的接收、调查、评价、处理与记录，及是否需上报/召回判定",
                "standards": [
                    "ISO 13485 §8.2.2",
                    "独立软件现场检查指导原则 §11.1.1"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-025",
                "category": "分析与改进",
                "name": "不良事件报告控制程序",
                "type": "procedure",
                "desc": "可疑不良事件的识别、评价、上报程序与时限、再评价启动",
                "standards": [
                    "医疗器械不良事件监测和再评价管理办法",
                    "独立软件现场检查指导原则 §11.2.1"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "不良事件监测"
                    }
                ]
            },
            {
                "id": "QMS-QP-026",
                "category": "分析与改进",
                "name": "产品召回控制程序",
                "type": "procedure",
                "desc": "存在安全隐患医疗器械的召回判定、实施、报告与效果评估",
                "standards": [
                    "医疗器械召回管理办法",
                    "独立软件现场检查指导原则 §11.5.1"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "不良事件监测"
                    }
                ]
            },
            {
                "id": "QMS-QP-027",
                "category": "质量控制与放行",
                "name": "过程偏差处理控制程序",
                "type": "procedure",
                "desc": "过程偏差的识别、记录、评估与处置",
                "standards": [
                    "ISO 13485 §8.3"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-028",
                "category": "质量控制与放行",
                "name": "产品的监视和测量控制程序",
                "type": "procedure",
                "desc": "软件产品检验规程、检验报告出具与放行前测量要求",
                "standards": [
                    "ISO 13485 §8.2.6",
                    "独立软件现场检查指导原则 §8.3"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-029",
                "category": "质量控制与放行",
                "name": "不合格品控制程序",
                "type": "procedure",
                "desc": "不合格品的标识、隔离、评审、让步接受、返工与处置",
                "standards": [
                    "ISO 13485 §8.3",
                    "独立软件现场检查指导原则 §10"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-030",
                "category": "分析与改进",
                "name": "数据统计与分析控制程序",
                "type": "procedure",
                "desc": "收集分析质量/不良事件/反馈/体系运行数据，涵盖软件缺陷与网络安全事件",
                "standards": [
                    "ISO 13485 §8.4",
                    "独立软件·附录 §2.8.1",
                    "独立软件现场检查指导原则 §11.3"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-QP-031",
                "scope": "sw",
                "category": "设计开发",
                "name": "软件可追溯性分析控制程序",
                "type": "procedure",
                "desc": "追踪需求-设计-源代码-测试-风险关系并形成可追溯性分析报告以供评审",
                "standards": [
                    "独立软件·附录 §2.3.6",
                    "IEC 62304",
                    "独立软件现场检查指导原则 §5.6"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-QP-032",
                "scope": "sw",
                "category": "设计开发",
                "name": "配置管理控制程序",
                "type": "procedure",
                "desc": "配置标识、变更控制、配置状态记录、配置审计（与L2-004版本控制互补，侧重配置项管理）",
                "standards": [
                    "IEC 62304 §8",
                    "独立软件·附录 §2.3.4",
                    "独立软件现场检查指导原则 §5.4"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-QP-033",
                "scope": "sw",
                "category": "设计开发",
                "name": "软件生存周期过程控制程序",
                "type": "procedure",
                "desc": "结合软件生存周期模型确定策划-需求-设计-编码-验证确认-更新-停运等全过程活动要求",
                "standards": [
                    "独立软件·附录 §2.3.1",
                    "IEC 62304",
                    "YY/T 0664",
                    "独立软件现场检查指导原则 §5.1"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-QP-034",
                "scope": "sw",
                "category": "网络安全",
                "name": "网络安全应急响应控制程序",
                "type": "procedure",
                "desc": "网络安全事件风险管理、应急响应措施验证、用户告知、召回等活动要求",
                "standards": [
                    "独立软件·附录 §2.8.2",
                    "医疗器械网络安全注册审查指导原则",
                    "独立软件现场检查指导原则 §11.7"
                ],
                "refs": [
                    {
                        "collection": "guidance-cybersecurity",
                        "match": "网络安全注册审查"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-QP-035",
                "category": "质量保证",
                "name": "风险分析和识别评价控制程序",
                "type": "procedure",
                "desc": "内外部环境识别、风险和机遇识别评价（体系层风险，区别于产品风险L2-006）",
                "standards": [
                    "ISO 13485 §4.1.2/§8.5.1",
                    "ISO 14971"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-036",
                "category": "机构与人员",
                "name": "管理职责与组织程序",
                "type": "procedure",
                "desc": "任命管理者代表、制定质量方针与可测量质量目标、明确组织架构与各岗位职责权限及相互沟通",
                "standards": [
                    "ISO 13485 §5.5",
                    "§5.3",
                    "§5.4",
                    "GB/T 42061 §5.5",
                    "独立软件现场检查指导原则 §1"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    },
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            },
            {
                "id": "QMS-QP-037",
                "category": "质量保证",
                "name": "质量管理体系策划和过程管理程序",
                "type": "procedure",
                "desc": "对质量管理体系所需过程进行识别、策划、监视与改进，明确过程输入输出、判定准则、相互作用及质量保证活动安排",
                "standards": [
                    "ISO 13485 §4.1",
                    "GB/T 42061 §4.1",
                    "医疗器械生产质量管理规范(2025)·质量保证章"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    },
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            },
            {
                "id": "QMS-QP-038",
                "category": "委托生产与外协加工",
                "name": "委托生产与外协加工控制程序",
                "type": "procedure",
                "desc": "注册人制度下委托生产/外协加工的受托方评估、质量协议签订、过程监督与放行控制要求",
                "standards": [
                    "医疗器械生产质量管理规范(2025)·委托生产与外协加工章",
                    "ISO 13485 §7.4",
                    "医疗器械注册与备案管理办法"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    },
                    {
                        "collection": "regulations",
                        "match": "注册与备案管理办法"
                    }
                ]
            },
            {
                "id": "QMS-QP-039",
                "category": "验证与确认",
                "name": "验证与确认控制程序",
                "type": "procedure",
                "desc": "对设备、工艺、软件、方法等的验证与确认活动进行策划、实施、再验证与记录管理的总体控制要求",
                "standards": [
                    "医疗器械生产质量管理规范(2025)·验证与确认章",
                    "ISO 13485 §7.5.6",
                    "GB/T 42061 §7.5.6"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    },
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-QP-040",
                "scope": "sw",
                "category": "验证与确认",
                "name": "计算机软件确认控制程序",
                "type": "procedure",
                "desc": "对用于生产、质量检验和质量管理的计算机软件在初次使用前及变更后进行确认的活动、方法与记录要求",
                "standards": [
                    "ISO 13485 §4.1.6",
                    "GB/T 42061 §4.1.6",
                    "医疗器械生产质量管理规范(2025)·验证与确认章"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    },
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            },
            {
                "id": "QMS-QP-041",
                "category": "质量控制与放行",
                "name": "返工控制程序",
                "type": "procedure",
                "desc": "不合格品返工的作业指导、重新检验与重新验证要求，返工风险评估",
                "standards": [
                    "生产质量规范2025 §89",
                    "ISO 13485 §8.3"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            }
        ]
    },
    {
        "level": 3,
        "name": "作业指导书/规程",
        "en": "Work Instructions / SOPs",
        "desc": "管理规程、作业指导书、检验/工艺规程等（QMS-SMP/WI/TD）",
        "color": "#dd6b20",
        "documents": [
            {
                "id": "QMS-SMP-062",
                "category": "生产管理与追溯",
                "name": "UDI管理制度/记录",
                "type": "system",
                "parent": "QMS-QP-020",
                "desc": "UDI 实施的职责、赋码流程、数据库维护与变更管理制度及实施记录",
                "standards": [
                    "医疗器械唯一标识系统规则",
                    "医疗器械生产质量管理规范(2025)·标识可追溯",
                    "ISO 13485 §7.5.8"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    },
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-SMP-063",
                "category": "质量保证",
                "name": "质量风险管理制度",
                "type": "system",
                "parent": "QMS-QP-006",
                "desc": "规定质量风险的识别、评估、控制与监控职责流程的制度性文件，落实风险管理程序",
                "standards": [
                    "ISO 14971:2019",
                    "医疗器械生产质量管理规范(2025)·质量保证章",
                    "GB/T 42062"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "风险管理对医疗器械"
                    },
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            },
            {
                "id": "QMS-SMP-064",
                "category": "机构与人员",
                "name": "培训管理制度",
                "type": "system",
                "parent": "QMS-QP-014",
                "desc": "规定人员培训的需求识别、计划、实施、考核与档案管理职责与要求的制度性文件",
                "standards": [
                    "ISO 13485 §6.2",
                    "医疗器械生产质量管理规范(2025)·机构与人员"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    },
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            },
            {
                "id": "QMS-SMP-065",
                "category": "文件和数据管理",
                "name": "技术文件管理制度",
                "type": "system",
                "parent": "QMS-QP-001",
                "desc": "规定产品技术文件(设计输出、图纸、规格、源代码标识等)的编制、审批、归档与保密要求的制度",
                "standards": [
                    "ISO 13485 §4.2.3",
                    "§4.2.4",
                    "医疗器械生产质量管理规范(2025)·文件管理"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    },
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            },
            {
                "id": "QMS-SMP-066",
                "category": "文件和数据管理",
                "name": "电子记录与数据完整性管理制度",
                "type": "system",
                "parent": "QMS-QP-001",
                "desc": "规定电子记录的生成、审计追踪、权限、电子签名、备份与数据完整性(ALCOA+)控制要求的制度",
                "standards": [
                    "ISO 13485 §4.2.5",
                    "医疗器械生产质量管理规范(2025)·数智化与数据完整性",
                    "21 CFR Part 11"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    },
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            },
            {
                "id": "QMS-SMP-067",
                "category": "生产管理与追溯",
                "name": "留样管理制度",
                "type": "system",
                "parent": "QMS-QP-019",
                "desc": "规定产品(含软件发布版本/介质)留样的抽取、标识、贮存、观察与销毁职责与要求的制度",
                "standards": [
                    "ISO 13485 §7.5.1",
                    "医疗器械生产质量管理规范(2025)·质量保证章"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    },
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            },
            {
                "id": "QMS-SMP-068",
                "category": "生产管理与追溯",
                "name": "标签和说明书管理制度",
                "type": "system",
                "parent": "QMS-QP-020",
                "desc": "规定标签、说明书的设计、审核、批准、版本控制、印制与发放的制度性文件",
                "standards": [
                    "医疗器械说明书和标签管理规定",
                    "ISO 13485 §7.5.8",
                    "医疗器械生产质量管理规范(2025)·标识可追溯"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    },
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-SMP-071",
                "category": "机构与人员",
                "name": "人员健康管理制度与健康档案",
                "type": "system",
                "parent": "QMS-QP-014",
                "desc": "对影响产品质量人员按产品特性进行健康管理并建立健康档案",
                "standards": [
                    "生产质量规范2025 §24",
                    "ISO 13485 §6.2"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            },
            {
                "id": "QMS-SMP-016",
                "category": "检验和试验操作规程",
                "name": "检验样品管理规程",
                "type": "tech",
                "parent": "QMS-QP-028",
                "desc": "取样方法、取样量、标识、存放条件；取样/分发/接收/存放/返回/报废受控",
                "standards": [
                    "生产质量规范2025 §99"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            },
            {
                "id": "QMS-SMP-017",
                "category": "检验和试验操作规程",
                "name": "检验结果不合格调查处理规程",
                "type": "tech",
                "parent": "QMS-QP-028",
                "desc": "检验不合格的调查、原因分析、处理与复检规则，保留记录",
                "standards": [
                    "生产质量规范2025 §103"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            },
            {
                "id": "QMS-WI-001",
                "scope": "ai",
                "category": "作业指导书",
                "name": "数据标注作业指导书",
                "type": "tech",
                "parent": "QMS-QP-003",
                "desc": "训练/验证/测试数据的标注规范、质控规则与一致性要求",
                "standards": [
                    "YY/T 1833.3 数据标注通用要求"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "数据标注通用要求"
                    }
                ]
            },
            {
                "id": "QMS-WI-002",
                "scope": "ai",
                "category": "作业指导书",
                "name": "数据集构建与管理作业指导书",
                "type": "tech",
                "parent": "QMS-QP-003",
                "desc": "数据采集、清洗、划分、数据集说明（datasheet）",
                "standards": [
                    "YY/T 1833.2 数据集通用要求"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "数据集通用要求"
                    }
                ]
            },
            {
                "id": "QMS-WI-003",
                "scope": "ai",
                "category": "作业指导书",
                "name": "算法验证与性能评估作业指导书",
                "type": "tech",
                "parent": "QMS-QP-018",
                "desc": "模型性能指标、泛化与鲁棒性测试、影响因素分析方法",
                "standards": [
                    "人工智能医疗器械注册审查指导原则",
                    "YY/T 1858/1843"
                ],
                "refs": [
                    {
                        "collection": "guidance-ai",
                        "match": "人工智能医疗器械注册审查"
                    }
                ]
            },
            {
                "id": "QMS-WI-004",
                "scope": "sw",
                "category": "作业指导书",
                "name": "软件测试作业指导书",
                "type": "tech",
                "parent": "QMS-QP-003",
                "desc": "单元/集成/系统测试用例设计、执行与缺陷记录方法",
                "standards": [
                    "IEC 62304 §5.6",
                    "GB/T 25000.51"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    }
                ]
            },
            {
                "id": "QMS-WI-005",
                "scope": "sw",
                "category": "作业指导书",
                "name": "软件编码规则作业指导书",
                "type": "tech",
                "parent": "QMS-QP-003",
                "desc": "源代码编写与注释规范，供编码与源代码审核对照",
                "standards": [
                    "IEC 62304 §5.5",
                    "独立软件现场检查指导原则 §5.11"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    }
                ]
            },
            {
                "id": "QMS-WI-006",
                "scope": "sw",
                "category": "作业指导书",
                "name": "软件版本命名规则作业指导书",
                "type": "tech",
                "parent": "QMS-QP-004",
                "desc": "基于合规性确定版本命名规则，涵盖软件/现成软件/网络安全全部更新类型",
                "standards": [
                    "独立软件·附录 §2.3.5",
                    "医疗器械软件注册审查指导原则",
                    "独立软件现场检查指导原则 §5.5"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "医疗器械软件注册审查"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-WI-007",
                "scope": "sw",
                "category": "作业指导书",
                "name": "现成软件使用作业指导书",
                "type": "tech",
                "parent": "QMS-QP-011",
                "desc": "现成软件(遗留/成品/外包/开源)分类、评价、验证与许可协议合规要求",
                "standards": [
                    "独立软件·附录 §2.3.7/§2.4.1",
                    "独立软件现场检查指导原则 §5.7/§6.4"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-WI-008",
                "scope": "sw",
                "category": "作业指导书",
                "name": "软件发布与部署作业指导书",
                "type": "tech",
                "parent": "QMS-QP-019",
                "desc": "软件产品文件创建、归档备份、版本标记、交付验证、安装配置与用户培训",
                "standards": [
                    "独立软件·附录 §2.5.1/§2.7.1",
                    "独立软件现场检查指导原则 §7.2/§9.4"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-WI-009",
                "scope": "sw",
                "category": "作业指导书",
                "name": "软件产品放行作业指导书",
                "type": "tech",
                "parent": "QMS-QP-028",
                "desc": "软件版本识别、安装卸载测试、产品完整性检查、放行批准活动要求",
                "standards": [
                    "独立软件·附录 §2.6.1",
                    "独立软件现场检查指导原则 §8.5"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-WI-010",
                "scope": "sw",
                "category": "作业指导书",
                "name": "软件维护与停运作业指导书",
                "type": "tech",
                "parent": "QMS-QP-013",
                "desc": "上市后维护、停运后续用户服务、数据迁移、患者数据与隐私保护、用户告知",
                "standards": [
                    "独立软件·附录 §2.7.2",
                    "独立软件现场检查指导原则 §9.6"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-WI-011",
                "category": "检验和试验操作规程",
                "name": "进货检验规程",
                "type": "tech",
                "parent": "QMS-QP-011",
                "desc": "对采购的物料/组件/现成软件进行进货检验的项目、方法、判定准则与记录要求",
                "standards": [
                    "ISO 13485 §7.4.3",
                    "医疗器械生产质量管理规范(2025)·质量保证章"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    },
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            },
            {
                "id": "QMS-WI-012",
                "category": "检验和试验操作规程",
                "name": "过程检验规程",
                "type": "tech",
                "parent": "QMS-QP-019",
                "desc": "对生产/构建过程中的关键工序进行过程检验与监视的项目、方法与判定准则",
                "standards": [
                    "ISO 13485 §8.2.6",
                    "医疗器械生产质量管理规范(2025)·质量保证章"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    },
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            },
            {
                "id": "QMS-WI-013",
                "category": "检验和试验操作规程",
                "name": "成品检验规程",
                "type": "tech",
                "parent": "QMS-QP-028",
                "desc": "对成品/软件发布版本进行放行前成品检验的项目、方法、判定准则与检验报告要求",
                "standards": [
                    "ISO 13485 §8.2.6",
                    "医疗器械生产质量管理规范(2025)·质量保证章"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    },
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            },
            {
                "id": "QMS-WI-014",
                "category": "作业指导书",
                "name": "UDI赋码作业指导书",
                "type": "tech",
                "parent": "QMS-QP-020",
                "desc": "医疗器械唯一标识(UDI)的编制、赋码、载体标记、数据上传与核验作业方法",
                "standards": [
                    "医疗器械唯一标识系统规则",
                    "医疗器械生产质量管理规范(2025)·标识可追溯",
                    "ISO 13485 §7.5.8"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    },
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-WI-015",
                "category": "作业指导书",
                "name": "委托生产受托方现场审核作业指导书",
                "type": "tech",
                "parent": "QMS-QP-038",
                "desc": "对委托生产/外协加工受托方开展现场审核的准备、检查项、评分与结论判定作业方法",
                "standards": [
                    "医疗器械生产质量管理规范(2025)·委托生产与外协加工章",
                    "ISO 13485 §7.4.1"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    },
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-TD-101",
                "category": "产品技术要求及相关标准",
                "name": "产品技术要求",
                "type": "tech",
                "desc": "产品性能指标与检验方法，注册核心技术文件，上市后须持续符合",
                "standards": [
                    "生产质量规范2025 §42/§51",
                    "产品技术要求编写指导原则"
                ],
                "refs": [
                    {
                        "collection": "guidance-registration",
                        "match": "产品技术要求编写"
                    }
                ]
            },
            {
                "id": "QMS-TD-102",
                "scope": "sw",
                "category": "作业指导书",
                "name": "软件概要设计说明书",
                "type": "tech",
                "desc": "软件架构、模块划分、接口定义、SOUP识别",
                "standards": [
                    "IEC 62304 §5.3",
                    "YY/T 0664",
                    "生产质量规范2025 §42"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    }
                ]
            },
            {
                "id": "QMS-TD-103",
                "scope": "sw",
                "category": "作业指导书",
                "name": "软件详细设计说明书",
                "type": "tech",
                "desc": "模块详细设计、算法伪码/流程、数据结构",
                "standards": [
                    "IEC 62304 §5.4",
                    "YY/T 0664"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    }
                ]
            },
            {
                "id": "QMS-TD-104",
                "category": "生产工艺规程",
                "name": "生产工艺规程(TSP)",
                "type": "tech",
                "desc": "软件构建、打包、部署、发布的工艺流程规程",
                "standards": [
                    "生产质量规范2025 §42/§78"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    }
                ]
            }
        ]
    },
    {
        "level": 4,
        "name": "记录与表单",
        "en": "Records / Forms — 客观证据",
        "desc": "数量最多，是审核/注册申报的直接证据，不可修改，须可追溯",
        "color": "#e53e3e",
        "documents": [
            {
                "id": "QMS-REC-001",
                "category": "质量保证",
                "name": "风险管理档案（RMF）",
                "type": "record",
                "parent": "QMS-QP-006",
                "depends_docs": [
                    "QMS-REC-056"
                ],
                "desc": "危害识别、风险分析、控制措施、剩余风险评价完整档案",
                "standards": [
                    "ISO 14971 §3.5",
                    "GB/T 42062"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "风险管理对医疗器械"
                    }
                ]
            },
            {
                "id": "QMS-REC-002",
                "scope": "sw",
                "category": "设计开发",
                "name": "软件需求规格说明（SRS）",
                "type": "record",
                "parent": "QMS-QP-018",
                "desc": "功能、性能、安全、接口需求记录",
                "standards": [
                    "IEC 62304 §5.2",
                    "YY/T 0664",
                    "独立软件现场检查指导原则 §5.9"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    }
                ]
            },
            {
                "id": "QMS-REC-003",
                "scope": "sw",
                "category": "设计开发",
                "name": "测试报告",
                "type": "record",
                "parent": "QMS-QP-018",
                "depends_docs": [
                    "QMS-REC-002"
                ],
                "desc": "测试范围、用例、结果与通过判定记录",
                "standards": [
                    "IEC 62304 §5.6"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    }
                ]
            },
            {
                "id": "QMS-REC-004",
                "category": "设计开发",
                "name": "临床评价报告",
                "type": "record",
                "parent": "QMS-QP-012",
                "desc": "临床数据收集、文献评价、等同性论证、临床评价结论",
                "standards": [
                    "医疗器械临床评价技术指导原则",
                    "AI辅助检测临床评价指导原则"
                ],
                "refs": [
                    {
                        "collection": "guidance-clinical",
                        "match": "临床评价技术指导原则"
                    },
                    {
                        "collection": "guidance-ai-clinical",
                        "match": "临床评价注册审查"
                    }
                ]
            },
            {
                "id": "QMS-REC-005",
                "category": "分析与改进",
                "name": "CAPA 表单",
                "type": "record",
                "parent": "QMS-QP-009",
                "desc": "问题描述、根因分析、纠正措施、责任人、有效性验证",
                "standards": [
                    "ISO 13485 §8.5.2"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-006",
                "category": "文件和数据管理",
                "name": "文件审批记录表",
                "type": "record",
                "parent": "QMS-QP-001",
                "desc": "文件起草、审核、批准的签署记录",
                "standards": [
                    "ISO 13485 §4.2.4",
                    "独立软件现场检查指导原则 §4.2"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-007",
                "category": "文件和数据管理",
                "name": "文件发放回收销毁记录表",
                "type": "record",
                "parent": "QMS-QP-001",
                "desc": "文件分发、撤销、复制、销毁的受控记录",
                "standards": [
                    "ISO 13485 §4.2.4",
                    "独立软件现场检查指导原则 §4.2.2"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-008",
                "category": "文件和数据管理",
                "name": "作废文件保管清单",
                "type": "record",
                "parent": "QMS-QP-001",
                "desc": "作废/替换文件的标识与保管清单，防止误用",
                "standards": [
                    "ISO 13485 §4.2.4",
                    "独立软件现场检查指导原则 §4.2.4/§4.3.1"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-009",
                "category": "质量保证",
                "name": "管理评审计划",
                "type": "record",
                "parent": "QMS-QP-002",
                "desc": "管理评审的时间、范围、输入项与参加人安排",
                "standards": [
                    "ISO 13485 §5.6.1",
                    "独立软件现场检查指导原则 §11.9"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-010",
                "category": "质量保证",
                "name": "管理评审报告",
                "type": "record",
                "parent": "QMS-QP-002",
                "depends_docs": [
                    "QMS-REC-009",
                    "QMS-REC-041"
                ],
                "desc": "管理评审输出：结论、改进措施、资源决策及法规符合性评价",
                "standards": [
                    "ISO 13485 §5.6.3",
                    "独立软件现场检查指导原则 §11.9"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-011",
                "category": "机构与人员",
                "name": "年度培训计划",
                "type": "record",
                "parent": "QMS-QP-014",
                "desc": "按岗位能力需求编制的年度培训安排",
                "standards": [
                    "ISO 13485 §6.2",
                    "独立软件现场检查指导原则 §1.6"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-012",
                "category": "机构与人员",
                "name": "培训记录表",
                "type": "record",
                "parent": "QMS-QP-014",
                "desc": "培训内容、参加人、考核结果与有效性评价记录",
                "standards": [
                    "ISO 13485 §6.2",
                    "独立软件现场检查指导原则 §1.6"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-013",
                "category": "厂房设施与设备",
                "name": "设备验收单",
                "type": "record",
                "parent": "QMS-QP-015",
                "desc": "开发/测试设备与工具到货验收记录",
                "standards": [
                    "ISO 13485 §6.3",
                    "独立软件现场检查指导原则 §3.1"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-014",
                "category": "厂房设施与设备",
                "name": "设备运行与维修记录",
                "type": "record",
                "parent": "QMS-QP-015",
                "desc": "设备运行状态、维护与维修情况记录",
                "standards": [
                    "ISO 13485 §6.3",
                    "独立软件现场检查指导原则 §3.3"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-015",
                "category": "厂房设施与设备",
                "name": "设备台账",
                "type": "record",
                "parent": "QMS-QP-015",
                "desc": "开发/测试软硬件设备与工具清单台账",
                "standards": [
                    "ISO 13485 §6.3",
                    "独立软件现场检查指导原则 §3.1"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-016",
                "category": "厂房设施与设备",
                "name": "开发测试环境温湿度/维护记录表",
                "type": "record",
                "parent": "QMS-QP-016",
                "desc": "机房/计算环境温湿度、病毒防护、备份恢复等环境维护记录",
                "standards": [
                    "独立软件·附录 §2.2.2",
                    "独立软件现场检查指导原则 §3.2"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-REC-017",
                "category": "销售与售后服务",
                "name": "合同或订单评审记录表",
                "type": "record",
                "parent": "QMS-QP-017",
                "desc": "与顾客有关过程中合同/订单的评审记录",
                "standards": [
                    "ISO 13485 §7.2.2"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-018",
                "category": "设计开发",
                "name": "设计开发评审记录表",
                "type": "record",
                "parent": "QMS-QP-018",
                "depends_docs": [
                    "QMS-REC-002"
                ],
                "desc": "各设计阶段评审的参加人、发现问题与结论记录",
                "standards": [
                    "ISO 13485 §7.3.5",
                    "独立软件现场检查指导原则 §5.9~5.15"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "医疗器械软件注册审查"
                    }
                ]
            },
            {
                "id": "QMS-REC-019",
                "scope": "sw",
                "category": "设计开发",
                "name": "设计开发验证记录",
                "type": "record",
                "parent": "QMS-QP-018",
                "depends_docs": [
                    "QMS-REC-002",
                    "QMS-REC-003"
                ],
                "desc": "验证输出满足输入要求的客观证据记录",
                "standards": [
                    "ISO 13485 §7.3.6",
                    "IEC 62304 §5.6",
                    "独立软件现场检查指导原则 §5.12/5.13"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    }
                ]
            },
            {
                "id": "QMS-REC-020",
                "scope": "sw",
                "category": "设计开发",
                "name": "设计开发确认表",
                "type": "record",
                "parent": "QMS-QP-018",
                "depends_docs": [
                    "QMS-REC-002",
                    "QMS-REC-004"
                ],
                "desc": "软件满足用户需求和预期用途的确认记录(含用户测试/临床评价)",
                "standards": [
                    "ISO 13485 §7.3.7",
                    "独立软件现场检查指导原则 §5.14/5.15"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    }
                ]
            },
            {
                "id": "QMS-REC-021",
                "scope": "sw",
                "category": "设计开发",
                "name": "软件设计变更记录",
                "type": "record",
                "parent": "QMS-QP-018",
                "desc": "设计变更的评估、审批与实施记录",
                "standards": [
                    "ISO 13485 §7.3.9",
                    "独立软件·附录 §2.3.16",
                    "独立软件现场检查指导原则 §5.16"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-REC-022",
                "scope": "sw",
                "category": "设计开发",
                "name": "设计转换（试产）报告",
                "type": "record",
                "parent": "QMS-QP-018",
                "depends_docs": [
                    "QMS-REC-002",
                    "QMS-REC-003"
                ],
                "desc": "设计输出转换为生产/发布规范的验证报告",
                "standards": [
                    "ISO 13485 §7.3.8"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-023",
                "category": "采购与物料管理",
                "name": "供应商调查和分析表",
                "type": "record",
                "parent": "QMS-QP-011",
                "desc": "供应商基本情况调查与能力分析",
                "standards": [
                    "ISO 13485 §7.4.1",
                    "独立软件现场检查指导原则 §6.3"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-024",
                "category": "采购与物料管理",
                "name": "供方评定审批表",
                "type": "record",
                "parent": "QMS-QP-011",
                "desc": "供应商选择、评价、再评价的审批记录",
                "standards": [
                    "ISO 13485 §7.4.1",
                    "独立软件现场检查指导原则 §6.3"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-025",
                "category": "采购与物料管理",
                "name": "合格供方名录",
                "type": "record",
                "parent": "QMS-QP-011",
                "desc": "经评价合格的供应商清单(软件/云服务/外包)",
                "standards": [
                    "ISO 13485 §7.4.1"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-026",
                "category": "采购与物料管理",
                "name": "供方年度业绩评价表",
                "type": "record",
                "parent": "QMS-QP-011",
                "desc": "对合格供应商的年度绩效再评价",
                "standards": [
                    "ISO 13485 §7.4.1"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-027",
                "scope": "sw",
                "category": "采购与物料管理",
                "name": "现成软件清单",
                "type": "record",
                "parent": "QMS-QP-011",
                "desc": "产品使用的现成软件(遗留/成品/外包/开源)清单",
                "standards": [
                    "独立软件·附录 §2.3.7",
                    "独立软件现场检查指导原则 §5.7"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-REC-028",
                "scope": "sw",
                "category": "采购与物料管理",
                "name": "现成软件评价记录",
                "type": "record",
                "parent": "QMS-QP-011",
                "desc": "现成软件的风险、验证确认、缺陷、可追溯性等评价记录",
                "standards": [
                    "独立软件·附录 §2.3.7",
                    "独立软件现场检查指导原则 §5.7"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-REC-029",
                "category": "采购与物料管理",
                "name": "采购申请单",
                "type": "record",
                "parent": "QMS-QP-011",
                "desc": "采购需求的申请与审批记录",
                "standards": [
                    "ISO 13485 §7.4.2",
                    "独立软件现场检查指导原则 §6.7"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-030",
                "scope": "sw",
                "category": "采购与物料管理",
                "name": "外包软件质量协议",
                "type": "record",
                "parent": "QMS-QP-011",
                "desc": "与外包方约定需求/交付/验收/知识产权/维护及质量责任的协议",
                "standards": [
                    "独立软件·附录 §2.4.2",
                    "独立软件现场检查指导原则 §6.5"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-REC-031",
                "category": "采购与物料管理",
                "name": "云计算服务协议",
                "type": "record",
                "parent": "QMS-QP-011",
                "desc": "明确网络安全保证、患者数据与隐私保护责任的云服务协议",
                "standards": [
                    "独立软件·附录 §2.4.3",
                    "独立软件现场检查指导原则 §6.6"
                ],
                "refs": [
                    {
                        "collection": "guidance-cybersecurity",
                        "match": "网络安全注册审查"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-REC-032",
                "scope": "sw",
                "category": "设计开发",
                "name": "软件可追溯性分析报告",
                "type": "record",
                "parent": "QMS-QP-031",
                "depends_docs": [
                    "QMS-REC-002",
                    "QMS-REC-003"
                ],
                "desc": "需求-设计-代码-测试-风险追溯关系分析结论，供评审",
                "standards": [
                    "独立软件·附录 §2.3.6",
                    "独立软件现场检查指导原则 §5.6"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-REC-033",
                "scope": "sw",
                "category": "设计开发",
                "name": "配置审计报告",
                "type": "record",
                "parent": "QMS-QP-032",
                "desc": "配置项状态审计结果记录",
                "standards": [
                    "IEC 62304 §8",
                    "独立软件现场检查指导原则 §5.4"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    }
                ]
            },
            {
                "id": "QMS-REC-034",
                "scope": "sw",
                "category": "设计开发",
                "name": "软件缺陷分析报告",
                "type": "record",
                "parent": "QMS-QP-005",
                "depends_docs": [
                    "QMS-REC-051"
                ],
                "desc": "缺陷评估、修复、回归测试结论，供评审",
                "standards": [
                    "独立软件·附录 §2.3.17",
                    "独立软件现场检查指导原则 §5.17"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-REC-035",
                "category": "质量控制与放行",
                "name": "偏差处理记录单",
                "type": "record",
                "parent": "QMS-QP-027",
                "desc": "过程偏差的识别、评估与处置记录",
                "standards": [
                    "ISO 13485 §8.3"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-036",
                "category": "质量控制与放行",
                "name": "不合格报告单",
                "type": "record",
                "parent": "QMS-QP-029",
                "desc": "来料/过程/成品不合格的报告与处置记录",
                "standards": [
                    "ISO 13485 §8.3",
                    "独立软件现场检查指导原则 §10.2"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-037",
                "category": "质量控制与放行",
                "name": "让步接受单",
                "type": "record",
                "parent": "QMS-QP-029",
                "desc": "不合格品让步接受的评审与审批记录",
                "standards": [
                    "ISO 13485 §8.3.2"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-038",
                "category": "质量控制与放行",
                "name": "返工记录单",
                "type": "record",
                "parent": "QMS-QP-029",
                "desc": "不合格品返工的实施与再验证记录",
                "standards": [
                    "ISO 13485 §8.3.4"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-039",
                "category": "质量保证",
                "name": "年度内审计划",
                "type": "record",
                "parent": "QMS-QP-010",
                "desc": "内部审核的年度频次、范围与准则安排",
                "standards": [
                    "ISO 13485 §8.2.4",
                    "独立软件现场检查指导原则 §11.8"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-040",
                "category": "质量保证",
                "name": "内审检查表",
                "type": "record",
                "parent": "QMS-QP-010",
                "desc": "内审对照标准条款的检查清单",
                "standards": [
                    "ISO 13485 §8.2.4",
                    "独立软件现场检查指导原则 §11.8"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-041",
                "category": "质量保证",
                "name": "内部审核报告",
                "type": "record",
                "parent": "QMS-QP-010",
                "depends_docs": [
                    "QMS-REC-040"
                ],
                "desc": "内审发现、不符合项与整改跟踪结论",
                "standards": [
                    "ISO 13485 §8.2.4",
                    "独立软件现场检查指导原则 §11.8"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-042",
                "category": "分析与改进",
                "name": "纠正预防措施记录单",
                "type": "record",
                "parent": "QMS-QP-009",
                "desc": "CAPA 的根因分析、措施、责任人与有效性验证记录(表单实例)",
                "standards": [
                    "ISO 13485 §8.5.2/§8.5.3",
                    "独立软件现场检查指导原则 §11.4"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-043",
                "category": "分析与改进",
                "name": "可疑医疗器械不良事件报告表",
                "type": "record",
                "parent": "QMS-QP-025",
                "desc": "可疑不良事件的上报记录",
                "standards": [
                    "医疗器械不良事件监测和再评价管理办法",
                    "独立软件现场检查指导原则 §11.2"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "不良事件监测"
                    }
                ]
            },
            {
                "id": "QMS-REC-044",
                "category": "分析与改进",
                "name": "医疗器械召回事件报告表",
                "type": "record",
                "parent": "QMS-QP-026",
                "desc": "召回事件的报告与实施情况记录",
                "standards": [
                    "医疗器械召回管理办法",
                    "独立软件现场检查指导原则 §11.5"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "不良事件监测"
                    }
                ]
            },
            {
                "id": "QMS-REC-045",
                "category": "销售与售后服务",
                "name": "客户反馈/满意度记录表",
                "type": "record",
                "parent": "QMS-QP-023",
                "desc": "顾客反馈与满意度调查的收集记录",
                "standards": [
                    "ISO 13485 §8.2.1",
                    "独立软件现场检查指导原则 §9.5"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-046",
                "category": "销售与售后服务",
                "name": "售后服务与安装验收记录",
                "type": "record",
                "parent": "QMS-QP-013",
                "desc": "软件安装验收、售后服务与售后培训记录",
                "standards": [
                    "ISO 13485 §7.5.4",
                    "独立软件现场检查指导原则 §9.3/§9.4"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    }
                ]
            },
            {
                "id": "QMS-REC-047",
                "scope": "sw",
                "category": "销售与售后服务",
                "name": "软件停运报告",
                "type": "record",
                "parent": "QMS-QP-013",
                "desc": "软件停运后续服务、数据迁移与用户告知记录",
                "standards": [
                    "独立软件·附录 §2.7.2",
                    "独立软件现场检查指导原则 §9.6"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-REC-048",
                "scope": "sw",
                "category": "销售与售后服务",
                "name": "软件维护告知记录",
                "type": "record",
                "parent": "QMS-QP-013",
                "desc": "产品变动/使用等补充信息通知用户的记录",
                "standards": [
                    "独立软件现场检查指导原则 §11.6"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    }
                ]
            },
            {
                "id": "QMS-REC-049",
                "category": "设计开发",
                "name": "变更申请审批单",
                "type": "record",
                "parent": "QMS-QP-018",
                "desc": "变更请求的评估与审批记录",
                "standards": [
                    "ISO 13485 §7.3.9",
                    "独立软件·附录 §2.3.16"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-REC-050",
                "category": "设计开发",
                "name": "变更台账",
                "type": "record",
                "parent": "QMS-QP-018",
                "desc": "所有变更的登记台账，与版本变更相匹配",
                "standards": [
                    "ISO 13485 §7.3.9",
                    "独立软件·附录 §2.3.5"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-REC-051",
                "scope": "sw",
                "category": "设计开发",
                "name": "软件问题报告",
                "type": "record",
                "parent": "QMS-QP-005",
                "desc": "软件问题的报告与跟踪记录",
                "standards": [
                    "IEC 62304 §9",
                    "独立软件现场检查指导原则 §5.17"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "YY_T0664"
                    }
                ]
            },
            {
                "id": "QMS-REC-052",
                "scope": "sw",
                "category": "质量控制与放行",
                "name": "软件产品放行单",
                "type": "record",
                "parent": "QMS-QP-028",
                "depends_docs": [
                    "QMS-REC-003",
                    "QMS-REC-001"
                ],
                "desc": "版本识别、完整性检查、放行批准的放行记录",
                "standards": [
                    "独立软件·附录 §2.6.1",
                    "独立软件现场检查指导原则 §8.5"
                ],
                "refs": [
                    {
                        "collection": "guidance-software",
                        "match": "独立软件"
                    },
                    {
                        "collection": "guidance-qms-software",
                        "match": "附录独立软件"
                    }
                ]
            },
            {
                "id": "QMS-REC-054",
                "category": "质量保证",
                "name": "质量目标监视记录",
                "type": "record",
                "parent": "QMS-QP-036",
                "desc": "对质量目标达成情况的定期监视与测量记录，作为管理评审输入",
                "standards": [
                    "ISO 13485 §5.4.1",
                    "§5.6.2",
                    "GB/T 42061 §5.4.1"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-055",
                "category": "文件和数据管理",
                "name": "受控文件清单",
                "type": "record",
                "parent": "QMS-QP-001",
                "desc": "现行有效受控文件一览表，记录文件编号、名称、版本、状态与保管信息",
                "standards": [
                    "ISO 13485 §4.2.4",
                    "GB/T 42061 §4.2.4",
                    "独立软件现场检查指导原则 §4.2"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-056",
                "category": "质量保证",
                "name": "风险管理计划",
                "type": "record",
                "parent": "QMS-QP-006",
                "desc": "对风险管理活动的策划：范围、职责与权限、评审要求、风险可接受准则与验证活动安排（区别于风险管理档案）",
                "standards": [
                    "ISO 14971:2019 §4.4",
                    "GB/T 42062 §4.4",
                    "YY/T 0316"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "风险管理对医疗器械"
                    },
                    {
                        "collection": "standards",
                        "match": "0316"
                    }
                ]
            },
            {
                "id": "QMS-REC-057",
                "category": "设计开发",
                "name": "可用性工程文件（使用规范 + 形成性/总结性评估报告）",
                "type": "record",
                "parent": "QMS-QP-007",
                "desc": "使用规范、使用相关风险分析、形成性评价与总结性评价报告，构成可用性工程档案",
                "standards": [
                    "IEC 62366-1",
                    "可用性工程注册审查指导原则"
                ],
                "refs": [
                    {
                        "collection": "guidance-usability",
                        "match": "可用性工程注册审查"
                    }
                ]
            },
            {
                "id": "QMS-REC-058",
                "scope": "sw",
                "category": "网络安全",
                "name": "网络安全威胁建模报告",
                "type": "record",
                "parent": "QMS-QP-008",
                "desc": "采用 STRIDE 等方法对软件资产、攻击面与威胁进行建模分析，识别安全需求与缓解措施",
                "standards": [
                    "YY/T 1833",
                    "医疗器械网络安全注册审查指导原则",
                    "IEC 81001-5-1"
                ],
                "refs": [
                    {
                        "collection": "guidance-cybersecurity",
                        "match": "网络安全注册审查"
                    },
                    {
                        "collection": "cybersecurity",
                        "match": "网络安全法"
                    }
                ]
            },
            {
                "id": "QMS-REC-059",
                "scope": "sw",
                "category": "网络安全",
                "name": "网络安全测试报告",
                "type": "record",
                "parent": "QMS-QP-008",
                "depends_docs": [
                    "QMS-REC-058"
                ],
                "desc": "渗透测试、漏洞扫描与安全测试结果记录，含发现的漏洞、风险等级与修复验证",
                "standards": [
                    "YY/T 1833",
                    "医疗器械网络安全注册审查指导原则",
                    "IEC 81001-5-1"
                ],
                "refs": [
                    {
                        "collection": "guidance-cybersecurity",
                        "match": "网络安全注册审查"
                    },
                    {
                        "collection": "cybersecurity",
                        "match": "网络安全法"
                    }
                ]
            },
            {
                "id": "QMS-REC-060",
                "scope": "ai",
                "category": "AI算法与数据治理",
                "name": "算法性能持续监测记录",
                "type": "record",
                "parent": "QMS-QP-013",
                "depends_docs": [
                    "AI-001"
                ],
                "desc": "上市后对 AI 模型性能与数据漂移的持续监测记录，含监测指标、阈值、告警与触发变更控制的判定",
                "standards": [
                    "人工智能医疗器械注册审查指导原则",
                    "医疗器械不良事件监测和再评价管理办法"
                ],
                "refs": [
                    {
                        "collection": "guidance-ai",
                        "match": "人工智能医疗器械注册审查"
                    },
                    {
                        "collection": "regulations",
                        "match": "不良事件监测"
                    }
                ]
            },
            {
                "id": "QMS-REC-061",
                "category": "分析与改进",
                "name": "上市后监督报告（PMS）",
                "type": "record",
                "parent": "QMS-QP-013",
                "depends_docs": [
                    "QMS-REC-001"
                ],
                "desc": "上市后数据的收集、趋势分析与再评价结论报告，作为管理评审与再评价输入",
                "standards": [
                    "ISO 13485 §8.2.1",
                    "医疗器械不良事件监测和再评价管理办法"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "不良事件监测"
                    },
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-069",
                "category": "委托生产与外协加工",
                "name": "委托生产质量协议",
                "type": "record",
                "parent": "QMS-QP-038",
                "desc": "委托方与受托方就质量责任、技术要求、过程控制、放行、变更与追溯等约定的质量协议",
                "standards": [
                    "医疗器械生产质量管理规范(2025)·委托生产与外协加工章",
                    "ISO 13485 §7.4.2"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    },
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "QMS-REC-070",
                "category": "验证与确认",
                "name": "验证方案与报告（设备/工艺/软件确认）",
                "type": "record",
                "parent": "QMS-QP-039",
                "desc": "设备安装/运行/性能确认、工艺验证及计算机软件确认的方案、实施记录、结果与再验证结论",
                "standards": [
                    "医疗器械生产质量管理规范(2025)·验证与确认章",
                    "ISO 13485 §7.5.6",
                    "§4.1.6"
                ],
                "refs": [
                    {
                        "collection": "regulations",
                        "match": "医疗器械生产质量管理规范"
                    },
                    {
                        "collection": "standards",
                        "match": "质量管理体系用于法规"
                    }
                ]
            },
            {
                "id": "AI-001",
                "scope": "ai",
                "category": "AI算法与数据治理",
                "name": "算法文档包（模型卡 + 算法验证报告）",
                "type": "ai",
                "parent": "QMS-QP-003",
                "depends_docs": [
                    "QMS-WI-001",
                    "QMS-WI-002",
                    "QMS-WI-003"
                ],
                "desc": "模型卡、数据集说明、算法验证报告，描述算法设计与性能",
                "standards": [
                    "YY/T 1833.1 术语",
                    "YY/T 1833.5 预训练模型",
                    "人工智能医疗器械注册审查指导原则"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "术语"
                    },
                    {
                        "collection": "standards",
                        "match": "预训练模型"
                    },
                    {
                        "collection": "guidance-ai",
                        "match": "人工智能医疗器械注册审查"
                    }
                ]
            },
            {
                "id": "AI-002",
                "scope": "ai",
                "category": "AI算法与数据治理",
                "name": "数据治理文件（数据管理计划 + 溯源记录）",
                "type": "ai",
                "parent": "QMS-QP-003",
                "depends_docs": [
                    "QMS-WI-001",
                    "QMS-WI-002"
                ],
                "desc": "数据管理计划、标注规范、数据溯源记录",
                "standards": [
                    "YY/T 1833.2 数据集",
                    "YY/T 1833.3 标注",
                    "YY/T 1833.4 可追溯性"
                ],
                "refs": [
                    {
                        "collection": "standards",
                        "match": "数据集通用要求"
                    },
                    {
                        "collection": "standards",
                        "match": "数据标注通用要求"
                    },
                    {
                        "collection": "standards",
                        "match": "可追溯性"
                    }
                ]
            },
            {
                "id": "AI-003",
                "scope": "ai",
                "category": "AI算法与数据治理",
                "name": "变更控制文件（PCCP / 重大变更评审）",
                "type": "ai",
                "parent": "QMS-QP-004",
                "depends_docs": [
                    "AI-001"
                ],
                "desc": "版本变更申请、PCCP 预定变更控制计划、重大变更评审",
                "standards": [
                    "IEC 62304 §8",
                    "人工智能医疗器械注册审查指导原则",
                    "FDA PCCP"
                ],
                "refs": [
                    {
                        "collection": "guidance-ai",
                        "match": "人工智能医疗器械注册审查"
                    }
                ]
            }
        ]
    }
]

# ── 档案汇编层（DHF / DMR / DHR / 技术文档）─────────────────────────────────
# 这些不是"新写的文件"，而是把已有文件按法规要求汇编归档的档案集合。
# compiles 列出该档案汇编了体系里哪些文件（引用 DOC_LEVELS 的 id）。
DOSSIERS = [
    {
        "id": "DOSSIER-DHF",
        "name": "DHF · 设计历史文档",
        "en": "Design History File",
        "market": "FDA / 通用",
        "standards": ["21 CFR 820.30(j)", "ISO 13485 §7.3.10"],
        "desc": "汇编设计开发全过程的记录，证明产品按设计控制程序开发。SaMD 软件应覆盖软件全生命周期各阶段。",
        "compiles": ["QMS-QP-003", "QMS-REC-002", "QMS-REC-003", "QMS-QP-006", "QMS-REC-001", "AI-001", "QMS-REC-004"],
        "compiles_note": "软件开发计划、SRS、架构/详细设计、测试报告、风险管理档案、算法验证报告、设计评审记录、验证确认报告、设计变更记录",
        "refs": [
            {"collection": "guidance-software", "match": "医疗器械软件注册审查"},
            {"collection": "standards", "match": "YY_T0664"},
        ],
    },
    {
        "id": "DOSSIER-DMR",
        "name": "DMR · 器械主记录",
        "en": "Device Master Record",
        "market": "FDA / 通用",
        "standards": ["21 CFR 820.181", "ISO 13485 §4.2.3 医疗器械文档"],
        "desc": "一个产品型号的完整规格\"配方\"。SaMD 应包含软件规格、源代码标识、构建/发布规范、标签、安装与使用说明、质控规程。",
        "compiles": ["QMS-REC-002", "QMS-QP-004", "QMS-QP-003", "QMS-QP-012", "AI-001"],
        "compiles_note": "软件规格(SRS)、配置管理与版本规范、构建/发布规程、产品技术要求、标签与说明书、算法/模型规格",
        "refs": [
            {"collection": "guidance-registration", "match": "产品技术要求编写"},
            {"collection": "standards", "match": "YY_T0664"},
        ],
    },
    {
        "id": "DOSSIER-DHR",
        "name": "DHR · 器械历史记录",
        "en": "Device History Record",
        "market": "FDA / 通用",
        "standards": ["21 CFR 820.184", "ISO 13485 §7.5.1"],
        "desc": "证明每一次生产/发布都按 DMR 执行的实际记录。SaMD 对应每个软件版本的构建记录、发布清单、版本验证与放行记录。",
        "compiles": ["QMS-REC-003", "AI-003", "QMS-QP-004"],
        "compiles_note": "版本构建记录、发布清单、版本测试/验证记录、放行批准记录、变更控制记录",
        "refs": [{"collection": "standards", "match": "YY_T0664"}],
    },
    {
        "id": "DOSSIER-TF",
        "name": "技术文档（Technical Documentation）",
        "en": "EU MDR Annex II/III",
        "market": "EU MDR",
        "standards": ["EU MDR Annex II", "Annex III", "GSPR Annex I"],
        "desc": "欧盟 CE 认证要求的技术文档，汇编设计、风险、临床评价、PMS 等，证明符合通用安全与性能要求(GSPR)。",
        "compiles": ["QMS-TD-101", "QMS-QM-001", "QMS-QP-006", "QMS-REC-001", "QMS-REC-004", "QMS-QP-013", "AI-001", "AI-002"],
        "compiles_note": "器械描述、GSPR符合性、设计与制造信息、风险管理档案、临床评价报告、PMS/PMCF计划、算法与数据治理文档",
        "refs": [{"collection": "guidance-clinical", "match": "临床评价技术指导原则"}],
    },
    {
        "id": "DOSSIER-NMPA",
        "name": "注册申报资料（NMPA）",
        "en": "NMPA Registration Dossier",
        "market": "NMPA",
        "standards": ["医疗器械注册与备案管理办法", "注册申报资料要求"],
        "desc": "中国注册申报的完整资料，汇编综述、研究资料、软件研究、临床评价、产品技术要求等。",
        "compiles": ["QMS-TD-101", "QMS-QP-012", "QMS-REC-002", "QMS-REC-003", "QMS-QP-006", "QMS-REC-004", "AI-001", "AI-002"],
        "compiles_note": "申报综述、产品技术要求、软件研究资料、算法研究资料、风险管理资料、临床评价资料、说明书样稿",
        "refs": [
            {"collection": "regulations", "match": "注册与备案管理办法"},
            {"collection": "guidance-software", "match": "医疗器械软件注册审查"},
        ],
    },
]


# ── 产品/注册线文档（不属四级体系，是某产品的注册产出物；由档案 compiles 引用）──
# TD-101 产品技术要求本是产品特定文件，已移出四级体系；保留定义以便 get_document_by_id
# 仍能解析（档案汇编、生成入口用），归属技术文档(TF)/注册资料(NMPA)档案。
PRODUCT_LINE_DOCS = [
    {
        "id": "QMS-TD-101",
        "category": "产品技术要求及相关标准",
        "name": "产品技术要求",
        "type": "tech",
        "desc": "产品性能指标与检验方法，注册核心技术文件，上市后须持续符合（产品特定，归注册/技术文档档案）",
        "standards": [
            "生产质量规范2025 §42/§51",
            "产品技术要求编写指导原则"
        ],
        "refs": [
            {
                "collection": "guidance-registration",
                "match": "产品技术要求编写"
            }
        ]
    },
]


# ── 第一层：核心工作框架（9 大模块，用于地图顶部展示）─────────────────────────
# 每个模块挂上它对应的文件（docs 引用真实 id）+ 区分色（color），点模块即可展开并生成其文件。
CORE_MODULES = [
    {"id": "M1", "name": "文件体系", "sub": "四级文件架构", "group": "base",
     "color": "#2f855a", "docs": ["QMS-QP-001", "QMS-QM-001", "QMS-REC-006", "QMS-REC-007", "QMS-REC-008"]},
    {"id": "M2", "name": "风险管理", "sub": "ISO 14971 全周期", "group": "base",
     "color": "#38a169", "docs": ["QMS-QP-006", "QMS-QP-035", "QMS-REC-001"]},
    {"id": "M3", "name": "软件开发", "sub": "IEC 62304 生命周期", "group": "base",
     "color": "#48bb78", "docs": ["QMS-QP-003", "QMS-QP-004", "QMS-QP-005", "QMS-QP-018", "QMS-QP-031", "QMS-QP-032", "QMS-QP-033", "QMS-WI-004", "QMS-WI-005", "QMS-WI-006", "QMS-REC-002", "QMS-REC-003", "QMS-REC-018", "QMS-REC-019", "QMS-REC-020", "QMS-REC-021", "QMS-REC-022", "QMS-REC-032", "QMS-REC-033", "QMS-REC-034", "QMS-REC-051"]},
    {"id": "M4", "name": "临床与性能", "sub": "验证确认评价", "group": "base",
     "color": "#68d391", "docs": ["QMS-QP-007", "QMS-QP-028", "QMS-REC-004", "QMS-REC-020"]},
    {"id": "M5", "name": "上市后监督", "sub": "持续监测反馈", "group": "base",
     "color": "#276749", "docs": ["QMS-QP-013", "QMS-QP-023", "QMS-QP-024", "QMS-QP-030", "QMS-REC-045", "QMS-REC-046", "QMS-REC-047", "QMS-REC-048"]},
    {"id": "M6", "name": "数据管理", "sub": "训练/验证/测试集 · 数据标注质量", "group": "ai",
     "color": "#dd6b20", "docs": ["QMS-WI-001", "QMS-WI-002", "AI-002"]},
    {"id": "M7", "name": "算法验证", "sub": "模型性能评估 · 泛化与鲁棒性", "group": "ai",
     "color": "#ed8936", "docs": ["QMS-WI-003", "AI-001"]},
    {"id": "M8", "name": "模型变更控制", "sub": "版本管理 · 持续学习评审", "group": "ai",
     "color": "#f6ad55", "docs": ["AI-003", "QMS-QP-004", "QMS-QP-031", "QMS-REC-021", "QMS-REC-049", "QMS-REC-050"]},
    {"id": "M9", "name": "可解释性", "sub": "算法透明度 · 偏差监测", "group": "ai",
     "color": "#c05621", "docs": ["AI-001"]},
    {"id": "M10", "name": "人员培训", "sub": "能力矩阵 · 上岗资质", "group": "support",
     "color": "#4a5568", "docs": ["QMS-QP-014", "QMS-REC-011", "QMS-REC-012"]},
    {"id": "M11", "name": "内外部审核", "sub": "内审 · 管理评审 · CAPA", "group": "support",
     "color": "#718096", "docs": ["QMS-QP-002", "QMS-QP-009", "QMS-QP-010", "QMS-QP-027", "QMS-QP-029", "QMS-REC-005", "QMS-REC-009", "QMS-REC-010", "QMS-REC-035", "QMS-REC-036", "QMS-REC-037", "QMS-REC-038", "QMS-REC-039", "QMS-REC-040", "QMS-REC-041", "QMS-REC-042"]},
    {"id": "M12", "name": "供应商与基础设施", "sub": "算力 · 云平台 · 外包管理", "group": "support",
     "color": "#a0aec0", "docs": ["QMS-QP-008", "QMS-QP-011", "QMS-QP-015", "QMS-QP-016", "QMS-QP-034", "QMS-WI-007", "QMS-REC-013", "QMS-REC-014", "QMS-REC-015", "QMS-REC-016", "QMS-REC-023", "QMS-REC-024", "QMS-REC-025", "QMS-REC-026", "QMS-REC-027", "QMS-REC-028", "QMS-REC-029", "QMS-REC-030", "QMS-REC-031"]},
    {"id": "M13", "name": "注册申报与持续合规", "sub": "技术文档 · 临床评价报告 · 注册证维护 · 不良事件报告", "group": "registration",
     "color": "#c53030", "docs": ["QMS-QP-012", "QMS-QP-017", "QMS-QP-019", "QMS-QP-020", "QMS-QP-021", "QMS-QP-022", "QMS-QP-025", "QMS-QP-026", "QMS-WI-008", "QMS-WI-009", "QMS-WI-010", "QMS-REC-017", "QMS-REC-043", "QMS-REC-044", "QMS-REC-052"]},
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


# ── 体系搭建流程（纵向）——建立并运行一套 QMS 的管理工程 ─────────────────────
# 重点：这是「把管理体系建起来并跑通」的工程阶段（策划→差距→设计→文件化→培训→
# 试运行→内审管评→认证核查），不是「按什么顺序写文档」。写文件只是阶段 4 一环。
# steps=该阶段的管理动作；docs=该阶段顺带产出/落地的受控文件（引用真实 id，可点生成）。
BUILD_FLOW = [
    {
        "phase": "阶段 1 · 策划与启动", "no": "1", "color": "#6b46c1",
        "goal": "把「要建一套什么样的体系、谁负责、覆盖到哪」定下来——建体系的决策与立项",
        "steps": [
            "最高管理者作出质量承诺、任命管理者代表（管代）、配置资源",
            "确定 QMS 覆盖范围与剪裁（哪些生命周期阶段、6/7/8 章哪些不适用及理由）",
            "制定质量方针与可测量目标，编制体系搭建项目计划（里程碑/责任人）",
        ],
        "tasks": ["任命管代并书面授权", "编制质量方针、目标、范围与剪裁声明", "制定体系搭建项目计划"],
        "docs": [],
        "outputs": "质量承诺/任命书、方针目标、范围与剪裁声明、项目计划",
        "depends": "无（起点）",
        "pitfall": "把「暂时没做」当「不适用」乱剪裁；一人多职时把放行归到执行者，破坏独立性红线",
        "std": "ISO 13485 §5.3 方针、§5.4 策划、§5.5 职责/管代、§1 剪裁",
    },
    {
        "phase": "阶段 2 · 差距分析", "no": "2", "color": "#805ad5",
        "goal": "对照标准盘现状，找出「缺什么」——这是建体系的诊断，不是写文档",
        "steps": [
            "对照 ISO 13485 / IEC 62304 / ISO 14971 及适用指导原则逐条评估现状",
            "列出差距清单：哪些过程缺、哪些文件缺、哪些能力缺",
            "排优先级，形成整改计划（谁、做什么、何时完成）",
        ],
        "tasks": ["按标准做差距分析（gap analysis）", "输出差距清单与整改计划"],
        "docs": [],
        "outputs": "差距分析报告、整改计划表",
        "depends": "阶段 1（范围既定才知道对照哪些要求）",
        "pitfall": "跳过差距分析直接照模板抄文件——体系与真实业务两张皮的根源",
        "std": "ISO 13485 §4.1 总要求（识别所需过程）",
    },
    {
        "phase": "阶段 3 · 体系设计", "no": "3", "color": "#dd6b20",
        "goal": "设计体系骨架：过程怎么流转、谁对谁负责、文件怎么分层——先画蓝图再动笔",
        "steps": [
            "绘制过程地图（识别过程及其相互作用、输入输出、判定准则）",
            "定组织架构与岗位职责权限矩阵（落实放行独立性）",
            "设计四级文件架构（手册/程序/作业指导书/记录），列出文件清单",
        ],
        "tasks": ["绘制过程地图", "制定职责权限矩阵", "设计文件架构与清单"],
        "docs": [],
        "outputs": "过程地图、组织架构与职责矩阵、文件清单/架构图",
        "depends": "阶段 2（知道缺什么才好设计补什么）",
        "pitfall": "只堆文件不画过程地图——审核员会问「你的过程长什么样、怎么衔接」",
        "std": "ISO 13485 §4.1 过程方法、§5.5 职责",
    },
    {
        "phase": "阶段 4 · 文件编制", "no": "4", "color": "#d69e2e",
        "goal": "把设计变成受控文件——「写文档」是这一环，不是整个搭建",
        "steps": [
            "先建文件与记录控制程序（元规则，其他文件都套它）",
            "编制核心业务程序：风险(14971)、软件生命周期(62304)、配置、采购、网络安全、可用性",
            "编制上市后/改进程序（CAPA、内审、管评、不良事件）与 AI 特有文件；质量手册最后写",
        ],
        "tasks": ["按文件清单逐份起草→评审→批准→发布"],
        "docs": ["QMS-QP-001", "QMS-QP-006", "QMS-QP-003", "QMS-QP-004", "QMS-QP-011", "QMS-QP-008", "QMS-QP-007",
                 "QMS-QP-009", "QMS-QP-010", "QMS-QP-002", "QMS-QP-013", "QMS-QP-005",
                 "QMS-WI-001", "QMS-WI-002", "QMS-WI-003", "QMS-WI-004",
                 "QMS-REC-001", "QMS-REC-002", "QMS-REC-003", "QMS-REC-004", "QMS-REC-005",
                 "AI-001", "AI-002", "AI-003", "QMS-QM-001"],
        "outputs": "受控的手册/程序/作业指导书/记录模板（点卡片可生成模板）",
        "depends": "阶段 3（文件清单与架构已定）",
        "pitfall": "先写质量手册必返工；模型再训练/迭代没纳入变更控制——AI 最易失控处",
        "std": "ISO 13485 §4.2 文件要求、IEC 62304、ISO 14971",
    },
    {
        "phase": "阶段 5 · 培训与发布", "no": "5", "color": "#38a169",
        "goal": "让体系从「纸面」变成「大家会用」——发布受控、全员培训、正式生效",
        "steps": [
            "受控发布文件（版本标识、发放回收，作废文件防误用）",
            "对全员培训「怎么按体系做」，重点补研发团队法规意识",
            "宣布体系生效日期，评价培训有效性并留档",
        ],
        "tasks": ["受控发布体系文件", "组织全员体系培训并考核", "发布体系生效通知"],
        "docs": [],
        "outputs": "发布记录、培训计划与考核记录、生效通知",
        "depends": "阶段 4（文件已批准）",
        "pitfall": "只培训 RA/QA 不培训研发；文件发了没人真按它做——体系空转",
        "std": "ISO 13485 §6.2 人力资源、§4.2.4 文件控制",
    },
    {
        "phase": "阶段 6 · 试运行", "no": "6", "color": "#00a3c4",
        "goal": "体系真正跑起来，按程序产生真实记录——没有运行记录的体系是空壳",
        "steps": [
            "选一个产品/项目实际按体系走一遍（设计开发、风险、验证等真实执行）",
            "各过程按程序产生客观记录（可追溯、可归因、防篡改）",
            "边跑边发现不适用/难执行处，反馈迭代文件",
        ],
        "tasks": ["以真实产品试运行体系", "收集各过程运行记录", "反馈优化文件"],
        "docs": [],
        "outputs": "设计开发/风险/验证/评审等真实运行记录",
        "depends": "阶段 5（体系已生效、人已受训）",
        "pitfall": "文件写得漂亮但从没执行——体系核查一调原始记录就露馅",
        "std": "ISO 13485 §7 产品实现、§4.2.5 记录",
    },
    {
        "phase": "阶段 7 · 内审与管理评审", "no": "7", "color": "#3182ce",
        "goal": "外审之前自己先查一遍：内审→CAPA→管理评审→决策改进（PDCA 闭环）",
        "steps": [
            "按内审程序做一次完整内部审核，开出不符合项",
            "对不符合项走 CAPA（根因→纠正→有效性验证）",
            "召开管理评审，输入绩效/审核/反馈，输出改进与资源决策",
        ],
        "tasks": ["组织首次内部审核", "对不符合项执行 CAPA 闭环", "召开管理评审"],
        "docs": [],
        "outputs": "内审报告、不符合项与 CAPA 记录、管理评审报告",
        "depends": "阶段 6（有运行记录才审得动）",
        "pitfall": "内审走过场、CAPA 只纠正不验证有效性——审核员最爱查、最易挂",
        "std": "ISO 13485 §8.2.4 内审、§8.5.2 纠正措施、§5.6 管理评审",
    },
    {
        "phase": "阶段 8 · 认证 / 体系核查", "no": "8", "color": "#e53e3e",
        "goal": "迎接外部：ISO 13485 认证审核 或 注册体系核查，整改闭环拿结果",
        "steps": [
            "准备迎审：自查表对照、组织现场、备齐可调阅的执行记录",
            "接受外部审核/核查，如实应对现场提问与记录调阅",
            "对审核发现限期整改并验证关闭，取得证书/通过核查",
        ],
        "tasks": ["迎审自查与准备", "接受认证审核/体系核查", "整改并关闭审核发现"],
        "docs": [],
        "outputs": "自查报告、核查/审核记录、整改报告、认证证书/核查结论",
        "depends": "阶段 7（内部已闭环）",
        "pitfall": "申报资料写的与现场记录对不上——真实性问题是最严重红线",
        "std": "独立软件现场检查指导原则、ISO 13485 认证审核要求",
    },
]


def get_document_by_id(doc_id: str) -> dict | None:
    for doc in get_all_documents():
        if doc["id"] == doc_id:
            return doc
    for d in PRODUCT_LINE_DOCS:
        if d["id"] == doc_id:
            return d
    for d in DOSSIERS:
        if d["id"] == doc_id:
            return d
    return None


def get_stats() -> dict:
    all_docs = get_all_documents()
    return {
        "total": len(all_docs),
        "levels": len([l for l in DOC_LEVELS if l["level"] > 0]),
        "core_modules": len(CORE_MODULES),
        "dossiers": len(DOSSIERS),
        "markets": ["NMPA", "FDA", "EU"],
        "by_type": {t: sum(1 for d in all_docs if d["type"] == t) for t in DOC_TYPE_LABELS},
    }


# 剪裁声明：纯软件(SaMD)对《医疗器械生产质量管理规范2025》中物理生产类条款的不适用声明。
# 依据 §130「企业可根据所生产医疗器械特点，确定不适用本规范的具体条款，并说明不适用的合理性」。
TAILORING = [
    {"clause": "§25-§32 洁净厂房/洁净级别/静压差", "reason": "SaMD 为纯软件，无物理生产洁净车间，不涉及洁净级别与压差控制"},
    {"clause": "§66 仓储管理制度（原材料/中间产品实物贮存）", "reason": "SaMD 无实物原材料与成品仓储；交付介质/安装包按配置与发布管理控制"},
    {"clause": "§82 物料平衡", "reason": "软件可无限复制，无实物料量守恒概念，不适用物料平衡核算"},
    {"clause": "§86 清场管理制度", "reason": "无物理生产线切换，不存在实物清场；版本/环境隔离由配置管理与环境控制覆盖"},
    {"clause": "§92 共线/共用生产车间/设备", "reason": "SaMD 无共用生产车间/产线，不适用共线防混淆要求"},
    {"clause": "§93 连续生产最大批次/时间", "reason": "软件非连续物理生产，不适用批次数量/生产时间限制"},
    {"clause": "§73/§79 清洁验证", "reason": "无物理生产设备清洁需求，不适用清洁方法验证"},
    {"clause": "§29 有毒易燃易爆危险品贮存", "reason": "SaMD 生产不涉及危险品"},
]


def get_framework() -> dict:
    return {
        "core_modules": CORE_MODULES,
        "regulatory_matrix": REGULATORY_MATRIX,
        "doc_levels": DOC_LEVELS,
        "dossiers": DOSSIERS,
        "build_flow": BUILD_FLOW,
        "tailoring": TAILORING,
        "stats": get_stats(),
    }
