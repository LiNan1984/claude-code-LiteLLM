# ---
# pytest: false
# ---
# # Deploy Qwen3.6-27B on Modal with vLLM (OpenAI-compatible)
#
# ## Deploy
#   modal deploy modal-deploy-qwen36-27b.py
#
# ## Test locally
#   modal run modal-deploy-qwen36-27b.py
#
# ## Usage (after deploy)
#   curl https://<your-app-url>/v1/chat/completions \
#     -H "Content-Type: application/json" \
#     -d '{"model":"Qwen/Qwen3.6-27B","messages":[{"role":"user","content":"Hello"}]}'

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
MODEL_NAME = "Qwen/Qwen3.6-27B"
# Full 27B dense model ~54GB in BF16. Single H100 (80GB) works with reduced ctx.
N_GPU = 1
MAX_CTX = 65536  # reduce from 262144 to fit single H100; increase with more GPUs
FAST_BOOT = True

# ── Volumes for caching ──────────────────────────────────────────────────────
hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-cache", create_if_missing=True)

MINUTES = 60
VLLM_PORT = 8000

app = modal.App("qwen36-27b-vllm")


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
        # Health check
        print("Waiting for server...")
        async with session.get("/health", timeout=aiohttp.ClientTimeout(total=540)) as resp:
            assert resp.status == 200
            print("Server is healthy!")

        # Test request
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
