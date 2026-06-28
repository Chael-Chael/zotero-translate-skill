#!/usr/bin/env python3
"""Cross-platform Zotero Translate pdf2zh orchestration."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def configure_stdio() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_name(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", name)
    return cleaned[:80] if len(cleaned) > 80 else cleaned


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def run_json(command: list[str]) -> dict:
    completed = subprocess.run(command, check=True, text=True, encoding="utf-8", stdout=subprocess.PIPE)
    return json.loads(completed.stdout)


def command_string(args: list[str]) -> str:
    values = [str(arg) for arg in args]
    if os.name == "nt":
        return subprocess.list2cmdline(values)
    return " ".join(shlex.quote(value) for value in values)


def get_runtime(script_dir: Path, python_exe: str | None, force_runtime: bool, dry_run: bool) -> dict:
    ensure_script = script_dir / "ensure_runtime.py"
    venv_dir = script_dir.parent / ".runtime" / "venv"
    venv_python = None
    for candidate in (venv_dir / "Scripts" / "python.exe", venv_dir / "bin" / "python3", venv_dir / "bin" / "python"):
        if candidate.exists():
            venv_python = candidate
            break
    pdf2zh_exe = None
    for candidate in (venv_dir / "Scripts" / "pdf2zh.exe", venv_dir / "Scripts" / "pdf2zh", venv_dir / "bin" / "pdf2zh"):
        if candidate.exists():
            pdf2zh_exe = candidate
            break

    if dry_run and not force_runtime:
        return {
            "pythonExe": str((venv_python or Path(sys.executable)).resolve()),
            "pdf2zhExe": str(pdf2zh_exe.resolve()) if pdf2zh_exe else "pdf2zh",
        }

    command = [sys.executable, str(ensure_script)]
    if python_exe:
        command += ["--python-exe", python_exe]
    if force_runtime:
        command += ["--force"]
    return run_json(command)


def build_context(script_dir: Path, runtime_python: str, input_pdf: Path, output_path: Path, source_language: str, target_language: str) -> dict:
    command = [
        runtime_python,
        str(script_dir / "build_context_pack.py"),
        "--input-pdf",
        str(input_pdf),
        "--output-path",
        str(output_path),
        "--source-language",
        source_language,
        "--target-language",
        target_language,
        "--force",
    ]
    return run_json(command)


def invoke_pdf2zh(pdf2zh_exe: str, args: list[str], temp_dir: Path) -> None:
    temp_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TEMP"] = str(temp_dir)
    env["TMP"] = str(temp_dir)
    env["TMPDIR"] = str(temp_dir)
    completed = subprocess.run([pdf2zh_exe] + args, env=env)
    if completed.returncode != 0:
        raise RuntimeError(f"pdf2zh exited with code {completed.returncode}.")


def new_run_directory(input_pdf: Path) -> Path:
    pdf_hash = sha256_file(input_pdf)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    run_id = f"{safe_name(input_pdf.stem)}-{pdf_hash[:12]}-{stamp}"
    return Path(tempfile.gettempdir()) / "zotero-translate-runs" / run_id


def add_output_mode_args(args_list: list[str], output_mode: str) -> None:
    if output_mode == "mono":
        args_list.append("--no-dual")
    elif output_mode == "dual":
        args_list.append("--no-mono")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Zotero Translate collect or render phase.")
    parser.add_argument("--phase", "-Phase", choices=("collect", "render"), default="collect")
    parser.add_argument("--input-pdf", "-InputPdf")
    parser.add_argument("--run-dir", "-RunDir")
    parser.add_argument("--pages", "-Pages")
    parser.add_argument("--lang-in", "-LangIn", default="en")
    parser.add_argument("--lang-out", "-LangOut", default="zh")
    parser.add_argument("--output-mode", "-OutputMode", choices=("mono", "dual", "both"), default="both")
    parser.add_argument("--watermark-output-mode", "-WatermarkOutputMode", choices=("no_watermark", "watermarked", "both"), default="no_watermark")
    parser.add_argument("--no-auto-glossary", "-NoAutoGlossary", action="store_true")
    parser.add_argument("--cli-translator-timeout", "-CliTranslatorTimeout", type=int, default=120)
    parser.add_argument("--python-exe", "-PythonExe")
    parser.add_argument("--force-runtime", "-ForceRuntime", action="store_true")
    parser.add_argument("--keep-artifacts", "-KeepArtifacts", action="store_true")
    parser.add_argument("--cleanup-policy", "-CleanupPolicy", choices=("success", "always", "never"), default="success")
    parser.add_argument("--dry-run", "-DryRun", action="store_true")
    return parser


def collect_phase(args: argparse.Namespace, script_dir: Path, runtime: dict) -> int:
    if not args.input_pdf:
        raise ValueError("InputPdf is required for the collect phase.")
    input_pdf = Path(args.input_pdf).expanduser().resolve()
    if not input_pdf.exists():
        raise FileNotFoundError(f"InputPdf does not exist: {input_pdf}")
    if input_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"InputPdf must be a PDF file: {input_pdf}")

    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else new_run_directory(input_pdf).resolve()
    collect_output_dir = run_dir / "collect-output"
    render_output_dir = run_dir / "render-output"
    temp_dir = run_dir / "tmp"
    segments_path = run_dir / "segments.jsonl"
    translations_path = run_dir / "translations.jsonl"
    missing_path = run_dir / "missing_segments.jsonl"
    context_pack = run_dir / "context_pack.md"
    manifest_path = run_dir / "run_manifest.json"
    for directory in (collect_output_dir, render_output_dir, temp_dir):
        directory.mkdir(parents=True, exist_ok=True)
    segments_path.touch(exist_ok=True)

    builder_result = build_context(script_dir, runtime["pythonExe"], input_pdf, context_pack, args.lang_in, args.lang_out)
    pdf_hash = sha256_file(input_pdf)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {
        "schemaVersion": 1,
        "runId": run_dir.name,
        "createdAt": now,
        "updatedAt": now,
        "status": "collecting",
        "phase": "collect",
        "inputPdf": str(input_pdf),
        "inputPdfSha256": pdf_hash,
        "sourceLanguage": args.lang_in,
        "targetLanguage": args.lang_out,
        "pages": args.pages,
        "outputMode": args.output_mode,
        "watermarkOutputMode": args.watermark_output_mode,
        "noAutoGlossary": bool(args.no_auto_glossary),
        "cleanupPolicy": args.cleanup_policy,
        "keepArtifacts": bool(args.keep_artifacts),
        "runDir": str(run_dir),
        "contextPack": builder_result["contextPack"],
        "contextHash": builder_result["contextSha256"],
        "segmentsPath": str(segments_path),
        "translationsPath": str(translations_path),
        "missingPath": str(missing_path),
        "collectOutputDir": str(collect_output_dir),
        "renderOutputDir": str(render_output_dir),
        "tempDir": str(temp_dir),
        "finalPdfs": [],
        "attached": [],
        "segmentCount": 0,
    }
    write_json(manifest_path, manifest)

    collector_command = command_string([
        runtime["pythonExe"],
        str(script_dir / "collect_segments.py"),
        "--segments-path",
        str(segments_path),
        "--manifest-path",
        str(manifest_path),
        "--source-language",
        args.lang_in,
        "--target-language",
        args.lang_out,
    ])

    pdf_args = [
        str(input_pdf),
        "--lang-in", args.lang_in,
        "--lang-out", args.lang_out,
        "--output", str(collect_output_dir),
        "--qps", "1",
        "--pool-max-workers", "1",
        "--watermark-output-mode", args.watermark_output_mode,
    ]
    if args.pages:
        pdf_args += ["--pages", args.pages]
    add_output_mode_args(pdf_args, args.output_mode)
    if args.no_auto_glossary:
        pdf_args.append("--no-auto-extract-glossary")
    pdf_args += ["--clitranslator", "--clitranslator-command", collector_command, "--clitranslator-timeout", str(args.cli_translator_timeout)]

    if args.dry_run:
        manifest["status"] = "dry-run"
        write_json(manifest_path, manifest)
        print(json.dumps({
            "phase": "collect",
            "runDir": str(run_dir),
            "manifestPath": str(manifest_path),
            "contextPack": builder_result["contextPack"],
            "segmentsPath": str(segments_path),
            "translationsPath": str(translations_path),
            "outputMode": args.output_mode,
            "pages": args.pages,
            "pdf2zhExe": runtime["pdf2zhExe"],
            "args": pdf_args,
            "nextStep": "Translate segments.jsonl in the active conversation, write translations.jsonl, then run --phase render --run-dir this directory.",
        }, ensure_ascii=False, indent=2))
        return 0

    invoke_pdf2zh(runtime["pdf2zhExe"], pdf_args, temp_dir)
    segment_count = sum(1 for line in segments_path.read_text(encoding="utf-8").splitlines() if line.strip())
    manifest = read_json(manifest_path)
    manifest["status"] = "awaiting_translations"
    manifest["phase"] = "translate"
    manifest["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["segmentCount"] = segment_count
    write_json(manifest_path, manifest)
    print(json.dumps({
        "phase": "collect",
        "status": "awaiting_translations",
        "runDir": str(run_dir),
        "manifestPath": str(manifest_path),
        "contextPack": builder_result["contextPack"],
        "segmentsPath": str(segments_path),
        "translationsPath": str(translations_path),
        "segmentCount": segment_count,
        "nextStep": "Translate segments.jsonl in the active conversation, write translations.jsonl, then run --phase render --run-dir this directory.",
    }, ensure_ascii=False, indent=2))
    return 0


def render_phase(args: argparse.Namespace, script_dir: Path, runtime: dict) -> int:
    if not args.run_dir:
        raise ValueError("RunDir is required for the render phase.")
    run_dir = Path(args.run_dir).expanduser().resolve()
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Run manifest not found: {manifest_path}")
    manifest = read_json(manifest_path)

    input_pdf = Path(args.input_pdf).expanduser().resolve() if args.input_pdf else Path(manifest["inputPdf"]).expanduser().resolve()
    if not input_pdf.exists():
        raise FileNotFoundError(f"InputPdf does not exist: {input_pdf}")

    render_output_dir = Path(manifest["renderOutputDir"]).expanduser().resolve()
    temp_dir = Path(manifest["tempDir"]).expanduser().resolve()
    translations_path = Path(manifest["translationsPath"]).expanduser().resolve()
    missing_path = Path(manifest["missingPath"]).expanduser().resolve()
    render_output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    if not translations_path.exists():
        raise FileNotFoundError(f"Translations file does not exist: {translations_path}")

    output_mode = args.output_mode if "--output-mode" in sys.argv or "-OutputMode" in sys.argv else manifest.get("outputMode", "both")
    watermark = args.watermark_output_mode if "--watermark-output-mode" in sys.argv or "-WatermarkOutputMode" in sys.argv else manifest.get("watermarkOutputMode", "no_watermark")
    pages = args.pages if "--pages" in sys.argv or "-Pages" in sys.argv else manifest.get("pages")
    no_auto_glossary = bool(args.no_auto_glossary) if "--no-auto-glossary" in sys.argv or "-NoAutoGlossary" in sys.argv else bool(manifest.get("noAutoGlossary"))

    lookup_command = command_string([
        runtime["pythonExe"],
        str(script_dir / "lookup_translator.py"),
        "--translations-path",
        str(translations_path),
        "--missing-path",
        str(missing_path),
    ])

    pdf_args = [
        str(input_pdf),
        "--lang-in", manifest["sourceLanguage"],
        "--lang-out", manifest["targetLanguage"],
        "--output", str(render_output_dir),
        "--qps", "1",
        "--pool-max-workers", "1",
        "--watermark-output-mode", watermark,
    ]
    if pages:
        pdf_args += ["--pages", str(pages)]
    add_output_mode_args(pdf_args, output_mode)
    if no_auto_glossary:
        pdf_args.append("--no-auto-extract-glossary")
    pdf_args += ["--clitranslator", "--clitranslator-command", lookup_command, "--clitranslator-timeout", str(args.cli_translator_timeout)]

    if args.dry_run:
        print(json.dumps({
            "phase": "render",
            "runDir": str(run_dir),
            "manifestPath": str(manifest_path),
            "translationsPath": str(translations_path),
            "outputMode": output_mode,
            "pages": pages,
            "pdf2zhExe": runtime["pdf2zhExe"],
            "args": pdf_args,
        }, ensure_ascii=False, indent=2))
        return 0

    started_at = datetime.now().timestamp()
    invoke_pdf2zh(runtime["pdf2zhExe"], pdf_args, temp_dir)
    pdfs = sorted(
        [str(path.resolve()) for path in render_output_dir.rglob("*.pdf") if path.stat().st_mtime >= started_at - 2],
        reverse=True,
    )
    manifest["status"] = "rendered"
    manifest["phase"] = "attach"
    manifest["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["outputMode"] = output_mode
    manifest["watermarkOutputMode"] = watermark
    manifest["pages"] = pages
    manifest["finalPdfs"] = pdfs
    write_json(manifest_path, manifest)
    print(json.dumps({
        "phase": "render",
        "status": "rendered",
        "runDir": str(run_dir),
        "manifestPath": str(manifest_path),
        "outputMode": output_mode,
        "pages": pages,
        "pdfs": pdfs,
        "nextStep": "Attach the rendered PDF files to the Zotero parent item, then run cleanup_artifacts.py with --confirm-attached unless KeepArtifacts was requested.",
    }, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = make_parser()
    args = parser.parse_args()
    script_dir = Path(__file__).resolve().parent
    runtime = get_runtime(script_dir, args.python_exe, args.force_runtime, args.dry_run)
    if args.phase == "collect":
        return collect_phase(args, script_dir, runtime)
    return render_phase(args, script_dir, runtime)


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
