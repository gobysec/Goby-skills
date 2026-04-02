---
name: goby-scan-orchestrator
description: Use when operating Goby for executable discovery, activation readiness, startup checks, scan orchestration, task lookup, asset search, vulnerability search, POC lookup, POC update, or cautious proxy and environment handling.
---

# Goby Scan Orchestration

Use `scripts/goby_tool.py` as the default helper. Prefer it over ad hoc HTTP calls.

This skill is intended for macOS and Windows.

Path rules:
- `scripts/...` and `references/...` are always resolved relative to this skill directory
- do not interpret those paths relative to the shell working directory
- resolve the helper path from the skill directory before running documented commands

Read references only when needed:
- `references/runtime-discovery.md` for locating and persisting `goby-cmd`
- `references/activation.md` for local activation flow
- `references/tool-commands.md` for exact commands
- `references/scan-parameter-assembly.md` for scan-case-to-payload rules
- `references/query-patterns.md` for `task list`, `asset search`, `vul search`, and `poc list`
- `references/result-interpretation.md` for reporting

## Core rules

Keep these separate:
- executable path
- runtime directory
- API base URL

Executable path rules:
- only accept a user-provided or previously persisted `goby-cmd` path
- do not infer, discover, guess, or search for the executable path
- if no valid stored path exists and the tool needs to start Goby, ask the user for the full executable path

Base URL rules:
- `preferred_base_url` is always `http://127.0.0.1:8361`
- `active_base_url` is the currently active Goby API address persisted in config
- when Goby stops, clear `active_base_url` immediately

Port rules:
- port availability only means whether the port is occupied by some process
- do not use Goby API responses to decide whether a port is occupied
- Goby API checks happen only after a known Goby instance is reused or after Goby is started

Do not:
- assume Goby is running or activated
- write `license.key` before resolving the runtime directory
- change global Goby environment settings unless the user explicitly asks
- start a scan when preflight fails
- treat `401 sign failed` as proof that the helper script must change before checking activation or license state
- rely on environment variables for Goby path or API base URL
- invent unsupported CLI flags; use only arguments implemented by `scripts/goby_tool.py`
- accept any executable path not provided by the user or loaded from persisted config
- search the repository, workspace, or local disks for `goby-cmd`; if the stored path is missing or invalid, stop and ask the user for the full executable path

## Session order

Always work in this order:
1. Read persisted config for `active_base_url`.
2. If it exists, check whether that port is occupied.
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

Map requests like this:
- readiness or startup check: first check whether `127.0.0.1:8361` is occupied; if the user confirms that occupied port is their Goby instance, reuse it; otherwise use `config get`, `runtime resolve --persist`, start Goby if needed, then `preflight --persist`
- start Goby API mode: `server start`
- check Goby API mode status: `server status`
- locate or remember Goby path: `runtime resolve --persist` or `config set --goby-cmd-path`
- fresh scan: `preflight --persist`, `env get`, then `scan start`
- progress: `scan progress --taskid <taskid>`
- stop a running scan: `scan stop --taskid <taskid>`
- resume a stopped scan: `scan resume --taskid <taskid>`
- list prior work: `task list`
- asset results: `asset search --taskid <taskid>`
- vulnerability results: `vul search --taskid <taskid>`
- POC lookup: `poc list` or `poc list --keyword <keyword>`
- POC update: after `preflight --persist`, use the official update APIs, then poll update status until completion
- proxy change: `env get`, `proxy check`, then `env set` only if explicitly requested

## Scan target intent recognition

When the user wants a new scan, classify the target description before assembling the scan payload.

Use four cases:

1. `host-only`
- targets are only IPs, CIDRs, or hostnames
- no separate port list is provided
- do not assume ports
- ask the user to choose `enterprise`, `compact`, or `full`

2. `host-with-ports`
- targets are IPs, CIDRs, or hostnames
- ports are also provided
- treat this as a normal port scan request

3. `url-only`
- targets are one or more URLs with explicit schemes such as `http://` or `https://`
- no separate port list is provided
- treat the URLs themselves as the scan targets
- this is URL-style host-list scanning, not normal host-plus-port scanning

4. `url-with-ports`
- targets are URLs with explicit schemes
- ports are also separately provided
- treat this as a normal port scan request, not URL-only mode

Recognition rules:
- if any target starts with `http://` or `https://`, treat that target as a URL target
- a port embedded in a URL such as `http://1.2.3.4:3001` does not count as a separately specified port
- "separately specified ports" means the user explicitly adds ports outside the URL targets, such as `80,443`, `port 8080`, or `ports 80 443`
- if the request mixes URL targets and host-only targets without separately specified ports, ask a short clarification question
- if the request mixes URL targets and host targets and also includes separately specified ports, classify it as `host-with-ports`
- if the user says "scan these" but the targets are missing or ambiguous, ask for the targets

Required outputs of the intent decision:
- chosen case: `host-only`, `host-with-ports`, `url-only`, or `url-with-ports`
- whether clarification is required before scanning
- if clarification is required, the exact reason: missing ports for hosts, mixed ambiguous target types, or missing targets

Default port-scope values for clarification:
- enterprise: `21,22,23,25,53,U:53,U:69,80,81,U:88,110,111,U:111,123,U:123,135,U:137,139,U:161,U:177,389,U:427,443,445,465,500,515,U:520,U:523,548,623,U:626,636,873,902,1080,1099,1433,U:1434,1521,U:1604,U:1645,U:1701,1883,U:1900,2049,2181,2375,2379,U:2425,3128,3306,3389,4730,U:5060,5222,U:5351,U:5353,5432,5555,5601,5672,U:5683,5900,5938,5984,6000,6379,7001,7077,8080,8081,8443,8545,8686,9000,9001,9042,9092,9200,9418,9999,11211,U:11211,27017,U:33848,37777,50000,50070,61616`
- compact: `21,22,80,U:137,U:161,443,445,U:1900,3306,3389,U:5353,8080`
- full: all ports

Examples:
- `scan 1.1.1.1` -> `host-only`
- `scan 1.1.1.1 2.2.2.2 ports 80,443` -> `host-with-ports`
- `scan http://118.145.183.131:3001 https://81.0.248.189` -> `url-only`
- `scan http://118.145.183.131:3001 https://81.0.248.189 with ports 80,443` -> `url-with-ports`

## Scan parameter assembly

After classifying the scan-target case, read `references/scan-parameter-assembly.md` and let the model assemble the final scan payload itself.

Assembly rules:
- keep scan-case recognition and payload assembly in the model layer
- keep `scripts/goby_tool.py` as the execution backend
- use `scan start --json-file` or `scan start --json-body` for the actual call
- do not push these four-case branching rules down into helper-script logic unless the user explicitly asks for that refactor

Clarification rules:
- for `host-only`, ask the user to choose `enterprise`, `compact`, or `full`
- for mixed URL and host targets without separately specified ports, ask a short clarification question
- otherwise, assemble the payload directly and continue

Execution order for a new scan:
1. `preflight --persist`
2. `env get`
3. model-side payload assembly or clarification
4. `scan start`

CLI reminders:
- `config get` takes no extra selector flags such as `--key`
- if you need `active_base_url`, run `config get` and read that field from the returned JSON

## Query and task selection rules

Prefer existing tasks over creating a new scan.

Use:
- `task list` to find candidate tasks
- `asset search` for hosts, ports, protocols, services, products, and application findings
- `vul search` for vulnerability findings and affected assets
- `poc list` for POC inventory or keyword lookup

Create a new scan only when:
- the user explicitly asks for a scan
- no suitable prior task exists

If the user asks for assets or vulnerabilities without a `taskid`:
1. Run `task list`.
2. Choose the most relevant task.
3. Explain which task was chosen.
4. Run the search with that `taskid`.

If the user asks to stop or resume a scan without a `taskid`:
1. Run `task list`.
2. Choose the most relevant task.
3. Explain which task was chosen.
4. Run `scan stop` or `scan resume` with that `taskid`.

If a Goby service is already running on `127.0.0.1:8361`, prefer reusing it over starting another one.

For filtered results, prefer query forms such as:
- `asset search --query "taskid=<taskid> && port=80"`
- `asset search --query "taskid=<taskid> && ip=10.10.10.10"`
- `vul search --query "taskid=<taskid> && vulname=\"CVE-2021-1234\""`

Read `references/query-patterns.md` before building more complex filters.

## Mutating operations and reporting

Treat proxy settings as global Goby state.

If the user did not explicitly ask for a proxy change, do not modify proxy settings.

If the user did ask for a proxy change:
1. Run `env get`.
2. Run `proxy check --proxy <proxy-url>`.
3. Explain that the change is global.
4. Run `env set` only if explicitly requested.

When changing the scan proxy, use the Goby environment field `proxyServer`.

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
