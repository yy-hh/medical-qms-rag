# 医疗行业 QMS 智能问答系统

基于 RAG（检索增强生成）的医疗器械质量管理体系法规智能问答平台。上传法规/标准文件，即可就医疗器械注册、体系建设等问题进行智能问答。

## 功能特性

- **流式回答**：实时逐字显示，无需等待
- **Markdown 渲染**：表格、标题、加粗格式完整显示
- **多轮对话**：支持追问，保留上下文
- **法规感知分块**：按「第X条/章」和 ISO 章节边界切分，每块 = 完整条款
- **文档管理**：上传 PDF / DOCX / TXT，支持扫描版 PDF（OCR）
- **多集合管理**：法规文件 / 标准文件 / 指导原则分类管理

## 系统架构

```
用户问题 → jieba 分词 → BM25 检索 → Top-K 相关条款 → Claude 生成回答（流式）
```

| 组件 | 技术 |
|------|------|
| 检索引擎 | BM25Okapi + jieba（医学专业词典）|
| 存储 | SQLite（本地持久化，无需数据库服务）|
| LLM | OpenAI 兼容 API（默认 Poe + Claude Opus）|
| 后端 | FastAPI + SSE 流式输出 |
| 文档解析 | PyMuPDF / python-docx / pytesseract（OCR）|

## 快速开始

### 环境要求

- Linux / macOS（Windows 建议 WSL2）
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) 或 Anaconda
- tesseract-ocr（扫描版 PDF 需要，可选）

```bash
# Ubuntu/Debian 安装 tesseract
sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim
```

### 1. 克隆项目

```bash
git clone https://github.com/你的用户名/medical-qms-rag.git
cd medical-qms-rag
```

### 2. 配置 API Key

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 API 信息：

```env
API_KEY=sk-poe-你的key
API_BASE_URL=https://api.poe.com/v1
CLAUDE_MODEL=claude-opus-4-6
```

> 支持任何 OpenAI 兼容 API（Poe、OpenAI、Azure、本地 Ollama 等）

### 3. 一键启动

```bash
bash start.sh
```

首次运行会自动创建 conda 环境（约 2-3 分钟）。启动后访问：

**http://localhost:8003**

### 4. 上传文档开始问答

在界面左侧上传法规 PDF 文件，选择对应集合（法规/标准/指导原则），然后在右侧对话框提问。

## 批量导入文档

```bash
# 批量抓取内置法规链接（含自动下载+OCR）
conda activate medical_qms
python scripts/batch_fetch.py

# 批量导入本地目录
python scripts/ingest.py data/documents/

# 更换 chunker 后重新索引所有文件
python scripts/reingest_all.py
```

## API 文档

启动后访问 **http://localhost:8003/docs** 查看 Swagger 文档。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/query` | 问答（阻塞） |
| POST | `/api/query/stream` | 问答（SSE 流式） |
| POST | `/api/documents/upload` | 上传文档 |
| GET | `/api/documents` | 列出文档 |
| DELETE | `/api/documents/{id}` | 删除文档 |
| GET | `/api/health` | 健康检查 |

## 推荐上传的文档

### 法规文件
- 《医疗器械监督管理条例》（国务院令第739号）
- 《医疗器械注册与备案管理办法》
- 《网络安全法》《数据安全法》《个人信息保护法》

### 国家/行业标准
- YY/T 0287 / ISO 13485 医疗器械质量管理体系
- GB/T 42062 / ISO 14971 医疗器械风险管理
- YY/T 0664 医疗器械软件文档
- YY/T 1833.1 医疗器械网络安全

### 指导原则
- 医疗器械软件注册审查指导原则
- 医疗器械临床评价技术指导原则
- 医疗器械网络安全注册审查指导原则

## 常见问题

**Q: 支持哪些 API？**
A: 任何 OpenAI 兼容接口，修改 `.env` 中的 `API_BASE_URL` 和 `CLAUDE_MODEL` 即可。

**Q: 扫描版 PDF 支持吗？**
A: 支持，需安装 tesseract-ocr。系统会自动检测并调用 OCR。

**Q: 数据存在哪里？**
A: 文档存于 `data/documents/`，索引存于 `qms.db`，均在项目根目录，不会上传到 GitHub。
