#
# Copyright (c) 2025 Huawei Technologies Co., Ltd. All Rights Reserved.
# This file is a part of the vllm-ascend project.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import torch
import torch.nn.functional as F
from einops import rearrange

# Throughput instrumentation: recurrent GDN call count / total time.
_rec_gdr_n = [0]
_rec_gdr_t = [0.0]
from vllm.distributed import get_pcp_group
from vllm.forward_context import get_forward_context
from vllm.model_executor.layers.fla.ops.l2norm import l2norm_fwd
from vllm.model_executor.layers.fla.ops.fused_recurrent import (
    fused_recurrent_gated_delta_rule as _triton_fused_recurrent_gdr)
from vllm.model_executor.layers.mamba.gdn.base import GatedDeltaNetAttention
from vllm.model_executor.layers.mamba.mamba_utils import MambaStateShapeCalculator
from vllm.triton_utils import triton
from vllm.v1.attention.backend import AttentionBackend, AttentionMetadata  # type: ignore
from vllm.v1.attention.backends.gdn_attn import GDNAttentionMetadata
from vllm.v1.attention.backends.utils import PAD_SLOT_ID

from vllm_ascend.attention.utils import maybe_save_kv_layer_to_connector

# State writeback uses scatter_ (in-place) with proper shape alignment.
# Earlier "161002 error" was a shape mismatch (EZ1001), NOT a graph capture
# limitation. With correct non-dim-0 shape alignment, scatter_ captures
# successfully in vLLM FULL graph mode AND produces correct output.
from vllm_ascend.device.device_op import DeviceOperator
from vllm_ascend.ops.gdn_attn_builder import AscendGDNAttentionBackend
from vllm_ascend.ops.triton.fla.chunk import chunk_gated_delta_rule
from vllm_ascend.ops.triton.fla.fused_qkvzba_split_reshape import fused_qkvzba_split_reshape_cat
from vllm_ascend.ops.triton.fla.utils import clear_ssm_states
from vllm_ascend.ops.triton.mamba.causal_conv1d import extract_last_width


def _chunk_gdr_pytorch_shim(q, k, v, g, beta, *, initial_state=None,
                            output_final_state=False, cu_seqlens=None,
                            prebuilt_meta=None, head_first=False,
                            use_qk_l2norm_in_kernel=False, scale=None,
                            **kwargs):
    """Pure-PyTorch fallback for the triton chunk_gated_delta_rule.

    CANN 8.5.0 lacks aclnnChunkGatedDeltaRuleFwdH / aclnnChunkFwdO (9.0.1 custom
    aclnn ops) used by the 910B triton chunk path. Route to the _310p reference
    (chunk_gated_delta_rule_pytorch): a vLLM-compatible pure-PyTorch
    implementation with no aclnn dependency. `prebuilt_meta` is dropped (the
    reference computes chunk indices internally). Slower but functional.
    """
    from vllm_ascend._310p.ops.fla.chunk_gated_delta_rule import (
        chunk_gated_delta_rule_pytorch)
    return chunk_gated_delta_rule_pytorch(
        q, k, v, g, beta, scale=scale, initial_state=initial_state,
        output_final_state=output_final_state, cu_seqlens=cu_seqlens,
        head_first=head_first, use_qk_l2norm_in_kernel=use_qk_l2norm_in_kernel)

def _recurrent_gdr_bf16(*, query, key, value, g, beta, state, scale,
                        actual_seq_lengths, ssm_state_indices, **kwargs):
    """Wrap npu_recurrent_gated_delta_rule for CANN 8.5.0 (blocker #15).

    The gdn.py comment claims the AscendC custom op 'extends dtype support
    (e.g. float32 state)', but under 8.5.0 its fp32 path routes to
    aclnnRecurrentGatedDeltaRule which rejects fp32:
      AclNN_Parameter_Error(EZ1001): params.state not implemented for
      DT_FLOAT, should be in [DT_BFLOAT16].
    Cast state -> bf16 for the op, then copy the in-place-updated indexed
    entries back to the original buffer's dtype so the recurrent state
    persists across decode steps. (Under 9.0.1 the aclnn accepts fp32 and
    this shim is a no-op when state is already bf16.)
    """
    import sys
    if state.dtype == torch.bfloat16:
        return torch.ops._C_ascend.npu_recurrent_gated_delta_rule(
            query=query, key=key, value=value, g=g, beta=beta, state=state,
            scale=scale, actual_seq_lengths=actual_seq_lengths,
            ssm_state_indices=ssm_state_indices, **kwargs)
    print(f"DBG recurrent_gdr: casting state {state.dtype}->bf16 "
          f"#idx={int(ssm_state_indices.numel())}", file=sys.stderr, flush=True)
    state_bf16 = state.to(torch.bfloat16)
    out = torch.ops._C_ascend.npu_recurrent_gated_delta_rule(
        query=query, key=key, value=value, g=g, beta=beta, state=state_bf16,
        scale=scale, actual_seq_lengths=actual_seq_lengths,
        ssm_state_indices=ssm_state_indices, **kwargs)
    # op updated state_bf16[ssm_state_indices] in place; persist back to the
    # original (fp32) buffer so the next decode step sees the advanced state.
    state[ssm_state_indices] = state_bf16[ssm_state_indices].to(state.dtype)
    return out

def _recurrent_gdr_pytorch_vec(query, key, value, g, beta, *, state, scale,
                               ssm_state_indices, num_accepted_tokens=None,
                               **kwargs):
    """Vectorized pure-PyTorch recurrent GDN decode (throughput fix).

    The loop-based _310p reference calls int(ssm_state_indices[...].item())
    twice per token per layer, forcing a full NPU queue drain (host sync) that
    starves the NPU (AICore ~14%) and yields ~350 ms/token. For non-spec
    decode every sequence contributes exactly 1 token and the sequences are
    mutually independent, so the whole recurrence is computed with a handful
    of batched NPU ops + index_select / advanced-index write -- no .item(),
    no Python loop, no host sync.

    Layouts (aclnn call-site convention):
      query/key: (T, H, K)   value: (T, HV, V)   g/beta: (T, HV)
      state: (N, HV, K, V)   ssm_state_indices: (T,) slot ids, T == #decode seqs
    Returns (T, HV, V), or None to signal "use the loop fallback".
    """
    T, H, K = query.shape
    HV, V = value.shape[1], value.shape[2]
    idx1d = ssm_state_indices.view(-1).to(torch.long)
    N_dec = idx1d.shape[0]
    # Only the pure-decode case (1 token / sequence, no spec acceptance) is
    # vectorizable here; anything else falls back to the loop reference.
    # NOTE: the N==1 guard was removed so single-request decode also takes this
    # capture-compatible path (no .item() host sync) -- required for FULL graph
    # capture. In eager mode N==1 is marginally slower than the 1-iter loop, but
    # under FULL capture the launch overhead is eliminated anyway.
    if T != N_dec or num_accepted_tokens is not None or g is None or beta is None:
        return None

    from vllm_ascend._310p.ops.fla.l2norm import l2norm_310p
    # l2norm over the head dim. The call site already applied l2norm_fwd; this
    # is idempotent and matches use_qk_l2norm_in_kernel=True of the reference.
    q = l2norm_310p(query).to(torch.float32) * scale      # (T,H,K)
    k = l2norm_310p(key).to(torch.float32)                # (T,H,K)
    v = value.to(torch.float32)                            # (T,HV,V)
    g_f = g.to(torch.float32)                              # (T,HV)
    beta_f = beta.to(torch.float32)                        # (T,HV)

    # grouped-value: expand H k-heads -> HV v-heads (repeat_interleave)
    if H != HV:
        grp = HV // H
        q_hv = q.repeat_interleave(grp, dim=1)             # (T,HV,K)
        k_hv = k.repeat_interleave(grp, dim=1)             # (T,HV,K)
    else:
        q_hv, k_hv = q, k

    # state (N,HV,K,V) -> (N,HV,V,K); gather the decoded slots -> (N_dec,HV,V,K)
    h = state.transpose(-1, -2).index_select(0, idx1d).to(torch.float32).contiguous()

    # delta-rule recurrence, fully vectorized over N_dec sequences (fp32):
    h = h * torch.exp(g_f).view(N_dec, HV, 1, 1)                      # state decay
    v_corr = v - (h * k_hv.unsqueeze(-2)).sum(-1)                     # (N_dec,HV,V)
    v_corr = v_corr * beta_f.view(N_dec, HV, 1)                       # gate
    h = h + v_corr.unsqueeze(-1) * k_hv.unsqueeze(-2)                 # state update (N_dec,HV,V,K)
    o = (h * q_hv.unsqueeze(-2)).sum(-1)                              # output (N_dec,HV,V)

    # scatter_ writeback (in-place, capture-safe with correct shapes).
    # The earlier "161002 error" was a shape mismatch, not a capture limit.
    new_h = h.transpose(-1, -2).contiguous().to(state.dtype)   # (N_dec,HV,K,V)
    idx_exp = idx1d.view(-1, 1, 1, 1).expand_as(new_h)
    state.scatter_(0, idx_exp, new_h)
    return o.to(value.dtype)                                          # (N_dec,HV,V)

def _recurrent_gdr_pytorch(query, key, value, g, beta, *, state, scale,
                           actual_seq_lengths, ssm_state_indices,
                           num_accepted_tokens=None, **kwargs):
    """Pure-PyTorch recurrent GDN (blocker #15 correctness fix).

    The aclnn npu_recurrent_gated_delta_rule under CANN 8.5.0 -- even with the
    bf16 state cast -- produces garbled decode output: the recurrence drifts
    in pure bf16 (no fp32 upcast) and the in-place state update is not
    reliably reflected in the passed buffer. Use the _310p pure-PyTorch
    reference instead, which upcasts to fp32 for the recurrence (stable) and
    returns the updated states explicitly.

    Throughput fix: the loop reference calls .item() (host sync) per token per
    layer, starving the NPU. For the common pure-decode case we use a fully
    vectorized batched path (_recurrent_gdr_pytorch_vec) with no syncs; any
    unexpected shape falls back to the loop reference (correctness preserved).
    """
    # Fast path: vectorized batched decode (no .item() syncs, no Python loop).
    # No N>1 guard: single-request decode (N=1) also uses the vec path --
    # required for FULL graph capture (the loop fallback has .item() host
    # syncs that crash capture).  scatter_ writeback is capture-safe and
    # verified correct on CANN 8.5.0.
    try:
        out = _recurrent_gdr_pytorch_vec(
            query, key, value, g, beta, state=state, scale=scale,
            ssm_state_indices=ssm_state_indices,
            num_accepted_tokens=num_accepted_tokens)
    except Exception as _e:
        import sys; print(f"VEC RECURRENT EXC: {_e}", file=sys.stderr, flush=True)
        out = None
    if out is not None:
        return out
    # Fallback: loop-based _310p reference (correctness-preserving).
    from vllm_ascend._310p.ops.fla.fused_recurrent_gated_delta_rule import (
        fused_recurrent_gated_delta_rule_pytorch)
    q4 = query.unsqueeze(0)
    k4 = key.unsqueeze(0)
    v4 = value.unsqueeze(0)
    g4 = g.unsqueeze(0) if g is not None else g
    beta4 = beta.unsqueeze(0) if beta is not None else beta
    # ssm_state (N,HV,K,V) -> (N,HV,V,K) for the pytorch ref. Contiguous copy
    # so inplace_final_state=True updates *this* copy, not the view of state.
    init_state = state.transpose(-1, -2).contiguous()
    # Decode: each sequence is exactly 1 token. Flatten the slot ids to 1D
    # (ssm_state_indices may arrive as (1,N), (N,1), or (N,)), derive
    # num_decodes, and build cu_seqlens = arange(N+1) plus ssi2 (N,1) for
    # the pytorch ref _state_index lookup. actual_seq_lengths is ignored
    # since non-spec decode sequences are always single tokens.
    idx1d = ssm_state_indices.view(-1)
    num_decodes = int(idx1d.shape[0])
    ssi2 = idx1d.view(num_decodes, 1)
    cu = torch.arange(num_decodes + 1, dtype=torch.int64, device=state.device)
    out, new_states = fused_recurrent_gated_delta_rule_pytorch(
        q4, k4, v4, g4, beta4,
        initial_state=init_state,
        inplace_final_state=True,
        cu_seqlens=cu,
        ssm_state_indices=ssi2,
        num_accepted_tokens=num_accepted_tokens,
        use_qk_l2norm_in_kernel=True,
    )
    # Persist only the decoded slots: (N,HV,V,K) -> (N,HV,K,V).
    state[idx1d] = new_states[idx1d].transpose(-1, -2).contiguous().to(state.dtype)
    return out.squeeze(0)

def _causal_conv1d_update_vec(x, conv_state, weight, bias, activation,
                              conv_state_indices, pad_slot_id=PAD_SLOT_ID):
    """Vectorized causal_conv1d_update for pure decode (no .item(), no loop).

    The _310p causal_conv1d_update loops over sequences calling
    int(conv_state_indices[i].item()) / int(query_start_loc[i].item()), which
    forces a host sync that (a) starves the NPU and (b) breaks graph capture
    ("Not allow to synchronize captured-stream"). For non-spec decode every
    sequence contributes exactly 1 token, so the whole batch is computed with
    index_select + a batched depthwise conv + index_copy_ -- no syncs, no loop.

    x: (N, dim) [seq-first]; conv_state: (N_total, dim, state_len) [dim-first];
    weight: (dim, width); conv_state_indices: (N,) slot ids.
    Returns (N, dim); updates conv_state[indices] in place.
    """
    N, dim = x.shape
    idx = conv_state_indices.to(torch.long)
    states = conv_state.index_select(0, idx)              # (N, dim, state_len) or transposed
    w = weight
    if w.shape[0] != dim and w.shape[1] == dim:
        w = w.transpose(0, 1)
    w = w.contiguous()
    _, width = w.shape
    state_len = width - 1
    if states.shape[-2] != dim and states.shape[-1] == dim:
        states = states.transpose(-1, -2)
    states = states[..., :state_len]
    x_exp = x.to(states.dtype).unsqueeze(-1)              # (N, dim, 1)
    x_cat = torch.cat([states, x_exp], dim=-1)            # (N, dim, width)
    out = (x_cat * w.unsqueeze(0)).sum(-1)                # (N, dim) depthwise conv
    if bias is not None:
        out = out + bias.to(out.dtype)
    if activation is not None:
        out = F.silu(out)
    new_state = x_cat[..., 1:].contiguous()               # (N, dim, state_len)
    new_state = new_state.to(conv_state.dtype)
    # Match conv_state layout for scatter_: conv_state may be stored as
    # (N_total, state_len, dim) while new_state is (N, dim, state_len).
    # Transpose to align non-dim-0 shapes (scatter_ requires match).
    if conv_state.shape[-1] == dim and conv_state.shape[-2] != dim:
        new_state = new_state.transpose(-1, -2).contiguous()  # (N, state_len, dim)
    idx_exp = idx.view(-1, 1, 1).expand_as(new_state)
    conv_state.scatter_(0, idx_exp, new_state)
    return out.to(x.dtype)                                # (N, dim)

def _causal_conv1d_custom_py(output, x, weight, *, conv_state, bias_opt=None,
                             query_start_loc_opt=None,
                             cache_indices_opt=None,
                             initial_state_mode_opt=None,
                             num_accepted_tokens_opt=None,
                             activation_mode=0,
                             pad_slot_id=PAD_SLOT_ID,
                             run_mode=0):
    """PyTorch shim for torch.ops._C_ascend.npu_causal_conv1d_custom.

    CANN 8.5.0 lacks aclnnCausalConv1d (a 9.0.1 custom aclnn op), so the fused
    conv1d cannot run. Route to the _310p PyTorch reference instead:
    causal_conv1d_fn for prefill (run_mode==0), causal_conv1d_update for decode
    (run_mode==1). Both update conv_state in place and return the output; copy
    it into the out-of-place `output` buffer the original op writes to.
    """
    from vllm_ascend._310p.ops.causal_conv1d import (
        causal_conv1d_fn, causal_conv1d_update)
    activation = "silu" if activation_mode else None
    if run_mode == 0:
        if initial_state_mode_opt is None:
            batch = query_start_loc_opt.shape[0] - 1
            has_initial_state = torch.zeros(
                batch, dtype=torch.bool, device=x.device)
        else:
            has_initial_state = initial_state_mode_opt
        # causal_conv1d_fn expects x as (dim, total_tokens) [dim-first]; the
        # GDN passes (total_tokens, dim) [seq-first]. Transpose 2D x if needed
        # and transpose the result back to match the seq-first `output`.
        x_in = x
        transposed = False
        if x.dim() == 2:
            feature_dim = max(weight.shape)
            if x.shape[0] != feature_dim:
                x_in = x.transpose(0, 1).contiguous()
                transposed = True
        out = causal_conv1d_fn(
            x_in, weight, bias_opt, activation, conv_state, has_initial_state,
            cache_indices_opt, query_start_loc_opt, pad_slot_id)
        if transposed and out is not None and out.dim() == 2:
            output.copy_(out.transpose(0, 1))
        elif out is not None and out.shape == output.shape:
            output.copy_(out)
        elif out is not None:
            output[:out.shape[0], :out.shape[1]].copy_(out)
    else:
        # causal_conv1d_update expects x as (num_tokens, dim) [seq-first] ->
        # matches the GDN layout; out has the same shape as x.
        # Fast path: vectorized batched decode (no .item() syncs, no loop).
        # For pure non-spec decode every segment is exactly 1 token, i.e.
        # x.shape[0] == query_start_loc.shape[0]-1 (a shape check, no sync).
        # NOTE: the scatter back (scatter_) is capture-INcompatible on CANN 8.5.0
        # (aclnnInplaceScatter error 161002), so this path is only used when the
        # GDN runs eagerly (PIECEWISE mode, where the split op is not captured).
        out = None
        qs = query_start_loc_opt
        _decode_single = qs is None or x.shape[0] == qs.shape[0] - 1
        if (num_accepted_tokens_opt is None and cache_indices_opt is not None
                and x.dim() == 2 and _decode_single):
            try:
                out = _causal_conv1d_update_vec(
                    x, conv_state, weight, bias_opt, activation,
                    cache_indices_opt, pad_slot_id)
            except Exception as _e:
                import sys; print(f"VEC CONV1D EXC: {_e}", file=sys.stderr, flush=True)
                out = None
        if out is None:
            out = causal_conv1d_update(
                x, conv_state, weight, bias_opt, activation, cache_indices_opt,
                num_accepted_tokens_opt, query_start_loc_opt, pad_slot_id)
        if out is not None and out.shape == output.shape:
            output.copy_(out)
        elif out is not None:
            output[:out.shape[0], :out.shape[1]].copy_(out)
    return output



class AscendGatedDeltaNetAttention(GatedDeltaNetAttention):
    def _split_ba_for_tp(self, ba: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if hasattr(self, "split_ba"):
            return self.split_ba(ba)
        return ba.chunk(2, dim=-1)

    def get_state_shape(
        self,
    ) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
        return MambaStateShapeCalculator.gated_delta_net_state_shape(
            self.tp_size,
            self.num_k_heads,
            self.num_v_heads,
            self.head_k_dim,
            self.head_v_dim,
            self.conv_kernel_size,
            self.num_spec,
        )

    def _warmup_prefill_kernels(self, qkv_or_qkvz: torch.Tensor, v_dim: int) -> None:
        return

    def _warmup_prefill_kernels_v0202(self, mixed_qkv: torch.Tensor) -> None:
        return

    def get_attn_backend(self) -> type[AttentionBackend]:
        return AscendGDNAttentionBackend

    def forward(
        self,
        hidden_states: torch.Tensor,
        output: torch.Tensor,
    ):
        """
        Forward pass with three parts:
        1. Input projection
        2. Core attention (custom op)
        3. Output projection
        """
        num_tokens = hidden_states.size(0)
        if hasattr(self, "in_proj_qkv"):
            mixed_qkv, _ = self.in_proj_qkv(hidden_states)
            ba, _ = self.in_proj_ba(hidden_states)
            z, _ = self.in_proj_z(hidden_states)
            z = z.reshape(z.size(0), -1, self.head_v_dim)
            b, a = self._split_ba_for_tp(ba)
            b = b.contiguous()
            a = a.contiguous()
        else:
            if not self.gqa_interleaved_layout:
                mixed_qkvz, _ = self.in_proj_qkvz(hidden_states)
                num_tokens = mixed_qkvz.size(0)
                qkv_size = (self.key_dim * 2 + self.value_dim) // self.tp_size
                z_size = self.value_dim // self.tp_size
                mixed_qkv, z = mixed_qkvz.split([qkv_size, z_size], dim=-1)
                z = z.reshape(z.size(0), -1, self.head_v_dim)
                ba, _ = self.in_proj_ba(hidden_states)
                b, a = self._split_ba_for_tp(ba)

                b = b.contiguous()
                a = a.contiguous()
            else:
                projected_states_qkvz, _ = self.in_proj_qkvz(hidden_states)
                projected_states_ba, _ = self.in_proj_ba(hidden_states)
                num_tokens = projected_states_qkvz.size(0)

                mixed_qkv, z, b, a = fused_qkvzba_split_reshape_cat(
                    projected_states_qkvz,
                    projected_states_ba,
                    triton.cdiv(self.num_k_heads, self.tp_size),
                    triton.cdiv(self.num_v_heads, self.tp_size),
                    self.head_k_dim,
                    self.head_v_dim,
                )

        # ============================================================
        # Part 2: Core Attention (Custom Op)
        # ============================================================
        # Note: we should not use torch.empty here like other attention backends,
        # see discussions in https://github.com/vllm-project/vllm/pull/28182
        core_attn_out = torch.zeros(
            (num_tokens, self.num_v_heads // self.tp_size, self.head_v_dim),
            dtype=hidden_states.dtype,
            device=hidden_states.device,
        )

        torch.ops.vllm.qwen_gdn_attention_core(
            mixed_qkv,
            b,
            a,
            core_attn_out,
            self.prefix,
            False,
        )

        # ============================================================
        # Part 3: Output Projection
        # ============================================================
        maybe_save_kv_layer_to_connector("", [])
        z_shape_og = z.shape
        # Reshape input data into 2D tensor
        core_attn_out = core_attn_out.reshape(-1, core_attn_out.shape[-1])
        z = z.reshape(-1, z.shape[-1])
        core_attn_out = self.norm(core_attn_out, z)
        core_attn_out = core_attn_out.reshape(z_shape_og)
        core_attn_out = rearrange(core_attn_out, "... h d -> ... (h d)")
        output[:num_tokens], _ = self.out_proj(core_attn_out)

    def _forward_core(
        self,
        mixed_qkv: torch.Tensor,
        b: torch.Tensor,
        a: torch.Tensor,
        core_attn_out: torch.Tensor,
    ):
        """
        Core attention computation (called by custom op).
        """
        forward_context = get_forward_context()
        attn_metadata: AttentionMetadata = forward_context.attn_metadata

        if attn_metadata is None:
            # V1 profile run
            return

        assert isinstance(attn_metadata, dict)
        attn_metadata = attn_metadata[self.prefix]
        assert isinstance(attn_metadata, GDNAttentionMetadata)
        spec_sequence_masks = attn_metadata.spec_sequence_masks
        spec_token_indx = attn_metadata.spec_token_indx
        non_spec_token_indx = attn_metadata.non_spec_token_indx
        spec_state_indices_tensor = attn_metadata.spec_state_indices_tensor  # noqa: E501
        non_spec_state_indices_tensor = attn_metadata.non_spec_state_indices_tensor  # noqa: E501
        self_kv_cache = self.kv_cache
        ssm_state = self_kv_cache[1]
        num_actual_tokens = attn_metadata.num_actual_tokens

        mixed_qkv = mixed_qkv[:num_actual_tokens]
        b = b[:num_actual_tokens]
        a = a[:num_actual_tokens]

        # 1. Convolution sequence transformation
        conv_weights = self.conv1d.weight.view(self.conv1d.weight.size(0), self.conv1d.weight.size(2))
        if spec_sequence_masks is not None:
            if attn_metadata.num_prefills == 0 and attn_metadata.num_decodes == 0:
                mixed_qkv_spec = mixed_qkv
                mixed_qkv_non_spec = None
            else:
                mixed_qkv_spec = mixed_qkv.index_select(0, spec_token_indx)
                mixed_qkv_non_spec = mixed_qkv.index_select(0, non_spec_token_indx)
        else:
            mixed_qkv_spec = None
            mixed_qkv_non_spec = mixed_qkv

        # 1.1: Process the multi-query part
        if spec_sequence_masks is not None:
            conv_weights_T = conv_weights.transpose(0, 1)
            activation_num = 1 if self.activation else 0
            spec_causal_conv1d_meta = attn_metadata.spec_decode_metadata.spec_causal_conv1d
            spec_query_start_loc_device = spec_causal_conv1d_meta.query_start_loc
            output_spec = torch.empty_like(mixed_qkv_spec)
            _causal_conv1d_custom_py(
                output_spec,
                mixed_qkv_spec,
                conv_weights_T,
                conv_state=self_kv_cache[0],
                bias_opt=self.conv1d.bias,
                query_start_loc_opt=spec_query_start_loc_device,
                cache_indices_opt=spec_causal_conv1d_meta.cache_indices,
                initial_state_mode_opt=None,
                num_accepted_tokens_opt=spec_causal_conv1d_meta.num_accepted_tokens,
                activation_mode=activation_num,
                pad_slot_id=PAD_SLOT_ID,
                run_mode=1,
            )
            mixed_qkv_spec = output_spec

        # 1.2: Process the remaining part
        if attn_metadata.num_prefills > 0:
            if mixed_qkv_non_spec is not None:
                non_spec_causal_conv1d_meta = attn_metadata.non_spec_prefill_metadata.causal_conv1d
                query_start_loc_opt = non_spec_causal_conv1d_meta.query_start_loc
                cache_indices_opt = non_spec_causal_conv1d_meta.cache_indices
                initial_state_mode_opt = non_spec_causal_conv1d_meta.initial_state_mode
                if get_pcp_group().world_size > 1:
                    conv_weights_T = conv_weights.transpose(0, 1)
                    activation_num = 1 if self.activation else 0
                    non_spec_query_start_loc = attn_metadata.non_spec_query_start_loc
                    assert non_spec_query_start_loc is not None
                    non_spec_state_indices_tensor = attn_metadata.non_spec_state_indices_tensor
                    width = conv_weights.shape[1]
                    state_len = width - 1
                    num_seqs = non_spec_query_start_loc.shape[0] - 1
                    prefill_seq_offset = max(0, num_seqs - attn_metadata.num_prefills)
                    prefill_cache_indices = non_spec_state_indices_tensor[prefill_seq_offset:]
                    mixed_qkv_non_spec_T = mixed_qkv_non_spec.transpose(0, 1)
                    last_width_prefill_x = extract_last_width(
                        mixed_qkv_non_spec_T, non_spec_query_start_loc[prefill_seq_offset:], state_len
                    )
                    pcp_rank = get_pcp_group().rank_in_group
                    all_last_width_prefill_x = get_pcp_group().all_gather(
                        last_width_prefill_x.unsqueeze(0).contiguous(), 0
                    )
                    if pcp_rank > 0 and prefill_cache_indices.shape[0] > 0:
                        self_kv_cache[0][prefill_cache_indices, :state_len, :] = all_last_width_prefill_x[
                            pcp_rank - 1, ...
                        ].transpose(-1, -2)
                    mixed_qkv_non_spec_output = torch.empty_like(mixed_qkv_non_spec)
                    _causal_conv1d_custom_py(
                        mixed_qkv_non_spec_output,
                        mixed_qkv_non_spec,
                        conv_weights_T,
                        conv_state=self_kv_cache[0],
                        bias_opt=self.conv1d.bias,
                        query_start_loc_opt=query_start_loc_opt,
                        cache_indices_opt=cache_indices_opt,
                        initial_state_mode_opt=initial_state_mode_opt,
                        num_accepted_tokens_opt=None,
                        activation_mode=activation_num,
                        pad_slot_id=PAD_SLOT_ID,
                        run_mode=0,
                    )
                    mixed_qkv_non_spec = mixed_qkv_non_spec_output
                    if prefill_cache_indices.shape[0] > 0:
                        self_kv_cache[0][prefill_cache_indices, :state_len, :] = all_last_width_prefill_x[
                            -1, ...
                        ].transpose(-1, -2)
                else:
                    conv_weights_T = conv_weights.transpose(0, 1)
                    activation_num = 1 if self.activation else 0
                    mixed_qkv_non_spec_output = torch.empty_like(mixed_qkv_non_spec)
                    _causal_conv1d_custom_py(
                        mixed_qkv_non_spec_output,
                        mixed_qkv_non_spec,
                        conv_weights_T,
                        conv_state=self_kv_cache[0],
                        bias_opt=self.conv1d.bias,
                        query_start_loc_opt=query_start_loc_opt,
                        cache_indices_opt=cache_indices_opt,
                        initial_state_mode_opt=initial_state_mode_opt,
                        num_accepted_tokens_opt=None,
                        activation_mode=activation_num,
                        pad_slot_id=PAD_SLOT_ID,
                        run_mode=0,
                    )
                    mixed_qkv_non_spec = mixed_qkv_non_spec_output
        elif attn_metadata.num_decodes > 0:
            conv_weights_T = conv_weights.transpose(0, 1)
            activation_num = 1 if self.activation else 0
            non_spec_causal_conv1d_meta = attn_metadata.non_spec_decode_metadata.causal_conv1d
            non_spec_query_start_loc_device = non_spec_causal_conv1d_meta.query_start_loc
            output_non_spec = torch.empty_like(mixed_qkv_non_spec)
            _causal_conv1d_custom_py(
                output_non_spec,
                mixed_qkv_non_spec,
                conv_weights_T,
                conv_state=self_kv_cache[0],
                bias_opt=self.conv1d.bias,
                query_start_loc_opt=non_spec_query_start_loc_device,
                cache_indices_opt=non_spec_causal_conv1d_meta.cache_indices,
                initial_state_mode_opt=None,
                num_accepted_tokens_opt=None,
                activation_mode=activation_num,
                pad_slot_id=PAD_SLOT_ID,
                run_mode=1,
            )
            mixed_qkv_non_spec = output_non_spec
        else:
            mixed_qkv_non_spec = None

        query_spec, key_spec, value_spec = self.rearrange_mixed_qkv(mixed_qkv_spec)
        query_non_spec, key_non_spec, value_non_spec = self.rearrange_mixed_qkv(mixed_qkv_non_spec)

        # 2. Recurrent attention
        from vllm_ascend._310p.ops.fla.fused_gdn_gating import (
            fused_gdn_gating_pytorch)
        g, beta = fused_gdn_gating_pytorch(self.A_log, a, b, self.dt_bias)
        # _310p ref computes g in fp32 and only casts beta; the 910B triton
        # chunk_gated_delta_rule kernel expects g in the model dtype (bf16).
        g = g.to(self.A_log.dtype)
        if spec_sequence_masks is not None:
            if attn_metadata.num_prefills == 0 and attn_metadata.num_decodes == 0:
                g_spec = g
                beta_spec = beta
                g_non_spec = None
                beta_non_spec = None
            else:
                g_spec = g.index_select(1, spec_token_indx)
                beta_spec = beta.index_select(1, spec_token_indx)
                g_non_spec = g.index_select(1, non_spec_token_indx)
                beta_non_spec = beta.index_select(1, non_spec_token_indx)
        else:
            g_spec = None
            beta_spec = None
            g_non_spec = g
            beta_non_spec = beta

        split_non_spec = (
            spec_sequence_masks is None and attn_metadata.num_prefills > 0 and attn_metadata.num_decodes > 0
        )
        num_decode_tokens = attn_metadata.num_decode_tokens

        # 2.1: Process the multi-query part
        if spec_sequence_masks is not None:
            actual_seq_lengths = attn_metadata.spec_decode_metadata.actual_seq_lengths
            query_spec = l2norm_fwd(query_spec)
            key_spec = l2norm_fwd(key_spec)
            # Dispatches to the vllm-ascend AscendC custom operator
            # (csrc/recurrent_gated_delta_rule), NOT the built-in CANN operator.
            # The custom op extends dtype support (e.g. float32 state) and is
            # loaded at runtime via ASCEND_CUSTOM_OPP_PATH.
            core_attn_out_spec = _recurrent_gdr_bf16(
                query=query_spec.squeeze(0),
                key=key_spec.squeeze(0),
                value=value_spec.squeeze(0),
                g=g_spec.squeeze(0),
                beta=beta_spec.squeeze(0),
                state=ssm_state,
                scale=key_spec.shape[-1] ** -0.5,
                actual_seq_lengths=actual_seq_lengths,
                ssm_state_indices=spec_state_indices_tensor.flatten(),
                num_accepted_tokens=spec_causal_conv1d_meta.num_accepted_tokens.to(torch.int32),
            ).unsqueeze(0)
        else:
            core_attn_out_spec, last_recurrent_state = None, None

        # 2.2: Process non-spec-decode part in mixed non-spec batches
        if split_non_spec:
            assert mixed_qkv_non_spec is not None
            assert g_non_spec is not None
            assert beta_non_spec is not None
            query_decode, key_decode, value_decode = self.rearrange_mixed_qkv(mixed_qkv_non_spec[:num_decode_tokens])
            # TRITON fused recurrent decode (same as 2.3 below)
            try:
                core_attn_out_decode, _ = _triton_fused_recurrent_gdr(
                    q=query_decode,
                    k=key_decode,
                    v=value_decode,
                    g=g_non_spec[:, :num_decode_tokens],
                    beta=beta_non_spec[:, :num_decode_tokens],
                    scale=key_decode.shape[-1] ** -0.5,
                    initial_state=ssm_state,
                    inplace_final_state=True,
                    ssm_state_indices=non_spec_state_indices_tensor[: attn_metadata.num_decodes],
                    use_qk_l2norm_in_kernel=True,
                )
            except Exception:
                actual_seq_lengths = attn_metadata.non_spec_decode_metadata.actual_seq_lengths
                query_decode_fb = l2norm_fwd(query_decode)
                key_decode_fb = l2norm_fwd(key_decode)
                core_attn_out_decode = _recurrent_gdr_pytorch(
                    query=query_decode_fb.squeeze(0),
                    key=key_decode_fb.squeeze(0),
                    value=value_decode.squeeze(0),
                    g=g_non_spec[:, :num_decode_tokens].squeeze(0),
                    beta=beta_non_spec[:, :num_decode_tokens].squeeze(0),
                    state=ssm_state,
                    scale=key_decode_fb.shape[-1] ** -0.5,
                    actual_seq_lengths=actual_seq_lengths,
                    ssm_state_indices=non_spec_state_indices_tensor[: attn_metadata.num_decodes],
                ).unsqueeze(0)
        else:
            core_attn_out_decode = None

        # 2.3: Process the remaining part
        if attn_metadata.num_prefills > 0:
            prefill_query_start_loc = attn_metadata.prefill_query_start_loc
            prefill_state_indices = attn_metadata.prefill_state_indices
            prefill_has_initial_state = attn_metadata.prefill_has_initial_state
            assert prefill_query_start_loc is not None
            assert prefill_state_indices is not None
            assert prefill_has_initial_state is not None
            assert g_non_spec is not None
            assert beta_non_spec is not None
            if split_non_spec:
                query_non_spec = query_non_spec[:, num_decode_tokens:]
                key_non_spec = key_non_spec[:, num_decode_tokens:]
                value_non_spec = value_non_spec[:, num_decode_tokens:]
                g_non_spec = g_non_spec[:, num_decode_tokens:]
                beta_non_spec = beta_non_spec[:, num_decode_tokens:]

            initial_state = ssm_state[prefill_state_indices].transpose(-1, -2).contiguous()
            clear_ssm_states(initial_state, prefill_has_initial_state)
            (core_attn_out_non_spec, last_recurrent_state) = _chunk_gdr_pytorch_shim(
                q=query_non_spec,
                k=key_non_spec,
                v=value_non_spec,
                g=g_non_spec,
                beta=beta_non_spec,
                initial_state=initial_state,
                output_final_state=True,
                cu_seqlens=prefill_query_start_loc,
                prebuilt_meta=attn_metadata.non_spec_prefill_metadata.chunk,
                head_first=False,
                use_qk_l2norm_in_kernel=True,
            )
            ssm_state[prefill_state_indices] = last_recurrent_state.transpose(-1, -2).contiguous().to(ssm_state.dtype)
            if split_non_spec:
                core_attn_out_non_spec = torch.cat(
                    [core_attn_out_decode, core_attn_out_non_spec],
                    dim=1,
                )
        elif attn_metadata.num_decodes > 0:
            # TRITON fused recurrent decode: single kernel handles l2norm +
            # gating + delta-rule recurrence + state update.  Replaces ~12
            # PyTorch ops (l2norm_fwd×2 + _recurrent_gdr_pytorch_vec) with 1
            # fused triton kernel — major single-request throughput win.
            try:
                core_attn_out_non_spec, _ = _triton_fused_recurrent_gdr(
                    q=query_non_spec,
                    k=key_non_spec,
                    v=value_non_spec,
                    g=g_non_spec if g_non_spec is not None else None,
                    beta=beta_non_spec if beta_non_spec is not None else None,
                    scale=key_non_spec.shape[-1] ** -0.5,
                    initial_state=ssm_state,
                    inplace_final_state=True,
                    ssm_state_indices=non_spec_state_indices_tensor,
                    use_qk_l2norm_in_kernel=True,
                )
            except Exception:
                # Fallback to PyTorch path if triton kernel fails at runtime
                actual_seq_lengths = attn_metadata.non_spec_decode_metadata.actual_seq_lengths
                query_non_spec_fb = l2norm_fwd(query_non_spec)
                key_non_spec_fb = l2norm_fwd(key_non_spec)
                core_attn_out_non_spec = _recurrent_gdr_pytorch(
                    query=query_non_spec_fb.squeeze(0),
                    key=key_non_spec_fb.squeeze(0),
                    value=value_non_spec.squeeze(0),
                    g=g_non_spec.squeeze(0) if g_non_spec is not None else g_non_spec,
                    beta=beta_non_spec.squeeze(0) if beta_non_spec is not None else beta_non_spec,
                    state=ssm_state,
                    scale=key_non_spec_fb.shape[-1] ** -0.5,
                    actual_seq_lengths=actual_seq_lengths,
                    ssm_state_indices=non_spec_state_indices_tensor,
                ).unsqueeze(0)
        else:
            core_attn_out_non_spec, last_recurrent_state = None, None

        # 3. Merge core attention output
        if spec_sequence_masks is not None and core_attn_out_non_spec is not None:
            merged_out = torch.empty(
                (1, num_actual_tokens, *core_attn_out_spec.shape[2:]),
                dtype=core_attn_out_non_spec.dtype,
                device=core_attn_out_non_spec.device,
            )
            merged_out.index_copy_(1, spec_token_indx, core_attn_out_spec)
            merged_out.index_copy_(1, non_spec_token_indx, core_attn_out_non_spec)
            core_attn_out[:num_actual_tokens] = merged_out.squeeze(0)
        elif spec_sequence_masks is not None:
            core_attn_out[:num_actual_tokens] = core_attn_out_spec.squeeze(0)
        else:
            core_attn_out[:num_actual_tokens] = core_attn_out_non_spec.squeeze(0)
