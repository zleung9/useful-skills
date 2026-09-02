---
name: deploy-qwen3
description: "Deploy and serve Qwen3 / Qwen3.5 MoE and other GDN / hybrid-linear-attention models (gated delta net, Mamba-style) on Huawei Ascend 910B / 910B4 NPUs with vLLM + vllm-ascend under CANN — for inference serving, not training or fine-tuning. Use this skill whenever deploying, troubleshooting, or optimizing an LLM for inference on Ascend NPUs: CANN 8.x vs 9.x version mismatches, torch_npu / vllm-ascend compatibility, triton-ascend setup, tensor-parallel (TP) sizing for GDN models, HBM leaks after killing workers, FULL graph capture, single-request throughput tuning, or building a container image for Ascend NPU inference. Trigger when the work is on Ascend / CANN / NPU and involves aclnn op errors, GEInitializeV2, libhccl.so, platform_config, npu-smi, 910B, vLLM-ascend startup failures, or scatter_ / graph-capture issues. Do not trigger for NVIDIA / CUDA (A100, H100, nvidia-smi, VRAM) or for fine-tuning / training questions."
---

# Deploy Qwen3 / Qwen3.5 on Ascend NPU

This skill captures a hard-won deployment: Qwen3.5-35B MoE (hybrid GDN linear +
full attention) on 4× Ascend 910B4 NPUs via vLLM 0.23.0 + vllm-ascend 0.23.0rc1
under CANN 8.5.0, achieving **46.3 tok/s single-request** and **385.7 tok/s at
64 concurrent** with correct inference.

The knowledge here applies beyond Qwen3.5 — the vllm-ascend + CANN 8.5.0
compatibility blockers affect **any** model on this stack, and the GDN-specific
parts apply to any hybrid-linear-attention model (Qwen3.5, and similar gated
delta net architectures).

## Why this is hard (read first)

The core tension: **torch_npu 2.10.0.post2 is built against CANN 8.5.0, but
vllm-ascend 0.23.0rc1's custom ops are prebuilt for CANN 9.0.1.** The two CANN
versions are incompatible (9.0.1 GE/ops layer fails `GEInitializeV2` against the
8.5.0-built torch_npu; 9.0.1 also never shipped top-level `libhccl.so`). So you
must use CANN 8.5.0 as the base, and **route every 9.0.1 aclnn op** in
vllm-ascend to a torch_npu built-in, a PyTorch fallback, or a triton kernel.

This produced **17 environment blockers**, all resolved here. Six are source
patches (bundled in `assets/`); the rest are env/launch steps. Walk through them
on any fresh deploy — most failures map to one.

## The deployment workflow

```
1. Verify hardware (4 NPUs, CANN 8.5.0)
2. Create venv + pip install pinned versions
3. Apply 6 source patches (scripts/apply_all_patches.py)
4. Create cann-fix wrapper (scripts/setup_cann_fix.sh)
5. Reinstall triton-ascend 3.2.0 + set CC to HCC g++
6. Launch with FULL_AND_PIECEWISE graph capture
7. Verify health + correctness + throughput
```

### Quick start (on the NPU host)

```bash
# 0. Source CANN env
source /usr/local/Ascend/ascend-toolkit/set_env.sh

# 1. Create venv with pinned versions (see references/requirements.md)
python3.10 -m venv /opt/vllm-ascend && source /opt/vllm-ascend/bin/activate
pip install torch==2.10.0 torch-npu==2.10.0.post2 transformers==5.14.1
pip install vllm==0.23.0 vllm-ascend==0.23.0rc1
pip install --no-deps triton-ascend==3.2.0

# 2. Apply the 6 source patches (copies assets/*.py into the venv)
python3 scripts/apply_all_patches.py /opt/vllm-ascend

# 3. Create the cann-fix wrapper for ATB platform_config
bash scripts/setup_cann_fix.sh

# 4. Fix triton-ascend + set compiler
pip install --no-deps --force-reinstall triton-ascend==3.2.0
rm -rf ~/.triton/cache
export CC=/usr/local/Ascend/cann-8.5.0/tools/hcc/bin/aarch64-target-linux-gnu-g++

# 5. Verify triton works on NPU
python3 scripts/verify_triton.py

# 6. Launch (adapt assets/launch_vllm.sh paths to your host)
bash assets/launch_vllm.sh   # ~5-8 min startup (FULL graph capture)

# 7. Verify
curl -s http://127.0.0.1:8080/health   # → 200
```

## Critical decisions (get these right)

### TP=4, not TP=3
GDN linear-attention `conv_dim = head_k_dim × num_k_heads × 2 + head_v_dim × num_v_heads`. For Qwen3.5-35B: `128×16×2 + 128×32 = 8192`. vLLM asserts `conv_dim % TP == 0` → valid TP ∈ {1,2,4,8}. **3 NPUs → TP=3 → hard abort.** You need 4 NPUs for TP=4. Check the model's `config.json` for these dims before choosing TP.

### CANN 8.5.0, not 9.0.1
torch_npu 2.10.0.post2 is built against 8.5.0. Use the system CANN 8.5.0 at
`/usr/local/Ascend/cann-8.5.0`. Source `/usr/local/Ascend/ascend-toolkit/set_env.sh`.
Do NOT point `ASCEND_HOME_PATH` at 9.0.1 for runtime libs. (9.0.1 is only useful
for compiling vllm-ascend custom TBE ops, which we disable anyway.)

### triton-ascend 3.2.0 — the throughput enabler
**This is the difference between 3.1 tok/s and 46.3 tok/s (15×).** vLLM 0.23.0
ships fused triton kernels for GDN (`fused_recurrent_gated_delta_rule` in
`vllm/model_executor/layers/fla/ops/`). triton-ascend 3.2.0 provides the NPU
backend that compiles these kernels to Ascend machine code. Without it, decode
falls back to ~360 unfused PyTorch ops. Install with `--no-deps` (NOT 3.2.1 —
doesn't exist). The `gdn.py` patch calls this kernel directly for decode.

### FULL graph capture, not eager
Use `--compilation-config '{"cudagraph_mode": "FULL_AND_PIECEWISE"}'`. No
`--enforce-eager`. FULL capture for decode (35/35 captures), PIECEWISE for
prefill. Startup takes ~5-8 min (torch.compile + capture). This requires the vec
decode paths with `scatter_` writeback (no `.item()` host syncs) — already in
the patched `gdn.py`.

### The HCC g++ 7.3.0 compiler
There's no system gcc/clang on openEuler NPU hosts. CANN 8.5.0 bundles HCC g++
7.3.0 at `.../cann-8.5.0/tools/hcc/bin/aarch64-target-linux-gnu-g++`.
triton-ascend needs it to JIT-build `npu_utils.so`. `export CC=<that path>` in
the launch script. This also requires patching PyTorch's `C++17.h` gate (9→7).

## The 17 environment blockers (summary)

| # | Blocker | Fix type |
|---|---------|----------|
| 1 | TP divisibility (8192 % 3 ≠ 0) | TP=4 |
| 2 | CANN 9.0.1 vs 8.5.0 mismatch | Use 8.5.0 only |
| 3 | libhccl.so missing in 9.0.1 | 8.5.0 has it |
| 4 | triton-ascend corruption | Reinstall 3.2.0, clear ~/.triton/cache |
| 5 | No C/C++ compiler | `export CC=<HCC g++>` |
| 6 | PyTorch C++17.h GCC 9+ gate | Patch: gate 9→7 (assets/C++17.h) |
| 7 | aclnnAddRmsNormBias (9.0.1) | Disable custom ops (assets/utils.py) |
| 8 | aclnnMoeInitRoutingCustom (9.0.1) | → npu_moe_init_routing_v2 (assets/device_op.py) |
| 9 | fast_moe_cold_start hang | `--compilation-config` flag |
| 10 | ATB warmup segfault | Skip _warm_up_atb (assets/worker.py) |
| 11 | aclnnCausalConv1d (9.0.1) | PyTorch shim (assets/gdn.py) |
| 12 | aclnnFusedGdnGating (9.0.1) | PyTorch fallback (assets/gdn.py) |
| 13 | aclnnChunkGatedDeltaRule (9.0.1) | Pure-PyTorch chunk (assets/gdn.py) |
| 14 | ATB platform_config segfault | cann-fix wrapper (scripts/setup_cann_fix.sh) |
| 15 | aclnnRecurrentGatedDeltaRule (9.0.1) | **triton kernel** (assets/gdn.py) |
| 16 | aclnnApplyTopKTopPCustom (9.0.1) | PyTorch sampler (assets/sampler.py) |
| 17 | scatter_ shape mismatch (EZ1001) | transpose before scatter_ (assets/gdn.py) |

**Full diagnosis of each:** read `references/blockers.md`.
**Per-file patch detail:** read `references/patches.md`.

## Key gotchas

### HBM leak after killing the server
`pkill -9 -f "vllm serve"` kills the API server but the 4 `VLLMWorker_TP` child
processes survive (their cmdline has no "vllm serve"), holding ~26GB/NPU HBM.
Next launch sees only 3GB free and aborts. **Fix:** kill by PID from
`npu-smi info` Process section. Also use the bracket trick `pkill -f "v[l]lm serve"`
to avoid self-matching your ssh shell. See `references/troubleshooting.md`.

### scatter_ for state writeback, NOT copy_
FULL graph capture requires `scatter_` for persistent state buffer updates.
The `matmul+where+copy_` alternative (one-hot + matmul) captures fine but
produces **garbled output** — `copy_` to a persistent buffer doesn't properly
update during graph replay. `scatter_` is simpler, numerically exact, AND
correct. (Blocker #17.)

### Thinking model output
Qwen3.5 is a thinking model — it outputs "Thinking Process: ..." reasoning
before the answer. With `max_tokens=10`, you only see the start of the thinking,
which looks like garbling but isn't. Use `max_tokens ≥ 100` to see coherent
reasoning + correct answer. A `.cw\n})` artifact at the thinking→answer boundary
is a close-tag rendering quirk (special tokens 248068/248069); the answer is
correct.

### vllm-ascend's own triton chunk wrapper is broken on NPU
`vllm_ascend/ops/triton/fla/chunk.py` has a `prepare_chunk_indices` host-device
bug. Do NOT use it for prefill. The patched `gdn.py` uses the pure-PyTorch
`chunk_gated_delta_rule_pytorch` reference for prefill instead. The triton
`fused_recurrent_gated_delta_rule` (decode) works fine — the bug is prefill-only.

## Performance

| Concurrent | With triton | Without triton | AICore (triton) |
|-----------:|------------:|---------------:|----------------:|
| 1 | **46.3 tok/s** | 3.1 tok/s | 50-56% |
| 16 | 246.8 tok/s | 41.6 tok/s | — |
| 32 | 317.9 tok/s | 72.5 tok/s | — |
| 64 | **385.7 tok/s** | 111.0 tok/s | — |

AICore is **lower** with triton (50-56% vs 93%) but throughput is **higher** —
the NPU is efficient (1 fused kernel), not just busy (360 tiny kernels).
**Lower AICore + higher throughput = genuine speedup.**

For full tuning details, benchmarks, and the path to higher throughput:
read `references/performance.md`.

## What's in this skill

```
deploy-qwen3/
├── SKILL.md                      (this file)
├── references/
│   ├── requirements.md           full bill of materials + Dockerfile
│   ├── blockers.md               the 17 blockers, full diagnosis
│   ├── patches.md                the 6 source patches, per-file detail
│   ├── performance.md            throughput tuning + benchmarks
│   └── troubleshooting.md        symptom → root cause → fix tables
├── scripts/
│   ├── apply_all_patches.py      copies 6 patched files into the venv
│   ├── setup_cann_fix.sh         creates the ASCEND_HOME_PATH wrapper
│   └── verify_triton.py          verifies triton-ascend works on NPU
└── assets/
    ├── gdn.py                    patched GDN ops (triton decode + PyTorch prefill)
    ├── sampler.py                patched sampler (PyTorch top-k/top-p)
    ├── utils.py                  patched utils (custom ops disabled)
    ├── worker.py                 patched worker (ATB warmup skipped)
    ├── device_op.py              patched device_op (MoE routing v2)
    ├── C++17.h                   patched C++17.h (GCC gate 9→7)
    └── launch_vllm.sh            launch script template
```

**Read order when deploying:** this SKILL.md → `references/requirements.md`
(for exact versions) → `references/blockers.md` (if anything fails) →
`references/troubleshooting.md` (for symptom matching).

**For container/Kubernetes builds:** `references/requirements.md` has a complete
Dockerfile sketch. The `assets/` patched files + `scripts/` are COPY'd into the
image; the model is a PVC mount; NPU devices come from the Ascend k8s device
plugin (driver/firmware stay host-side).
