#!/usr/bin/env python3
"""
MinerU PDF to Markdown Converter (v4 API)

Usage:
    python3 convert.py <pdf_path> [--api-key KEY]

API Base URL: https://mineru.net/api/v4
"""

import argparse
import os
import sys
import time
import json
import zipfile
import io
import requests
from pathlib import Path

# CORRECT API base URL (v4 standard API)
API_BASE_URL = "https://mineru.net/api/v4"


def get_api_key(api_key: str = None) -> str:
    """Get API key from args, environment, or config file."""
    if api_key:
        return api_key

    # Check environment variable
    api_key = os.environ.get("MINERU_API_KEY")
    if api_key:
        return api_key

    # Check config file (~/.mineru/config)
    config_path = Path("~/.mineru/config").expanduser()
    if config_path.exists():
        with open(config_path) as f:
            for line in f:
                if line.startswith("MINERU_API_KEY="):
                    return line.split("=", 1)[1].strip()

    print("Error: No API key provided.")
    print("Set MINERU_API_KEY env var, use --api-key, or create ~/.mineru/config")
    sys.exit(1)


def submit_task_url(api_key: str, pdf_url: str, model_version: str = "vlm",
                    language: str = "ch", enable_table: bool = True,
                    enable_formula: bool = True, page_range: str = None) -> dict:
    """Submit a parse task via remote URL (MinerU downloads the file).

    Returns dict with task_id and file_url (signed upload URL, if needed).
    """
    url = f"{API_BASE_URL}/extract/task"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "url": pdf_url,
        "model_version": model_version,
        "language": language,
        "enable_table": enable_table,
        "enable_formula": enable_formula,
        "is_ocr": False,
    }
    if page_range:
        payload["page_range"] = page_range

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    result = resp.json()

    if result.get("code") != 0:
        print(f"Submission failed: {result}")
        sys.exit(1)

    return result.get("data", {})


def upload_file_to_oss(api_key: str, file_url: str, file_path: str) -> None:
    """PUT a local file to the signed OSS upload URL."""
    with open(file_path, "rb") as f:
        data = f.read()

    # The signed URL may require specific headers
    resp = requests.put(file_url, data=data, timeout=120)
    if resp.status_code not in (200, 201):
        print(f"Upload to OSS failed (HTTP {resp.status_code}): {resp.text}")
        sys.exit(1)
    print(f"File uploaded to OSS successfully.")


def submit_task_file(api_key: str, file_path: str, model_version: str = "vlm",
                     language: str = "ch", enable_table: bool = True,
                     enable_formula: bool = True, page_range: str = None) -> dict:
    """Submit a parse task via local file (2-step: get URL, then PUT)."""
    file_name = Path(file_path).name

    # Step 1: get signed upload URL
    url = f"{API_BASE_URL}/file-urls/batch"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "file_name": file_name,
        "language": language,
        "enable_table": enable_table,
        "enable_formula": enable_formula,
        "is_ocr": False,
        "model_version": model_version,
    }
    if page_range:
        payload["page_range"] = page_range

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    result = resp.json()

    if result.get("code") != 0:
        print(f"Failed to get upload URL: {result}")
        sys.exit(1)

    data = result.get("data", [{}])[0]
    task_id = data.get("task_id")
    file_url = data.get("file_url")

    if not file_url:
        print(f"No file_url in response: {result}")
        sys.exit(1)

    # Step 2: PUT file to OSS
    print(f"Uploading {file_name} to OSS...")
    upload_file_to_oss(api_key, file_url, file_path)

    return {"task_id": task_id}


def poll_result(api_key: str, task_id: str, timeout: int = 300,
                interval: int = 3) -> dict:
    """Poll task status until done/failed/timeout."""
    url = f"{API_BASE_URL}/extract/task/{task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    state_labels = {
        "uploading": "Downloading file",
        "pending": "Queued",
        "running": "Extracting",
        "waiting-file": "Waiting for file upload",
    }

    start = time.time()
    while time.time() - start < timeout:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        data = result.get("data", {})
        state = data.get("state", "unknown")

        if state == "done":
            markdown_url = data.get("markdown_url")
            print(f"[{int(time.time()-start)}s] Done! Markdown URL: {markdown_url}")
            return data

        elif state == "failed":
            err_msg = data.get("err_msg", "Unknown error")
            err_code = data.get("err_code", "?")
            print(f"[{int(time.time()-start)}s] Failed (code {err_code}): {err_msg}")
            sys.exit(1)

        else:
            label = state_labels.get(state, state)
            elapsed = int(time.time() - start)
            progress = data.get("extract_progress", {})
            extracted = progress.get("extracted_pages", "?")
            total = progress.get("total_pages", "?")
            print(f"[{elapsed}s] {label}... (pages: {extracted}/{total})")

        time.sleep(interval)

    print(f"Timeout after {timeout}s. Task ID: {task_id}")
    sys.exit(1)


def download_markdown(url: str, output_path: str) -> str:
    """Download the markdown file from CDN URL and save to output_path."""
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    content = resp.text

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return content


def convert_pdf(pdf_path: str, api_key: str = None, model_version: str = "vlm",
                language: str = "ch", page_range: str = None) -> str:
    """Convert a local PDF to Markdown. Returns path to the .md file."""
    api_key = get_api_key(api_key)
    pdf_path = Path(pdf_path).resolve()

    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)

    # Output .md alongside the PDF
    md_path = pdf_path.with_suffix(".md")

    # Check if already converted
    if md_path.exists():
        print(f"Already exists: {md_path} (skipping)")
        return str(md_path)

    print(f"Converting: {pdf_path}")
    print(f"Model: {model_version}, Language: {language}")

    # Use file upload mode (2-step: get URL + PUT)
    task_data = submit_task_file(
        api_key, str(pdf_path),
        model_version=model_version,
        language=language,
        page_range=page_range
    )
    task_id = task_data.get("task_id")
    print(f"Task ID: {task_id}")

    # Poll for result
    print("Processing (this may take a few minutes)...")
    result = poll_result(api_key, task_id)

    # Download markdown
    markdown_url = result.get("markdown_url")
    if not markdown_url:
        print(f"No markdown_url in result: {result}")
        sys.exit(1)

    print(f"Downloading markdown...")
    download_markdown(markdown_url, str(md_path))

    print(f"\n✓ Done! Saved: {md_path}")
    return str(md_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert PDF to Markdown using MinerU v4 API")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("--api-key", help="MinerU API key")
    parser.add_argument("--model", default="vlm",
                        help="Model version: pipeline, vlm (default), MinerU-HTML")
    parser.add_argument("--lang", default="ch",
                        help="Language: ch (default), en, ch_server, ...")
    parser.add_argument("--page-range",
                        help="Page range, e.g. '1-10' or '5'")

    args = parser.parse_args()
    convert_pdf(
        args.pdf_path,
        api_key=args.api_key,
        model_version=args.model,
        language=args.lang,
        page_range=args.page_range,
    )
