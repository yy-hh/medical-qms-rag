# QMS 体系搭建助手

面向医疗器械软件（SaMD）企业的质量管理体系搭建平台，覆盖中国 NMPA、欧盟 CE/MDR、美国 FDA 多市场合规要求。

## 功能模块

### 🗺️ 体系地图
按 4 个实施阶段展示 43 份必要文件（质量手册、程序文件、记录表单），标注对应标准（ISO 13485、IEC 62304、ISO 14971 等）和适用市场，点击任意文件可直接触发生成。

### 📝 文件生成器
选择文件类型 → AI 流式生成定制化模板。模板结合公司信息（企业名称、产品、预期用途）自动填入，生成后可直接复制使用。

### 💬 法规顾问
上传法规/标准文件后，基于 RAG 检索回答问题，支持多轮追问，回答附带原文来源引用。

### ⚙️ 公司信息
配置企业名称、产品名称、注册类别、目标市场，所有文件生成和顾问回答自动结合公司信息。

## 系统架构

```
文件生成：公司信息 + 文件类型 → Claude 流式生成定制模板
法规问答：问题 → jieba BM25 检索 → Top-K 相关条款 → Claude 生成回答
```

| 组件 | 技术 |
|------|------|
| 检索引擎 | BM25Okapi + jieba（医学专业词典）|
| 存储 | SQLite（本地持久化）|
| LLM | OpenAI 兼容 API（默认 Poe + Claude Opus）|
| 后端 | FastAPI + SSE 流式输出 |
| 文档解析 | PyMuPDF / python-docx / pytesseract（OCR）|

## 适用场景

- **SaMD 软件**（二类 / 三类）
- **多市场注册**：中国 NMPA、欧盟 CE/MDR、美国 FDA
- **从零开始**搭建质量管理体系

涵盖标准：ISO 13485、IEC 62304、ISO 14971、IEC 62366、YY/T 0664、YY/T 1833.1、GDPR、个人信息保护法等。

## 快速开始

### 环境要求

- Linux / macOS（Windows 建议 WSL2）
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) 或 Anaconda
- tesseract-ocr（扫描版 PDF 需要，可选）

```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim
```

### 安装与启动

```bash
# 1. 克隆项目
git clone https://github.com/yy-hh/medical-qms-rag.git
cd medical-qms-rag

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 API_KEY（支持任何 OpenAI 兼容接口）

# 3. 一键启动（首次自动创建 conda 环境，约 2-3 分钟）
bash start.sh
```

访问 **http://localhost:8003**

### .env 配置示例

```env
API_KEY=sk-poe-你的key
API_BASE_URL=https://api.poe.com/v1
CLAUDE_MODEL=claude-opus-4-6
```

> 支持 Poe、OpenAI、Azure、本地 Ollama 等任何 OpenAI 兼容 API。

## 使用流程

1. **配置公司信息** → 填写企业名称、产品、目标市场
2. **查看体系地图** → 了解需要建立的所有 QMS 文件
3. **生成文件模板** → 点击文件 → AI 生成定制化模板
4. **上传法规文件** → 导入相关法规 PDF，开启问答功能

## API 文档

启动后访问 **http://localhost:8003/docs**

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/company` | 公司信息读写 |
| GET | `/api/generate/framework` | QMS 体系框架数据 |
| POST | `/api/generate/stream` | 文件生成（SSE 流式）|
| POST | `/api/query/stream` | 法规问答（SSE 流式）|
| POST | `/api/documents/upload` | 上传法规文件 |
| GET | `/api/health` | 健康检查 |

## 注意事项

- 上传的法规文件和知识库数据（`qms.db`、`data/documents/`）不会同步到 GitHub
- 另一台电脑克隆后需重新上传法规文件，或运行 `python scripts/batch_fetch.py` 自动抓取
- 生成的文件模板为起点，需结合实际情况修改完善，不能直接作为注册提交材料
