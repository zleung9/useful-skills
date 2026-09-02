#!/usr/bin/env bash
# entrypoint.sh — container entrypoint for the Qwen3.5 Ascend NPU deployment.
# Sources CANN env, clears triton cache (npu_utils.so rebuilds on first JIT),
# then execs vllm with all args passed through.
#
# In the container image, this is /entrypoint.sh. CMD passes the vllm serve args.

# CANN userspace toolkit (8.5.0)
if [ -f /usr/local/Ascend/ascend-toolkit/set_env.sh ]; then
  source /usr/local/Ascend/ascend-toolkit/set_env.sh
fi

# ATB (accelerator library)
if [ -f /usr/local/Ascend/nnal/atb/set_env.sh ]; then
  source /usr/local/Ascend/nnal/atb/set_env.sh
fi

# Clear triton cache so npu_utils.so rebuilds cleanly with $CC=HCC g++ on first
# kernel JIT. Safe to do every start — the build is cached after first use.
rm -rf ~/.triton/cache

# CC must be set (ENV in Dockerfile) to the HCC g++ for triton-ascend JIT.
# ASCEND_HOME_PATH must point at the cann-fix wrapper (ENV in Dockerfile).

exec vllm "$@"
