#!/usr/bin/env python3
"""Create and verify the skill-local Python runtime."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def configure_stdio() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def run(command: list[str], *, check: bool = True, stdout=None, stderr=None) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=check, stdout=stdout, stderr=stderr, text=True)


def command_works(command: list[str]) -> bool:
    try:
        completed = run(command + ["-c", "import sys; print(sys.version)"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return completed.returncode == 0
    except OSError:
        return False


def iter_base_python(explicit: str | None) -> list[list[str]]:
    candidates: list[list[str]] = []
    if explicit:
        candidates.append([str(Path(explicit).expanduser())])

    if sys.executable:
        candidates.append([sys.executable])

    home = Path.home()
    codex_root = home / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "python"
    for path in (
        codex_root / "python.exe",
        codex_root / "python",
        codex_root / "bin" / "python3",
        codex_root / "bin" / "python",
    ):
        if path.exists():
            candidates.append([str(path)])

    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            candidates.append([found])

    if os.name == "nt":
        py = shutil.which("py")
        if py:
            candidates.append([py, "-3"])

    deduped: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for candidate in candidates:
        key = tuple(candidate)
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def find_base_python(explicit: str | None) -> list[str]:
    for command in iter_base_python(explicit):
        if command_works(command):
            return command
    raise RuntimeError("No usable Python 3 executable was found. Install Python 3 or pass --python-exe.")


def get_venv_python(venv_dir: Path) -> Path | None:
    for path in (
        venv_dir / "Scripts" / "python.exe",
        venv_dir / "bin" / "python3",
        venv_dir / "bin" / "python",
    ):
        if path.exists():
            return path
    return None


def get_venv_pdf2zh(venv_dir: Path) -> Path | None:
    for path in (
        venv_dir / "Scripts" / "pdf2zh.exe",
        venv_dir / "Scripts" / "pdf2zh",
        venv_dir / "bin" / "pdf2zh",
    ):
        if path.exists():
            return path
    return None


def test_import(python: Path, module: str) -> bool:
    completed = run([str(python), "-c", f"import {module}"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return completed.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or verify the Zotero Translate skill runtime.")
    parser.add_argument("--python-exe", "-PythonExe")
    parser.add_argument("--package-spec", "-PackageSpec", default="pdf2zh-next>=2.8.2")
    parser.add_argument("--force", "-Force", action="store_true")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    skill_dir = script_dir.parent
    runtime_dir = skill_dir / ".runtime"
    venv_dir = runtime_dir / "venv"

    if args.force and venv_dir.exists():
        resolved_skill = skill_dir.resolve()
        resolved_venv = venv_dir.resolve()
        if resolved_skill not in (resolved_venv, *resolved_venv.parents):
            raise RuntimeError(f"Refusing to remove runtime outside the skill directory: {resolved_venv}")
        shutil.rmtree(venv_dir)

    runtime_dir.mkdir(parents=True, exist_ok=True)
    install_log = runtime_dir / "install.log"

    venv_python = get_venv_python(venv_dir)
    if venv_python is None:
        base_python = find_base_python(args.python_exe)
        run(base_python + ["-m", "venv", str(venv_dir)])
        venv_python = get_venv_python(venv_dir)
    if venv_python is None:
        raise RuntimeError(f"Skill runtime was created but its Python executable was not found: {venv_dir}")

    with install_log.open("a", encoding="utf-8") as log:
        if not test_import(venv_python, "pdf2zh_next"):
            run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], stdout=log, stderr=subprocess.STDOUT)
            run([str(venv_python), "-m", "pip", "install", args.package_spec], stdout=log, stderr=subprocess.STDOUT)

        if not test_import(venv_python, "fitz"):
            run([str(venv_python), "-m", "pip", "install", "PyMuPDF"], stdout=log, stderr=subprocess.STDOUT)

    pdf2zh_exe = get_venv_pdf2zh(venv_dir)
    if pdf2zh_exe is None:
        raise RuntimeError(f"pdf2zh executable was not found in the skill runtime: {venv_dir}")

    print(json.dumps({
        "skillDir": str(skill_dir.resolve()),
        "runtimeDir": str(runtime_dir.resolve()),
        "venvDir": str(venv_dir.resolve()),
        "pythonExe": str(venv_python.resolve()),
        "pdf2zhExe": str(pdf2zh_exe.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
