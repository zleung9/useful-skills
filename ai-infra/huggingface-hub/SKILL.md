---
name: huggingface-hub
description: "HuggingFace hf CLI: search/download/upload models, datasets."
version: 1.0.0
author: Hugging Face
license: MIT
tags: [huggingface, hf, models, datasets, hub, mlops]
platforms: [linux, macos, windows]
---

# Hugging Face CLI (`hf`) Reference Guide

The `hf` command is the modern command-line interface for interacting with the Hugging Face Hub, providing tools to manage repositories, models, datasets, and Spaces.

> **IMPORTANT:** The `hf` command replaces the now deprecated `huggingface-cli` command.

## Quick Start
*   **Installation:** `curl -LsSf https://hf.co/cli/install.sh | bash -s`
*   **Help:** Use `hf --help` to view all available functions and real-world examples.
*   **Authentication:** Recommended via `HF_TOKEN` environment variable or the `--token` flag.

---

## Core Commands

### General Operations
*   `hf download REPO_ID`: Download files from the Hub.
*   `hf upload REPO_ID`: Upload files/folders (recommended for single-commit).
*   `hf upload-large-folder REPO_ID LOCAL_PATH`: Recommended for resumable uploads of large directories.
*   `hf sync`: Sync files between a local directory and a bucket.
*   `hf env` / `hf version`: View environment and version details.

### Authentication (`hf auth`)
*   `login` / `logout`: Manage sessions using tokens from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
*   `list` / `switch`: Manage and toggle between multiple stored access tokens.
*   `whoami`: Identify the currently logged-in account.

### Repository Management (`hf repos`)
*   `create` / `delete`: Create or permanently remove repositories.
*   `duplicate`: Clone a model, dataset, or Space to a new ID.
*   `move`: Transfer a repository between namespaces.
*   `branch` / `tag`: Manage Git-like references.
*   `delete-files`: Remove specific files using patterns.

---

## Specialized Hub Interactions

### Datasets & Models
*   **Datasets:** `hf datasets list`, `info`, and `parquet` (list parquet URLs).
*   **SQL Queries:** `hf datasets sql SQL` — Execute raw SQL via DuckDB against dataset parquet URLs.
*   **Models:** `hf models list` and `info`.
*   **Papers:** `hf papers list` — View daily papers.

### Discussions & Pull Requests (`hf discussions`)
*   Manage the lifecycle of Hub contributions: `list`, `create`, `info`, `comment`, `close`, `reopen`, and `rename`.
*   `diff`: View changes in a PR.
*   `merge`: Finalize pull requests.

### Infrastructure & Compute
*   **Endpoints:** Deploy and manage Inference Endpoints (`deploy`, `pause`, `resume`, `scale-to-zero`, `catalog`).
*   **Jobs:** Run compute tasks on HF infrastructure. Includes `hf jobs uv` for running Python scripts with inline dependencies and `stats` for resource monitoring.
*   **Spaces:** Manage interactive apps. Includes `dev-mode` and `hot-reload` for Python files without full restarts.

### Storage & Automation
*   **Buckets:** Full S3-like bucket management (`create`, `cp`, `mv`, `rm`, `sync`).
*   **Cache:** Manage local storage with `list`, `prune` (remove detached revisions), and `verify` (checksum checks).
*   **Webhooks:** Automate workflows by managing Hub webhooks (`create`, `watch`, `enable`/`disable`).
*   **Collections:** Organize Hub items into collections (`add-item`, `update`, `list`).

---

## Downloading Large Datasets — Practical Patterns

### File path resolution
HuggingFace file paths inside a repo use **forward slashes** and include subdirectories.
**WRONG:** `https://huggingface.co/datasets/OWNER/REPO/resolve/main/MD_snapshot_JSON_PVNL.tar.gz`
**RIGHT:** `https://huggingface.co/datasets/OWNER/REPO/resolve/main/MD_snapshot_JSON/PVNL.tar.gz`
Always run `list_repo_files()` first to get exact paths — never guess.

### Bulk download with resume (curl-based)
For datasets with many large files where `hf download` is too slow or lacks fine-grained resume:
```bash
BASE="https://huggingface.co/datasets/OWNER/REPO/resolve/main/SUBDIR"
PROXY="http://127.0.0.1:7890"
for f in PA6.tar.gz PA66.tar.gz PC.tar.gz; do
    curl -L -C - -o "$DEST/$f" "$BASE/$f" --proxy "$PROXY" --max-time 1200 --retry 3
done
```
Key flags: `-C -` for resume, `-L` for redirect follow, `--retry 3` for transient failures.

### Integrity verification
After downloading `.tar.gz` files, verify with `gzip -t file.tar.gz`. Small file size compared to siblings is a strong corruption signal — list files sorted by size to spot outliers.

### Parquet datasets
Many HF datasets (e.g., ColabFit) store data as sharded parquet (`co_0.parquet`, `co_1.parquet`, …) + `ds.parquet` metadata. Download with:
```bash
hf download OWNER/REPO --repo-type dataset --local-dir ./DEST
```
This auto-handles sharded structures.

### hf download timeout
`hf download` can be slow on large datasets (>30 GB). Run in background with `terminal(background=True, notify_on_complete=True)`. If interrupted, re-running `hf download` with the same `--local-dir` resumes automatically.

### Pitfalls
- `huggingface-cli` is deprecated — use `hf` instead.
- `list_repo_files()` returns a generator, not a list — wrap with `list()` before checking `len()`.
- Proxy: use `https_proxy=http://127.0.0.1:7890` env var or `--proxy` flag. Some datasets require it from China/restricted networks.
- Some datasets have train/val/test as separate repos (e.g., `OPoly26-train`, `OPoly26-val`), not branches.

---

## Advanced Usage & Tips

### Global Flags
*   `--format json`: Produces machine-readable output for automation.
*   `-q` / `--quiet`: Limits output to IDs only.

### Extensions & Skills
*   **Extensions:** Extend CLI functionality via GitHub repositories using `hf extensions install REPO_ID`.
*   **Skills:** Manage AI assistant skills with `hf skills add`.
