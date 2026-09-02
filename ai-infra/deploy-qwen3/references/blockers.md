# Environment Blockers — 17 Issues and Fixes

This is the complete catalog of environment blockers encountered deploying
Qwen3.5-35B MoE on 4× Ascend 910B4 with vLLM 0.23.0 + vllm-ascend 0.23.0rc1
under CANN 8.5.0. Each was diagnosed and fixed. When deploying a fresh stack,
walk through this list — most failures map to one of these.

The root cause for most (#7–#13, #15, #16) is the same: **vllm-ascend 0.23.0rc1
custom ops are prebuilt for CANN 9.0.1, but torch_npu 2.10.0.post2 is built
against CANN 8.5.0, and the two are incompatible.** The fix pattern: route every
9.0.1 aclnn op to a torch_npu built-in, a PyTorch fallback, or a triton kernel.

## Table of Contents
1. [TP divisibility → TP=4](#1-tp-divisibility--tp4)
2. [CANN version mismatch → pure 8.5.0](#2-cann-version-mismatch--pure-850)
3. [libhccl.so → 8.5.0 has it](#3-libhcclso--850-has-it)
4. [triton-ascend corruption → reinstall 3.2.0](#4-triton-ascend-corruption--reinstall-320)
5. [No C/C++ compiler → HCC g++ 7.3.0](#5-no-cc-compiler--hcc-g-730)
6. [GCC 9+ gate → patch C++17.h](#6-gcc-9-gate--patch-c17h)
7. [aclnnAddRmsNormBias → disable custom ops](#7-aclnnaddrmsnormbias--disable-custom-ops)
8. [aclnnMoeInitRoutingCustom → npu_moe_init_routing_v2](#8-aclnnmoeinitroutingcustom--npu-moe-init-routing-v2)
9. [fast_moe_cold_start hang → disable](#9-fast-moe-cold-start-hang--disable)
10. [ATB warmup segfault → skip _warm_up_atb](#10-atb-warmup-segfault--skip-_warm_up_atb)
11. [aclnnCausalConv1d → PyTorch shim](#11-aclnncausalconv1d--pytorch-shim)
12. [aclnnFusedGdnGating → PyTorch fallback](#12-aclnnfusedgdngating--pytorch-fallback)
13. [aclnnChunkGatedDeltaRule → pure-PyTorch chunk](#13-aclnnchunkgateddeltarule--pure-pytorch-chunk)
14. [ATB platform_config → ASCEND_HOME_PATH wrapper](#14-atb-platform_config--ascend_home_path-wrapper)
15. [aclnnRecurrentGatedDeltaRule → pure-PyTorch / triton](#15-aclnnrecurrentgateddeltarule--pure-pytorch--triton)
16. [aclnnApplyTopKTopPCustom → PyTorch sampler](#16-aclnnapplytopktoppcustom--pytorch-sampler)
17. [scatter_ shape mismatch → transpose](#17-scatter_-shape-mismatch--transpose)

---

### #1 TP divisibility → TP=4
**Symptom:** `Assertion failed, 8192 is not divisible by 3` (or other TP).
**Root cause:** GDN linear-attention `conv_dim = head_k_dim(128) × num_k_heads(16) × 2 + head_v_dim(128) × num_v_heads(32) = 8192`. vLLM asserts `conv_dim % TP == 0` → valid TP ∈ {1,2,4,8}.
**Fix:** Use 4 NPUs with TP=4 (8192/4=2048 ✓, 16 k-heads/4=4 ✓, 32 v-heads/4=8 ✓). If you have 3 NPUs, you CANNOT run this model — TP=3 is invalid for GDN conv_dim 8192.

### #2 CANN version mismatch → pure 8.5.0
**Symptom:** `GEInitializeV2` fails; or `aclnnInplaceZero` fails with "ParseDynamicKernels fail".
**Root cause:** torch_npu 2.10.0.post2 is built against CANN 8.5.0. Mixing 9.0.1 runtime/GE with the 8.5.0-built torch_npu breaks initialization.
**Fix:** Source only `/usr/local/Ascend/ascend-toolkit/set_env.sh` (8.5.0). Do NOT point `ASCEND_HOME_PATH` at 9.0.1 for runtime libs.

### #3 libhccl.so → 8.5.0 has it
**Symptom:** `libhccl.so not found` / torch_npu import fails.
**Root cause:** The user-local CANN 9.0.1 never shipped top-level `libhccl.so` (only split `libhccl_v2.so`); 8.5.0 has it.
**Fix:** Use CANN 8.5.0 which includes `libhccl.so`.

### #4 triton-ascend corruption → reinstall 3.2.0
**Symptom:** triton-ascend fails to init its NPU driver; or `npu_utils.so` build errors.
**Fix:** `pip install --no-deps --force-reinstall triton-ascend==3.2.0`, then `rm -rf ~/.triton/cache` so `npu_utils.so` rebuilds cleanly. **NOT 3.2.1** — does not exist on the index.

### #5 No C/C++ compiler → HCC g++ 7.3.0
**Symptom:** triton-ascend JIT build fails — no gcc/g++/clang on the system.
**Fix:** CANN 8.5.0 bundles HCC g++ 7.3.0 at `/usr/local/Ascend/cann-8.5.0/tools/hcc/bin/aarch64-target-linux-gnu-g++`. triton-ascend's `_get_cxx` honors `$CC` first → `export CC=<that path>` in the launch script. `npu_utils.so` builds once and caches in `~/.triton/cache`.

### #6 GCC 9+ gate → patch C++17.h
**Symptom:** PyTorch C++ headers reject HCC g++ 7.3.0 (gated on `__GNUC__ < 9`).
**Fix:** `torch/include/c10/util/C++17.h` line 13: `__GNUC__ < 9` → `__GNUC__ < 7`. Only the gate changes; the code is C++17-compatible. (Bundled as `assets/C++17.h`.)

### #7 aclnnAddRmsNormBias → disable custom ops
**Symptom:** custom aclnn ops fail `dlsym` under 8.5.0 (prebuilt for 9.0.1).
**Fix:** `vllm_ascend/utils.py` — set `_CUSTOM_OP_ENABLED = False` (both assignment sites, ~lines 441 & 451). The `vllm_ascend_C` import is kept (registers GDN fallback ops), but the custom aclnn path is disabled → norms route to torch_npu built-ins. (Bundled as `assets/utils.py`.)

### #8 aclnnMoeInitRoutingCustom → npu_moe_init_routing_v2
**Symptom:** MoE init routing calls a 9.0.1 custom op.
**Fix:** `vllm_ascend/device/device_op.py` — route `npu_moe_init_routing` → `torch_npu.npu_moe_init_routing_v2` (built-in, 910B). Only the base function needed fixing; device-adaptor overrides already used v2. (Bundled as `assets/device_op.py`.)

### #9 fast_moe_cold_start hang → disable
**Symptom:** MoE cold-start compilation hangs on first expert dispatch.
**Fix:** Launch flag `--compilation-config '{"fast_moe_cold_start": false}'`.

### #10 ATB warmup segfault → skip _warm_up_atb
**Symptom:** `torch_npu._npu_matmul_add_fp32` segfaults inside `_warm_up_atb()` under 8.5.0 (ATB mki_log logger issue).
**Fix:** `vllm_ascend/worker/worker.py` — comment out the `_warm_up_atb()` call (~line 762). Warmup is perf-only; server still starts. (Bundled as `assets/worker.py`.)

### #11 aclnnCausalConv1d → PyTorch shim
**Symptom:** GDN causal conv1d uses a 9.0.1 aclnn op unavailable in 8.5.0.
**Fix:** `gdn.py` — `_causal_conv1d_custom_py` shim routes prefill → `causal_conv1d_fn` (with seq-first↔dim-first transpose) and decode → `causal_conv1d_update`, from `vllm_ascend._310p.ops.causal_conv1d`. Replaced all 4 `npu_causal_conv1d_custom` call sites. (Bundled in `assets/gdn.py`.)

### #12 aclnnFusedGdnGating → PyTorch fallback
**Symptom:** GDN gating uses a 9.0.1 aclnn op.
**Fix:** `gdn.py` — `DeviceOperator.fused_gdn_gating(...)` → `fused_gdn_gating_pytorch(...)` (from `_310p`), plus `g = g.to(self.A_log.dtype)` cast (ref computes in fp32; chunk kernel expects bf16). Returns `g = -exp(A_log)*softplus(a+dt_bias)`, `beta = sigmoid(b)`. (Bundled in `assets/gdn.py`.)

### #13 aclnnChunkGatedDeltaRule → pure-PyTorch chunk
**Symptom:** GDN **prefill** chunk attention uses two 9.0.1 aclnn ops (`aclnnChunkGatedDeltaRuleFwdH` + `aclnnChunkFwdO`). The `_310p` production chunk path also uses aclnn.
**Fix:** `gdn.py` — `_chunk_gdr_pytorch_shim` uses the pure-PyTorch reference `chunk_gated_delta_rule_pytorch` (drops `prebuilt_meta`; ref computes chunk indices internally). Slower (Python loop over chunks) but correct. **Note:** vllm-ascend's own triton chunk wrapper (`vllm_ascend/ops/triton/fla/chunk.py`) has a `prepare_chunk_indices` host-device bug on NPU — do NOT use it; use the PyTorch ref for prefill. (Bundled in `assets/gdn.py`.)

### #14 ATB platform_config → ASCEND_HOME_PATH wrapper
**Symptom:** first inference request segfaults in ATB: `libmki.so` reads `$ASCEND_HOME_PATH/runtime/data/platform_config`, but CANN 8.5.0 installs SoC `.ini` at `aarch64-linux/data/platform_config` (no `data/` under `runtime/`). → "Initialize platform manager" → `ReshapeAndCacheNdKernel not found` → `atb::OperationSetup` segfault.
**Fix:** `setup_cann_fix.sh` creates `~/cann-fix/` mirroring cann-8.5.0 via symlinks + a real `runtime/data/platform_config` symlink → the `.ini` dir. Launch script sets `export ASCEND_HOME_PATH=$HOME/cann-fix` **after** sourcing CANN `set_env.sh`. Only `libmki.so` reads this at runtime. (Run `scripts/setup_cann_fix.sh`.)

### #15 aclnnRecurrentGatedDeltaRule → pure-PyTorch / triton
**Symptom:** GDN **decode** uses `npu_recurrent_gated_delta_rule` → `aclnnRecurrentGatedDeltaRule`. Under 8.5.0 this rejects fp32 `state` (`DT_FLOAT not in [DT_BFLOAT16]`); the `ssm_state` buffer is fp32.
- **bf16 cast attempt:** cast state→bf16, run op, copy back. First token correct but subsequent tokens **garbled** (random multilingual). Root cause: aclnn computes recurrence in pure bf16 (no fp32 upcast) → rapid drift; in-place state update not reliably reflected.
- **Fix (decode):** `gdn.py` — use triton `fused_recurrent_gated_delta_rule` (from `vllm.model_executor.layers.fla.ops.fused_recurrent`) with `use_qk_l2norm_in_kernel=True`. This is the **throughput win** — see `references/performance.md`. Has `try/except` fallback to pure-PyTorch `fused_recurrent_gated_delta_rule_pytorch` (fp32, stable, explicit state return) if triton unavailable. (Bundled in `assets/gdn.py`.)
- **Spec-decode site** still uses `_recurrent_gdr_bf16` aclnn shim (only exercised with `--speculative-config`).

### #16 aclnnApplyTopKTopPCustom → PyTorch sampler
**Symptom:** non-greedy sampling (temperature>0) triggers `aclnnApplyTopKTopPCustom`, a 9.0.1 op not in 8.5.0's `libopapi`.
**Fix:** `vllm_ascend/sample/sampler.py` — force `apply_top_k_top_p = _apply_top_k_top_p_pytorch` (bypass the AscendC path). Greedy (temperature=0) uses argmax and was unaffected. (Bundled as `assets/sampler.py`.)

### #17 scatter_ shape mismatch → transpose
**Symptom:** FULL graph capture vec decode paths' `scatter_` state writeback fails with `aclnnInplaceScatter error 161002`.
**Root cause:** SHAPE MISMATCH (EZ1001 AclNN_Parameter_Error), NOT a graph-capture limitation. `scatter_` requires non-dim-0 shapes of `index`/`src` to match `self`. conv_state stored as `(N_total, state_len, dim)` = `[843, 3, 2048]` but `new_state` was `(N, dim, state_len)` = `[256, 2048, 3]` — dims 1/2 swapped.
**Fix:** conv1d vec: `new_state.transpose(-1, -2)` before `scatter_`. Recurrent vec: `idx_exp = idx.view(-1,1,1,1).expand_as(new_h)` (shapes already align). N>1 guards REMOVED — N=1 decode also uses vec path (required for FULL capture; loop fallback has `.item()` host syncs).
**Key insight:** `scatter_` is capture-safe AND correctly updates persistent buffers during graph replay. The alternative `matmul+where+copy_` (one-hot + matmul) captures but produces **garbled output** — `copy_` to persistent buffer doesn't update during replay. Always use `scatter_` for state writeback.
