# Goby Activation Workflow

Use this workflow when Goby is not yet activated, activation status is unknown, or readiness checks return `401 sign failed`.

## When to use it

Switch to this workflow when:
- `preflight` reports activation is unknown or missing
- `/api/v1/check` returns HTTP `401 sign failed`
- `/api/v1/getEnvi` returns HTTP `401 sign failed`

When those signals appear, do not start by changing the helper client or adding custom signing logic. Re-check activation first.

If no usable `goby-cmd` path is available and the only available signal is a running Goby service returning `401 sign failed`, stop and tell the user that Goby Red Team edition is required for API use.

## Key terms

- MID: machine identifier used by the licensing flow
- activation code: short code that must be converted first
- license key: final content that must be written to `license.key`
- runtime directory: directory containing the Goby executable

Activation code vs license key:
- a short 32-hex string is typically an activation code or identifier, not the final `license.key`
- do not overwrite `license.key` with an activation code
- only write `license.key` when the user explicitly confirms the content is the final license key

## MID retrieval

If a usable `goby-cmd` path is available, obtain the MID by running:

```bash
<goby-cmd> -mid
```

Expect the command output to include a line like `MID: <mid>`. The command may also print warnings or startup logs, so extract the MID from the `MID:` line instead of assuming the output is otherwise clean.

## Convert activation code to license key

If the user provides an activation code (not a final license key), convert it to a `license.key` using the official Gobies license API workflow:
1. Get the current MID via `<goby-cmd> -mid`.
2. Generate a timestamp and token where `token = md5("{mid}_{timestamp}")`.
3. Call the license API endpoint:
   `GET https://api.gobies.org/api/license/generateByKey?mid=<mid>&active_key=<active_key>`
4. Send required headers at minimum: `Timestamp`, `Token`, `mid`, plus standard JSON accept headers.
5. On success, the response `statusCode` is `200` and `data` contains the final license key.

Only write `license.key` after the user explicitly confirms the returned value is the final license key.

## Required order

1. Start Goby if the service is not running yet.
2. Obtain the current MID.
3. Identify whether the user provided an activation code or a final license key.
4. If the user provided an activation code, convert it to a license key.
5. Resolve the Goby runtime directory.
6. Write the final license key to `license.key` in that runtime directory.
7. Re-check readiness before claiming activation succeeded.

## Expected outcomes

Use these normalized results:
- `LICENSE_KEY:<license_key>` when conversion succeeds
- `ACTIVATED_READY` when Goby is ready for business APIs
- `UNACTIVATED:MID:<mid>` when the MID still needs to be shown
- `FAILED:*` or `DEGRADED:*` for failures or partial problems

## Rules

- Do not write `license.key` until the runtime directory is resolved.
- Do not assume an activation code can be used directly as `license.key`.
- Do not claim activation succeeded until readiness has been re-checked after the file write.
- Do not treat `401 sign failed` as proof that the client request format is wrong before checking activation or license state.
- Do not depend on business APIs that may be unavailable before activation is complete.
- If the user provides neither an activation code nor a license key, stop and explain what is missing.
- If there are multiple Goby installations, write only to the runtime the user intends to use.
- If no executable is available to complete local activation and a running Goby service still returns `401 sign failed`, tell the user that Goby Red Team edition is required for API use.
