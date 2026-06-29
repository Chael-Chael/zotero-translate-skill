#!/usr/bin/env python3
"""Check whether the configured OpenAI-compatible translation API is usable."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
from pathlib import Path

from run_pdf2zh import (
    api_args_provided,
    api_config_ready,
    configure_stdio,
    discover_api_model,
    resolved_api_config,
    sanitize_api_config,
    write_api_config,
)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-config", "-ApiConfig")
    parser.add_argument("--api-base-url", "-ApiBaseUrl")
    parser.add_argument("--api-port", "-ApiPort")
    parser.add_argument("--api-key", "-ApiKey")
    parser.add_argument("--api-model", "-ApiModel")
    parser.add_argument("--api-timeout", "-ApiTimeout", type=float, default=20.0)
    parser.add_argument("--skip-api-probe", "-SkipApiProbe", action="store_true")
    parser.add_argument("--force-agent-route", "-ForceAgentRoute", action="store_true")
    return parser


def emit_result(
    *,
    available: bool,
    reason: str,
    config_path: Path,
    config: dict,
    probe_status: str,
    discovered_model: str = "",
) -> None:
    payload = {
        "phase": "check-api",
        "apiAvailable": available,
        "status": "ok" if available else "api_unavailable",
        "reason": reason,
        "nextRoute": "api" if available else "agent",
        "apiConfigPath": str(config_path),
        "api": {key: value for key, value in sanitize_api_config(config).items() if key != "api_key"},
        "probe": probe_status,
    }
    if discovered_model:
        payload["discoveredModel"] = discovered_model
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    parser = make_parser()
    args = parser.parse_args()
    if args.api_timeout <= 0:
        parser.error("--api-timeout/-ApiTimeout must be positive.")

    script_dir = Path(__file__).resolve().parent
    config, config_path = resolved_api_config(args, script_dir, persist_if_provided=True)
    should_persist = api_args_provided(args) or config_path.exists()

    if args.force_agent_route:
        emit_result(
            available=False,
            reason="force agent route requested",
            config_path=config_path,
            config=config,
            probe_status="skipped",
        )
        return 0

    discovered_model = ""
    probe_status = "not_run"
    if not config.get("model") and config.get("base_url") and config.get("api_key") and not args.skip_api_probe:
        try:
            discovered_model = discover_api_model(config, args.api_timeout)
            if discovered_model:
                config["model"] = discovered_model
                if should_persist:
                    write_api_config(config_path, config)
            probe_status = "ok" if discovered_model else "no_model_returned"
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
            probe_status = f"failed: {exc}"

    ready, reason = api_config_ready(config)
    if not ready:
        if probe_status.startswith("failed:"):
            reason = f"{reason}; {probe_status}"
        emit_result(
            available=False,
            reason=reason,
            config_path=config_path,
            config=config,
            probe_status=probe_status,
            discovered_model=discovered_model,
        )
        return 0

    if args.skip_api_probe:
        emit_result(
            available=True,
            reason="",
            config_path=config_path,
            config=config,
            probe_status="skipped",
            discovered_model=discovered_model,
        )
        return 0

    try:
        discover_api_model(config, args.api_timeout)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
        emit_result(
            available=False,
            reason=f"API probe failed: {exc}",
            config_path=config_path,
            config=config,
            probe_status=f"failed: {exc}",
            discovered_model=discovered_model,
        )
        return 0

    emit_result(
        available=True,
        reason="",
        config_path=config_path,
        config=config,
        probe_status="ok",
        discovered_model=discovered_model,
    )
    return 0


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
