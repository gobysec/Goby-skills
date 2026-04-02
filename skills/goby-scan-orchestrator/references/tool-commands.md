# Goby Tool Commands

Use these commands on macOS or Windows.

Path rule:
- `scripts/goby_tool.py` is relative to the current skill directory, not the shell working directory
- resolve that path from the skill directory before running the commands below

If `127.0.0.1:8361` is already serving Goby and the user confirms it is their instance, you can use that service directly without starting Goby from `goby-cmd`.

## Path and config

```bash
python scripts/goby_tool.py config get
```

`config get` prints the full config JSON. It does not support selector flags such as `--key`.

```bash
python scripts/goby_tool.py config set --goby-cmd-path "C:\Program Files\Goby\goby-cmd.exe"
```

```bash
python scripts/goby_tool.py config set --goby-base-url "http://127.0.0.1:8361"
```

```bash
python scripts/goby_tool.py runtime resolve --persist
```

## Preflight

```bash
python scripts/goby_tool.py preflight --persist
```

```bash
python scripts/goby_tool.py preflight --base-url "http://127.0.0.1:8361" --persist
```

## Server

```bash
python scripts/goby_tool.py server start
```

```bash
python scripts/goby_tool.py server status
```

```bash
python scripts/goby_tool.py server stop
```

## Scan and query

```bash
python scripts/goby_tool.py scan start --json-file payload.json
```

```bash
python scripts/goby_tool.py scan start --ips 10.10.10.0/24 --ports 1-1024
```

```bash
python scripts/goby_tool.py scan progress --taskid 20260326183000
```

```bash
python scripts/goby_tool.py scan stop --taskid 20260326183000
```

```bash
python scripts/goby_tool.py scan resume --taskid 20260326183000
```

```bash
python scripts/goby_tool.py task list
```

```bash
python scripts/goby_tool.py asset search --taskid 20260326183000
```

```bash
python scripts/goby_tool.py asset search --query "taskid=20260326183000 && port=80"
```

```bash
python scripts/goby_tool.py vul search --taskid 20260326183000
```

```bash
python scripts/goby_tool.py vul search --query "taskid=20260326183000 && vulname=test"
```

```bash
python scripts/goby_tool.py poc list
```

```bash
python scripts/goby_tool.py poc list --keyword exchange
```

## POC update

Use raw API fallback for POC update until the helper script grows first-class subcommands.

```bash
python scripts/goby_tool.py api --method POST --path /api/v1/poc/update/start
```

```bash
python scripts/goby_tool.py api --method GET --path /api/v1/poc/update/status
```

## Environment and proxy

```bash
python scripts/goby_tool.py env get
```

```bash
python scripts/goby_tool.py env set --json-file env.json
```

Set scan proxy through the Goby environment field `proxyServer`.

Example payload:

```json
{
  "proxyServer": "http://127.0.0.1:8080"
}
```

```bash
python scripts/goby_tool.py proxy check --proxy "http://127.0.0.1:8080"
```

## Raw API fallback

Use this only when the higher-level subcommands are not enough.

```bash
python scripts/goby_tool.py api --method GET --path /api/v1/check
```

```bash
python scripts/goby_tool.py api --method POST --path /api/v1/startScan --json-file payload.json
```
