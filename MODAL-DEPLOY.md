# Modal LLM 部署文档

## 已部署模型

| 模型 | 参数量 | 精度 | GPU | 上下文 | API 地址 |
|------|--------|------|-----|--------|----------|
| Qwen3.6-27B | 27B Dense | BF16 | 1x H100 | 65,536 | `https://lalong--qwen36-27b-vllm-serve.modal.run` |
| Qwen3.5-9B | 9B Dense | BF16 | 1x H100 | 131,072 | `https://lalong--qwen35-9b-vllm-serve.modal.run` |

## 部署架构

```
用户请求 → Modal Web Server (HTTPS) → vLLM (OpenAI 兼容 API) → H100 GPU
                ↑
         冷启动时返回 303 重定向
```

- **推理引擎**: vLLM 0.19.0
- **运行时**: NVIDIA CUDA 12.8 + Python 3.12
- **模型缓存**: Modal Volume (`huggingface-cache`, `vllm-cache`)
- **自动缩容**: 15 分钟无请求后释放 GPU
- **冷启动**: 约 1-2 分钟（含模型加载）

## 部署文件

| 文件 | 用途 |
|------|------|
| `modal-deploy-qwen36-27b.py` | Qwen3.6-27B 部署脚本 |
| `modal-deploy-qwen35-9b.py` | Qwen3.5-9B 部署脚本 |

### 部署/更新

```bash
modal deploy modal-deploy-qwen36-27b.py
modal deploy modal-deploy-qwen35-9b.py
```

### 查看日志

```bash
modal app logs qwen36-27b-vllm
modal app logs qwen35-9b-vllm
```

### 管理控制台

https://modal.com/apps/lalong/main

## API 调用

### 注意事项

- curl 必须加 `-L --post303` 处理 Modal 冷启动的 303 重定向
- 流式请求加 `-N` 禁用 curl 缓冲

### 流式请求（默认思考模式）

```bash
curl -N -L --post303 https://lalong--qwen36-27b-vllm-serve.modal.run/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.6-27B",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 8192,
    "temperature": 1.0,
    "top_p": 0.95,
    "stream": true
  }'
```

### 关闭推理（非思考模式）

```bash
curl -N -L --post303 https://lalong--qwen36-27b-vllm-serve.modal.run/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.6-27B",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 1024,
    "temperature": 0.7,
    "top_p": 0.80,
    "presence_penalty": 1.5,
    "stream": true,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

### Python SDK 调用

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://lalong--qwen36-27b-vllm-serve.modal.run/v1",
    api_key="EMPTY"
)

# 思考模式
response = client.chat.completions.create(
    model="Qwen/Qwen3.6-27B",
    messages=[{"role": "user", "content": "你好"}],
    max_tokens=8192,
    temperature=1.0,
    top_p=0.95,
    extra_body={"top_k": 20},
)

# 非思考模式
response = client.chat.completions.create(
    model="Qwen/Qwen3.6-27B",
    messages=[{"role": "user", "content": "你好"}],
    max_tokens=1024,
    temperature=0.7,
    top_p=0.80,
    presence_penalty=1.5,
    extra_body={
        "top_k": 20,
        "chat_template_kwargs": {"enable_thinking": False},
    },
)
```

### 接入 LiteLLM

```yaml
model_list:
  - model_name: qwen3.6-27b
    litellm_params:
      model: openai/Qwen/Qwen3.6-27B
      api_base: https://lalong--qwen36-27b-vllm-serve.modal.run/v1
      api_key: EMPTY

  - model_name: qwen3.5-9b
    litellm_params:
      model: openai/Qwen/Qwen3.5-9B
      api_base: https://lalong--qwen35-9b-vllm-serve.modal.run/v1
      api_key: EMPTY
```

## 推荐参数

| 场景 | temperature | top_p | top_k | presence_penalty |
|------|-------------|-------|-------|------------------|
| 思考模式（通用） | 1.0 | 0.95 | 20 | 0.0 |
| 思考模式（编程） | 0.6 | 0.95 | 20 | 0.0 |
| 非思考模式 | 0.7 | 0.80 | 20 | 1.5 |

## 性能基准

### Qwen3.6-27B (单卡 H100)

| 指标 | 数值 |
|------|------|
| 模型显存占用 | 51.1 GiB |
| TTFT (首 token) | ~1.3s |
| 生成速度 (thinking) | ~13 tok/s |
| 生成速度 (content) | ~15 tok/s |
| 模型加载时间 | ~5 min (Volume 缓存) |

## vLLM 启动参数说明

| 参数 | 值 | 说明 |
|------|-----|------|
| `--reasoning-parser` | `qwen3` | 解析思考内容到 reasoning 字段 |
| `--gdn-prefill-backend` | `triton` | 避免 FlashInfer JIT 编译导致的首次请求卡顿 |
| `--enforce-eager` | (Qwen3.6) | 禁用 Torch 编译和 CUDA graph，加快冷启动 |
| `--max-model-len` | 按模型不同 | 最大上下文长度 |

## 常见问题

### curl 无返回

加 `-L --post303`。Modal 冷启动返回 303 重定向，默认 curl 会把 POST 变 GET。

### 首次请求很慢

冷启动需要加载模型到 GPU（约 1-5 分钟）。后续请求秒级响应。

### 如何减少冷启动

- 增大 `scaledown_window` 保持容器存活更久
- 使用 `keep_warm` 参数维持最小副本
- 预加载模型权重到镜像（适用于小模型）
