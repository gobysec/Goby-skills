---
name: goby-scan-orchestrator
description: Use when operating Goby for executable discovery, activation readiness, startup checks, scan orchestration, task lookup, asset search, vulnerability search, POC lookup, POC update, or cautious proxy and environment handling.
---

# Goby Scan Orchestration

Use `scripts/goby_tool.py` as the default helper. Prefer it over ad hoc HTTP calls.

This skill is intended for macOS and Windows.

Path rule:
- `scripts/...` and `references/...` are always resolved relative to this skill directory
- do not interpret those paths relative to the shell working directory
- before running a documented command, resolve the helper path from the skill directory first

Read references only when needed:
- `references/runtime-discovery.md` for locating and persisting `goby-cmd`
- `references/activation.md` for local activation flow
- `references/tool-commands.md` for exact commands
- `references/query-patterns.md` for `task list`, `asset search`, `vul search`, and `poc list`
- `references/result-interpretation.md` for reporting

## Core rules

Treat these as separate:
- executable path
- runtime directory
- API base URL

Executable path rule:
- only accept a user-provided or previously persisted `goby-cmd` path
- do not infer, discover, guess, or search for the executable path
- if no valid stored path exists and the tool needs to start Goby, ask the user for the full executable path

Port policy:
- `preferred_base_url` is always `http://127.0.0.1:8361`
- `active_base_url` is the currently active Goby API address persisted in config
- when Goby stops, clear `active_base_url` immediately

Port check rule:
- port availability only means whether the port is already occupied by some process
- do not use Goby API responses to decide whether a port is occupied
- Goby API checks happen only after a known Goby instance is reused or after Goby is started

Do not:
- assume Goby is running
- assume Goby is activated
- write `license.key` before resolving the runtime directory
- change global Goby environment settings unless the user explicitly asks
- start a scan when preflight fails
- treat `401 sign failed` as proof that the helper script must be changed before checking activation or license state
- rely on environment variables for Goby path or API base URL
- search broad filesystem locations for Goby; if no valid stored path exists, ask the user directly
- invent unsupported CLI flags; use only arguments implemented by `scripts/goby_tool.py`
- accept any executable path that was not provided by the user or loaded from persisted config
- search the repository, workspace, or local disks for `goby-cmd`; if the stored path is missing or invalid, stop and ask the user for the full executable path

## Session order

Always work in this order:
1. Read persisted config for `active_base_url`.
2. If it exists, check whether that port is already occupied.
3. If it is missing or free, check `preferred_base_url` (`127.0.0.1:8361`) the same way.
4. If the preferred port is occupied, treat that only as port-in-use information. Reuse it only after the user confirms it is their Goby instance.
5. Only require executable discovery when the tool needs to start Goby itself.
6. If `runtime resolve` fails, ask for the full `goby-cmd` path and persist it with `python scripts/goby_tool.py config set --goby-cmd-path "<path>"`. Do not run `rg`, `Get-ChildItem`, or similar searches to hunt for the binary.
7. If the chosen port is free and the executable is known, start Goby on that port.
8. After reuse of a user-confirmed Goby instance or after a successful start, run `python scripts/goby_tool.py preflight --persist`.
9. If preflight shows `401 sign failed` or missing activation, follow `references/activation.md`, then re-run preflight.
10. Persist the chosen `active_base_url` after a successful reuse or start, then continue with query or scan work.

Starting Goby only brings the service up. If activation is still missing, complete activation before using business APIs.

If no usable `goby-cmd` path is available and a user-confirmed running Goby service returns `401 sign failed` during readiness checks, stop and tell the user that Goby Red Team edition is required for API use.

## Intent routing

Map requests to commands like this:
- readiness or startup check: first check whether `127.0.0.1:8361` is occupied; if the user confirms that occupied port is their Goby instance, reuse it; otherwise use `config get`, `runtime resolve --persist`, start Goby if needed, then `preflight --persist`
- start Goby API mode: `server start`
- check Goby API mode status: `server status`
- locate or remember Goby path: `runtime resolve --persist` or `config set --goby-cmd-path`
- fresh scan: `preflight --persist`, `env get`, then `scan start`
- progress: `scan progress --taskid <taskid>`
- list prior work: `task list`
- asset results: `asset search --taskid <taskid>`
- vulnerability results: `vul search --taskid <taskid>`
- POC lookup: `poc list` or `poc list --keyword <keyword>`
- POC update: after `preflight --persist`, use the official update APIs, then poll update status until completion
- proxy change: `env get`, `proxy check`, then `env set` only if explicitly requested

CLI reminder:
- `config get` takes no extra selector flags such as `--key`
- if you need `active_base_url`, run `config get` and read that field from the returned JSON

If the user asks for assets or vulnerabilities without a `taskid`:
1. Run `task list`.
2. Choose the most relevant task.
3. Explain which task was chosen.
4. Run the search with that `taskid`.

If a Goby service is already running on `127.0.0.1:8361`, prefer reusing it over starting another one.

## Query and scan rules

Prefer existing tasks over creating a new scan.

Use:
- `task list` to find candidate tasks
- `asset search` for hosts, ports, protocols, services, products, and application findings
- `vul search` for vulnerability findings and affected assets
- `poc list` for POC inventory or keyword lookup

Create a new scan only when:
- the user explicitly asks for a scan, or
- no suitable prior task exists

For filtered results, prefer query forms such as:
- `asset search --query "taskid=<taskid> && port=80"`
- `asset search --query "taskid=<taskid> && ip=10.10.10.10"`
- `vul search --query "taskid=<taskid> && vulname=\"CVE-2021-1234\""`

Read `references/query-patterns.md` before building more complex filters.

## Proxy and reporting rules

Treat proxy settings as global Goby state.

If the user did not explicitly ask for a proxy change, do not modify proxy settings.

If the user did ask:
1. Run `env get`.
2. Run `proxy check --proxy <proxy-url>`.
3. Explain that the change is global.
4. Run `env set` only if explicitly requested.

When changing the scan proxy, use the Goby environment field `proxyServer`.

## POC update rules

Treat POC update as a core Goby operation.

Before updating POCs:
1. Ensure Goby is started or a user-confirmed Goby instance is being reused.
2. Run `preflight --persist`.
3. If readiness still shows `401 sign failed` or missing activation, stop and handle activation first.

Use the official POC update APIs rather than searching the repository for update logic.

Do not stop or restart a user-managed Goby instance unless the user explicitly asks.

When reporting:
1. readiness or task status
2. scope or selected task
3. main asset or vulnerability findings
4. operational impact
5. next actions

Always identify the selected `taskid`, mark partial results clearly, summarize before raw details, avoid inventing severity, and mention any environment or proxy changes that affected execution.

Read `references/result-interpretation.md` before writing a detailed summary.
