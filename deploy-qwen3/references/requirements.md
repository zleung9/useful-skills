# Requirements — Bill of Materials

Pinned dependency list for reproducing the deployment. The versions are a
**matched set** — mixing versions breaks the stack. Grouped by build layer.

## Table of Contents
1. [Hardware](#hardware)
2. [Base image / OS](#base-image--os)
3. [System CANN stack](#system-cann-stack)
4. [Python venv — pinned pip installs](#python-venv--pinned-pip-installs)
5. [The 6 source patches](#the-6-source-patches)
6. [Environment variables](#environment-variables)
7. [Model artifacts](#model-artifacts)
8. [Dockerfile sketch](#dockerfile-sketch)

---

## Hardware

| Item | Requirement | Notes |
|------|-------------|-------|
| NPU | 4× Ascend 910B4 | TP=4 required: GDN conv_dim=8192 → TP∈{1,2,4,8} |
| HBM | ≥29.5 GB / NPU | 910B4 has ~32 GB; model+KV uses ~30 GB at 0.90 util |
| Arch | aarch64 | 910B4 is ARM-only |

**Why exactly 4 NPUs:** GDN conv_dim = `128×16×2 + 128×32 = 8192`; TP must divide 8192 → {1,2,4,8}. 3 NPUs → TP=3 → hard abort.

NPU driver & firmware are **host-side** (exposed via Ascend k8s device plugin), NOT in the image. Container only needs the CANN userspace toolkit.

## Base image / OS

| Item | Value |
|------|-------|
| OS | openEuler 24.03 LTS-SP1 (aarch64) |
| Kernel | 5.10.x aarch64 (host-provided) |
| Python | 3.10.16 |

## System CANN stack

Everything must match exactly. Here: **CANN 8.5.0** (NOT 9.0.1).

| Component | Version | Path |
|-----------|---------|------|
| Ascend-cann-toolkit | **8.5.0** | `/usr/local/Ascend/cann-8.5.0` |
| set_env.sh | — | `/usr/local/Ascend/ascend-toolkit/set_env.sh` |
| HCC g++ | 7.3.0 (Do-Compiler) | `.../cann-8.5.0/tools/hcc/bin/aarch64-target-linux-gnu-g++` |
| libhccl.so | (from 8.5.0) | 9.0.1 never shipped top-level libhccl.so |
| ATB | (system) | `/usr/local/Ascend/nnal/atb/set_env.sh` |

**CANN 9.0.1 is NOT used** because torch_npu 2.10.0.post2 is built against 8.5.0; 9.0.1 → `GEInitializeV2` fails + no `libhccl.so` + custom ops prebuilt for 9.0.1 can't load.

Install (root, on image build host):
```bash
chmod +x Ascend-cann-toolkit_8.5.0_linux-aarch64.run
./Ascend-cann-toolkit_8.5.0_linux-aarch64.run --install --install-for-all --install-path=/usr/local/Ascend
```

## Python venv — pinned pip installs

```bash
python3.10 -m venv /opt/vllm-ascend
source /opt/vllm-ascend/bin/activate
pip install --upgrade pip
pip install torch==2.10.0 torch-npu==2.10.0.post2 transformers==5.14.1
pip install vllm==0.23.0 vllm-ascend==0.23.0rc1
pip install --no-deps triton-ascend==3.2.0
```

### Pinned package table (verified working set)

| Package | Version | Role |
|---------|---------|------|
| **torch** | 2.10.0 | base framework (CPU build; NPU via torch_npu) |
| **torch-npu** | 2.10.0.post2 | NPU device + built-in aclnn ops (built vs CANN 8.5.0) |
| **vllm** | 0.23.0 | serving engine + **FLA triton kernels** |
| **vllm-ascend** | 0.23.0rc1 | Ascend backend (custom ops disabled) |
| **triton-ascend** | **3.2.0** | **NPU triton backend — the throughput enabler** |
| **transformers** | 5.14.1 | model loading (Qwen3.5 arch) |
| tokenizers | 0.22.2 | (auto) |
| numpy | 2.2.6 | (auto) |
| sentencepiece | 0.2.2 | tokenizer |
| einops | 0.8.2 | tensor rearrange |

> **triton-ascend 3.2.0, NOT 3.2.1** — 3.2.1 does not exist on the index. Install `--no-deps` to avoid pulling a mismatched base triton. vllm pulls ~225 transitive deps automatically — only the 6 seeds above are load-bearing pins.

## The 6 source patches

vllm-ascend 0.23.0rc1's custom ops are prebuilt for CANN 9.0.1 and can't load
under 8.5.0. Six surgical patches route every 9.0.1 aclnn op to a built-in /
PyTorch / triton fallback. Apply with `scripts/apply_all_patches.py <venv-path>`
(copies the 6 audited files from `assets/`):

| # | File (in venv site-packages) | Change |
|---|------------------------------|--------|
| 1 | `torch/include/c10/util/C++17.h` | gate `9→7` (HCC g++ 7.3.0 is the only compiler) |
| 2 | `vllm_ascend/utils.py` | `_CUSTOM_OP_ENABLED = False` (route norms to torch_npu built-ins) |
| 3 | `vllm_ascend/device/device_op.py` | `npu_moe_init_routing` → `npu_moe_init_routing_v2` |
| 4 | `vllm_ascend/worker/worker.py` | `_warm_up_atb()` commented (segfault under 8.5.0) |
| 5 | `vllm_ascend/sample/sampler.py` | `apply_top_k_top_p` → PyTorch fallback |
| 6 | `vllm_ascend/ops/gdn.py` | **the big one**: triton decode + PyTorch prefill + scatter_ writeback |

See `references/patches.md` for the per-file detail, and `references/blockers.md`
for the full diagnosis of each blocker these patches resolve.

## Environment variables

Set in the container entrypoint or Pod env (after sourcing CANN set_env.sh):

```bash
export CC=/usr/local/Ascend/cann-8.5.0/tools/hcc/bin/aarch64-target-linux-gnu-g++
export ASCEND_HOME_PATH=/opt/cann-fix   # wrapper for ATB platform_config (blocker #14)
export ASCEND_RT_VISIBLE_DEVICES=0,1,2,3
export HCCL_BUFFSIZE=1024
export VLLM_USE_V1=1
export VLLM_WORKER_MULTIPROC_METHOD=spawn
```

The `cann-fix` wrapper: create via `scripts/setup_cann_fix.sh`. It mirrors
cann-8.5.0 via symlinks + adds `runtime/data/platform_config/` → real `.ini` dir.
Only `libmki.so` reads `ASCEND_HOME_PATH` at runtime.

## Model artifacts

Mount as PVC (not in image):

| Item | Value |
|------|-------|
| Model path | `/models/qwen3.5-35b` |
| Architecture | `Qwen3_5MoeForConditionalGeneration` (multimodal) |
| Auto class | `AutoModelForImageTextToText` (NOT `AutoModelForCausalLM`) |
| Layers | 40 (30 GDN/linear + 10 full attention) |
| Experts | 256 total, 8 active/token, MoE intermediate 512 |
| Config | hidden_size=2048, head_dim=256, linear_key_head_dim=128, linear_value_head_dim=128, linear_num_key_heads=16, linear_num_value_heads=32, linear_conv_kernel_dim=4, full_attention_interval=4 |

**Thinking model:** outputs "Thinking Process: ..." before the answer. Use `max_tokens ≥ 100` to see coherent output; low `max_tokens` truncates thinking and looks like garbling (it isn't).

## Dockerfile sketch

```dockerfile
FROM openeuler/openeuler:24.03-lts-sp1
ARG ARCH=aarch64

# 1. System CANN 8.5.0
COPY Ascend-cann-toolkit_8.5.0_linux-${ARCH}.run /tmp/
RUN chmod +x /tmp/Ascend-cann-toolkit_8.5.0_linux-${ARCH}.run && \
    /tmp/Ascend-cann-toolkit_8.5.0_linux-${ARCH}.run --install --install-for-all \
        --install-path=/usr/local/Ascend && rm /tmp/*.run

# 2. Python 3.10 + venv
RUN yum install -y python3.10 python3.10-pip && \
    python3.10 -m venv /opt/vllm-ascend
ENV PATH=/opt/vllm-ascend/bin:$PATH

# 3. Pinned pip installs
RUN pip install --upgrade pip && \
    pip install torch==2.10.0 torch-npu==2.10.0.post2 transformers==5.14.1 && \
    pip install vllm==0.23.0 vllm-ascend==0.23.0rc1 && \
    pip install --no-deps triton-ascend==3.2.0

# 4. Source patches (6 files from assets/)
COPY assets/ /deploy/assets/
COPY scripts/apply_all_patches.py /deploy/
RUN cd /deploy && python3 apply_all_patches.py /opt/vllm-ascend

# 5. cann-fix wrapper (blocker #14)
COPY scripts/setup_cann_fix.sh /deploy/
RUN bash /deploy/setup_cann_fix.sh /opt/cann-fix

# 6. Env
ENV CC=/usr/local/Ascend/cann-8.5.0/tools/hcc/bin/aarch64-target-linux-gnu-g++ \
    ASCEND_HOME_PATH=/opt/cann-fix \
    ASCEND_RT_VISIBLE_DEVICES=0,1,2,3 \
    HCCL_BUFFSIZE=1024 \
    VLLM_USE_V1=1 \
    VLLM_WORKER_MULTIPROC_METHOD=spawn

# 7. Entrypoint
COPY assets/entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["serve", "/models/qwen3.5-35b", "--host", "0.0.0.0", "--port", "8080", \
     "--tensor-parallel-size", "4", "--dtype", "bfloat16", \
     "--max-model-len", "8192", "--gpu-memory-utilization", "0.90", \
     "--trust-remote-code", "--distributed-executor-backend", "mp", \
     "--compilation-config", "{\"fast_moe_cold_start\": false, \"cudagraph_mode\": \"FULL_AND_PIECEWISE\"}"]
```

Model mounted at `/models/qwen3.5-35b` via PVC. NPU devices exposed by the Ascend k8s device plugin.
