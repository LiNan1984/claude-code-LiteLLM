# ---
# pytest: false
# ---
# # Deploy MiMo-V2.5 (310B/15B MoE) on Modal with vLLM (OpenAI-compatible)
#
# Hardware: 4x H200 (564GB) — official vLLM recipe recommendation
# Model:   XiaomiMiMo/MiMo-V2.5 — 310B total, 15B active, native FP8, omnimodal
# Engine:  vLLM mimov25-cu129 (pre-built, stable vLLM doesn't support MiMo yet)
#
# ## Step 1: Pre-download model weights (run once)
#   modal run modal-deploy-mimo-v25.py::download_weights
#
# ## Step 2: Deploy
#   modal deploy modal-deploy-mimo-v25.py
#
# ## Test locally
#   modal run modal-deploy-mimo-v25.py

import subprocess

import modal

# ── Container images ─────────────────────────────────────────────────────────
# Lightweight image for downloading weights (no GPU needed)
download_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("huggingface-hub==0.36.0")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

# vLLM image for serving (has everything built-in, no extra installs)
serve_image = (
    modal.Image.from_registry(
        "vllm/vllm-openai:mimov25-cu129",
        add_python="3.12",
    )
    .entrypoint([])
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

# ── Model config ─────────────────────────────────────────────────────────────
MODEL_NAME = "XiaomiMiMo/MiMo-V2.5"
N_GPU = 4
MAX_CTX = 32768

# ── Volumes for caching ──────────────────────────────────────────────────────
hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-cache", create_if_missing=True)

MINUTES = 60
VLLM_PORT = 8000

app = modal.App("mimo-v25-vllm")


# ── Step 1: Pre-download weights to Volume ───────────────────────────────────
@app.function(
    image=download_image,
    timeout=30 * MINUTES,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
    },
)
def download_weights():
    """Pre-download model weights to Modal Volume (run once before deploy)."""
    import huggingface_hub
    import os

    cache_dir = "/root/.cache/huggingface/hub"
    print(f"Downloading {MODEL_NAME} (~316GB) to {cache_dir}...")

    if os.path.exists(cache_dir):
        total = sum(
            os.path.getsize(os.path.join(dp, f))
            for dp, dn, fn in os.walk(cache_dir)
            for f in fn
        )
        print(f"Cache dir size before: {total / 1e9:.1f} GB")

    huggingface_hub.snapshot_download(
        MODEL_NAME,
        cache_dir=cache_dir,
    )

    total = sum(
        os.path.getsize(os.path.join(dp, f))
        for dp, dn, fn in os.walk(cache_dir)
        for f in fn
    )
    print(f"Cache dir size after: {total / 1e9:.1f} GB")
    hf_cache_vol.commit()
    print("Weights saved to Volume!")


# ── Step 2: Serve ────────────────────────────────────────────────────────────
@app.function(
    image=serve_image,
    gpu=f"H200:{N_GPU}",
    scaledown_window=15 * MINUTES,
    timeout=30 * MINUTES,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
)
@modal.concurrent(max_inputs=128)
@modal.web_server(port=VLLM_PORT, startup_timeout=30 * MINUTES)
def serve():
    cmd = [
        "vllm", "serve", MODEL_NAME,
        "--served-model-name", MODEL_NAME,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--tensor-parallel-size", str(N_GPU),
        "--trust-remote-code",
        "--gpu-memory-utilization", "0.95",
        "--max-model-len", str(MAX_CTX),
        "--reasoning-parser", "mimo",
        "--tool-call-parser", "mimo",
        "--enable-auto-tool-choice",
        "--generation-config", "vllm",
        "--kv-cache-dtype", "fp8",
        "--block-size", "256",
        "--max-num-seqs", "8",
        "--enforce-eager",
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
        print("Waiting for server (cold start ~3-5 min with cached weights)...")
        async with session.get("/health", timeout=aiohttp.ClientTimeout(total=840)) as resp:
            assert resp.status == 200
            print("Server is healthy!")

        # Non-think mode
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": "Hello! What is 17*19?"}],
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

        # Think mode
        payload_think = {
            **payload,
            "max_tokens": 2048,
            "chat_template_kwargs": {"enable_thinking": True},
        }
        print("\n--- Think mode ---")
        async with session.post(
            "/v1/chat/completions", json=payload_think, headers=headers
        ) as resp:
            async for raw in resp.content:
                line = raw.decode().strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    chunk = json.loads(line[6:])
                    delta = chunk["choices"][0]["delta"]
                    content = delta.get("content", "")
                    reasoning = delta.get("reasoning", "")
                    if reasoning:
                        print(f"[think]{reasoning}[/think]", end="", flush=True)
                    if content:
                        print(content, end="", flush=True)
        print()
