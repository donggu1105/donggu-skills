#!/usr/bin/env bash
# ComfyUI 로컬 서비스 기동 (127.0.0.1:8188, Apple Silicon MPS).
# gen_image.py --backend comfyui 가 호출하는 그 서버.
# 사용: bash start_comfyui.sh   (이미 떠 있으면 그대로 둠)
set -e
COMFY="${COMFYUI_DIR:-$HOME/ComfyUI}"
PORT="${COMFYUI_PORT:-8188}"

if curl -sf "http://127.0.0.1:${PORT}/system_stats" >/dev/null 2>&1; then
  echo "ComfyUI already running on :${PORT}"
  exit 0
fi

cd "$COMFY"
mkdir -p "$COMFY/logs"
nohup "$COMFY/.venv/bin/python" main.py --listen 127.0.0.1 --port "$PORT" \
  > "$COMFY/logs/comfyui.log" 2>&1 &
echo "ComfyUI starting (pid $!) — log: $COMFY/logs/comfyui.log"
# 준비 대기(최대 ~60s: 모델 로드 포함은 첫 생성 때)
for i in $(seq 1 30); do
  sleep 2
  if curl -sf "http://127.0.0.1:${PORT}/system_stats" >/dev/null 2>&1; then
    echo "ComfyUI ready on :${PORT}"; exit 0
  fi
done
echo "ComfyUI not ready yet — check $COMFY/logs/comfyui.log"; exit 1
