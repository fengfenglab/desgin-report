#!/usr/bin/env bash
# 一键：PPTX/PDF → 汇报网页。用法: ./run.sh 方案.pptx 项目代号 [已导出的.pdf]
set -e
cd "$(dirname "$0")"
SRC="$1"; PROJ="$2"; PDF="$3"
[ -z "$SRC" ] || [ -z "$PROJ" ] && { echo "用法: ./run.sh 方案.pptx 项目代号 [已导出的.pdf]"; exit 1; }
python3 tools/extract.py "$SRC" --project "$PROJ" ${PDF:+--pdf "$PDF"}
python3 tools/classify.py --project "$PROJ"
python3 tools/build.py --project "$PROJ" --lite
echo "网页已生成：out/$PROJ/index.html  （改 work/$PROJ/config.json 后重跑 build.py 即可）"
