#!/usr/bin/env python3
"""
LiteLLM 启动脚本（修复 SSL 兼容性问题）
用法: python3 start-litellm-ssl.py
"""
import ssl
import os
import sys

# 修复 OpenSSL 3.x UNEXPECTED_EOF_WHILE_READING 错误
# 某些服务器（如 finmall.com）关闭连接时缺少 TLS close_notify
original_create_default_context = ssl.create_default_context

def patched_create_default_context(*args, **kwargs):
    ctx = original_create_default_context(*args, **kwargs)
    # SSL_OP_IGNORE_UNEXPECTED_EOF = 0x4
    ctx.options |= 0x4
    return ctx

ssl.create_default_context = patched_create_default_context

# 同时设置 ssl_verify 为 False
os.environ.setdefault("SSL_VERIFY", "false")

# 启动 LiteLLM
from litellm import run_server

if __name__ == "__main__":
    sys.argv = ["litellm", "--config", "litellm-config/config.yaml", "--port", "4000"]
    run_server()
