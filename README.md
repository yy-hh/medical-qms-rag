# QMS 体系搭建助手（含 AI 医疗器械软件 · SaMD）

面向医疗器械软件（SaMD，尤其含 AI 的产品）企业的**注册合规体系搭建平台**：把"哪个注册阶段、要产出哪些文档、满足哪条法规审查要点"用知识图谱关联起来，并能结合企业产品信息一键生成体系文件。覆盖中国 NMPA 全流程（兼顾 CE/MDR、FDA 参考）。

## 功能模块

### 🗺️ 体系地图
四级文件体系（质量手册 / 程序文件 / 作业指导书 / 记录表单 + AI 专项 + 档案汇编 DHF/DMR/DHR/技术文档/NMPA），标注对应标准与适用市场。

### 🚀 实施路线图
按注册推进的 **6 大阶段 73 项活动**组织（立项 6 / 研发 33 / 申报 13 / 审查 6 / 上市准备 6 / 上市后 9）；研发阶段再细分 2A 软件生命周期 / 2B 风险管理 / 2C AI 算法 / 2D 网络安全 / 2E 可用性。**文档生成的唯一入口**：点任务卡生成文档，完成后自动归档到「文件管理」。

### 🔗 合规知识图谱
基于 **networkx** 的真知识图谱（~640 节点 / ~1670 边）：法规/标准 × 审查要点 × 注册阶段 × 文档 × 归档档案。
- 力导向可视化（聚焦子图模式，点节点展开关联）
- 三维互查（按阶段 / 按法规 / 按文档）
- 审查要点来自 21 部核心法规原文的模型抽取（516 条），经联网交叉校验

### 📁 文件管理
已生成文档的存档库，**按归档要求分组**（DHF / DMR / DHR / 技术文档 / NMPA），支持查看、下载 Word、删除。

### 💬 法规顾问
**双路召回 RAG**：BM25 检索法规原文 + 合规图谱检索相关审查要点，回答既给法规条款依据，又说明"涉及哪个注册阶段、要产出哪些文档"。

### ⚙️ 公司 / 产品信息
企业信息 + 注册产品信息（核心功能、AI 类型、算法、输入输出、适应症、数据来源、性能指标、SOUP 等），生成文件时自动注入，使内容贴合具体产品。

## 技术架构

| 组件 | 技术 |
|------|------|
| 检索引擎 | BM25Okapi + jieba（中文医疗词典）+ 向量语义召回，RRF 融合 |
| 向量 embedding | 本地 bge-large-zh-v1.5（sentence-transformers，首次自动下载约 1.3GB，无外部依赖）|
| 知识图谱 | networkx MultiDiGraph（自包含，不依赖图数据库）|
| 存储 | SQLite（知识库 qms.db / 文档存档 generated_docs.db）|
| LLM | OpenAI 兼容 API（默认 Poe + Claude Opus 4）|
| 后端 | FastAPI + SSE 流式输出 |
| 文档解析 | PyMuPDF / python-docx |
| 文档导出 | python-docx（Markdown → Word）|

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/yy-hh/medical-qms-rag.git
cd medical-qms-rag

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 API_KEY（任何 OpenAI 兼容接口）

# 3. 一键启动（首次自动创建 conda 环境）
bash start.sh
```

访问 **http://localhost:8003**

知识库索引 `qms.db`（~4MB，53 篇法规/标准、1737 chunks）**已随仓库提供，开箱即用**——法规问答、合规图谱无需任何导入即可使用。

### .env 配置

```env
API_KEY=你的key
API_BASE_URL=https://api.poe.com/v1
CLAUDE_MODEL=claude-opus-4-6
```

> 支持 Poe、OpenAI、Azure、本地 Ollama 等任何 OpenAI 兼容 API。

## 使用流程

1. **配置公司 / 产品信息** → 填企业与注册产品信息（填得越细，生成越贴合）
2. **实施路线图** → 按阶段查看 73 项活动，点任务生成文档
3. **文件管理** → 已生成文档按 DHF/DMR/DHR 等档案分组，下载 Word
4. **合规图谱** → 可视化查"法规↔审查要点↔阶段↔文档"关联
5. **法规顾问** → 提问，获得带条款依据 + 阶段/文档关联的回答

## 知识库重建（可选）

仓库已含 `qms.db`，通常无需重建。如需用 `data/source_docs/` 里的法规原文重新导入，可运行 `scripts/` 下按类别的 `import_*.py`。法规要点抽取（重建合规图谱数据）：`scripts/extract_requirements.py --batch`。

## 数据与隐私

以下为运行时/敏感数据，**不随仓库提交**（见 .gitignore）：
- `.env`（API 密钥）
- `data/generated_docs.db`（你生成的文档存档）
- `data/company_profile.json`（公司/产品配置）
- `data/documents/`（入库用的原始 PDF，~67MB）

## 注意事项

- 生成的文件模板为起点，需结合实际修改完善，**不能直接作为注册提交材料**
- 法规时效性以官方最新发布为准（图谱数据截至 2026-06 联网校验）

## API 速览

启动后访问 **http://localhost:8003/docs**

| 路径 | 说明 |
|------|------|
| `/api/compliance/*` | 合规图谱：overview / graph / checklist / stage / document / search / node / subgraph |
| `/api/docs/*` | 文件管理：列表（按档案分组）/ 详情 / 下载 / 删除 |
| `/api/generate/stream` | 文件生成（SSE 流式）|
| `/api/generate/outline` | 章节大纲 |
| `/api/query/stream` | 法规问答（双路召回，SSE 流式）|
| `/api/company` | 公司/产品信息读写 |
| `/api/health` | 健康检查 |
