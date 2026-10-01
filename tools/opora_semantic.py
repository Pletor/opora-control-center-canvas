#!/usr/bin/env python3
"""Explicit local-model installer, offline ONNX worker, and loopback semantic API client.

`install-model` is the only command that contacts Hugging Face.  `worker`, `status`, and
`query` perform no model download; the worker runs only against an already-installed cache.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = "Xenova/multilingual-e5-small"
REVISION = "761b726dd34fb83930e26aab4e9ac3899aa1fa78"
MODEL_DIR = Path("C:/Users/Admin/.cache/opora/models/multilingual-e5-small")
MODEL_FILES = ("onnx/model_quantized.onnx", "tokenizer.json", "config.json")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def install_model(model_dir: Path) -> int:
    """Download only explicit public pinned model files; never upload source data."""
    from huggingface_hub import hf_hub_download

    model_dir = model_dir.resolve()
    allowed_root = MODEL_DIR.resolve()
    if model_dir != allowed_root:
        raise ValueError(f"Model destination is fixed to {allowed_root}.")
    model_dir.mkdir(parents=True, exist_ok=True)
    for filename in MODEL_FILES:
        hf_hub_download(REPO, filename=filename, revision=REVISION, local_dir=str(model_dir), token=False)
    files = {name: sha256(model_dir / name) for name in MODEL_FILES}
    manifest = {
        "repo": REPO,
        "revision": REVISION,
        "files": files,
        "provenance": {
            "source": f"https://huggingface.co/{REPO}/tree/{REVISION}",
            "baseModel": "intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3",
            "license": "MIT (declared by the upstream intfloat/multilingual-e5-small model card)",
            "downloadedWith": "huggingface_hub token=False",
            "runtimeNetwork": "disabled (HF_HUB_OFFLINE=1)",
        },
    }
    (model_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def _vectors(session, tokenizer, texts):
    import numpy as np

    tokenizer.enable_truncation(max_length=256)
    encoded = tokenizer.encode_batch(texts, add_special_tokens=True)
    width = max(len(item.ids) for item in encoded)
    input_ids = np.zeros((len(encoded), width), dtype=np.int64)
    attention_mask = np.zeros((len(encoded), width), dtype=np.int64)
    token_type_ids = np.zeros((len(encoded), width), dtype=np.int64)
    for row, item in enumerate(encoded):
        size = len(item.ids)
        input_ids[row, :size] = item.ids
        attention_mask[row, :size] = item.attention_mask
        token_type_ids[row, :size] = item.type_ids
    available = {item.name for item in session.get_inputs()}
    inputs = {"input_ids": input_ids, "attention_mask": attention_mask}
    if "token_type_ids" in available:
        inputs["token_type_ids"] = token_type_ids
    output = session.run(None, {name: value for name, value in inputs.items() if name in available})[0]
    if output.ndim == 3:
        mask = attention_mask[..., None].astype(np.float32)
        pooled = (output * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1, None)
    elif output.ndim == 2:
        pooled = output
    else:
        raise ValueError("Unexpected ONNX embedding output shape.")
    pooled = pooled.astype(np.float32)
    return pooled / np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None)


def worker() -> int:
    """Read local JSON once, calculate dense cosine scores, and emit numeric JSON only."""
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1"})
    try:
        payload = json.loads(sys.stdin.buffer.read(1024 * 1024 + 1))
        if not isinstance(payload, dict) or not isinstance(payload.get("query"), str) or not isinstance(payload.get("chunks"), list):
            raise ValueError("invalid worker payload")
        if len(payload["chunks"]) > 128 or any(not isinstance(text, str) or len(text.encode("utf-8")) > 6144 for text in payload["chunks"]):
            raise ValueError("worker input limit exceeded")
        model_dir = Path(payload["modelDir"])
        if not (model_dir / "manifest.json").is_file() or any(not (model_dir / name).is_file() for name in MODEL_FILES):
            raise ValueError("local model files are unavailable")
        import onnxruntime as ort
        from tokenizers import Tokenizer

        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        session = ort.InferenceSession(str(model_dir / "onnx/model_quantized.onnx"), sess_options=options,
                                      providers=["CPUExecutionProvider"])
        tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        query = _vectors(session, tokenizer, ["query: " + payload["query"]])[0]
        passages = _vectors(session, tokenizer, ["passage: " + text for text in payload["chunks"]])
        print(json.dumps({"scores": [float(score) for score in passages @ query]}, separators=(",", ":")))
        return 0
    except Exception as exc:
        print(f"semantic worker: {str(exc)[:240]}", file=sys.stderr)
        return 2


def api_call(args) -> int:
    if args.command == "status":
        params = urllib.parse.urlencode({"project": args.project, "workspace": args.workspace})
        request = urllib.request.Request(args.api.rstrip("/") + "/api/semantic-search/status?" + params)
    else:
        body = json.dumps({"project": args.project, "workspace": args.workspace, "path": args.path,
                           "query": args.query, "limit": args.limit}).encode("utf-8")
        request = urllib.request.Request(args.api.rstrip("/") + "/api/semantic-search/query", data=body,
                                         headers={"Content-Type": "application/json", "Origin": args.api.rstrip("/")}, method="POST")
    with urllib.request.urlopen(request, timeout=65) as response:
        print(json.dumps(json.loads(response.read()), indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    install = commands.add_parser("install-model", help="explicitly install the pinned public ONNX model")
    install.add_argument("--model-dir", type=Path, default=MODEL_DIR)
    commands.add_parser("worker", help=argparse.SUPPRESS)
    for name in ("status", "query"):
        command = commands.add_parser(name, help=f"call local semantic API {name}")
        command.add_argument("--api", default="http://127.0.0.1:8740")
        command.add_argument("--project", required=True)
        command.add_argument("--workspace", required=True)
        if name == "query":
            command.add_argument("--path", required=True)
            command.add_argument("--query", required=True)
            command.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    if args.command == "install-model":
        return install_model(args.model_dir)
    if args.command == "worker":
        return worker()
    return api_call(args)


if __name__ == "__main__":
    raise SystemExit(main())
