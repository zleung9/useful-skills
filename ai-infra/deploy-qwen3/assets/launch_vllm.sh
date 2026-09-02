#!/usr/bin/env bash
# Launch Qwen3.5-35B MoE (qwen3_5_moe, hybrid linear/full attention + GDN, multimodal)
# via vLLM + vllm-ascend on 4x Ascend 910B4, using the SYSTEM CANN 8.5.0.
#
# === Why 4 NPUs / TP=4 (the original blocker, now resolved) ===
# The prior attempt used TP=3 on the then-3 NPUs and FAILED: vLLM raised
# "Assertion failed, 8192 is not divisible by 3" because the GDN (Gated Delta Net)
# linear-attention conv_dim = head_k_dim*num_k_heads*2 + head_v_dim*num_v_heads
# = 128*16*2 + 128*32 = 8192, and TP must divide 8192 → valid TP ∈ {1,2,4,8}.
# The host now has 4 NPUs, so TP=4 is used (8192/4 = 2048 ✓, num_k_heads 16/4=4 ✓,
# num_v_heads 32/4=8 ✓, max_model_len 8192 % 4 == 0 ✓).
#
# === Why SYSTEM CANN 8.5.0, NOT the user-local CANN 9.0.1 ===
# torch_npu 2.10.0.post2 in the venv is built against CANN 8.5.0 (its _C links
# libhccl.so / libascendcl.so / libacl_op_executor.so etc.).
#   * Pure 8.5.0 (runtime + OPP kernels consistent) → torch.zeros_like works. ✓
#   * Pure 9.0.1 + libhccl.so shim → GEInitializeV2 / FEOpsKernelInfoStore init
#     FAILS (9.0.1 GE/ops layer incompatible with the 8.5.0-built torch_npu). ✗
#   * 9.0.1 OPP kernels + 8.5.0 runtime libs (mixed) → aclnnInplaceZero fails with
#     "ParseDynamicKernels fail / ZerosLike ADD_TO_LAUNCHER_LIST_AICORE failed". ✗
# Also: the user-local CANN 9.0.1 install never shipped the top-level libhccl.so
# (only the split libhccl_v2.so etc.), so torch_npu can't even import from 9.0.1
# alone. vllm-ascend 0.23.0rc1 has NO hard CANN-9.0 gate (it only reads
# ASCEND_HOME_PATH to compile its custom TBE ops), so 8.5.0 is the correct base.
# The 9.0.1 user-local install + the old TP=3 launch are kept as
# launch_vllm_tp3.bak.sh / cann-9.0.1/ for reference but are NOT used.
#
# Drop-in replacement for the hand-rolled FastAPI llm_server.py: vLLM serves the
# same OpenAI /v1/chat/completions path on port 8080. Kills stale llm_server.py /
# vllm to free HBM first. To fall back to FastAPI: bash /home/liangzhu/launch_server.sh
#
# CANN env scripts use unset variables → never set -u / set -euo pipefail here.
set +e

VENV=/home/liangzhu/venvs/vllm-ascend
MODEL=/home/liangzhu/models/qwen3.5-35b
PORT=${VLLM_PORT:-8080}
LOG=/home/liangzhu/vllm_serve.log
MARK=/home/liangzhu/vllm_launcher_marker.txt

echo "=== VLLM LAUNCHER $(date) ===" > "$MARK"

# --- SYSTEM CANN 8.5.0 (matches the 8.5.0-built torch_npu; has libhccl.so) ---
if [ -f /usr/local/Ascend/ascend-toolkit/set_env.sh ]; then
  source /usr/local/Ascend/ascend-toolkit/set_env.sh >> "$MARK" 2>&1
else
  echo "FATAL: system CANN set_env not found at /usr/local/Ascend/ascend-toolkit/set_env.sh" >> "$MARK"
fi
# atb (accelerator library), system copy
if [ -f /usr/local/Ascend/nnal/atb/set_env.sh ]; then
  source /usr/local/Ascend/nnal/atb/set_env.sh >> "$MARK" 2>&1
fi

# --- ATB mki platform_config fix (blocker #14): libmki.so reads
# $ASCEND_HOME_PATH/runtime/data/platform_config, but CANN 8.5.0 installs the
# SoC .ini configs at aarch64-linux/data/platform_config (runtime/ has no data/).
# /usr/local is root-owned so no symlink there; override ASCEND_HOME_PATH to a
# user wrapper that mirrors cann-8.5.0 and adds runtime/data/platform_config ->
# the real .ini dir. Only libmki.so reads this at runtime; graph-engine libs
# (aoe/metadef/data_flow) are not used under enforce-eager. Without this, ATB
# fails "Initialize platform manager" -> ReshapeAndCache kernel not found ->
# atb::OperationSetup segfault in the mki logger during inference.
export ASCEND_HOME_PATH=/home/liangzhu/cann-fix

export PATH="/home/liangzhu/.local/bin:${PATH}"

# --- C++ compiler for triton-ascend npu_utils.so build (HCC g++ 7.3.0 bundled with CANN 8.5.0; container has no system g++/clang). triton _get_cxx honors $CC first; npu_utils.so is cached at ~/.triton once built. ---
export CC=/usr/local/Ascend/cann-8.5.0/tools/hcc/bin/aarch64-target-linux-gnu-g++

# --- NPU device visibility: all 4 logical NPUs (physical 3/4/5/6 → logical 0/1/2/3) ---
export ASCEND_RT_VISIBLE_DEVICES=${ASCEND_RT_VISIBLE_DEVICES:-0,1,2,3}

# --- vLLM / HCCL env knobs ---
export HCCL_BUFFSIZE=1024          # multi-card HCCL buffer
export VLLM_USE_V1=1               # vllm-ascend 0.23 targets the V1 engine
export VLLM_WORKER_MULTIPROC_METHOD=spawn

PY="$VENV/bin/python"
echo "python: $($PY --version 2>&1)" >> "$MARK"
echo "cann: ${ASCEND_HOME_PATH:-unset}" >> "$MARK"
echo "MODEL=$MODEL PORT=$PORT TP=4" >> "$MARK"

# --- KILL the FastAPI fallback + any stale vllm to free HBM ---
echo "--- killing stale llm_server.py / vllm to free HBM ---" >> "$MARK"
pkill -9 -f "llm_server.py" 2>/dev/null
echo "fastapi kill rc=$?" >> "$MARK"
pkill -9 -f "vllm.entrypoints" 2>/dev/null
pkill -9 -f "vllm serve" 2>/dev/null
sleep 5

# --- wait for HBM to actually free ---
echo "--- waiting for HBM to free ---" >> "$MARK"
for i in $(seq 1 30); do
  max_used=$(npu-smi info 2>/dev/null | awk '
    match($0, /[0-9]+ \/ [0-9]+/) {
      v = substr($0, RSTART, RLENGTH);
      split(v, p, " / ");
      used = p[1]+0; total = p[2]+0;
      if (total >= 10000 && used > maxu) maxu = used;
    }
    END { print maxu+0 }')
  echo "  attempt $i: max HBM used across cards = $max_used MB" >> "$MARK"
  if [ -n "$max_used" ] && [ "$max_used" -lt 8000 ] 2>/dev/null; then
    echo "  HBM freed (max used ${max_used}MB < 8000MB)" >> "$MARK"
    break
  fi
  sleep 2
done

pgrep -af "llm_server.py" >> "$MARK" 2>&1 || echo "no llm_server.py procs (good)" >> "$MARK"
pgrep -af "vllm" >> "$MARK" 2>&1 || echo "no stale vllm procs" >> "$MARK"

rm -f "$LOG"

# --- launch vLLM serve ---
# bf16, TP=4 across the 4 NPUs, multimodal auto-detected from config (vision_config).
# --max-model-len 8192: divisible by TP=4 (2048), so the full 8192 is usable
#   (the TP=3 attempt had to use 8190 = largest multiple of 3 ≤ 8192).
# --enforce-eager: no graph capture (safest first TP=4 bring-up of this hybrid
#   MoE config; can be dropped later for throughput once stable).
setsid nohup "$VENV/bin/vllm" serve "$MODEL" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --tensor-parallel-size 4 \
    --dtype bfloat16 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.90 \
    --trust-remote-code \
    --distributed-executor-backend mp \
    --uvicorn-log-level info \
    --compilation-config '{"fast_moe_cold_start": false, "cudagraph_mode": "FULL_AND_PIECEWISE"}' \
    > "$LOG" 2>&1 < /dev/null &

echo "LAUNCH_PID=$!" >> "$MARK"
echo "=== VLLM LAUNCHER_END $(date) ===" >> "$MARK"
