#!/bin/bash
# LiteLLM 代理启动脚本
# 使用方法: ./start-litellm.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LITELLM_BIN="$PROJECT_DIR/.venv/bin/litellm"
CONFIG="$SCRIPT_DIR/config.yaml"
PORT=4000

if [ ! -f "$CONFIG" ]; then
    echo "Error: config.yaml not found. Run: cp config.yaml.example config.yaml"
    exit 1
fi

if [ ! -f "$LITELLM_BIN" ]; then
    echo "Error: LiteLLM not installed. Run: uv pip install 'litellm[proxy]'"
    exit 1
fi

echo "Starting LiteLLM proxy on port $PORT..."
$LITELLM_BIN --config "$CONFIG" --port $PORT
