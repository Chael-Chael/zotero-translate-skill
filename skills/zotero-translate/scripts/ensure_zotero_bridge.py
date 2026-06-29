#!/usr/bin/env python3
"""Build, install, and probe the minimal Zotero Translate bridge XPI."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


BRIDGE_ID = "zotero-translate-bridge@codex.local"
BRIDGE_BASE_URL = "http://127.0.0.1:23119/zotero-translate-bridge"
BRIDGE_TOKEN_HEADER = "X-Zotero-Translate-Bridge-Token"
TOKEN_PLACEHOLDER = "__ZOTERO_TRANSLATE_BRIDGE_TOKEN__"


def configure_stdio() -> None:
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def skill_dir() -> Path:
    return script_dir().parent


def runtime_dir() -> Path:
    return skill_dir() / ".runtime" / "zotero-translate-bridge"


def default_config_path() -> Path:
    return runtime_dir() / "bridge_config.json"


def bridge_source_dir() -> Path:
    return skill_dir() / "assets" / "zotero-translate-bridge"


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def load_or_create_config(path: Path, rotate_token: bool) -> dict:
    config = read_json(path)
    if rotate_token or not config.get("token"):
        config["token"] = generate_token()
    config.setdefault("schemaVersion", 1)
    config.setdefault("bridgeUrl", BRIDGE_BASE_URL)
    return config


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def reset_directory(path: Path, allowed_parent: Path) -> None:
    path = path.resolve()
    allowed_parent = allowed_parent.resolve()
    if path.exists():
        if not is_relative_to(path, allowed_parent):
            raise RuntimeError(f"Refusing to delete outside runtime directory: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def build_bridge_xpi(config: dict) -> tuple[Path, Path]:
    source = bridge_source_dir()
    if not (source / "manifest.json").exists() or not (source / "bootstrap.js").exists():
        raise FileNotFoundError(f"Bridge source is incomplete: {source}")

    build_dir = runtime_dir() / "build"
    xpi_path = runtime_dir() / "zotero-translate-bridge.xpi"
    reset_directory(build_dir, runtime_dir())
    shutil.copytree(source, build_dir, dirs_exist_ok=True)

    bootstrap_path = build_dir / "bootstrap.js"
    bootstrap = bootstrap_path.read_text(encoding="utf-8")
    if TOKEN_PLACEHOLDER not in bootstrap:
        raise RuntimeError(f"Token placeholder not found in {bootstrap_path}")
    bootstrap_path.write_text(bootstrap.replace(TOKEN_PLACEHOLDER, str(config["token"])), encoding="utf-8")

    xpi_path.parent.mkdir(parents=True, exist_ok=True)
    if xpi_path.exists():
        xpi_path.unlink()
    with zipfile.ZipFile(xpi_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(build_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(build_dir).as_posix())
    return build_dir, xpi_path


def profile_ini_candidates() -> list[Path]:
    candidates: list[Path] = []
    system = platform.system().lower()
    home = Path.home()
    if system == "windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / "Zotero" / "Zotero" / "profiles.ini")
    elif system == "darwin":
        candidates.append(home / "Library" / "Application Support" / "Zotero" / "profiles.ini")
    else:
        candidates.append(home / ".zotero" / "zotero" / "profiles.ini")
        candidates.append(home / ".var" / "app" / "org.zotero.Zotero" / "data" / "zotero" / "profiles.ini")
    return candidates


def parse_profiles_ini(path: Path) -> list[dict]:
    parser = configparser.RawConfigParser()
    parser.read(path, encoding="utf-8")
    profiles: list[dict] = []
    for section in parser.sections():
        if not section.lower().startswith("profile"):
            continue
        raw_path = parser.get(section, "Path", fallback="")
        if not raw_path:
            continue
        is_relative = parser.get(section, "IsRelative", fallback="1") == "1"
        profile_path = (path.parent / raw_path if is_relative else Path(raw_path)).resolve()
        profiles.append({
            "section": section,
            "name": parser.get(section, "Name", fallback=""),
            "path": profile_path,
            "default": parser.get(section, "Default", fallback="0") == "1",
        })
    return profiles


def find_zotero_profile(profile_dir: str | None) -> Path:
    if profile_dir:
        path = Path(profile_dir).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Zotero profile directory does not exist: {path}")
        return path

    profiles: list[dict] = []
    for ini_path in profile_ini_candidates():
        if ini_path.exists():
            profiles.extend(parse_profiles_ini(ini_path))
    existing = [profile for profile in profiles if Path(profile["path"]).exists()]
    if not existing:
        raise FileNotFoundError("No Zotero profile was found. Start Zotero once, then rerun this script.")
    for profile in existing:
        if profile.get("default"):
            return Path(profile["path"]).resolve()
    return Path(existing[0]["path"]).resolve()


def install_xpi(profile_dir: Path, xpi_path: Path) -> dict:
    extensions_dir = profile_dir / "extensions"
    extensions_dir.mkdir(parents=True, exist_ok=True)
    proxy_file = extensions_dir / BRIDGE_ID
    disabled_proxy = ""
    if proxy_file.exists():
        disabled_proxy_path = extensions_dir / f"{BRIDGE_ID}.disabled-by-xpi"
        if disabled_proxy_path.exists():
            disabled_proxy_path.unlink()
        shutil.move(str(proxy_file), str(disabled_proxy_path))
        disabled_proxy = str(disabled_proxy_path)
    destination = extensions_dir / f"{BRIDGE_ID}.xpi"
    previous_hash = sha256_file(destination) if destination.exists() else ""
    new_hash = sha256_file(xpi_path)
    changed = previous_hash != new_hash
    if changed:
        shutil.copy2(xpi_path, destination)
    return {
        "mode": "xpi",
        "path": str(destination),
        "changed": changed,
        "sha256": new_hash,
        "disabledProxy": disabled_proxy,
    }


def install_proxy(profile_dir: Path, build_dir: Path) -> dict:
    extensions_dir = profile_dir / "extensions"
    extensions_dir.mkdir(parents=True, exist_ok=True)
    xpi_file = extensions_dir / f"{BRIDGE_ID}.xpi"
    disabled_xpi = ""
    if xpi_file.exists():
        disabled_xpi_path = extensions_dir / f"{BRIDGE_ID}.xpi.disabled-by-proxy"
        if disabled_xpi_path.exists():
            disabled_xpi_path.unlink()
        shutil.move(str(xpi_file), str(disabled_xpi_path))
        disabled_xpi = str(disabled_xpi_path)
    proxy_dir = extensions_dir / BRIDGE_ID
    if proxy_dir.exists():
        if proxy_dir.is_dir():
            if not is_relative_to(proxy_dir, extensions_dir):
                raise RuntimeError(f"Refusing to replace unexpected extension path: {proxy_dir}")
            shutil.rmtree(proxy_dir)
        else:
            proxy_dir.unlink()
    shutil.copytree(build_dir, proxy_dir)
    return {
        "mode": "proxy",
        "path": str(proxy_dir),
        "target": str(build_dir.resolve()),
        "changed": True,
        "disabledXpi": disabled_xpi,
    }


def invalidate_zotero_extension_scan_cache(profile_dir: Path) -> dict:
    prefs_path = profile_dir / "prefs.js"
    if not prefs_path.exists():
        return {"prefsPath": str(prefs_path), "changed": False, "reason": "prefs.js not found"}
    text = prefs_path.read_text(encoding="utf-8", errors="replace")
    removed: list[str] = []
    kept_lines: list[str] = []
    pattern = re.compile(r'^user_pref\("extensions\.(lastAppBuildId|lastAppVersion)",')
    for line in text.splitlines(keepends=True):
        if pattern.match(line.strip()):
            removed.append(line.strip())
            continue
        kept_lines.append(line)
    if not removed:
        return {"prefsPath": str(prefs_path), "changed": False, "removed": []}
    backup_path = prefs_path.with_suffix(".js.zotero-translate-bridge.bak")
    if not backup_path.exists():
        backup_path.write_text(text, encoding="utf-8")
    prefs_path.write_text("".join(kept_lines), encoding="utf-8")
    return {"prefsPath": str(prefs_path), "changed": True, "removed": removed, "backupPath": str(backup_path)}


def bridge_request(url: str, token: str, payload: dict | None, timeout: float) -> tuple[bool, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            BRIDGE_TOKEN_HEADER: token,
        },
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return True, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"body": body}
        parsed.update({"httpStatus": exc.code})
        return False, parsed
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return False, {"error": str(exc)}


def probe_bridge(config: dict, timeout: float) -> tuple[bool, dict]:
    base_url = str(config.get("bridgeUrl") or BRIDGE_BASE_URL).rstrip("/")
    return bridge_request(f"{base_url}/health", str(config.get("token") or ""), {}, timeout)


def find_zotero_executable() -> str | None:
    for name in ("zotero.exe", "zotero"):
        found = shutil.which(name)
        if found:
            return found
    system = platform.system().lower()
    if system == "windows":
        registry_candidates = windows_registry_zotero_paths()
        for candidate in registry_candidates:
            if candidate.exists():
                return str(candidate)
        roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")]
        candidates = []
        for root in roots:
            if not root:
                continue
            base = Path(root)
            candidates.append(base / "Zotero" / "zotero.exe")
            candidates.append(base / "Programs" / "Zotero" / "zotero.exe")
        for drive in ("C", "D", "E"):
            candidates.append(Path(f"{drive}:\\Program\\Zotero\\zotero.exe"))
            candidates.append(Path(f"{drive}:\\Programs\\Zotero\\zotero.exe"))
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
    elif system == "darwin":
        candidate = Path("/Applications/Zotero.app/Contents/MacOS/zotero")
        if candidate.exists():
            return str(candidate)
    return None


def windows_registry_zotero_paths() -> list[Path]:
    if platform.system().lower() != "windows":
        return []
    try:
        import winreg
    except ImportError:
        return []

    roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
    subkeys = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Zotero",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Zotero",
    )
    candidates: list[Path] = []
    for root in roots:
        for subkey in subkeys:
            try:
                with winreg.OpenKey(root, subkey) as key:
                    for value_name in ("InstallLocation", "DisplayIcon"):
                        try:
                            value, _ = winreg.QueryValueEx(key, value_name)
                        except OSError:
                            continue
                        text = str(value).strip().strip('"')
                        if not text:
                            continue
                        path = Path(text)
                        if path.name.lower() == "zotero.exe":
                            candidates.append(path)
                        else:
                            candidates.append(path / "zotero.exe")
            except OSError:
                continue
    return candidates


def stop_zotero() -> None:
    system = platform.system().lower()
    if system == "windows":
        subprocess.run(["taskkill", "/IM", "zotero.exe", "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif system == "darwin":
        subprocess.run(["osascript", "-e", 'quit app "Zotero"'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["pkill", "-f", "zotero"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_zotero() -> bool:
    system = platform.system().lower()
    if system == "darwin":
        completed = subprocess.run(["open", "-a", "Zotero"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return completed.returncode == 0
    executable = find_zotero_executable()
    if not executable:
        return False
    subprocess.Popen([executable], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def wait_for_bridge(config: dict, timeout_seconds: float, probe_timeout: float) -> tuple[bool, dict]:
    deadline = time.time() + timeout_seconds
    last: dict = {"error": "not probed"}
    while time.time() < deadline:
        ok, result = probe_bridge(config, probe_timeout)
        if ok and result.get("ok"):
            return True, result
        last = result
        time.sleep(1)
    return False, last


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build/install/probe the Zotero Translate bridge XPI.")
    parser.add_argument("--install", action="store_true", help="Copy the generated XPI into the Zotero profile extensions directory.")
    parser.add_argument("--install-mode", choices=("auto", "xpi", "proxy"), default="auto")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--probe", action="store_true", help="Probe an already loaded bridge without rebuilding or installing.")
    parser.add_argument("--profile-dir")
    parser.add_argument("--config")
    parser.add_argument("--rotate-token", action="store_true")
    parser.add_argument("--restart-zotero", action="store_true", help="Restart Zotero after installation and wait for the bridge.")
    parser.add_argument("--start-zotero", action="store_true", help="Start Zotero after installation without killing an existing process.")
    parser.add_argument("--wait-seconds", type=float, default=45.0)
    parser.add_argument("--probe-timeout", type=float, default=3.0)
    return parser


def main() -> int:
    args = make_parser().parse_args()
    config_path = Path(args.config).expanduser().resolve() if args.config else default_config_path().resolve()

    if args.probe and not args.install and not args.build_only:
        config = read_json(config_path)
        ok, result = probe_bridge(config, args.probe_timeout)
        print(json.dumps({
            "status": "ready" if ok and result.get("ok") else "unavailable",
            "bridgeUrl": config.get("bridgeUrl", BRIDGE_BASE_URL),
            "configPath": str(config_path),
            "probe": result,
        }, ensure_ascii=False, indent=2))
        return 0 if ok and result.get("ok") else 2

    config = load_or_create_config(config_path, args.rotate_token)
    build_dir, xpi_path = build_bridge_xpi(config)
    profile_dir = None
    install_result = None

    if args.install:
        profile_dir = find_zotero_profile(args.profile_dir)
        if args.install_mode == "proxy":
            install_result = install_proxy(profile_dir, build_dir)
        else:
            install_result = install_xpi(profile_dir, xpi_path)
        install_result["extensionScanCache"] = invalidate_zotero_extension_scan_cache(profile_dir)

    config.update({
        "updatedAt": utc_now(),
        "bridgeId": BRIDGE_ID,
        "bridgeUrl": config.get("bridgeUrl") or BRIDGE_BASE_URL,
        "buildDir": str(build_dir),
        "xpiPath": str(xpi_path),
        "profileDir": str(profile_dir) if profile_dir else config.get("profileDir", ""),
        "install": install_result or config.get("install", {}),
    })
    write_json(config_path, config)

    started = False
    restarted = False
    if args.install and args.restart_zotero:
        stop_zotero()
        time.sleep(1)
        if profile_dir and install_result:
            install_result["extensionScanCacheAfterStop"] = invalidate_zotero_extension_scan_cache(profile_dir)
            config["install"] = install_result
            write_json(config_path, config)
        started = start_zotero()
        restarted = True
    elif args.install and args.start_zotero:
        started = start_zotero()

    probe_ok, probe_result = (False, {"status": "skipped"})
    if args.install and (args.restart_zotero or args.start_zotero):
        probe_ok, probe_result = wait_for_bridge(config, args.wait_seconds, args.probe_timeout)
    elif args.install and not args.build_only:
        probe_ok, probe_result = probe_bridge(config, args.probe_timeout)

    if args.install and args.install_mode == "auto" and not (probe_ok and probe_result.get("ok")) and (args.restart_zotero or args.start_zotero):
        proxy_result = install_proxy(profile_dir, build_dir)
        proxy_result["extensionScanCache"] = invalidate_zotero_extension_scan_cache(profile_dir)
        install_result = {
            "mode": "auto",
            "attempts": [install_result, proxy_result],
            "active": proxy_result,
        }
        config["install"] = install_result
        write_json(config_path, config)
        stop_zotero()
        time.sleep(1)
        if profile_dir and install_result:
            install_result["extensionScanCacheAfterStop"] = invalidate_zotero_extension_scan_cache(profile_dir)
            config["install"] = install_result
            write_json(config_path, config)
        started = start_zotero()
        restarted = True
        probe_ok, probe_result = wait_for_bridge(config, args.wait_seconds, args.probe_timeout)

    status = "ready" if probe_ok and probe_result.get("ok") else ("built" if args.build_only or not args.install else "installed_unloaded")
    next_step = "Run attach_with_bridge.py after render." if probe_ok and probe_result.get("ok") else (
        "The bridge package was built/placed but Zotero did not load the endpoint. Install the generated XPI from Zotero Add-ons or retry after restarting Zotero."
        if args.install else
        "Run with --install --restart-zotero, then probe again."
    )
    output = {
        "status": status,
        "bridgeId": BRIDGE_ID,
        "bridgeUrl": config["bridgeUrl"],
        "configPath": str(config_path),
        "buildDir": str(build_dir),
        "xpiPath": str(xpi_path),
        "profileDir": str(profile_dir) if profile_dir else "",
        "install": install_result,
        "zoteroStarted": started,
        "zoteroRestarted": restarted,
        "probe": probe_result,
        "nextStep": next_step,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if args.build_only or not args.install:
        return 0
    return 0 if install_result else 1


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
