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
import urllib.error
import urllib.request
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


def split_csv_args(values: list[str] | None) -> list[Path]:
    paths: list[Path] = []
    for value in values or []:
        for part in value.split(","):
            part = part.strip()
            if part:
                paths.append(Path(part).expanduser().resolve())
    return paths


def default_api_config_path(script_dir: Path) -> Path:
    return script_dir.parent / ".runtime" / "api_config.json"


def normalize_api_base_url(base_url: str | None, api_port: str | None) -> str:
    if base_url and base_url.strip():
        return base_url.strip().rstrip("/")
    if api_port and api_port.strip():
        port = api_port.strip()
        if re.match(r"^https?://", port, re.IGNORECASE):
            return port.rstrip("/")
        return f"http://127.0.0.1:{port}/v1"
    return ""


def models_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/models"):
        return base
    if base.endswith("/v1"):
        return f"{base}/models"
    return f"{base}/v1/models"


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def sanitize_api_config(config: dict) -> dict:
    return {
        key: (mask_secret(value) if key == "api_key" else value)
        for key, value in config.items()
        if value not in (None, "")
    }


def load_api_config(path: Path) -> dict:
    if not path.exists():
        return {}
    data = read_json(path)
    return data if isinstance(data, dict) else {}


def write_api_config(path: Path, config: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, {key: value for key, value in config.items() if value not in (None, "")})


def api_args_provided(args: argparse.Namespace) -> bool:
    return any(
        getattr(args, name, None) not in (None, "", [])
        for name in ("api_base_url", "api_port", "api_key", "api_model")
    )


def resolved_api_config(args: argparse.Namespace, script_dir: Path, *, persist_if_provided: bool = False) -> tuple[dict, Path]:
    config_path = Path(args.api_config).expanduser().resolve() if args.api_config else default_api_config_path(script_dir).resolve()
    config = load_api_config(config_path)

    env_base_url = os.environ.get("ZOTERO_TRANSLATE_API_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
    env_api_key = os.environ.get("ZOTERO_TRANSLATE_API_KEY") or os.environ.get("OPENAI_API_KEY")
    env_model = os.environ.get("ZOTERO_TRANSLATE_API_MODEL") or os.environ.get("OPENAI_MODEL")
    env_port = os.environ.get("ZOTERO_TRANSLATE_API_PORT")

    base_url = normalize_api_base_url(args.api_base_url or config.get("base_url") or env_base_url, args.api_port or config.get("api_port") or env_port)
    api_key = args.api_key or config.get("api_key") or env_api_key or ""
    model = args.api_model or config.get("model") or env_model or ""

    resolved = {
        "base_url": base_url,
        "api_port": args.api_port or config.get("api_port") or env_port or "",
        "api_key": api_key,
        "model": model,
    }
    if persist_if_provided and api_args_provided(args):
        write_api_config(config_path, resolved)
    return resolved, config_path


def discover_api_model(config: dict, timeout: float) -> str:
    request = urllib.request.Request(
        models_endpoint(str(config.get("base_url") or "")),
        headers={"Authorization": f"Bearer {config.get('api_key', '')}"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    models = data.get("data") or []
    for item in models:
        if isinstance(item, dict) and item.get("id"):
            return str(item["id"])
    return ""


def api_config_ready(config: dict) -> tuple[bool, str]:
    if not config.get("base_url"):
        return False, "missing API base URL or port"
    if not config.get("api_key"):
        return False, "missing API key"
    if not config.get("model"):
        return False, "missing API model"
    return True, ""


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
    parser = argparse.ArgumentParser(description="Run Zotero Translate collect, batching, validation, or render phases.")
    parser.add_argument("--phase", "-Phase", choices=("configure-api", "collect", "api-translate", "build-glossary-batches", "merge-glossary", "build-batches", "validate", "render"), default="collect")
    parser.add_argument("--input-pdf", "-InputPdf")
    parser.add_argument("--run-dir", "-RunDir")
    parser.add_argument("--pages", "-Pages")
    parser.add_argument("--lang-in", "-LangIn", default="en")
    parser.add_argument("--lang-out", "-LangOut")
    parser.add_argument("--output-mode", "-OutputMode", choices=("mono", "dual", "both"), default="both")
    parser.add_argument("--watermark-output-mode", "-WatermarkOutputMode", choices=("no_watermark", "watermarked", "both"), default="no_watermark")
    parser.add_argument("--no-auto-glossary", "-NoAutoGlossary", action="store_true")
    parser.add_argument("--glossary-results-dir", "-GlossaryResultsDir")
    parser.add_argument("--glossary-csv", "-GlossaryCsv", action="append", default=[])
    parser.add_argument("--api-config", "-ApiConfig")
    parser.add_argument("--api-base-url", "-ApiBaseUrl")
    parser.add_argument("--api-port", "-ApiPort")
    parser.add_argument("--api-key", "-ApiKey")
    parser.add_argument("--api-model", "-ApiModel")
    parser.add_argument("--api-timeout", "-ApiTimeout", type=float, default=60.0)
    parser.add_argument("--api-temperature", "-ApiTemperature", type=float, default=0.2)
    parser.add_argument("--api-max-tokens", "-ApiMaxTokens", type=int)
    parser.add_argument("--api-qps", "-ApiQps", type=float, default=1.0)
    parser.add_argument("--api-retries", "-ApiRetries", type=int, default=2)
    parser.add_argument("--api-extra-instruction", "-ApiExtraInstruction")
    parser.add_argument("--skip-api-probe", "-SkipApiProbe", action="store_true")
    parser.add_argument("--force-agent-route", "-ForceAgentRoute", action="store_true")
    parser.add_argument("--term-max-segments", "-TermMaxSegments", type=int, default=12)
    parser.add_argument("--term-max-chars", "-TermMaxChars", type=int, default=3200)
    parser.add_argument("--cli-translator-timeout", "-CliTranslatorTimeout", type=int, default=120)
    parser.add_argument("--max-segments", "-MaxSegments", type=int, default=60)
    parser.add_argument("--max-chars", "-MaxChars", type=int, default=60000)
    parser.add_argument("--max-parallel-agents", "-MaxParallelAgents", type=int, default=16)
    parser.add_argument("--batch-results-dir", "-BatchResultsDir")
    parser.add_argument("--fail-on-reference-translation", "-FailOnReferenceTranslation", action="store_true")
    parser.add_argument("--python-exe", "-PythonExe")
    parser.add_argument("--force-runtime", "-ForceRuntime", action="store_true")
    parser.add_argument("--keep-artifacts", "-KeepArtifacts", action="store_true")
    parser.add_argument("--cleanup-policy", "-CleanupPolicy", choices=("success", "always", "never"), default="success")
    parser.add_argument("--dry-run", "-DryRun", action="store_true")
    return parser


def run_passthrough(command: list[str], env_extra: dict[str, str] | None = None) -> int:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    completed = subprocess.run(command, text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return completed.returncode


def configure_api_phase(args: argparse.Namespace, script_dir: Path) -> int:
    config, config_path = resolved_api_config(args, script_dir, persist_if_provided=True)
    if not config.get("model") and config.get("base_url") and config.get("api_key") and not args.skip_api_probe:
        try:
            discovered = discover_api_model(config, args.api_timeout)
            if discovered:
                config["model"] = discovered
                write_api_config(config_path, config)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            pass

    ready, reason = api_config_ready(config)
    if ready:
        write_api_config(config_path, config)
    probe_status = "skipped"
    if ready and not args.skip_api_probe:
        try:
            discover_api_model(config, args.api_timeout)
            probe_status = "ok"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            probe_status = f"failed: {exc}"

    print(json.dumps({
        "phase": "configure-api",
        "status": "ok" if ready else "incomplete",
        "reason": "" if ready else reason,
        "apiConfigPath": str(config_path),
        "api": sanitize_api_config(config),
        "probe": probe_status,
        "nextStep": "Run collect, then --phase api-translate. If api-translate reports api_unavailable, use the agent batch route.",
    }, ensure_ascii=False, indent=2))
    return 0 if ready else 2


def api_translate_phase(args: argparse.Namespace, script_dir: Path) -> int:
    if not args.run_dir:
        raise ValueError("RunDir is required for the api-translate phase.")
    run_dir = Path(args.run_dir).expanduser().resolve()
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Run manifest not found: {manifest_path}")
    manifest = read_json(manifest_path)

    config, config_path = resolved_api_config(args, script_dir, persist_if_provided=True)
    if args.force_agent_route:
        print(json.dumps({
            "phase": "api-translate",
            "status": "agent_route_requested",
            "runDir": str(run_dir),
            "nextStep": "Use build-glossary-batches/merge-glossary/build-batches, then dispatch agent translation batches.",
        }, ensure_ascii=False, indent=2))
        return 0

    if not config.get("model") and config.get("base_url") and config.get("api_key") and not args.skip_api_probe:
        try:
            discovered = discover_api_model(config, args.api_timeout)
            if discovered:
                config["model"] = discovered
                write_api_config(config_path, config)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            pass

    ready, reason = api_config_ready(config)
    if not ready:
        print(json.dumps({
            "phase": "api-translate",
            "status": "api_unavailable",
            "reason": reason,
            "apiConfigPath": str(config_path),
            "nextStep": "Use the agent batch route: build-glossary-batches, merge-glossary, build-batches, batch agents, validate.",
        }, ensure_ascii=False, indent=2))
        return 0

    if not args.skip_api_probe:
        try:
            discover_api_model(config, args.api_timeout)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(json.dumps({
                "phase": "api-translate",
                "status": "api_unavailable",
                "reason": f"API probe failed: {exc}",
                "apiConfigPath": str(config_path),
                "api": sanitize_api_config(config),
                "nextStep": "Use the agent batch route or rerun configure-api with a reachable base URL/model/key.",
            }, ensure_ascii=False, indent=2))
            return 0

    segments_path = Path(manifest["segmentsPath"]).expanduser().resolve()
    translations_path = Path(manifest["translationsPath"]).expanduser().resolve()
    missing_path = Path(manifest["missingPath"]).expanduser().resolve()
    context_pack = Path(manifest["contextPack"]).expanduser().resolve()
    api_results_path = run_dir / "api_results.jsonl"
    glossary_csvs = split_csv_args(args.glossary_csv)
    auto_glossary_raw = manifest.get("autoGlossaryPath")
    if not manifest.get("noAutoGlossary") and auto_glossary_raw:
        auto_glossary_path = Path(auto_glossary_raw).expanduser()
        if auto_glossary_path.exists():
            glossary_csvs.append(auto_glossary_path.resolve())

    command = [
        sys.executable,
        str(script_dir / "api_translate_segments.py"),
        str(segments_path),
        "--output-results",
        str(api_results_path),
        "--base-url",
        str(config["base_url"]),
        "--model",
        str(config["model"]),
        "--target-language",
        str(manifest["targetLanguage"]),
        "--context-pack",
        str(context_pack),
        "--timeout",
        str(args.api_timeout),
        "--temperature",
        str(args.api_temperature),
        "--qps",
        str(args.api_qps),
        "--retries",
        str(args.api_retries),
        "--resume",
    ]
    if args.api_max_tokens is not None:
        command += ["--max-tokens", str(args.api_max_tokens)]
    if args.api_extra_instruction:
        command += ["--extra-instruction", args.api_extra_instruction]
    for glossary_csv in glossary_csvs:
        command += ["--glossary-csv", str(glossary_csv)]

    if args.dry_run:
        print(json.dumps({
            "phase": "api-translate",
            "runDir": str(run_dir),
            "manifestPath": str(manifest_path),
            "apiConfigPath": str(config_path),
            "api": sanitize_api_config(config),
            "apiResultsPath": str(api_results_path),
            "glossaryCsvs": [str(path) for path in glossary_csvs],
            "command": [part for part in command if part != str(config.get("api_key", ""))],
        }, ensure_ascii=False, indent=2))
        return 0

    code = run_passthrough(command, env_extra={"ZOTERO_TRANSLATE_API_KEY": str(config["api_key"])})
    if code != 0:
        return code

    validate_command = [
        sys.executable,
        str(script_dir / "validate_translations.py"),
        str(segments_path),
        str(api_results_path),
        "--write-translations",
        str(translations_path),
        "--missing-path",
        str(missing_path),
    ]
    if args.fail_on_reference_translation:
        validate_command.append("--fail-on-reference-translation")
    code = run_passthrough(validate_command)
    if code != 0:
        return code

    manifest["status"] = "translations_validated"
    manifest["phase"] = "render"
    manifest["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["translationRoute"] = "api"
    manifest["apiConfigPath"] = str(config_path)
    manifest["api"] = {key: value for key, value in sanitize_api_config(config).items() if key != "api_key"}
    manifest["apiResultsPath"] = str(api_results_path)
    manifest["glossaryCsvs"] = [str(path) for path in glossary_csvs]
    write_json(manifest_path, manifest)
    return 0


def build_glossary_batches_phase(args: argparse.Namespace, script_dir: Path) -> int:
    if not args.run_dir:
        raise ValueError("RunDir is required for the build-glossary-batches phase.")
    run_dir = Path(args.run_dir).expanduser().resolve()
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Run manifest not found: {manifest_path}")
    manifest = read_json(manifest_path)
    if manifest.get("noAutoGlossary"):
        print(json.dumps({
            "phase": "build-glossary-batches",
            "status": "skipped",
            "reason": "noAutoGlossary is true",
            "runDir": str(run_dir),
        }, ensure_ascii=False, indent=2))
        return 0

    segments_path = Path(manifest["segmentsPath"]).expanduser().resolve()
    term_batches_dir = run_dir / "term_batches"
    glossary_results_dir = run_dir / "glossary_results"
    glossary_results_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(script_dir / "build_term_batches.py"),
        str(segments_path),
        "--output-dir",
        str(term_batches_dir),
        "--target-language",
        str(manifest["targetLanguage"]),
        "--max-segments",
        str(args.term_max_segments),
        "--max-chars",
        str(args.term_max_chars),
    ]

    if args.dry_run:
        print(json.dumps({
            "phase": "build-glossary-batches",
            "runDir": str(run_dir),
            "manifestPath": str(manifest_path),
            "command": command,
            "termBatchesDir": str(term_batches_dir),
            "glossaryResultsDir": str(glossary_results_dir),
        }, ensure_ascii=False, indent=2))
        return 0

    code = run_passthrough(command)
    if code != 0:
        return code

    manifest["status"] = "awaiting_glossary_results"
    manifest["phase"] = "glossary"
    manifest["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["termBatchesDir"] = str(term_batches_dir)
    manifest["termBatchManifest"] = str(term_batches_dir / "term_batch_manifest.json")
    manifest["glossaryResultsDir"] = str(glossary_results_dir)
    manifest["autoGlossaryPath"] = str(run_dir / "auto_glossary.csv")
    write_json(manifest_path, manifest)
    return 0


def merge_glossary_phase(args: argparse.Namespace, script_dir: Path) -> int:
    if not args.run_dir:
        raise ValueError("RunDir is required for the merge-glossary phase.")
    run_dir = Path(args.run_dir).expanduser().resolve()
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Run manifest not found: {manifest_path}")
    manifest = read_json(manifest_path)
    results_dir = Path(args.glossary_results_dir).expanduser().resolve() if args.glossary_results_dir else Path(manifest.get("glossaryResultsDir") or (run_dir / "glossary_results")).expanduser().resolve()
    output_path = Path(manifest.get("autoGlossaryPath") or (run_dir / "auto_glossary.csv")).expanduser().resolve()

    command = [
        sys.executable,
        str(script_dir / "merge_glossary.py"),
        str(results_dir),
        "--output",
        str(output_path),
        "--target-language",
        str(manifest["targetLanguage"]),
    ]

    if args.dry_run:
        print(json.dumps({
            "phase": "merge-glossary",
            "runDir": str(run_dir),
            "manifestPath": str(manifest_path),
            "command": command,
            "glossaryResultsDir": str(results_dir),
            "autoGlossaryPath": str(output_path),
        }, ensure_ascii=False, indent=2))
        return 0

    code = run_passthrough(command)
    if code != 0:
        return code

    manifest["status"] = "glossary_ready"
    manifest["phase"] = "translate"
    manifest["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["glossaryResultsDir"] = str(results_dir)
    manifest["autoGlossaryPath"] = str(output_path)
    write_json(manifest_path, manifest)
    return 0


def build_batches_phase(args: argparse.Namespace, script_dir: Path) -> int:
    if not args.run_dir:
        raise ValueError("RunDir is required for the build-batches phase.")
    run_dir = Path(args.run_dir).expanduser().resolve()
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Run manifest not found: {manifest_path}")
    manifest = read_json(manifest_path)

    segments_path = Path(manifest["segmentsPath"]).expanduser().resolve()
    translations_path = Path(manifest["translationsPath"]).expanduser().resolve()
    context_pack = Path(manifest["contextPack"]).expanduser().resolve()
    batches_dir = run_dir / "batches"
    batch_results_dir = run_dir / "batch_results"
    batch_results_dir.mkdir(parents=True, exist_ok=True)
    glossary_csvs = split_csv_args(args.glossary_csv)
    auto_glossary_raw = manifest.get("autoGlossaryPath")
    if not manifest.get("noAutoGlossary") and auto_glossary_raw:
        auto_glossary_path = Path(auto_glossary_raw).expanduser()
        if auto_glossary_path.exists():
            glossary_csvs.append(auto_glossary_path.resolve())

    command = [
        sys.executable,
        str(script_dir / "build_batches.py"),
        str(segments_path),
        "--output-dir",
        str(batches_dir),
        "--translations-path",
        str(translations_path),
        "--context-pack",
        str(context_pack),
        "--max-segments",
        str(args.max_segments),
        "--max-chars",
        str(args.max_chars),
        "--max-parallel-agents",
        str(args.max_parallel_agents),
        "--target-language",
        str(manifest["targetLanguage"]),
    ]
    for glossary_csv in glossary_csvs:
        command += ["--glossary-csv", str(glossary_csv)]

    if args.dry_run:
        print(json.dumps({
            "phase": "build-batches",
            "runDir": str(run_dir),
            "manifestPath": str(manifest_path),
            "command": command,
            "batchesDir": str(batches_dir),
            "batchResultsDir": str(batch_results_dir),
            "maxParallelAgents": args.max_parallel_agents,
            "glossaryCsvs": [str(path) for path in glossary_csvs],
        }, ensure_ascii=False, indent=2))
        return 0

    code = run_passthrough(command)
    if code != 0:
        return code

    manifest["status"] = "awaiting_batch_results"
    manifest["phase"] = "translate"
    manifest["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["batchesDir"] = str(batches_dir)
    manifest["batchManifest"] = str(batches_dir / "batch_manifest.json")
    manifest["batchResultsDir"] = str(batch_results_dir)
    manifest["maxParallelAgents"] = args.max_parallel_agents
    manifest["glossaryCsvs"] = [str(path) for path in glossary_csvs]
    write_json(manifest_path, manifest)
    return 0


def validate_phase(args: argparse.Namespace, script_dir: Path) -> int:
    if not args.run_dir:
        raise ValueError("RunDir is required for the validate phase.")
    run_dir = Path(args.run_dir).expanduser().resolve()
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Run manifest not found: {manifest_path}")
    manifest = read_json(manifest_path)

    segments_path = Path(manifest["segmentsPath"]).expanduser().resolve()
    translations_path = Path(manifest["translationsPath"]).expanduser().resolve()
    missing_path = Path(manifest["missingPath"]).expanduser().resolve()
    results_dir = Path(args.batch_results_dir).expanduser().resolve() if args.batch_results_dir else Path(manifest.get("batchResultsDir") or (run_dir / "batch_results")).expanduser().resolve()

    command = [
        sys.executable,
        str(script_dir / "validate_translations.py"),
        str(segments_path),
        str(results_dir),
        "--write-translations",
        str(translations_path),
        "--missing-path",
        str(missing_path),
    ]
    if args.fail_on_reference_translation:
        command.append("--fail-on-reference-translation")

    if args.dry_run:
        print(json.dumps({
            "phase": "validate",
            "runDir": str(run_dir),
            "manifestPath": str(manifest_path),
            "command": command,
            "translationsPath": str(translations_path),
            "batchResultsDir": str(results_dir),
        }, ensure_ascii=False, indent=2))
        return 0

    code = run_passthrough(command)
    if code != 0:
        return code

    manifest["status"] = "translations_validated"
    manifest["phase"] = "render"
    manifest["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["batchResultsDir"] = str(results_dir)
    write_json(manifest_path, manifest)
    return 0


def collect_phase(args: argparse.Namespace, script_dir: Path, runtime: dict) -> int:
    if not args.lang_out or not args.lang_out.strip():
        raise ValueError("LangOut is required for the collect phase. Ask the user for the target language and pass --lang-out <target-language>.")
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
    api_config, api_config_path = resolved_api_config(args, script_dir, persist_if_provided=True)
    api_ready, _ = api_config_ready(api_config)
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
        "autoGlossaryEnabled": not bool(args.no_auto_glossary),
        "babeldocAutoGlossaryDisabled": True,
        "preferredTranslationRoute": "agent" if args.force_agent_route else ("api" if api_ready else "agent"),
        "apiConfigPath": str(api_config_path),
        "apiConfigured": api_ready,
        "api": {key: value for key, value in sanitize_api_config(api_config).items() if key != "api_key"},
        "cleanupPolicy": args.cleanup_policy,
        "keepArtifacts": bool(args.keep_artifacts),
        "runDir": str(run_dir),
        "contextPack": builder_result["contextPack"],
        "contextHash": builder_result["contextSha256"],
        "segmentsPath": str(segments_path),
        "translationsPath": str(translations_path),
        "missingPath": str(missing_path),
        "termBatchesDir": str(run_dir / "term_batches"),
        "glossaryResultsDir": str(run_dir / "glossary_results"),
        "autoGlossaryPath": str(run_dir / "auto_glossary.csv"),
        "collectOutputDir": str(collect_output_dir),
        "renderOutputDir": str(render_output_dir),
        "tempDir": str(temp_dir),
        "finalPdfs": [],
        "attached": [],
        "segmentCount": 0,
        "maxParallelAgents": args.max_parallel_agents,
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
            "maxParallelAgents": args.max_parallel_agents,
            "preferredTranslationRoute": manifest["preferredTranslationRoute"],
            "apiConfigured": api_ready,
            "pdf2zhExe": runtime["pdf2zhExe"],
            "args": pdf_args,
            "nextStep": "Run --phase api-translate. If it reports api_unavailable, use the agent batch route.",
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
        "preferredTranslationRoute": manifest.get("preferredTranslationRoute", "agent"),
        "nextStep": "Run --phase api-translate. If it reports api_unavailable, use the agent batch route.",
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
    if args.phase == "collect" and (not args.lang_out or not args.lang_out.strip()):
        parser.error("--lang-out/-LangOut is required for the collect phase. Ask the user for the target language instead of using a default.")
    if args.max_parallel_agents <= 0:
        parser.error("--max-parallel-agents/-MaxParallelAgents must be positive.")
    if args.term_max_segments <= 0:
        parser.error("--term-max-segments/-TermMaxSegments must be positive.")
    if args.term_max_chars <= 0:
        parser.error("--term-max-chars/-TermMaxChars must be positive.")
    if args.api_qps <= 0:
        parser.error("--api-qps/-ApiQps must be positive.")
    if args.api_retries < 0:
        parser.error("--api-retries/-ApiRetries must be non-negative.")
    script_dir = Path(__file__).resolve().parent
    if args.phase == "configure-api":
        return configure_api_phase(args, script_dir)
    if args.phase == "api-translate":
        return api_translate_phase(args, script_dir)
    if args.phase == "build-glossary-batches":
        return build_glossary_batches_phase(args, script_dir)
    if args.phase == "merge-glossary":
        return merge_glossary_phase(args, script_dir)
    if args.phase == "build-batches":
        return build_batches_phase(args, script_dir)
    if args.phase == "validate":
        return validate_phase(args, script_dir)
    runtime = get_runtime(script_dir, args.python_exe, args.force_runtime, args.dry_run)
    if args.phase == "collect":
        return collect_phase(args, script_dir, runtime)
    return render_phase(args, script_dir, runtime)


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
