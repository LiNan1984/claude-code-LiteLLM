# ---
# pytest: false
# ---
# # Deploy Qwen3.5-9B on Modal with vLLM (OpenAI-compatible)
#
# ## Deploy
#   modal deploy modal-deploy-qwen35-9b.py
#
# ## Test locally
#   modal run modal-deploy-qwen35-9b.py

import subprocess

import modal

# ── Container image ──────────────────────────────────────────────────────────
vllm_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.8.0-devel-ubuntu22.04", add_python="3.12"
    )
    .entrypoint([])
    .uv_pip_install(
        "vllm==0.19.0",
        "huggingface-hub==0.36.0",
    )
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

# ── Model config ─────────────────────────────────────────────────────────────
MODEL_NAME = "Qwen/Qwen3.5-9B"
# 9B model ~18GB in BF16. Single H100 has plenty of room for large KV cache.
N_GPU = 1
MAX_CTX = 131072  # 9B fits easily, use larger context
FAST_BOOT = True

# ── Volumes for caching ──────────────────────────────────────────────────────
hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-cache", create_if_missing=True)

MINUTES = 60
VLLM_PORT = 8000

app = modal.App("qwen35-9b-vllm")


@app.function(
    image=vllm_image,
    gpu=f"H100:{N_GPU}",
    scaledown_window=15 * MINUTES,
    timeout=10 * MINUTES,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
)
@modal.concurrent(max_inputs=32)
@modal.web_server(port=VLLM_PORT, startup_timeout=10 * MINUTES)
def serve():
    cmd = [
        "vllm",
        "serve",
        MODEL_NAME,
        "--served-model-name",
        MODEL_NAME,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--tensor-parallel-size", str(N_GPU),
        "--max-model-len", str(MAX_CTX),
        "--reasoning-parser", "qwen3",
        "--gdn-prefill-backend", "triton",
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
        async with session.get("/health", timeout=aiohttp.ClientTimeout(total=540)) as resp:
            assert resp.status == 200
            print("Server is healthy!")

        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": "Write a haiku about GPUs."}],
            "max_tokens": 512,
            "temperature": 1.0,
            "top_p": 0.95,
            "stream": True,
        }
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}

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
