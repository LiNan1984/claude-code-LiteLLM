#!/usr/bin/env python3
"""Stress test MiMo-V2.5 to find concurrency limit.

Usage:
  python3 bench-mimo-v25.py [BASE_URL]
"""

import asyncio
import json
import sys
import time
import statistics

import aiohttp

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "https://lalong--mimo-v25-vllm-serve.modal.run"
MODEL = "XiaomiMiMo/MiMo-V2.5"

PAYLOAD = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "What is 17*19? Answer briefly."}],
    "max_tokens": 64,
    "temperature": 0.7,
    "stream": True,
}

# Escalating concurrency - stops when success rate drops below threshold
CONCURRENCY_LEVELS = [256, 384, 512, 768, 1024]
REQUESTS_PER_LEVEL = 16
MIN_SUCCESS_RATE = 0.5  # stop if less than 50% succeed
PER_REQ_TIMEOUT = 120


async def single_request(session: aiohttp.ClientSession, req_id: int) -> dict:
    start = time.monotonic()
    result = {"id": req_id, "status": None, "ttft": None, "tokens": 0, "total_time": None, "error": None}
    try:
        async with session.post(
            "/v1/chat/completions",
            json=PAYLOAD,
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            timeout=aiohttp.ClientTimeout(total=PER_REQ_TIMEOUT),
        ) as resp:
            result["status"] = resp.status
            if resp.status != 200:
                body = await resp.text()
                result["error"] = f"HTTP {resp.status}: {body[:200]}"
                return result
            first_token = None
            async for raw in resp.content:
                line = raw.decode().strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    if first_token is None:
                        first_token = time.monotonic()
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0]["delta"]
                        if delta.get("content"):
                            result["tokens"] += 1
                    except Exception:
                        pass
            end = time.monotonic()
            result["total_time"] = end - start
            if first_token:
                result["ttft"] = first_token - start
    except Exception as e:
        result["error"] = str(e)[:200]
        result["total_time"] = time.monotonic() - start
    return result


async def bench_level(session: aiohttp.ClientSession, concurrency: int, n_reqs: int) -> list[dict]:
    sem = asyncio.Semaphore(concurrency)
    async def bounded(req_id):
        async with sem:
            return await single_request(session, req_id)
    return await asyncio.gather(*[bounded(i + 1) for i in range(n_reqs)])


def print_results(concurrency: int, results: list[dict], wall: float):
    ok = [r for r in results if r["error"] is None and r["status"] == 200]
    fail = [r for r in results if r["error"] is not None or r["status"] != 200]
    rate = len(ok) / len(results) * 100

    print(f"\n{'='*65}")
    print(f"Concurrency: {concurrency} | {len(ok)}/{len(results)} OK ({rate:.0f}%) | Wall: {wall:.1f}s")
    print(f"{'='*65}")

    if ok:
        ttfts = [r["ttft"] for r in ok if r["ttft"] is not None]
        lats = [r["total_time"] for r in ok if r["total_time"] is not None]
        toks = sum(r["tokens"] for r in ok)
        total_t = sum(lats) if lats else 1

        if ttfts:
            print(f"  TTFT:  min={min(ttfts):.2f}s  avg={statistics.mean(ttfts):.2f}s  "
                  f"p50={statistics.median(ttfts):.2f}s  max={max(ttfts):.2f}s")
        if lats:
            print(f"  Latency: min={min(lats):.2f}s  avg={statistics.mean(lats):.2f}s  "
                  f"p50={statistics.median(lats):.2f}s  max={max(lats):.2f}s")
        print(f"  Tokens: {toks} total | Throughput: {toks/total_t:.1f} tok/s | "
              f"Effective: {toks/wall:.1f} tok/s (wall-clock)")

    for r in fail:
        print(f"  REQ-{r['id']}: FAIL ({r.get('total_time',0):.1f}s) {r.get('error','')[:80]}")

    return len(ok) / len(results)


async def main():
    print(f"=== MiMo-V2.5 STRESS TEST (No Limit) ===")
    print(f"Endpoint: {BASE_URL}")
    print(f"Levels: {CONCURRENCY_LEVELS}")
    print(f"Requests/level: {REQUESTS_PER_LEVEL}")
    print(f"Stop condition: success rate < {MIN_SUCCESS_RATE*100:.0f}%")

    async with aiohttp.ClientSession(base_url=BASE_URL) as session:
        # Health check
        print(f"\nWaiting for server...")
        for attempt in range(40):
            try:
                async with session.get("/health", timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        print("Server healthy!")
                        break
            except Exception:
                pass
            if attempt % 5 == 0:
                print(f"  Attempt {attempt+1}...")
            await asyncio.sleep(15)
        else:
            print("Server not ready, exiting.")
            sys.exit(1)

        summary = []
        stop = False

        for conc in CONCURRENCY_LEVELS:
            t0 = time.monotonic()
            results = await bench_level(session, conc, REQUESTS_PER_LEVEL)
            wall = time.monotonic() - t0

            ok = [r for r in results if r["error"] is None and r["status"] == 200]
            rate = print_results(conc, results, wall)

            summary.append({
                "conc": conc,
                "ok": len(ok),
                "total": len(results),
                "rate": rate,
                "wall": wall,
                "results": results,
            })

            if rate < MIN_SUCCESS_RATE:
                print(f"\n>>> SUCCESS RATE {rate*100:.0f}% < {MIN_SUCCESS_RATE*100:.0f}% threshold — STOPPING")
                stop = True
                break

        # Final summary
        print(f"\n{'='*65}")
        print("FINAL SUMMARY")
        print(f"{'='*65}")
        print(f"{'Conc':>4} | {'OK':>5} | {'Rate':>5} | {'AvgTTFT':>8} | {'AvgLat':>8} | {'Eff tok/s':>9}")
        print("-" * 65)

        best_throughput = 0
        best_conc = 0
        for s in summary:
            ok = [r for r in s["results"] if r["error"] is None]
            ttfts = [r["ttft"] for r in ok if r["ttft"]]
            lats = [r["total_time"] for r in ok if r["total_time"]]
            toks = sum(r["tokens"] for r in ok)
            eff = toks / s["wall"] if s["wall"] > 0 else 0
            avg_ttft = statistics.mean(ttfts) if ttfts else 0
            avg_lat = statistics.mean(lats) if lats else 0
            print(f"{s['conc']:>4} | {s['ok']:>3}/{s['total']:<2} | {s['rate']*100:>4.0f}% | "
                  f"{avg_ttft:>7.2f}s | {avg_lat:>7.2f}s | {eff:>8.1f}")
            if eff > best_throughput:
                best_throughput = eff
                best_conc = s["conc"]

        print(f"\n>>> BEST THROUGHPUT: {best_throughput:.1f} tok/s at concurrency {best_conc}")
        if stop:
            print(f">>> CONCURRENCY LIMIT REACHED (>{summary[-1]['conc']} causes >50% failures)")


if __name__ == "__main__":
    asyncio.run(main())
