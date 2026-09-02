#!/usr/bin/env python3
"""verify_triton.py — verify triton-ascend is working on the NPU.

The single most important package for throughput is triton-ascend==3.2.0.
Without it, the GDN decode path falls back to ~360 unfused PyTorch ops
(3.1 tok/s). With it, a fused triton kernel runs (46.3 tok/s, 15x).

Run this after `pip install --no-deps triton-ascend==3.2.0` and after
setting `export CC=<HCC g++>` and sourcing the CANN set_env.sh.

Usage:
  source /usr/local/Ascend/ascend-toolkit/set_env.sh
  export CC=/usr/local/Ascend/cann-8.5.0/tools/hcc/bin/aarch64-target-linux-gnu-g++
  python3 verify_triton.py
"""
import sys

def main():
    import torch
    import torch_npu  # noqa: F401
    device = "npu:0"

    # Test 1: triton-ascend imports and the fused recurrent kernel runs
    from vllm.model_executor.layers.fla.ops.fused_recurrent import (
        fused_recurrent_gated_delta_rule)

    q = torch.randn(1, 1, 4, 128, device=device, dtype=torch.bfloat16)
    k = torch.randn(1, 1, 4, 128, device=device, dtype=torch.bfloat16)
    v = torch.randn(1, 1, 8, 128, device=device, dtype=torch.bfloat16)
    g = torch.randn(1, 1, 8, device=device, dtype=torch.bfloat16)
    state = torch.randn(4, 8, 128, 128, device=device, dtype=torch.float32)

    try:
        out, _ = fused_recurrent_gated_delta_rule(
            q, k, v, g=g, scale=128 ** -0.5,
            initial_state=state, inplace_final_state=True,
            use_qk_l2norm_in_kernel=True)
        torch.npu.synchronize()
        print(f"PASS: fused_recurrent_gated_delta_rule runs on NPU, out={tuple(out.shape)}")
    except Exception as e:
        print(f"FAIL: triton kernel did not run: {e}")
        print("  → Check: triton-ascend installed? CC set to HCC g++? ~/.triton cache cleared?")
        return 1

    # Test 2: benchmark (expect ~0.4ms/call)
    import time
    torch.npu.synchronize()
    t0 = time.time()
    for _ in range(100):
        fused_recurrent_gated_delta_rule(
            q, k, v, g=g, scale=128 ** -0.5,
            initial_state=state, inplace_final_state=True,
            use_qk_l2norm_in_kernel=True)
    torch.npu.synchronize()
    ms_per_call = (time.time() - t0) * 10
    print(f"PASS: 100 calls in {ms_per_call*100:.1f}ms ({ms_per_call:.3f}ms/call)")
    print()
    print("triton-ascend is WORKING. GDN decode will use the fused kernel → ~46 tok/s.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
