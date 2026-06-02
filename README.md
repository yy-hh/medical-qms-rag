# 医疗行业 QMS 智能问答系统

基于 RAG（检索增强生成）的医疗器械质量管理体系法规智能问答平台。

## 功能特性

- **文档管理**：支持上传 PDF / DOCX / TXT / MD 格式的法规文件
- **智能问答**：基于上传文件内容，由 Claude 生成精准回答
- **来源引用**：每条回答附带原始文件来源和相关度评分
- **多集合管理**：按类别（法规、标准、指导原则）组织文档
- **批量导入**：命令行工具支持批量导入文档目录

## 系统架构

```
用户问题 → Embedding → ChromaDB 向量检索 → Top-K 相关文档块 → Claude 生成回答
```

| 组件 | 技术 |
|------|------|
| 向量嵌入 | BAAI/bge-small-zh-v1.5（中文优化） |
| 向量数据库 | ChromaDB（本地持久化） |
| LLM | Claude claude-sonnet-4-6 |
| 后端框架 | FastAPI |
| 文档解析 | PyMuPDF / python-docx |

## 快速开始

### 1. 创建环境

```bash
conda env create -f environment.yml
conda activate medical_qms
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY
```

### 3. 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

访问 http://localhost:8003

### 4. 批量导入文档（可选）

```bash
# 导入单个文件
python scripts/ingest.py path/to/document.pdf

# 导入整个目录
python scripts/ingest.py data/documents/ --collection regulations
```

## API 文档

启动后访问 http://localhost:8003/docs 查看完整 Swagger API 文档。

### 核心接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/documents/upload` | 上传文档 |
| GET | `/api/documents` | 列出文档 |
| DELETE | `/api/documents/{doc_id}` | 删除文档 |
| POST | `/api/query` | 提问 |
| GET | `/api/health` | 健康检查 |

## 推荐上传的文档类型

### 法规文件
- 《医疗器械监督管理条例》（2021）
- 《医疗器械注册与备案管理办法》
- 《体外诊断试剂注册与备案管理办法》

### 国家标准
- YY/T 0287 / ISO 13485 医疗器械质量管理体系
- GB/T 42062 / ISO 14971 医疗器械风险管理
- YY/T 0316 医疗器械软件相关标准

### 指导原则
- 医疗器械软件注册审查指导原则
- 医疗器械临床评价技术指导原则
- 医疗器械网络安全注册审查指导原则
