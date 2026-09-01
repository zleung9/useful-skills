# Performance & Throughput Tuning

## Table of Contents
1. [The triton breakthrough (15× single-request)](#the-triton-breakthrough-15-single-request)
2. [Throughput benchmarks](#throughput-benchmarks)
3. [FULL graph capture](#full-graph-capture)
4. [Launch flags for throughput](#launch-flags-for-throughput)
5. [Understanding AICore utilization](#understanding-aicore-utilization)
6. [Concurrency is the real aggregate win](#concurrency-is-the-real-aggregate-win)
7. [Path to higher single-request throughput](#path-to-higher-single-request-throughput)

---

## The triton breakthrough (15× single-request)

**The single most important optimization:** replace the pure-PyTorch GDN decode
path with the triton `fused_recurrent_gated_delta_rule` kernel.

### What changed
The pure-PyTorch GDN decode path ran ~12 ops per layer × 30 GDN layers = **360
small unfused kernel launches** per decode step. Each kernel is tiny; even with
FULL graph capture eliminating Python dispatch gaps (93% AICore), the kernels
themselves were too small for good throughput → 3.1 tok/s.

The triton `fused_recurrent_gated_delta_rule` kernel (from
`vllm.model_executor.layers.fla.ops.fused_recurrent`) fuses **l2norm + gating +
delta-rule recurrence + state update** into **1 kernel** → 46.3 tok/s.

### Why it works on 910B4
The FLA triton kernels in `vllm.model_executor.layers.fla.ops.*` import and run
on the Ascend NPU via triton-ascend 3.2.0. An earlier `constexpr_function`
triton error **only affects vLLM's own `triton_kernels/`** (matmul_ogs) — those
use a C++17 feature the triton-ascend frontend doesn't support. The FLA ops use
plain triton Python → compile and run fine.

### Which kernel to use
- ✅ `fused_recurrent_gated_delta_rule` — **decode** (works, 0.4ms/call)
- ❌ `fused_sigmoid_gating_delta_rule_update` — even more fused, but FAILS on
  910B4: "ub overflow, requires 1593600 bits while 1572864 bits available"
  (shared memory overflow for our head dims)
- ❌ vllm-ascend's own triton chunk wrapper (`vllm_ascend/ops/triton/fla/chunk.py`)
  — **prefill** only, has a `prepare_chunk_indices` host-device bug on NPU. Use
  the pure-PyTorch chunk ref for prefill instead.

### Verify it's working
```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
export CC=/usr/local/Ascend/cann-8.5.0/tools/hcc/bin/aarch64-target-linux-gnu-g++
python3 scripts/verify_triton.py
# → "PASS: fused_recurrent_gated_delta_rule runs on NPU"
```

---

## Throughput benchmarks

**With triton (current working config):**

| Concurrent reqs | Throughput | AICore | vs PyTorch |
|----------------:|-----------:|-------:|-----------:|
| 1 | **46.3 tok/s** | 50-56% | **14.9×** |
| 4 | 105.9 tok/s | — | — |
| 16 | 246.8 tok/s | — | 5.9× |
| 32 | 317.9 tok/s | — | 4.4× |
| 64 | **385.7 tok/s** | — | 3.5× |

**Without triton (pure-PyTorch fallback, the old baseline):**

| Concurrent reqs | FULL tok/s | Eager tok/s | FULL AICore |
|----------------:|-----------:|------------:|------------:|
| 1 | 3.1 | 2.8 | 93% |
| 16 | 41.6 | 22.4 | ~93% |
| 32 | 72.5 | 32.0 | 93% |
| 64 | 111.0 | N/A | 93% |

---

## FULL graph capture

**Mode:** `cudagraph_mode: "FULL_AND_PIECEWISE"` (via `--compilation-config`).
- FULL for **decode** graph capture (35/35 captures)
- PIECEWISE for **prefill**
- **No `--enforce-eager`** (eager = 2.8 tok/s, kills throughput)

**Startup:** ~5-8 min (torch.compile 122s + 35/35 FULL capture ~55s). Watch the
log for `Capturing CUDA graphs (decode, FULL): 100%`.

**Requirements for FULL capture:**
- Vec decode paths (no `.item()` host syncs — the loop fallback has them)
- `scatter_` for state writeback (NOT `copy_` — see blocker #17 in blockers.md)
- N>1 guards removed (N=1 must also use vec path)

---

## Launch flags for throughput

```bash
vllm serve /models/qwen3.5-35b \
    --tensor-parallel-size 4 \
    --dtype bfloat16 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.90 \
    --trust-remote-code \
    --distributed-executor-backend mp \
    --compilation-config '{"fast_moe_cold_start": false, "cudagraph_mode": "FULL_AND_PIECEWISE"}'
```

- `cudagraph_mode: FULL_AND_PIECEWISE` — the throughput enabler
- `fast_moe_cold_start: false` — avoids a cold-start MoE path that triggers an unloadable aclnn op
- `--tensor-parallel-size 4` — mandatory (GDN conv_dim divisibility)
- `--max-model-len 8192` — divisible by TP=4 (2048), full 8192 usable

---

## Understanding AICore utilization

AICore goes **14% (eager) → 93% (PyTorch FULL) → 50-56% (triton FULL)** for
single requests.

This is counterintuitive: **lower AICore with triton, but higher throughput.**
The 93% AICore with PyTorch was "busy with overhead" — 360 tiny kernel launches
kept the NPU "active" but doing small work. The 50-56% with triton means the NPU
does the same work in fewer, larger, more efficient cycles. **Lower AICore +
higher throughput = genuine speedup, not utilization theater.**

Read AICore from `npu-smi info` — the Chip row shows `AICore(%)`. Note: the NPU
row shows `Health | Power(W) Temp(C) Hugepages`; the Chip row shows
`Bus-Id | AICore(%) Memory-Usage HBM-Usage`.

---

## Concurrency is the real aggregate win

Even with triton, concurrency multiplies aggregate throughput:
- 1 request: 46.3 tok/s
- 64 concurrent: 385.7 tok/s aggregate

The NPU batches concurrent decode steps — each kernel launch processes N tokens
instead of 1, amortizing fixed launch overhead. KV cache has ~627,800 token
capacity (~76 full-length 8192-token sequences); HBM ~30/32 GB (~98%) at idle
but NOT HBM-limited even at 64 concurrent.

---

## Path to higher single-request throughput

The current 46.3 tok/s is the triton-fused-kernel ceiling on CANN 8.5.0. The
remaining bottleneck is the prefill path (pure-PyTorch chunk, Python loop) and
non-GDN layers (full attention, MoE FFN) which still use unfused ops.

**Future optimization:** A matched CANN 9.0.1 + torch_npu + vllm-ascend stack
would provide native aclnn GDN kernels (fused, capture-compatible) for BOTH
prefill and decode. This requires:
1. CANN 9.0.1 installed system-wide (root, complete install with libhccl.so)
2. A torch_npu wheel built against 9.0.1
3. vllm-ascend custom ops that load (they're prebuilt for 9.0.1)

This is a major multi-hour effort (the whole blocker chain exists because 9.0.1
+ 8.5.0-built torch_npu are incompatible). The triton path achieves most of the
benefit without it.
