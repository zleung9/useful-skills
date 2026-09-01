---
name: ascend-npu-llm-deploy
description: "Deploy LLM models on Huawei Ascend NPU with OpenAI-compatible FastAPI server"
version: 1.0.0
author: zliang
license: MIT
platforms: [linux]
metadata:
  tags: [llm, deployment, ascend, npu, fastapi, openai-compatible, huawei]
  category: deployment
  related_skills: [huawei-model-usage, llm-wiki]
---

# Deploy LLM on Ascend NPU

Comprehensive guide for deploying large language models on Huawei Ascend NPU
hardware as OpenAI-compatible API servers using torch_npu + transformers + FastAPI.

## When This Skill Activates

Use this skill when the user:
- Wants to deploy an LLM on Ascend NPU hardware
- Asks about serving a model with torch_npu
- Needs an OpenAI-compatible API on Huawei AI hardware
- Mentions "Ascend", "NPU", "torch_npu", "CANN" in a deployment context
- Wants to set up LLM inference on qwen6 or similar Huawei servers
- Asks about running Qwen, LLaMA, or other models on Ascend NPUs

## Critical Constraints (READ FIRST)

These are hard-won lessons from actual deployments. Violating them causes
silent failures, crashes, or irreparable environment breakage.

### 1. torch + torch_npu Version Locking

**MUST** use matching versions of torch and torch_npu. For example:
- torch 2.12.0+cu130 → torch_npu 2.12.0
- Do NOT upgrade torch independently — it breaks torch_npu
- Check with: `python3 -c "import torch; print(torch.__version__); import torch_npu; print(torch_npu.__version__)"`

### 2. NEVER Install torchvision

torchvision is **incompatible** with torch+torch_npu on Ascend NPU. Installing
it will break the torch/torch_npu compatibility and require a full reinstall.

- For multimodal models (Qwen3.5-VL, etc.), use `AutoTokenizer` directly
- Do NOT use `AutoProcessor` — it pulls in torchvision/PIL dependencies
- If text-only serving of a multimodal model, just use the tokenizer

### 3. bitsandbytes Quantization Does NOT Work on Ascend NPU

4-bit quantization via bitsandbytes fails at the ACL (Ascend Computing Language)
runtime level. The errors are:
```
Error: Bnb4bitQuantize on tensors destined for model.visual.merger.linear_fc2.weight
AclSetCompileopt error code 500001
```
Even with `llm_int8_enable_fp32_cpu_offload=True`, it still fails. This is a
fundamental incompatibility, not a configuration issue.

**Alternatives for reducing VRAM:**
- Use `device_map="auto"` with CPU offloading (slower but works)
- Use GPTQ/AWQ quantized model weights (pre-quantized, not bitsandbytes)
- Use smaller models or model distillation
- Wait for vLLM-ascend support (requires CANN 9.0.0+)

### 4. vLLM-ascend Requires CANN 9.0.0+

Current Ascend deployments typically run CANN 8.x. vLLM-ascend requires
CANN 9.0.0+, which may not be available on all nodes. Check:
```bash
cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg
```
If CANN < 9.0.0, use the manual FastAPI server approach in this skill.

### 5. CANN Environment Scripts Use Unset Variables

When writing shell scripts that source CANN environment:
```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
source /usr/local/Ascend/nnal/atb/set_env.sh
```
**Do NOT use `set -euo pipefail`** — the CANN scripts reference unset variables
(LD_LIBRARY_PATH, PYTHONPATH, CMAKE_PREFIX_PATH, ZSH_VERSION) which triggers
`set -u` and causes the script to fail.

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│                  Client                         │
│   (OpenAI SDK, curl, any HTTP client)           │
└────────────────┬────────────────────────────────┘
                 │ HTTP
┌────────────────▼────────────────────────────────┐
│              FastAPI Server                      │
│   /v1/chat/completions                          │
│   /v1/completions                               │
│   /v1/models                                    │
│   /health                                       │
├─────────────────────────────────────────────────┤
│            transformers Model                    │
│   AutoModelForCausalLM / AutoModelForImageTextToText │
│   device_map="auto" + max_memory                │
├──────────┬──────────┬───────────────────────────┤
│  NPU 0   │  NPU 1   │         CPU               │
│ (layers  │ (layers  │  (overflow layers +        │
│  0-N)    │  N-M)    │   lm_head + norm)          │
└──────────┴──────────┴───────────────────────────┘
```

## Step-by-Step Deployment

### Step 1: Check Hardware & Environment

```bash
# SSH into the target node
ssh <node>

# Check NPU devices
python3 -c "
import torch, torch_npu
print(f'torch: {torch.__version__}')
print(f'torch_npu: {torch_npu.__version__}')
print(f'NPUs: {torch.npu.device_count()}')
for i in range(torch.npu.device_count()):
    free, total = torch.npu.mem_get_info(i)
    print(f'  NPU {i}: {free/1024**3:.1f}GB free / {total/1024**3:.1f}GB total')
"

# Check CANN version
cat /usr/local/Ascend/ascend-toolkit/latest/version.cfg

# Check transformers version
python3 -c "import transformers; print(transformers.__version__)"
```

### Step 2: Prepare Model Weights

Copy model weights to the target node. Models are typically stored on shared
storage (e.g., HPC cluster) and need to be copied locally:

```bash
# Example: copy from HPC shared storage
mkdir -p ~/models/<model-name>
scp -r hpc:/path/to/model/* ~/models/<model-name>/

# Verify model files
ls ~/models/<model-name>/config.json
ls ~/models/<model-name>/model*.safetensors
```

**Model size estimation:**
- Count `.safetensors` files and check total size: `du -sh ~/models/<model-name>/`
- bfloat16 model: ~2 bytes per parameter
  - 7B model → ~14GB
  - 35B MoE model → ~67GB
  - 72B model → ~144GB
- If model size > total NPU VRAM, CPU offloading will be required

### Step 3: Identify the Correct Auto Class

Check the model's `config.json` to determine the right loading class:

```bash
python3 -c "
import json
with open('~/models/<model-name>/config.json') as f:
    cfg = json.load(f)
print('architectures:', cfg.get('architectures'))
print('model_type:', cfg.get('model_type'))
print('has vision_config:', 'vision_config' in cfg)
"
```

| If `vision_config` in config | Use this Auto class |
|------------------------------|---------------------|
| Yes (multimodal) | `AutoModelForImageTextToText` |
| No (text-only) | `AutoModelForCausalLM` |

**Important:** Always use `AutoTokenizer` (NOT `AutoProcessor`) to avoid
torchvision dependency.

### Step 4: Write the Server Script

Create `llm_server.py` using the template below. Key design decisions:

1. **`dtype` parameter** (not `torch_dtype` — deprecated in transformers 5.x)
2. **`device_map="auto"`** with `max_memory` for multi-NPU + CPU offloading
3. **`trust_remote_code=True`** for custom model architectures
4. **FastAPI** for the OpenAI-compatible API layer

```python
#!/usr/bin/env python3
"""
OpenAI-compatible LLM serving API for models on Ascend NPU.
Uses torch_npu + transformers + FastAPI.
"""

import os, time, json, uuid, logging
from typing import Optional, List, Union

import torch
import torch_npu  # registers NPU backend
from transformers import (
    AutoModelForCausalLM,
    AutoModelForImageTextToText,
    AutoTokenizer,
)
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
MODEL_PATH = os.environ.get("MODEL_PATH", "/home/<user>/models/<model-name>")
DTYPE = os.environ.get("DTYPE", "bfloat16")
MAX_MODEL_LEN = int(os.environ.get("MAX_MODEL_LEN", "4096"))
API_KEY = os.environ.get("API_KEY", "")  # empty = no auth
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8001"))  # Check for port conflicts!

# ── Load model ──────────────────────────────────────────────────────────────
logger.info(f"Loading model from {MODEL_PATH} ...")

DTYPE_MAP = {
    "bfloat16": torch.bfloat16,
    "float16": torch.float16,
    "float32": torch.float32,
}
torch_dtype = DTYPE_MAP.get(DTYPE, torch.bfloat16)

# Detect model type from config
is_multimodal = False
try:
    with open(os.path.join(MODEL_PATH, "config.json"), "r") as f:
        model_config = json.load(f)
    is_multimodal = "vision_config" in model_config
    model_arch = model_config.get("architectures", ["unknown"])[0]
    model_type = model_config.get("model_type", "unknown")
    logger.info(f"Model type: {model_type}, architecture: {model_arch}, multimodal={is_multimodal}")
except Exception as e:
    logger.warning(f"Could not read config.json: {e}")

# Load tokenizer
logger.info("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
logger.info("Tokenizer loaded successfully")

# Check NPU memory
npu_count = torch.npu.device_count()
logger.info(f"Available NPUs: {npu_count}")
for i in range(npu_count):
    free, total = torch.npu.mem_get_info(i)
    logger.info(f"  NPU {i}: {free/1024**3:.1f}GB free / {total/1024**3:.1f}GB total")

# Build max_memory for device_map="auto"
def build_max_memory(reserve_gb=1):
    """Build max_memory dict for device_map='auto' with CPU offloading."""
    max_memory = {}
    for i in range(npu_count):
        free_gb = torch.npu.mem_get_info(i)[0] // 1024**3
        max_memory[i] = f"{max(free_gb - reserve_gb, 1)}GB"
    max_memory["cpu"] = "256GiB"
    logger.info(f"Device map max_memory: {max_memory}")
    return max_memory

# Load the model
load_kwargs = {
    "dtype": torch_dtype,          # NOT torch_dtype (deprecated in transformers 5.x)
    "device_map": "auto",
    "trust_remote_code": True,
    "max_memory": build_max_memory(),
}

if is_multimodal:
    logger.info("Loading multimodal model with AutoModelForImageTextToText...")
    model = AutoModelForImageTextToText.from_pretrained(MODEL_PATH, **load_kwargs)
else:
    logger.info("Loading text-only model with AutoModelForCausalLM...")
    model = AutoModelForCausalLM.from_pretrained(MODEL_PATH, **load_kwargs)

model.eval()
logger.info(f"Model loaded: {type(model).__name__}")
logger.info(f"Device map: {model.hf_device_map if hasattr(model, 'hf_device_map') else 'N/A'}")

# ── FastAPI app ─────────────────────────────────────────────────────────────
app = FastAPI(title="LLM Server", version="1.0.0")

async def verify_api_key(auth_header: Optional[str] = Header(None, alias="Authorization")):
    if not API_KEY:
        return True
    if auth_header and auth_header.startswith("Bearer "):
        if auth_header[7:] == API_KEY:
            return True
    raise HTTPException(status_code=401, detail="Invalid API key")

# ── Request/Response schemas ────────────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: Union[str, list]

class ChatCompletionRequest(BaseModel):
    model: str = "default"
    messages: List[Message]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    max_tokens: int = Field(default=2048, ge=1, le=8192)
    stream: bool = False
    stop: Optional[Union[str, List[str]]] = None

class CompletionRequest(BaseModel):
    model: str = "default"
    prompt: Union[str, List[str]]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    max_tokens: int = Field(default=2048, ge=1, le=8192)
    stream: bool = False
    stop: Optional[Union[str, List[str]]] = None

class ChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str

class Choice(BaseModel):
    index: int
    message: ChoiceMessage
    finish_reason: str

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Usage

class TextChoice(BaseModel):
    index: int
    text: str
    finish_reason: str

class CompletionResponse(BaseModel):
    id: str
    object: str = "text_completion"
    created: int
    model: str
    choices: List[TextChoice]
    usage: Usage

# ── Generate helper ─────────────────────────────────────────────────────────

@torch.no_grad()
def generate_text(prompt: str, max_new_tokens: int, temperature: float,
                  top_p: float, stop_strings=None):
    """Generate text from a prompt string."""
    inputs = tokenizer(prompt, return_tensors="pt")
    first_device = next(model.parameters()).device
    inputs = {k: v.to(first_device) for k, v in inputs.items()}
    input_len = inputs["input_ids"].shape[1]

    gen_kwargs = {
        "max_new_tokens": max_new_tokens,
        "temperature": temperature if temperature > 0 else 1.0,
        "top_p": top_p,
        "do_sample": temperature > 0,
    }

    if stop_strings:
        try:
            gen_kwargs["stop_strings"] = stop_strings if isinstance(stop_strings, list) else [stop_strings]
            gen_kwargs["tokenizer"] = tokenizer
        except Exception:
            pass

    outputs = model.generate(**inputs, **gen_kwargs)
    generated_ids = outputs[0][input_len:]
    generated_text = tokenizer.decode(generated_ids, skip_special_tokens=True)

    # Trim at stop strings if present
    if stop_strings:
        stops = stop_strings if isinstance(stop_strings, list) else [stop_strings]
        for stop in stops:
            idx = generated_text.find(stop)
            if idx != -1:
                generated_text = generated_text[:idx]

    return generated_text, input_len, len(generated_ids)


def format_chat_prompt(messages: List[Message]) -> str:
    """Format chat messages using the tokenizer's chat template."""
    msgs = [{"role": m.role, "content": m.content} for m in messages]
    try:
        prompt = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    except Exception:
        # Fallback for models without chat template
        prompt = ""
        for m in messages:
            prompt += f"<|im_start|>{m.role}\n{m.content}<|im_end|>\n"
        prompt += "<|im_start|>assistant\n"
    return prompt

# ── API endpoints ───────────────────────────────────────────────────────────

@app.get("/v1/models")
async def list_models():
    return {"object": "list", "data": [{"id": "default", "object": "model",
            "created": int(time.time()), "owned_by": "local"}]}

@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_PATH,
            "model_type": type(model).__name__,
            "npu_count": npu_count,
            "device_map": str(model.hf_device_map) if hasattr(model, 'hf_device_map') else "N/A"}

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, auth=Header(None, alias="Authorization")):
    await verify_api_key(auth)
    prompt = format_chat_prompt(request.messages)
    generated_text, prompt_tokens, completion_tokens = generate_text(
        prompt=prompt, max_new_tokens=request.max_tokens,
        temperature=request.temperature, top_p=request.top_p,
        stop_strings=request.stop)
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
        created=int(time.time()), model=request.model,
        choices=[Choice(index=0, message=ChoiceMessage(content=generated_text),
                        finish_reason="stop")],
        usage=Usage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens))

@app.post("/v1/completions")
async def completions(request: CompletionRequest, auth=Header(None, alias="Authorization")):
    await verify_api_key(auth)
    prompt = request.prompt[0] if isinstance(request.prompt, list) else request.prompt
    generated_text, prompt_tokens, completion_tokens = generate_text(
        prompt=prompt, max_new_tokens=request.max_tokens,
        temperature=request.temperature, top_p=request.top_p,
        stop_strings=request.stop)
    return CompletionResponse(
        id=f"cmpl-{uuid.uuid4().hex[:8]}",
        created=int(time.time()), model=request.model,
        choices=[TextChoice(index=0, text=generated_text, finish_reason="stop")],
        usage=Usage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens))

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
```

### Step 5: Write the Startup Script

Create `start_server.sh`:

```bash
#!/usr/bin/env bash
# Startup script for LLM server on Ascend NPU
# NOTE: Do NOT use 'set -euo pipefail' — CANN scripts use unset variables

# Source Ascend CANN environment
source /usr/local/Ascend/ascend-toolkit/set_env.sh
source /usr/local/Ascend/nnal/atb/set_env.sh

# Add user pip to PATH
export PATH="/home/<user>/.local/bin:${PATH}"

# Configuration (override via environment variables)
MODEL_PATH="${MODEL_PATH:-/home/<user>/models/<model-name>}"
DTYPE="${DTYPE:-bfloat16}"
PORT="${PORT:-8001}"
HOST="${HOST:-0.0.0.0}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
API_KEY="${API_KEY:-}"

# Export for the Python server
export MODEL_PATH DTYPE PORT HOST MAX_MODEL_LEN API_KEY

# Kill any existing server
pkill -f "llm_server.py" 2>/dev/null || true
sleep 2

# Start the server
echo "[INFO] Starting LLM server..."
echo "[INFO]   Model: ${MODEL_PATH}"
echo "[INFO]   Port: ${HOST}:${PORT}"

nohup python3 /home/<user>/llm_server.py \
    > /home/<user>/llm_server.log 2>&1 &

SERVER_PID=$!
echo "[INFO] Server PID: ${SERVER_PID}"
echo "[INFO] Logs: /home/<user>/llm_server.log"

# Wait for server to be ready (up to 300 seconds)
echo "[INFO] Waiting for server to be ready..."
for i in $(seq 1 60); do
    if curl -s http://${HOST}:${PORT}/health > /dev/null 2>&1; then
        echo "[INFO] Server is ready! (took ~$((i*5)) seconds)"
        echo "[INFO] PID: ${SERVER_PID}"
        exit 0
    fi
    sleep 5
done

echo "[WARN] Server may still be loading. Check logs at /home/<user>/llm_server.log"
echo "[INFO] PID: ${SERVER_PID}"
```

### Step 6: Deploy and Test

```bash
# Copy scripts to target node
scp llm_server.py start_server.sh <node>:/home/<user>/

# Start the server (from your local machine)
ssh <node> "bash /home/<user>/start_server.sh"

# Or start manually for debugging:
ssh <node> "source /usr/local/Ascend/ascend-toolkit/set_env.sh; \
            source /usr/local/Ascend/nnal/atb/set_env.sh; \
            export PATH=/home/<user>/.local/bin:\$PATH; \
            PORT=8001 nohup python3 /home/<user>/llm_server.py \
            > /home/<user>/llm_server.log 2>&1 &"

# Wait for model to load (can take 30-120 seconds depending on model size)

# Test health endpoint
curl http://<node>:8001/health

# Test chat completions
curl http://<node>:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100
  }'

# Test with OpenAI Python SDK
python3 -c "
from openai import OpenAI
client = OpenAI(base_url='http://<node>:8001/v1', api_key='unused')
resp = client.chat.completions.create(
    model='default',
    messages=[{'role': 'user', 'content': 'Hello!'}],
    max_tokens=100)
print(resp.choices[0].message.content)
"
```

## Device Map Strategy

The key to multi-NPU deployment is `device_map="auto"` with `max_memory`. Here's
how it works:

### Understanding device_map="auto"

Transformers automatically distributes model layers across available devices:

1. Fills NPU 0 first (up to max_memory limit)
2. Overflows to NPU 1, NPU 2, etc.
3. Remaining layers go to CPU
4. If CPU memory is also insufficient, disk offloading (very slow)

### Tuning max_memory

```python
def build_max_memory(reserve_gb=1):
    max_memory = {}
    for i in range(npu_count):
        free_gb = torch.npu.mem_get_info(i)[0] // 1024**3
        # Reserve some VRAM for KV cache and activations
        max_memory[i] = f"{max(free_gb - reserve_gb, 1)}GB"
    # CPU memory for overflow layers
    max_memory["cpu"] = "256GiB"  # Adjust based on available RAM
    return max_memory
```

**`reserve_gb`** controls how much VRAM to leave free per NPU:
- Default: 1GB (minimal, may cause OOM during generation)
- Recommended: 2-4GB for production (leaves room for KV cache)
- Higher values = safer but more CPU offloading = slower inference

### Performance Impact of CPU Offloading

| Scenario | Typical Speed | Notes |
|----------|--------------|-------|
| Model fits entirely in NPU VRAM | 10-50 tok/s | Ideal |
| Partial CPU offloading (20% layers) | 1-5 tok/s | Manageable |
| Heavy CPU offloading (50%+ layers) | 0.1-0.5 tok/s | Functional but slow |

## Port Management

Always check for existing services before choosing a port:

```bash
# Check what's already running
ss -tlnp | grep -E '800[0-9]'

# Common port conflicts on Ascend nodes:
# - Port 8000: Often used by mineru-api or other services
# - Port 8080: Common for web dashboards
# - Port 8888: Jupyter notebooks

# Use PORT environment variable to override:
PORT=8001 bash start_server.sh
```

## Troubleshooting

### Model Loading Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `OOM during model loading` | Not enough VRAM+RAM | Increase `max_memory["cpu"]`, or use smaller model |
| `ACL error code 500001` | bitsandbytes incompatibility | Don't use 4-bit quantization on Ascend NPU |
| `torch_npu not found` | torch/torch_npu version mismatch | Reinstall matching versions |
| `NameError: name 'torch_npu'` | Missing import | Add `import torch_npu` before any torch.npu calls |
| `Can't determine auto class` | Unknown model architecture | Check config.json, use correct Auto class manually |
| `dtype vs torch_dtype warning` | transformers 5.x deprecation | Use `dtype=` parameter instead of `torch_dtype=` |

### Server Runtime Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Address already in use` | Port conflict | Change PORT, or kill existing process |
| SSH timeout during load | Model loading uses all resources | Use nohup, check logs separately |
| Very slow inference (<1 tok/s) | CPU offloading bottleneck | Need more NPUs or higher-VRAM NPUs |
| `set -u` script failure | CANN scripts use unset vars | Remove `set -euo pipefail` from startup scripts |
| 500 errors on requests | Model device mismatch | Check `model.hf_device_map`, ensure inputs go to correct device |

### Checking Server Logs

```bash
# Tail the log file
ssh <node> "tail -f /home/<user>/llm_server.log"

# Check for errors
ssh <node> "grep -i error /home/<user>/llm_server.log | tail -20"

# Check if server process is running
ssh <node> "ps aux | grep llm_server"
```

## Optimization Opportunities

### Short-term (Current Hardware)
1. **Install flash-linear-attention + causal-conv1d**: Speeds up models that use
   `linear_attention` layers (e.g., Qwen3.5 MoE). Without these, falls back to
   slower torch implementation.
2. **Increase `reserve_gb`**: Prevents OOM during generation but increases CPU
   offloading. Tune for your workload.
3. **Use pre-quantized models**: GPTQ/AWQ quantized weights are smaller and
   don't require bitsandbytes. Check if the model has a GPTQ variant.

### Medium-term (Infrastructure)
4. **More NPUs or higher-VRAM NPUs**: Ascend910B4 has 29.5GB. Ascend910B
   has 64GB. More VRAM = less CPU offloading = faster inference.
5. **Upgrade CANN to 9.0.0+**: Enables vLLM-ascend for much better throughput
   with continuous batching, PagedAttention, etc.

### Long-term
6. **vLLM-ascend**: Once CANN 9.0.0+ is available, vLLM gives production-grade
   serving with continuous batching, speculative decoding, and much higher
   throughput. **Caveat**: vLLM shards by tensor parallelism (TP), and TP must
   evenly divide certain layer dims. Models with hybrid linear-attention / GDN
   layers (e.g. Qwen3.5-35B MoE) compute a `conv_dim` that TP must divide —
   if your NPU count isn't a divisor, vLLM is structurally blocked regardless
   of CANN version. See the "Why vLLM is NOT usable" note under Reference
   Deployments for the traced example. `device_map="auto"` (this skill's
   FastAPI approach) sidesteps TP divisibility entirely.

## Reference Deployments

### Qwen3.5-35B MoE on qwen6 (3x Ascend910B4, all-VRAM) — VERIFIED 2026-08-07

- **Model**: Qwen3_5MoeForConditionalGeneration (multimodal, 256 experts, 8/token,
  hybrid linear-attention/GDN + full-attention, 40 layers)
- **Auto class**: `AutoModelForImageTextToText` (NOT `AutoModelForCausalLM`)
- **Tokenizer**: `AutoTokenizer` (NOT `AutoProcessor` — avoids the torchvision
  dependency that breaks torch/torch_npu on this stack)
- **Size**: 67GB bfloat16, entirely resident in NPU HBM (NO CPU offload)
- **Serving**: hand-rolled OpenAI-compatible FastAPI server (`llm_server.py`),
  sharding via `device_map="auto"` + `build_max_memory(reserve_gb=1)`. NOT vLLM
  — see "Why not vLLM" below.
- **Device map**: NPU0 = visual + embed_tokens + layers 0-12; NPU1 = layers 13-27;
  NPU2 = layers 28-39 + norm + rotary_emb + lm_head. HBM ~22.8/24.2/20.4GB.
- **Speed**: ~1.9 tok/s steady-state (~10× the prior 2-NPU CPU-offloaded deploy)
- **Port**: 8080 (changed 2026-08-07 from 8001; 8000 is nominally mineru-api)
- **API endpoint**: http://qwen6:8080/v1/chat/completions
- **Launcher**: `/home/liangzhu/launch_server.sh` — sources CANN 8.5.0 + nnal/atb,
  `pkill -9 -f llm_server.py` (frees leaked HBM), then
  `setsid nohup python3 llm_server.py`. Survives SSH disconnect (reparented to init).
- **Critical env**: torch 2.12.0+cu130 + torch_npu 2.12.0 (user-local, shadows
  broken system 2.4.0); transformers 5.14.1 (use `dtype=` not `torch_dtype=`);
  a no-op `torchvision` stub shadow (version `99.0.0stub`) so
  `is_torchvision_available()` returns True without the broken real package.
  **NEVER install real torchvision into user-local site-packages** — it breaks
  torch/torch_npu. **NEVER upgrade/downgrade torch.**
- **HBM-leak lesson**: a server that loads the model then fails to bind its port
  does NOT release ~22GB/NPU HBM. Always `pkill -9 -f llm_server.py` before
  relaunching. Diagnose with `/home/liangzhu/diag_npu.sh`.

### Why vLLM (vllm-ascend) is NOT usable for this model on 3 NPUs — verified 2026-08-08

A request to redeploy via vLLM + vllm-ascend was pursued to completion and is
**structurally impossible** on this hardware. Documented here so the attempt is
not repeated.

- **Install done**: CANN 9.0.1 user-local + isolated venv
  `/home/liangzhu/venvs/vllm-ascend` (torch 2.10.0 / torch_npu 2.10.0.post2 /
  vllm 0.23.0 / vllm-ascend 0.23.0rc1 / transformers 5.14.1 / torchvision 0.25.0
  with `--no-deps`). torchvision IS required in the venv for multimodal registry
  inspection (unlike the FastAPI deploy).
- **The blocker**: vLLM raises `Assertion failed, 8192 is not divisible by 3`
  during `VllmConfig` validation, before model load. The GDN (Gated Delta Net)
  linear-attention layer computes
  `conv_dim = head_k_dim * num_k_heads * 2 + head_v_dim * num_v_heads
  = 128*16*2 + 128*32 = 8192`, then calls `divide(conv_dim, tp_world_size)`.
  TP must divide 8192 → valid TP ∈ {1, 2, 4, 8}. TP=3 (our 3 NPUs) is forbidden.
  Call chain: `VllmConfig.__post_init__` → `try_verify_and_update_config` →
  `HybridAttentionMambaModelConfig.verify_and_update_config` →
  `patch_mamba_config.py` → `qwen3_5.py:get_mamba_state_shape_from_config` →
  `mamba_utils.py:gated_delta_net_state_shape` → `divide(8192, 3)`.
- **No TP alternative fits the memory**: model 67GB bf16; each 910B4 = 32GB HBM.
  TP=3 = 96GB (fits, but blocked by conv_dim). TP=2 = 64GB < 67GB (won't fit,
  wastes the 3rd NPU). TP=1 = 32GB (impossible). TP=4 needs 4 NPUs (only 3
  exist). No vllm-ascend config knob pads/aligns conv_dim.
- **The only vLLM escape** would be W8A8-quantized weights on TP=2 (~33.5GB,
  fits 64GB) — but no pre-quantized weights exist and on-the-fly quant is
  unsupported.
- **Conclusion**: stay on the hand-rolled FastAPI `llm_server.py`, which shards
  via `device_map="auto"` (not vLLM TP) and so sidesteps the conv_dim
  divisibility. Recovery from a failed vLLM attempt:
  `pkill -9 -f "vllm serve"` then `bash /home/liangzhu/launch_server.sh`.

## Related Skills

- [[huawei-model-usage]] — Query Huawei AI Platform for model usage statistics
- [[llm-wiki]] — Knowledge base for LLM research and deployment notes
