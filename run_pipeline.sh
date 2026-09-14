#!/bin/bash
# 全量流水线：先慢速下载全部 720p（断点续跑、内置限速/间隔/412冷却），
# 下载阶段结束后单模型常驻批量转写全部。任一阶段中断后重跑本脚本即可续：
# 下载器自动跳过已下载，转写器自动跳过已转写。
set -u
cd "$(dirname "$0")"
PY3=/usr/bin/python3
FP="/Users/wenjiechen/Doubao/chats/2026-08-26/new-chat/gaodun-course-knowledge-base/transcription/venv/bin/python"

echo "===== [$(date '+%F %T')] 阶段1/2 全量下载 720p（单线程·限速2MiB/s·防风控）====="
"$PY3" -u batch_build.py --quality 720 2>&1
echo "===== [$(date '+%F %T')] 下载阶段结束，进入阶段2/2 批量转写 ====="
"$FP" -u batch_transcribe.py --lang zh 2>&1
echo "===== [$(date '+%F %T')] ALL DONE ====="
