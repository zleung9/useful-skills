# The 6 Source Patches — Detail

vllm-ascend 0.23.0rc1's custom ops are prebuilt for CANN 9.0.1 and cannot load
under CANN 8.5.0 (the version torch_npu 2.10.0.post2 is built against). Six
surgical patches route every 9.0.1 aclnn op to a torch_npu built-in, a PyTorch
fallback, or a triton kernel.

All 6 patched files are bundled in `assets/`. Apply them with:
```bash
python3 scripts/apply_all_patches.py /path/to/venv
```
This copies each file over the freshly-installed venv file (backing up the
original as `.orig`). The script finds the patched files in `assets/`
automatically.

## Table of Contents
1. [C++17.h — GCC 9+ gate](#1-c17h--gcc-9-gate)
2. [utils.py — disable custom ops](#2-utilspy--disable-custom-ops)
3. [device_op.py — MoE init routing v2](#3-device_opyp --moe-init-routing-v2)
4. [worker.py — skip ATB warmup](#4-workerpy--skip-atb-warmup)
5. [sampler.py — PyTorch top-k/top-p](#5-samplerpy--pytorch-top-ktop-p)
6. [gdn.py — the big one](#6-gdnpy--the-big-one)

---

### #1 C++17.h — GCC 9+ gate
**File:** `torch/include/c10/util/C++17.h`
**Change:** line 13: `__GNUC__ < 9` → `__GNUC__ < 7`
**Why:** HCC g++ 7.3.0 (bundled with CANN 8.5.0) is the only available C++ compiler (no system gcc/clang). PyTorch's C++17 header gates features at `__GNUC__ < 9`, rejecting g++ 7.3.0. Only the gate changes — the code itself is C++17-compatible.

### #2 utils.py — disable custom ops
**File:** `vllm_ascend/utils.py`
**Change:** `_CUSTOM_OP_ENABLED = False` at both assignment sites (~lines 441 & 451)
**Why:** vllm-ascend's custom aclnn ops (e.g. `aclnnAddRmsNormBias`) are prebuilt for CANN 9.0.1 and fail `dlsym` under 8.5.0. Disabling the custom-op path routes norms to **torch_npu built-ins** (which are 8.5.0-compatible). The `vllm_ascend_C` import is kept — it still registers the `torch.ops._C_ascend` GDN ops used as fallbacks.

### #3 device_op.py — MoE init routing v2
**File:** `vllm_ascend/device/device_op.py`
**Change:** `npu_moe_init_routing` → `torch_npu.npu_moe_init_routing_v2`
**Why:** the base `npu_moe_init_routing` called the 9.0.1 custom op `aclnnMoeInitRoutingCustom`. `npu_moe_init_routing_v2` is a torch_npu built-in (910B-compatible). The device-adaptor overrides already used v2; only the base function needed fixing.

### #4 worker.py — skip ATB warmup
**File:** `vllm_ascend/worker/worker.py`
**Change:** comment out the `_warm_up_atb()` call (~line 762)
**Why:** `torch_npu._npu_matmul_add_fp32` segfaults inside `_warm_up_atb()` under 8.5.0 (ATB mki_log logger issue). Warmup is performance-only — the server starts fine without it.

### #5 sampler.py — PyTorch top-k/top-p
**File:** `vllm_ascend/sample/sampler.py`
**Change:** force `apply_top_k_top_p = _apply_top_k_top_p_pytorch`
**Why:** non-greedy sampling (temperature>0) triggers `aclnnApplyTopKTopPCustom`, a 9.0.1 op not in 8.5.0's `libopapi`. Bypassing the AscendC `_apply_top_k_top_p_ascendc` path fixes any top-k/top-p sampling. Greedy (temperature=0) uses argmax and was unaffected.

### #6 gdn.py — the big one
**File:** `vllm_ascend/ops/gdn.py` (808 lines)
**Why:** the GDN (Gated Delta Net) linear-attention layer uses multiple 9.0.1 aclnn ops for conv1d, gating, chunk prefill, and recurrent decode. This single file patches all of them + adds the triton throughput optimization.

**Changes:**
1. **Import:** `from vllm.model_executor.layers.fla.ops.fused_recurrent import fused_recurrent_gated_delta_rule as _triton_fused_recurrent_gdr`
2. **Decode (sections 2.2 + 2.3):** replaced `_recurrent_gdr_pytorch(...)` + `l2norm_fwd(q)` + `l2norm_fwd(k)` (~12 ops × 30 layers = 360 launches) with a single `_triton_fused_recurrent_gdr(...)` call (`use_qk_l2norm_in_kernel=True`). `try/except` fallback to pure-PyTorch vec path if triton fails.
3. **Prefill:** `_chunk_gdr_pytorch_shim` → `chunk_gated_delta_rule_pytorch` (pure-PyTorch, fp32). vllm-ascend's own triton chunk wrapper has a `prepare_chunk_indices` NPU bug — do NOT use it.
4. **Conv1d decode:** `_causal_conv1d_update_vec` (vectorized, scatter_ writeback with `.transpose(-1,-2)` shape alignment).
5. **Conv1d prefill:** `_causal_conv1d_custom_py` shim → `causal_conv1d_fn`.
6. **Gating:** `fused_gdn_gating_pytorch` + `g = g.to(bf16)` cast.
7. **scatter_ state writeback:** both recurrent and conv1d vec paths use `scatter_` (NOT `copy_`). `idx_exp = idx.view(-1,1,1,1).expand_as(new_h)` for recurrent; `new_state.transpose(-1,-2)` for conv1d.
8. **N>1 guards REMOVED:** N=1 decode also uses vec/triton path (no `.item()` host syncs → FULL graph capture compatible).

**The triton kernel** (`fused_recurrent_gated_delta_rule`) fuses l2norm + gating + delta-rule recurrence + state update into 1 kernel. This is the **15× single-request throughput win** (3.1 → 46.3 tok/s). See `references/performance.md`.

**If triton-ascend is missing:** the `try/except` falls back to the pure-PyTorch vec path. Server still runs and produces correct output — but at 3.1 tok/s instead of 46.3 tok/s. Correct-but-slow is the failure mode, not a crash.
