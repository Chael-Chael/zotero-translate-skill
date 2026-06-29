#!/usr/bin/env python3
"""Attach rendered Zotero Translate PDFs through the local Zotero bridge."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


BRIDGE_BASE_URL = "http://127.0.0.1:23119/zotero-translate-bridge"
BRIDGE_TOKEN_HEADER = "X-Zotero-Translate-Bridge-Token"


def configure_stdio() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def default_bridge_config_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".runtime" / "zotero-translate-bridge" / "bridge_config.json"


def post_json(base_url: str, path: str, token: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/{path.lstrip('/')}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            BRIDGE_TOKEN_HEADER: token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            data = json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {"ok": False, "error": body}
        data.setdefault("ok", False)
        data["httpStatus"] = exc.code
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        data = {"ok": False, "error": str(exc)}
    if not data.get("ok"):
        raise RuntimeError(f"Bridge request failed for {path}: {data.get('error') or data}")
    return data


def load_bridge_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Bridge config not found. Run ensure_zotero_bridge.py --install first: {path}")
    config = read_json(path)
    if not config.get("token"):
        raise RuntimeError(f"Bridge config has no token: {path}")
    return config


def resolve_manifest(args: argparse.Namespace) -> tuple[Path, dict]:
    if args.manifest:
        manifest_path = Path(args.manifest).expanduser().resolve()
    elif args.run_dir:
        manifest_path = Path(args.run_dir).expanduser().resolve() / "run_manifest.json"
    else:
        raise ValueError("--run-dir or --manifest is required.")
    if not manifest_path.exists():
        raise FileNotFoundError(f"Run manifest not found: {manifest_path}")
    return manifest_path, read_json(manifest_path)


def final_pdfs(args: argparse.Namespace, manifest: dict) -> list[Path]:
    raw_paths = args.pdf or manifest.get("finalPdfs") or []
    paths = [Path(value).expanduser().resolve() for value in raw_paths]
    if not paths:
        raise RuntimeError("No final PDFs were found. Run render first or pass --pdf.")
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Final PDF does not exist: {path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Final output is not a PDF: {path}")
    return paths


def parent_payload(args: argparse.Namespace, manifest: dict) -> dict:
    parent_item_id = args.parent_item_id or manifest.get("zoteroParentItemID") or manifest.get("parentItemID")
    parent_key = args.parent_key or manifest.get("zoteroParentKey") or manifest.get("parentKey")
    library_id = args.library_id or manifest.get("zoteroLibraryID") or manifest.get("libraryID")
    if parent_item_id:
        return {"parentItemID": int(parent_item_id)}
    if parent_key and library_id:
        return {"parentKey": str(parent_key), "libraryID": int(library_id)}
    raise ValueError("Pass --parent-item-id, or pass both --parent-key and --library-id.")


def title_for_pdf(args: argparse.Namespace, pdf_path: Path, manifest: dict) -> str:
    if args.title:
        if len(args.pdf or []) > 1:
            return f"{args.title} - {pdf_path.name}"
        return args.title
    prefix = args.title_prefix
    source = Path(str(manifest.get("inputPdf") or "")).stem
    if source:
        return f"{prefix}: {source} - {pdf_path.name}"
    return f"{prefix}: {pdf_path.name}"


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Attach rendered PDFs through the Zotero Translate bridge.")
    parser.add_argument("--run-dir")
    parser.add_argument("--manifest")
    parser.add_argument("--pdf", action="append", help="Attach a specific PDF. Can be repeated.")
    parser.add_argument("--parent-item-id")
    parser.add_argument("--parent-key")
    parser.add_argument("--library-id")
    parser.add_argument("--bridge-config")
    parser.add_argument("--bridge-url")
    parser.add_argument("--token")
    parser.add_argument("--title")
    parser.add_argument("--title-prefix", default="Zotero Translate")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = make_parser().parse_args()
    manifest_path, manifest = resolve_manifest(args)
    pdfs = final_pdfs(args, manifest)
    parent = parent_payload(args, manifest)
    config_path = Path(args.bridge_config).expanduser().resolve() if args.bridge_config else default_bridge_config_path().resolve()
    config = load_bridge_config(config_path)
    base_url = args.bridge_url or config.get("bridgeUrl") or BRIDGE_BASE_URL
    token = args.token or config["token"]

    planned = [
        {
            **parent,
            "filePath": str(pdf_path),
            "title": title_for_pdf(args, pdf_path, manifest),
        }
        for pdf_path in pdfs
    ]

    if args.dry_run:
        print(json.dumps({
            "status": "dry-run",
            "manifestPath": str(manifest_path),
            "bridgeUrl": base_url,
            "attachments": planned,
        }, ensure_ascii=False, indent=2))
        return 0

    post_json(base_url, "health", token, {}, args.timeout)
    attached = [post_json(base_url, "attach", token, payload, args.timeout)["attached"] for payload in planned]
    verification = post_json(base_url, "verify", token, parent, args.timeout)
    verified_ids = {item.get("id") for item in verification.get("attachments", [])}
    missing = [item for item in attached if item.get("id") not in verified_ids]
    if missing:
        raise RuntimeError(f"Bridge attached files but verification did not find them: {missing}")

    manifest["status"] = "attached"
    manifest["phase"] = "cleanup"
    manifest["updatedAt"] = utc_now()
    manifest["attachedAt"] = utc_now()
    manifest["attached"] = attached
    manifest["attachmentVerification"] = verification
    manifest["attachmentBridge"] = {
        "bridgeUrl": base_url,
        "configPath": str(config_path),
    }
    write_json(manifest_path, manifest)

    print(json.dumps({
        "status": "attached",
        "manifestPath": str(manifest_path),
        "attached": attached,
        "verifiedAttachmentCount": len(verification.get("attachments", [])),
        "nextStep": "Run cleanup_artifacts.py --confirm-attached unless artifacts should be kept.",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
