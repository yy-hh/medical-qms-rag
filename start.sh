#!/bin/bash
# 一键启动 Medical QMS RAG 服务

set -e
cd "$(dirname "$0")"

# 检查 .env
if [ ! -f .env ]; then
  echo "未找到 .env 文件，正在从模板创建..."
  cp .env.example .env
  echo "请编辑 .env 填入 API_KEY 后重新运行"
  exit 1
fi

# 检查 conda 环境
if ! conda env list | grep -q "medical_qms"; then
  echo "正在创建 conda 环境（首次约需 2-3 分钟）..."
  conda env create -f environment.yml
fi

# 检查 tesseract（PDF OCR 需要）
if ! command -v tesseract &> /dev/null; then
  echo "提示：未检测到 tesseract，扫描版 PDF 将无法 OCR。"
  echo "安装方法：sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim"
fi

echo "启动 Medical QMS RAG 服务 (http://localhost:8003)..."
conda run -n medical_qms uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
