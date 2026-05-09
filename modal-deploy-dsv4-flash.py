# ---
# pytest: false
# ---
# # Deploy DeepSeek-V4-Flash on Modal with vLLM 0.20 (OpenAI-compatible)
#
# ## Deploy
#   modal deploy modal-deploy-dsv4-flash.py
#
# ## Test locally
#   modal run modal-deploy-dsv4-flash.py

import subprocess

import modal

# ── Container image ──────────────────────────────────────────────────────────
vllm_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.8.0-devel-ubuntu22.04", add_python="3.12"
    )
    .entrypoint([])
    .uv_pip_install(
        "vllm==0.20.0",
        "huggingface-hub==0.36.0",
    )
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

# ── Model config ─────────────────────────────────────────────────────────────
MODEL_NAME = "deepseek-ai/DeepSeek-V4-Flash"
# 284B total / 13B activated MoE, FP4+FP8 mixed. ~150GB weights.
# 2x H200 (2x 141GB = 282GB) fits weights + KV cache with reduced context.
N_GPU = 2
MAX_CTX = 65536  # reduce from 1M to fit KV cache on 2x H200
FAST_BOOT = True

# ── Volumes for caching ──────────────────────────────────────────────────────
hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-cache", create_if_missing=True)

MINUTES = 60
VLLM_PORT = 8000

app = modal.App("dsv4-flash-vllm")


@app.function(
    image=vllm_image,
    gpu=f"H200:{N_GPU}",
    scaledown_window=15 * MINUTES,
    timeout=15 * MINUTES,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
)
@modal.concurrent(max_inputs=16)
@modal.web_server(port=VLLM_PORT, startup_timeout=15 * MINUTES)
def serve():
    cmd = [
        "vllm",
        "serve",
        MODEL_NAME,
        "--served-model-name", MODEL_NAME,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--tensor-parallel-size", str(N_GPU),
        "--max-model-len", str(MAX_CTX),
        "--trust-remote-code",
        "--tokenizer-mode", "deepseek_v4",
        "--reasoning-parser", "deepseek_v4",
        "--kv-cache-dtype", "fp8",
        "--block-size", "256",
        "--max-num-seqs", "8",
        "--enforce-eager" if FAST_BOOT else "--no-enforce-eager",
    ]
    print("Starting vLLM server:", " ".join(cmd))
    subprocess.Popen(" ".join(cmd), shell=True)


# ── Local test entrypoint ────────────────────────────────────────────────────
@app.local_entrypoint()
async def main():
    import aiohttp
    import json

    url = serve.get_web_url()
    print(f"Server URL: {url}")

    async with aiohttp.ClientSession(base_url=url) as session:
        print("Waiting for server...")
        async with session.get("/health", timeout=aiohttp.ClientTimeout(total=840)) as resp:
            assert resp.status == 200
            print("Server is healthy!")

        # Non-think mode
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": "What is 17*19?"}],
            "max_tokens": 256,
            "temperature": 1.0,
            "top_p": 1.0,
            "stream": True,
        }
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}

        print("\n--- Non-think mode ---")
        async with session.post(
            "/v1/chat/completions", json=payload, headers=headers
        ) as resp:
            async for raw in resp.content:
                line = raw.decode().strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    chunk = json.loads(line[6:])
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    print(delta, end="", flush=True)
        print()
