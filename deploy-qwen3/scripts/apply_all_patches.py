#!/usr/bin/env python3
"""apply_all_patches.py — reproduce the working Qwen3.5-35B MoE deployment on
4x Ascend 910B4 (CANN 8.5.0) from a fresh vllm-ascend 0.23.0rc1 venv.

Strategy: copy the 6 audited "known-good" files (pulled from the working qwen6
deployment) over the freshly-installed venv files. This reproduces the exact
working state. The per-file changes are documented in REPRODUCE.md and in the
PATCHED(qwen6) inline comments.

Patches (15 environment blockers, all resolved — see REPRODUCE.md):
  #6  GCC 9+ gate     -> torch/include/c10/util/C++17.h: __GNUC__ < 9 -> < 7
  #7  aclnnAddRmsNormBias      -> utils.py: _CUSTOM_OP_ENABLED = False
  #8  aclnnMoeInitRoutingCustom-> device_op.py: npu_moe_init_routing -> npu_moe_init_routing_v2
  #10 ATB warmup segfault      -> worker.py: comment out _warm_up_atb()
  #11 aclnnCausalConv1d        -> gdn.py: _causal_conv1d_custom_py shim (_310p PyTorch ref)
  #12 aclnnFusedGdnGating      -> gdn.py: fused_gdn_gating_pytorch + g dtype cast
  #13 aclnnChunkGatedDeltaRule -> gdn.py: _chunk_gdr_pytorch_shim (pure-PyTorch chunk ref)
  #15 recurrent state dtype    -> gdn.py: _recurrent_gdr_pytorch (pure-PyTorch, fp32) for decode
       + _recurrent_gdr_bf16 (aclnn bf16-cast) kept for spec-decode site only
  #16 aclnnApplyTopKTopPCustom -> sampler.py: force _apply_top_k_top_p_pytorch fallback
       (9.0.1 sampler op missing in 8.5.0; needed for any non-greedy sampling)
  + throughput: gdn.py adds _recurrent_gdr_pytorch_vec & _causal_conv1d_update_vec
    (vectorized batched decode, no .item() syncs) guarded to N>1 so batch=1 keeps
    the faster single-iteration loop. Helps concurrent multi-request serving.
  (#4 triton-ascend, #5 CC, #9 fast_moe flag, #14 cann-fix are env/launch steps, not file edits)

Usage:
  python3 apply_all_patches.py /home/liangzhu/venvs/vllm-ascend
"""
import sys, os, shutil

VENVP = sys.argv[1] if len(sys.argv) > 1 else "/home/liangzhu/venvs/vllm-ascend"
SP = f"{VENVP}/lib/python3.10/site-packages"
# known-good patched files live in assets/ (sibling of scripts/ in the skill layout)
_SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KGDIR = os.path.join(_SKILL_DIR, "assets")
# Fallback: also check a local known-good/ dir (original deploy-package layout)
if not os.path.exists(os.path.join(KGDIR, "gdn.py")):
    KGDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "known-good")

FILES = {
    "gdn.py":    f"{SP}/vllm_ascend/ops/gdn.py",          # #11 #12 #13 #15 + vec paths + triton decode
    "utils.py":  f"{SP}/vllm_ascend/utils.py",            # #7
    "device_op.py": f"{SP}/vllm_ascend/device/device_op.py",  # #8
    "worker.py": f"{SP}/vllm_ascend/worker/worker.py",    # #10
    "sampler.py": f"{SP}/vllm_ascend/sample/sampler.py",  # #16
    "C++17.h":   f"{SP}/torch/include/c10/util/C++17.h",  # #6
}

print(f"=== Applying known-good patches to venv: {VENVP} ===")
for name, dest in FILES.items():
    src = os.path.join(KGDIR, name)
    if not os.path.exists(src):
        sys.exit(f"FATAL: known-good {name} not found at {src}")
    if not os.path.exists(dest):
        sys.exit(f"FATAL: target {dest} not found (wrong venv path?)")
    shutil.copy2(dest, dest + ".orig")   # back up the fresh file
    shutil.copy2(src, dest)
    print(f"  [ok] {name:12s} -> {dest}  ({os.path.getsize(dest)} bytes)")

print()
print("=== ALL FILE PATCHES APPLIED ===")
print("Remaining setup steps (see REPRODUCE.md):")
print("  1. bash setup_cann_fix.sh                       # #14: ASCEND_HOME_PATH wrapper")
print("  2. pip install --no-deps --force-reinstall triton-ascend==3.2.0   # #4: fix triton")
print("  3. cp launch_vllm.sh ~/launch_vllm.sh && bash ~/launch_vllm.sh   # launch on :8080")
print("  4. curl -s http://127.0.0.1:8080/health         # expect 200")
