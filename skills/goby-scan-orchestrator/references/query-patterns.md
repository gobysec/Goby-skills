# Goby Query Patterns

Get a `taskid` first unless the user already provided one.

If no `taskid` is available:
1. run `task list`
2. prefer the most relevant recent task
3. prefer a completed task for final results
4. prefer a running task only for progress or partial results

## Asset queries

Use:
- `asset search --taskid <taskid>` for a broad asset summary
- `asset search --query ...` for filtered asset results

Common filters:

```text
taskid=20260326183000
taskid=20260326183000 && ip=10.10.10.10
taskid=20260326183000 && port=80
taskid=20260326183000 && protocol=https
taskid=20260326183000 && app="nginx"
```

## Vulnerability queries

Use:
- `vul search --taskid <taskid>` for a broad vulnerability summary
- `vul search --query ...` for filtered vulnerability results

Common filters:

```text
taskid=20260326183000
taskid=20260326183000 && ip=10.10.10.10
taskid=20260326183000 && vulname="CVE-2021-1234"
taskid=20260326183000 && host="example.com"
```

## POC queries

Use:
- `poc list` for the general inventory
- `poc list --keyword <text>` for product, vendor, CVE, or vulnerability filters

Examples:

```text
poc list --keyword exchange
poc list --keyword "CVE-2021"
poc list --keyword nginx
```

## Progress

Use `scan progress --taskid <taskid>` for running tasks, then follow with `asset search` or `vul search`.
