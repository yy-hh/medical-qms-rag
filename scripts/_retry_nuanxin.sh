#!/bin/bash
# 暖欣 Dx 补生成守护：链路探测通过才触发，避免抖动期空转。
# 跑：5份程序文件 + L1-001/L4-001 整篇重生。完成后写 .done 哨兵，定时任务见哨兵即跳过。
set -e
cd /home/ubuntu/Documents/trae_projects/medical-qms-rag
PY=~/miniconda3/envs/medical_qms/bin/python
DONE=/tmp/nuanxin_retry.done
LOCK=/tmp/nuanxin_retry.lock

[ -f "$DONE" ] && exit 0
# 防重入：已有补生成进程在跑就退出
pgrep -f "scripts/batch_generate.py" >/dev/null 2>&1 && exit 0
[ -f "$LOCK" ] && exit 0

# 链路探测：成功返回非空才继续
probe=$(PYTHONNOUSERSITE=1 PYTHONPATH=. $PY -c "
from app.core.rag_engine import curl_chat_stream
from app.core.config import settings
k=settings.api_key or settings.anthropic_api_key
try:
    g=''
    for ch in curl_chat_stream(k,settings.api_base_url,settings.claude_model,[{'role':'user','content':'回复:OK'}],16,connect_timeout=15,max_time=45):
        c=ch.choices[0].delta.content
        if c: g+=c
    print('UP' if g.strip() else 'DOWN')
except Exception:
    print('DOWN')
" 2>/dev/null | tail -1)

if [ "$probe" != "UP" ]; then
  echo "$(date '+%F %T') 链路未恢复($probe)，跳过" >> /tmp/nuanxin_retry.log
  exit 0
fi

touch "$LOCK"
echo "$(date '+%F %T') 链路恢复，开始补生成" >> /tmp/nuanxin_retry.log
PYTHONNOUSERSITE=1 PYTHONPATH=. $PY -u scripts/batch_generate.py \
  L2-012 L2-002 L2-011 L2-006 L3-003 L1-001 L4-001 >> /tmp/nuanxin_gen3.log 2>&1
touch "$DONE"
rm -f "$LOCK"
echo "$(date '+%F %T') 补生成进程结束" >> /tmp/nuanxin_retry.log
