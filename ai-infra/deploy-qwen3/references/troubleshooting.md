# Troubleshooting — Symptom → Root Cause → Fix

All of these are pre-resolved by the patches + env setup in this skill. This
table helps diagnose failures on a fresh or modified deployment.

## Table of Contents
- [Startup failures](#startup-failures)
- [Import / load failures](#import--load-failures)
- [Triton / compiler failures](#triton--compiler-failures)
- [Inference failures](#inference-failures)
- [Output quality](#output-quality)
- [Performance](#performance)
- [HBM / process management](#hbm--process-management)

---

## Startup failures

| Symptom | Root cause | Fix |
|---------|------------|-----|
| `Assertion failed, 8192 is not divisible by 3` | TP=3 on 3 NPUs; GDN conv_dim=8192 needs TP∈{1,2,4,8} | Use 4 NPUs, TP=4 |
| `GEInitializeV2` fails | CANN 9.0.1 runtime vs 8.5.0-built torch_npu | Use CANN 8.5.0 only |
| Server "hangs" 5-8 min at startup | torch.compile + 35/35 FULL graph capture | Normal — wait for `Application startup complete` |
| `Free memory on device (3.06/29.49 GiB) ... less than desired` | Stale VLLMWorker_TP processes holding HBM | Kill by PID from `npu-smi info` Process section (see HBM section) |
| MoE cold-start compilation hangs | `fast_moe_cold_start` enabled | `--compilation-config '{"fast_moe_cold_start": false}'` |

## Import / load failures

| Symptom | Root cause | Fix |
|---------|------------|-----|
| `libhccl.so not found` / torch_npu import fails | CANN 9.0.1 never shipped top-level libhccl.so | Use CANN 8.5.0 (has it) |
| `aclnnAddRmsNormBias` dlsym fail | vllm-ascend custom ops prebuilt for 9.0.1 | Patch utils.py: `_CUSTOM_OP_ENABLED = False` |
| `aclnnMoeInitRoutingCustom` not found | 9.0.1 custom MoE op | Patch device_op.py: → `npu_moe_init_routing_v2` |
| `aclnnApplyTopKTopPCustom` not found | 9.0.1 sampler op | Patch sampler.py: → PyTorch fallback |

## Triton / compiler failures

| Symptom | Root cause | Fix |
|---------|------------|-----|
| triton `npu_utils.so` build fail | No system gcc/g++/clang | `export CC=.../cann-8.5.0/tools/hcc/bin/aarch64-target-linux-gnu-g++` |
| triton-ascend fails to init NPU driver | Corrupted install | `pip install --no-deps --force-reinstall triton-ascend==3.2.0 && rm -rf ~/.triton/cache` |
| triton `constexpr_function` error | vLLM's own matmul_ogs triton kernels (C++17 feature) | Custom ops disabled; FLA triton ops are unaffected — use those |
| triton `ub overflow, requires 1593600 bits` | `fused_sigmoid_gating_delta_rule_update` too fused for head dims | Use `fused_recurrent_gated_delta_rule` instead (less fused, works) |
| PyTorch C++ headers reject g++ 7.3.0 | C++17.h gates at `__GNUC__ < 9` | Patch C++17.h: gate `9 → 7` |

## Inference failures

| Symptom | Root cause | Fix |
|---------|------------|-----|
| First inference segfaults in ATB | `libmki.so` can't find platform_config .ini | Create cann-fix wrapper, set `ASCEND_HOME_PATH` (blocker #14) |
| `_warm_up_atb()` segfault | `torch_npu._npu_matmul_add_fp32` crashes under 8.5.0 | Patch worker.py: comment out `_warm_up_atb()` |
| `aclnnInplaceScatter error 161002` | Shape mismatch (EZ1001), NOT graph-capture limit | `new_state.transpose(-1,-2)` before scatter_ (blocker #17) |
| GDN conv1d / gating / chunk / recurrent aclnn ops fail | All 9.0.1-only ops | Patch gdn.py (PyTorch shims + triton decode) |

## Output quality

| Symptom | Root cause | Fix |
|---------|------------|-----|
| Garbled output (random multilingual tokens) after first decode token | aclnn recurrent op computes in pure bf16 → drift | Use triton kernel or pure-PyTorch fp32 ref (NOT bf16-cast aclnn) |
| Garbled output with FULL graph capture | `copy_` to persistent buffer doesn't update during replay | Use `scatter_` for state writeback (NOT copy_) |
| Output looks truncated / garbled with low max_tokens | Thinking model: "Thinking Process:..." reasoning before answer | Use `max_tokens ≥ 100` to see coherent output |
| `.cw\n})` artifact at thinking→answer boundary | Thinking-mode close-tag rendering quirk (special tokens 248068/248069) | Post-processing strip or chat-template adjustment; answer is correct |

## Performance

| Symptom | Root cause | Fix |
|---------|------------|-----|
| 3.1 tok/s single-request (93% AICore) | Pure-PyTorch GDN decode (360 unfused ops) | Install triton-ascend 3.2.0 + gdn.py triton decode patch → 46.3 tok/s |
| 2.8 tok/s single-request | `--enforce-eager` (no graph capture) | Remove `--enforce-eager`, use `FULL_AND_PIECEWISE` |
| Low aggregate throughput | Not enough concurrency | Send 16-64 concurrent requests; NPU batches them |

## HBM / process management

| Symptom | Root cause | Fix |
|---------|------------|-----|
| Next launch sees only 3GB free HBM | `VLLMWorker_TP` child processes survive pkill | Kill by PID from `npu-smi info` Process section |
| `pkill -f "vllm serve"` kills your ssh shell | Self-match on cmdline | Use bracket trick: `pkill -f "v[l]lm serve"` |

### HBM leak cleanup procedure
```bash
# 1. Kill the API server (bracket trick avoids self-match)
pkill -9 -f "v[l]lm serve"

# 2. Find survivor VLLMWorker_TP PIDs from npu-smi
source /usr/local/Ascend/ascend-toolkit/set_env.sh
npu-smi info   # look at Process section for VLLMWorker_TP PIDs

# 3. Kill them by PID
for p in $(npu-smi info | grep VLLMWorker | awk -F'|' '{gsub(/ /,"");print $3}'); do
  kill -9 "$p"
done

# 4. Verify HBM drops to ~2.8GB baseline
npu-smi info
```
