# Goby Runtime Discovery

Use this guide when Goby executable location is unknown, invalid, or needs to be remembered for later runs.

Only use this guide when the tool needs to start Goby itself. If `127.0.0.1:8361` is already serving Goby and the user confirms it is their instance, reuse that service instead of resolving `goby-cmd`.

Executable path source is restricted:
- accept only a user-provided path or a previously persisted path
- do not infer, guess, or search for the executable location

Default config location:
- Windows: `%USERPROFILE%\\.goby-agent\\config.json`
- Unix-like: `~/.goby-agent/config.json`

## Discovery order

Resolve Goby executable path using this precedence:
1. persisted config from a prior successful run
2. ask the user for the full executable path if no valid stored path exists

Do not add a fallback search step. Do not scan the repository, workspace, common install locations, or local disks for `goby-cmd`.

## Validation rules

A candidate path is usable only if:
- the file exists
- it is the expected Goby executable or a clearly intended runtime binary
- its parent directory can be treated as the Goby runtime directory

After a path is validated:
- persist it
- persist its parent as the runtime directory
- store the verification time

## Persistence rules

Store a confirmed path in the user-level config file.

On later runs:
- use the stored path first
- revalidate it before use
- if invalid, ask the user for the full path again

## Asking the user

Ask the user for the executable path only when:
- no valid stored path exists

When asking, request the full executable path, not just the install directory.
