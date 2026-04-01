#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


CONFIG_DIR = Path.home() / ".goby-agent"
CONFIG_PATH = CONFIG_DIR / "config.json"
DEFAULT_BASE_URL = "http://127.0.0.1:8361"
COMMON_NAMES = ["goby-cmd.exe", "goby-cmd"]
COMMON_NAME_SET = {name.lower() for name in COMMON_NAMES}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def print_json(data: dict) -> int:
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


def validate_executable(path_str: str) -> tuple[bool, str]:
    path = Path(path_str).expanduser()
    if not path.exists():
        return False, "file does not exist"
    if not path.is_file():
        return False, "path is not a file"
    lowered = path.name.lower()
    if lowered not in COMMON_NAME_SET:
        return False, "file name must be goby-cmd or goby-cmd.exe"
    return True, ""


def discover_executable(config: dict) -> dict:
    candidates = []
    stored = config.get("goby_cmd_path")
    if stored:
        candidates.append(("config", stored))

    seen = set()
    for source, candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        ok, reason = validate_executable(candidate)
        if ok:
            resolved = str(Path(candidate).expanduser().resolve())
            return {
                "ok": True,
                "source": source,
                "goby_cmd_path": resolved,
                "goby_runtime_dir": str(Path(resolved).parent),
                "last_verified_at": utc_now_iso(),
            }
        last_reason = reason

    return {
        "ok": False,
        "error": "unable to resolve Goby executable",
        "hint": "ask the user for the full goby-cmd path and store it with config set",
        "last_reason": locals().get("last_reason", "no candidates found"),
    }


def api_request(base_url: str, method: str, api_path: str, payload: dict | None, timeout: int = 5) -> dict:
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    url = base_url.rstrip("/") + api_path
    req = urllib.request.Request(url=url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw
            return {
                "ok": True,
                "status": resp.status,
                "url": url,
                "data": parsed,
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        return {
            "ok": False,
            "status": exc.code,
            "url": url,
            "error": "http_error",
            "data": parsed,
        }
    except Exception as exc:
        return {
            "ok": False,
            "url": url,
            "error": "request_failed",
            "message": str(exc),
        }


def is_sign_failed_response(resp: dict | None) -> bool:
    if not isinstance(resp, dict):
        return False
    if resp.get("status") != 401:
        return False
    data = resp.get("data")
    return isinstance(data, str) and "sign failed" in data.lower()


def looks_like_running_goby(check_resp: dict | None, license_resp: dict | None = None) -> bool:
    return bool(
        (isinstance(check_resp, dict) and check_resp.get("ok", False))
        or is_sign_failed_response(check_resp)
        or is_sign_failed_response(license_resp)
    )


def preferred_base_url(config: dict, override: str | None = None) -> str:
    return override or config.get("preferred_base_url") or config.get("goby_base_url") or DEFAULT_BASE_URL


def active_base_url(config: dict) -> str | None:
    return config.get("active_base_url")


def runtime_base_url(config: dict, override: str | None = None, timeout: int = 3) -> tuple[str, str]:
    if override:
        return override, "override"

    active = active_base_url(config)
    preferred = preferred_base_url(config)

    if active:
        check = api_request(active, "GET", "/api/v1/check", None, timeout=timeout)
        if looks_like_running_goby(check):
            return active, "active"

    return preferred, "preferred"


def parse_bind_addr(base_url: str) -> str:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme and parsed.netloc:
        return parsed.netloc
    if "://" not in base_url and "/" not in base_url:
        return base_url
    raise ValueError("base URL must look like http://host:port")


def is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if handle == 0:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def spawn_goby_server(goby_cmd_path: str, bind_addr: str, extra_args: list[str] | None = None) -> subprocess.Popen:
    cmd = [goby_cmd_path, "-mode", "api", "-bind", bind_addr]
    if extra_args:
        cmd.extend(extra_args)

    kwargs = {
        "cwd": str(Path(goby_cmd_path).parent),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }

    if os.name == "nt":
        creationflags = 0
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        kwargs["creationflags"] = creationflags
    else:
        kwargs["start_new_session"] = True

    return subprocess.Popen(cmd, **kwargs)


def terminate_pid(pid: int) -> tuple[bool, str]:
    if pid <= 0:
        return False, "invalid pid"
    try:
        os.kill(pid, signal.SIGTERM)
        return True, ""
    except OSError as exc:
        return False, str(exc)


def parse_json_input(json_body: str | None, json_file: str | None) -> dict | None:
    if json_body and json_file:
        raise ValueError("use either --json-body or --json-file, not both")
    if json_body:
        return json.loads(json_body)
    if json_file:
        return json.loads(Path(json_file).read_text(encoding="utf-8"))
    return None


def normalize_query(query: str | None, taskid: str | None) -> str | None:
    if query:
        return query
    if taskid:
        return f"taskid={taskid}"
    return None


def resolve_api_context(args: argparse.Namespace) -> tuple[dict, str, str]:
    config = load_config()
    base_url, base_url_source = runtime_base_url(
        config,
        getattr(args, "base_url", None),
        timeout=getattr(args, "timeout", 3),
    )
    return config, base_url, base_url_source


def attach_api_context(result: dict, base_url: str, base_url_source: str, operation: str | None = None) -> dict:
    result["base_url"] = base_url
    result["base_url_source"] = base_url_source
    if operation:
        result["operation"] = operation
    return result


def print_api_result(
    args: argparse.Namespace,
    method: str,
    api_path: str,
    payload: dict | None = None,
    operation: str | None = None,
) -> int:
    _, base_url, base_url_source = resolve_api_context(args)
    result = api_request(base_url, method, api_path, payload, timeout=args.timeout)
    return print_json(attach_api_context(result, base_url, base_url_source, operation))


def cmd_config_get(args: argparse.Namespace) -> int:
    config = load_config()
    return print_json({
        "ok": True,
        "config_path": str(CONFIG_PATH),
        "config": config,
    })


def cmd_config_set(args: argparse.Namespace) -> int:
    config = load_config()
    if args.goby_cmd_path:
        ok, reason = validate_executable(args.goby_cmd_path)
        if not ok:
            return print_json({"ok": False, "error": "invalid_goby_cmd_path", "message": reason})
        resolved = str(Path(args.goby_cmd_path).expanduser().resolve())
        config["goby_cmd_path"] = resolved
        config["goby_runtime_dir"] = str(Path(resolved).parent)
        config["last_verified_at"] = utc_now_iso()
    if args.goby_base_url:
        config["preferred_base_url"] = args.goby_base_url
    save_config(config)
    return print_json({"ok": True, "config_path": str(CONFIG_PATH), "config": config})


def cmd_runtime_resolve(args: argparse.Namespace) -> int:
    config = load_config()
    result = discover_executable(config)
    if result["ok"] and args.persist:
        config.update({
            "goby_cmd_path": result["goby_cmd_path"],
            "goby_runtime_dir": result["goby_runtime_dir"],
            "last_verified_at": result["last_verified_at"],
        })
        save_config(config)
        result["config_path"] = str(CONFIG_PATH)
        result["persisted"] = True
    else:
        result["persisted"] = False
    return print_json(result)


def cmd_preflight(args: argparse.Namespace) -> int:
    config = load_config()
    runtime = discover_executable(config)
    base_url, base_url_source = runtime_base_url(config, args.base_url, timeout=args.timeout)
    result = {
        "ok": False,
        "goby_cmd_resolved": runtime.get("ok", False),
        "goby_cmd_path": runtime.get("goby_cmd_path"),
        "goby_runtime_dir": runtime.get("goby_runtime_dir"),
        "base_url": base_url,
        "base_url_source": base_url_source,
        "checks": {},
    }

    if runtime.get("ok") and args.persist:
        config.update({
            "goby_cmd_path": runtime["goby_cmd_path"],
            "goby_runtime_dir": runtime["goby_runtime_dir"],
            "last_verified_at": runtime["last_verified_at"],
        })
        config["preferred_base_url"] = preferred_base_url(config, args.base_url)
        save_config(config)

    check_resp = api_request(base_url, "GET", "/api/v1/check", None, timeout=args.timeout)
    result["checks"]["api_check"] = check_resp

    license_info = api_request(base_url, "GET", "/api/v1/getEnvi", None, timeout=args.timeout)
    result["checks"]["license_info"] = license_info

    running_goby = looks_like_running_goby(check_resp, license_info)

    api_ready = check_resp.get("ok", False)
    result["ok"] = runtime.get("ok", False) and api_ready
    if not runtime.get("ok", False):
        result["blocker"] = "executable_not_found"
    elif running_goby and not api_ready:
        result["blocker"] = "activation_or_license_not_ready"
    elif not api_ready:
        result["blocker"] = "api_not_ready"
    else:
        result["blocker"] = ""

    if args.persist and running_goby:
        config["active_base_url"] = base_url
        save_config(config)
    return print_json(result)


def cmd_server_start(args: argparse.Namespace) -> int:
    config = load_config()
    runtime = discover_executable(config)
    if not runtime.get("ok", False):
        return print_json(runtime)

    base_url = preferred_base_url(config, args.base_url)
    bind_addr = parse_bind_addr(base_url)

    check_resp = api_request(base_url, "GET", "/api/v1/check", None, timeout=args.timeout)
    if check_resp.get("ok", False):
        return print_json({
            "ok": True,
            "operation": "server_start",
            "message": "Goby API server is already reachable",
            "base_url": base_url,
            "already_running": True,
            "api_check": check_resp,
        })

    proc = spawn_goby_server(runtime["goby_cmd_path"], bind_addr)

    deadline = time.time() + args.wait_timeout
    last_check = None
    while time.time() < deadline:
        last_check = api_request(base_url, "GET", "/api/v1/check", None, timeout=args.timeout)
        if last_check.get("ok", False):
            config["goby_cmd_path"] = runtime["goby_cmd_path"]
            config["goby_runtime_dir"] = runtime["goby_runtime_dir"]
            config["preferred_base_url"] = preferred_base_url(config, args.base_url)
            config["active_base_url"] = base_url
            config["last_verified_at"] = runtime["last_verified_at"]
            config["server_pid"] = proc.pid
            config["server_started_at"] = utc_now_iso()
            save_config(config)
            return print_json({
                "ok": True,
                "operation": "server_start",
                "base_url": base_url,
                "bind": bind_addr,
                "pid": proc.pid,
                "api_check": last_check,
            })
        time.sleep(args.interval)

    return print_json({
        "ok": False,
        "operation": "server_start",
        "base_url": base_url,
        "bind": bind_addr,
        "pid": proc.pid,
        "error": "api_not_ready_after_start",
        "api_check": last_check,
    })


def cmd_server_status(args: argparse.Namespace) -> int:
    config, base_url, base_url_source = resolve_api_context(args)
    pid = int(config.get("server_pid", 0) or 0)
    api_check = api_request(base_url, "GET", "/api/v1/check", None, timeout=args.timeout)
    if args.base_url and looks_like_running_goby(api_check):
        config["active_base_url"] = base_url
        save_config(config)
    return print_json({
        "ok": api_check.get("ok", False),
        "operation": "server_status",
        "base_url": base_url,
        "base_url_source": base_url_source,
        "server_pid": pid if pid > 0 else None,
        "process_alive": is_process_alive(pid) if pid > 0 else False,
        "api_check": api_check,
    })


def cmd_server_stop(args: argparse.Namespace) -> int:
    config = load_config()
    base_url, base_url_source = runtime_base_url(config, args.base_url, timeout=args.timeout)
    pid = int(config.get("server_pid", 0) or 0)

    api_check = api_request(base_url, "GET", "/api/v1/check", None, timeout=args.timeout)
    stop_resp = None
    if api_check.get("ok", False):
        stop_resp = api_request(base_url, "GET", "/api/v1/stop", None, timeout=args.timeout)

    terminated = None
    terminate_error = ""
    if pid > 0 and is_process_alive(pid):
        deadline = time.time() + args.wait_timeout
        while time.time() < deadline:
            if not is_process_alive(pid):
                break
            time.sleep(args.interval)
        if is_process_alive(pid):
            terminated, terminate_error = terminate_pid(pid)
        else:
            terminated = True

    config.pop("server_pid", None)
    config.pop("server_started_at", None)
    config.pop("active_base_url", None)
    save_config(config)

    final_check = api_request(base_url, "GET", "/api/v1/check", None, timeout=args.timeout)
    ok = not final_check.get("ok", False)

    return print_json({
        "ok": ok,
        "operation": "server_stop",
        "base_url": base_url,
        "base_url_source": base_url_source,
        "server_pid": pid if pid > 0 else None,
        "api_check_before": api_check,
        "stop_response": stop_resp,
        "terminated_pid": terminated,
        "terminate_error": terminate_error,
        "api_check_after": final_check,
    })


def cmd_api_call(args: argparse.Namespace) -> int:
    payload = parse_json_input(args.json_body, args.json_file)
    return print_api_result(args, args.method, args.path, payload)


def cmd_scan_start(args: argparse.Namespace) -> int:
    payload = parse_json_input(args.json_body, args.json_file)
    if payload is None:
        payload = {
            "asset": {
                "ips": args.ips or [],
                "ports": args.ports or "",
            }
        }
    return print_api_result(args, "POST", "/api/v1/startScan", payload, "scan_start")


def cmd_scan_progress(args: argparse.Namespace) -> int:
    payload = {"taskid": args.taskid}
    return print_api_result(args, "POST", "/api/v1/getProgress", payload, "scan_progress")


def cmd_task_list(args: argparse.Namespace) -> int:
    method = "POST" if args.post else "GET"
    payload = {} if method == "POST" else None
    return print_api_result(args, method, "/api/v1/getTasks", payload, "task_list")


def cmd_asset_search(args: argparse.Namespace) -> int:
    query = normalize_query(args.query, args.taskid)
    if not query:
        return print_json({"ok": False, "error": "missing_query", "message": "provide --query or --taskid"})
    payload = {"query": query}
    return print_api_result(args, "POST", "/api/v1/assetSearch", payload, "asset_search")


def cmd_vul_search(args: argparse.Namespace) -> int:
    query = normalize_query(args.query, args.taskid)
    if not query:
        return print_json({"ok": False, "error": "missing_query", "message": "provide --query or --taskid"})
    payload = {"query": query}
    return print_api_result(args, "POST", "/api/v1/vulnerabilitySearch", payload, "vulnerability_search")


def cmd_poc_list(args: argparse.Namespace) -> int:
    path = "/api/v1/getPOCList"
    if args.keyword:
        path += "?keyword=" + urllib.parse.quote(args.keyword)
    return print_api_result(args, "GET", path, None, "poc_list")


def cmd_env_get(args: argparse.Namespace) -> int:
    return print_api_result(args, "GET", "/api/v1/getEnvi", None, "env_get")


def cmd_env_set(args: argparse.Namespace) -> int:
    payload = parse_json_input(args.json_body, args.json_file)
    if payload is None:
        return print_json({"ok": False, "error": "missing_payload", "message": "provide --json-body or --json-file"})
    return print_api_result(args, "POST", "/api/v1/setEnvi", payload, "env_set")


def cmd_proxy_check(args: argparse.Namespace) -> int:
    payload = {
        "proxy": args.proxy,
        "url": args.check_url,
    }
    return print_api_result(args, "POST", "/api/v1/checkProxy", payload, "proxy_check")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal Goby helper tool for skill-driven workflows.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config", help="Read or update persistent Goby config.")
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)

    config_get = config_sub.add_parser("get", help="Print config.")
    config_get.set_defaults(func=cmd_config_get)

    config_set = config_sub.add_parser("set", help="Update config.")
    config_set.add_argument("--goby-cmd-path")
    config_set.add_argument("--goby-base-url")
    config_set.set_defaults(func=cmd_config_set)

    runtime_parser = subparsers.add_parser("runtime", help="Resolve Goby executable path.")
    runtime_sub = runtime_parser.add_subparsers(dest="runtime_command", required=True)

    runtime_resolve = runtime_sub.add_parser("resolve", help="Resolve Goby executable path.")
    runtime_resolve.add_argument("--persist", action="store_true")
    runtime_resolve.set_defaults(func=cmd_runtime_resolve)

    preflight = subparsers.add_parser("preflight", help="Run minimal runtime and API preflight checks.")
    preflight.add_argument("--base-url")
    preflight.add_argument("--persist", action="store_true")
    preflight.add_argument("--timeout", type=int, default=5)
    preflight.set_defaults(func=cmd_preflight)

    api_parser = subparsers.add_parser("api", help="Make a raw Goby API call.")
    api_parser.add_argument("--method", default="GET")
    api_parser.add_argument("--path", required=True)
    api_parser.add_argument("--json-body")
    api_parser.add_argument("--json-file")
    api_parser.add_argument("--base-url")
    api_parser.add_argument("--timeout", type=int, default=10)
    api_parser.set_defaults(func=cmd_api_call)

    server_parser = subparsers.add_parser("server", help="Start or inspect Goby API server.")
    server_sub = server_parser.add_subparsers(dest="server_command", required=True)

    server_start = server_sub.add_parser("start", help="Start Goby in API mode.")
    server_start.add_argument("--base-url")
    server_start.add_argument("--timeout", type=int, default=3)
    server_start.add_argument("--wait-timeout", type=int, default=20)
    server_start.add_argument("--interval", type=float, default=1.0)
    server_start.set_defaults(func=cmd_server_start)

    server_status = server_sub.add_parser("status", help="Check Goby API server status.")
    server_status.add_argument("--base-url")
    server_status.add_argument("--timeout", type=int, default=3)
    server_status.set_defaults(func=cmd_server_status)

    server_stop = server_sub.add_parser("stop", help="Stop Goby API server.")
    server_stop.add_argument("--base-url")
    server_stop.add_argument("--timeout", type=int, default=3)
    server_stop.add_argument("--wait-timeout", type=int, default=5)
    server_stop.add_argument("--interval", type=float, default=0.5)
    server_stop.set_defaults(func=cmd_server_stop)

    scan_parser = subparsers.add_parser("scan", help="Run Goby scan-related operations.")
    scan_sub = scan_parser.add_subparsers(dest="scan_command", required=True)

    scan_start = scan_sub.add_parser("start", help="Start a scan.")
    scan_start.add_argument("--ips", nargs="*")
    scan_start.add_argument("--ports")
    scan_start.add_argument("--json-body")
    scan_start.add_argument("--json-file")
    scan_start.add_argument("--base-url")
    scan_start.add_argument("--timeout", type=int, default=30)
    scan_start.set_defaults(func=cmd_scan_start)

    scan_progress = scan_sub.add_parser("progress", help="Get scan progress.")
    scan_progress.add_argument("--taskid", required=True)
    scan_progress.add_argument("--base-url")
    scan_progress.add_argument("--timeout", type=int, default=10)
    scan_progress.set_defaults(func=cmd_scan_progress)

    task_parser = subparsers.add_parser("task", help="List or inspect tasks.")
    task_sub = task_parser.add_subparsers(dest="task_command", required=True)

    task_list = task_sub.add_parser("list", help="List tasks.")
    task_list.add_argument("--post", action="store_true")
    task_list.add_argument("--base-url")
    task_list.add_argument("--timeout", type=int, default=10)
    task_list.set_defaults(func=cmd_task_list)

    asset_parser = subparsers.add_parser("asset", help="Search assets.")
    asset_sub = asset_parser.add_subparsers(dest="asset_command", required=True)

    asset_search = asset_sub.add_parser("search", help="Search assets by query or taskid.")
    asset_search.add_argument("--query")
    asset_search.add_argument("--taskid")
    asset_search.add_argument("--base-url")
    asset_search.add_argument("--timeout", type=int, default=20)
    asset_search.set_defaults(func=cmd_asset_search)

    vul_parser = subparsers.add_parser("vul", help="Search vulnerabilities.")
    vul_sub = vul_parser.add_subparsers(dest="vul_command", required=True)

    vul_search = vul_sub.add_parser("search", help="Search vulnerabilities by query or taskid.")
    vul_search.add_argument("--query")
    vul_search.add_argument("--taskid")
    vul_search.add_argument("--base-url")
    vul_search.add_argument("--timeout", type=int, default=20)
    vul_search.set_defaults(func=cmd_vul_search)

    poc_parser = subparsers.add_parser("poc", help="Query POC information.")
    poc_sub = poc_parser.add_subparsers(dest="poc_command", required=True)

    poc_list = poc_sub.add_parser("list", help="List POCs.")
    poc_list.add_argument("--keyword")
    poc_list.add_argument("--base-url")
    poc_list.add_argument("--timeout", type=int, default=20)
    poc_list.set_defaults(func=cmd_poc_list)

    env_parser = subparsers.add_parser("env", help="Get or set Goby environment settings.")
    env_sub = env_parser.add_subparsers(dest="env_command", required=True)

    env_get = env_sub.add_parser("get", help="Get Goby environment settings.")
    env_get.add_argument("--base-url")
    env_get.add_argument("--timeout", type=int, default=10)
    env_get.set_defaults(func=cmd_env_get)

    env_set = env_sub.add_parser("set", help="Set Goby environment settings.")
    env_set.add_argument("--json-body")
    env_set.add_argument("--json-file")
    env_set.add_argument("--base-url")
    env_set.add_argument("--timeout", type=int, default=20)
    env_set.set_defaults(func=cmd_env_set)

    proxy_parser = subparsers.add_parser("proxy", help="Validate proxy settings before changing Goby env.")
    proxy_sub = proxy_parser.add_subparsers(dest="proxy_command", required=True)

    proxy_check = proxy_sub.add_parser("check", help="Check a proxy through Goby.")
    proxy_check.add_argument("--proxy", required=True)
    proxy_check.add_argument("--check-url", default="https://www.baidu.com")
    proxy_check.add_argument("--base-url")
    proxy_check.add_argument("--timeout", type=int, default=20)
    proxy_check.set_defaults(func=cmd_proxy_check)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except json.JSONDecodeError as exc:
        return print_json({"ok": False, "error": "invalid_json", "message": str(exc)})
    except Exception as exc:
        return print_json({"ok": False, "error": "unexpected_error", "message": str(exc)})


if __name__ == "__main__":
    sys.exit(main())
